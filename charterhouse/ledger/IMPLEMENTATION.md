# Ledger (S4) — IMPLEMENTATION
Owner: A3 Ledger/Registry Agent   Subsystem: S4   Source of truth: docs/32_database.md, docs/41_events.md, docs/12_memory.md + docs/40 §2, docs/43, docs/54 §S4
Scope note: this doc covers the **Ledger** (event store). The **Registry** (projection) is the same
subsystem (S4) documented in `charterhouse/registry/`. The event **catalog** (docs/41) is jointly
owned with A7 Memory (see §6).

## 1. Responsibility (one paragraph)
S4-Ledger is the **append-only source of truth** (`INV-LEDGER`): every meaningful change is one
immutable, hash-chained event appended to files under `K:\the_charter_house\data\ledger\`. It
provides atomic + totally-ordered `append`, filtered `read`, deterministic `replay` to world state,
and `snapshot`/`restore`. It **MUST NOT**: interpret business rules (lifecycle guards, governance
classes — those are S5/S6 and only *emit* events here), embed or store raw PII/secrets (redaction
is upstream at CHECKPOINT — S7; payloads carry refs only, docs/41 §4.4), call an LLM (deterministic,
docs/61 §INV-DET), or expose any mutation of a historical event. Corrections are **new compensating
events**, never edits (docs/41 §4.1).

## 2. Invariants enforced
- **`INV-LEDGER` (docs/32, docs/54 §S4):** `Registry/world state == replay(all_events)` for any event
  sequence. *Guaranteed by:* replay is a pure fold over the ordered event stream; property-based test.
- **Atomic + totally-ordered append (docs/32, docs/54 §S4):** a partial write never corrupts the log;
  concurrent appends never interleave a record. *Guaranteed by:* single-writer serialization +
  write-then-commit/fsync discipline; monotonic `event_id` (ULID) provides total order independent of file grouping.
- **Tamper-evidence (docs/32, docs/41 §1):** each event carries `prev_hash`; altering any historical
  event breaks the chain, is detected on read, and **replay refuses a broken chain (fail closed)**.
- **No raw PII/secret in any event (docs/41 §4.4, `INV-PII-1`):** the writer rejects a payload that
  fails a structural PII/secret pre-check (defense in depth behind S7 redaction); PII lives only in
  `*.private.md` sidecars referenced by ref.
- **Token id on gate/RED events (docs/41 §4.2):** the envelope `authorization` field carries the token
  id for gate/RED-classed events (the classification is S6's; the Ledger records what it is given and validates presence-when-required).
- **Once-per-lineage caps replay-checked (docs/41 §4.3):** `omw_grant` and `pivot_fork` are validated
  during replay to enforce their caps (`INV-SM-5`/OMW-LEDGER); a second occurrence in a lineage is a replay-detected violation.
- **`schema_version` on every event (docs/41 §5):** additive evolution; the reader supports all prior versions.

## 3. Internal design
- **Deterministic**, no LLM. Durable state = the ledger files (the *only* durable state in the system, docs/61).
- **Physical format (docs/32):** append-only JSONL segments under `data/ledger/` (one event per line).
  Segmentation/rotation by size or time is allowed but **MUST NOT affect global order** — order comes
  from the monotonic `event_id`, not file layout. Implementer choice (JSONL vs one-file-per-event) is
  recorded here as **JSONL segments**; either is legal per docs/32 provided order+atomicity+chain hold.
- **The common envelope (docs/41 §1 — reproduced verbatim, this is the frozen shape for IF-1):**
  ```
  event_id        : uuid (monotonic-sortable, e.g. ULID)
  schema_version  : int (this catalog's version; start 1)
  timestamp       : ISO-8601 wall-clock (for humans)
  active_time     : factory-active-time counter at emission (for deadlines)
  venture_id      : id | null (null for factory-global events)
  actor           : "conductor" | "founder" | capability-name | "system"
  type            : one of docs/41 §2
  from_state      : state | null
  to_state        : state | null
  payload         : type-specific object (docs/41 §2)
  authorization   : token_id | null   (present for gate/RED events)
  prev_hash       : hash of previous event (tamper-evident chain)
  ```
- **Append path:** validate envelope shape → structural PII/secret pre-check → compute `prev_hash` over
  the canonical serialization of the previous event → serialize → write → fsync → return `event_id`.
- **Read path:** stream events (optionally filtered by venture/type/time), verifying the chain as it reads; a break raises immediately.
- **Replay:** pure fold `events → WorldState` (registry records + slot/lineage accounting inputs);
  refuses a broken chain; deterministic and side-effect-free.
- **Backup:** `snapshot()` copies ledger(+vault+vectors) to `K:\Backups\YYYY-MM-DD\`; `restore()` +
  `replay()` reproduces byte-identical registry state (docs/23, docs/32; CRITICAL backup class).
- **Concurrency:** single-writer (append serialized); reads are lock-free over immutable segments (docs/32).

## 4. Dependencies
- **Consumes:** none of the subsystem APIs (docs/51 A3: "APIs consumed: none"). Uses only resolved paths
  (`data/ledger/`, `K:\Backups`) supplied by A1's `EnvContext` and stdlib/hashing.
- **Consumed by (IF-1 downstream):** A4 Lifecycle (emits transition/park/omw/pivot events; reads state),
  A5 Governance/Security (emits spend/send/pii_block/override; reads for envelope + replay checks),
  A7 Memory (emits `lesson_written`/`consolidate`; reads), A11 Telemetry (emits `llm_call`/`error`/`pii_block`),
  A10 Conductor/Projections (reads for all projections). All consume via docs/40 §2 signatures + the frozen envelope.

## 5. Failure behavior
| Failure mode | Fail-closed response |
|---|---|
| Partial/interrupted write | write-then-commit means an incomplete record is never visible; last good state stands; error logged |
| Broken hash chain on read | raise immediately; `replay` refuses; no partial world state returned |
| Payload contains structural PII/secret | reject the append; error names the offending field; event not written |
| Gate/RED event missing required `authorization` | reject the append (fail closed); logged |
| Unknown/absent event `type` | reject the append; error names the type |
| Second `omw_grant`/`pivot_fork` in a lineage | replay flags a violation; surfaced to caller (S5 enforces the guard) |
| Restore from a corrupt snapshot | chain verification fails on replay → restore refused; prior state retained |
No path silently drops, edits, or reorders an event.

## 6. Open questions → RESOLVED
- **Q: Catalog co-ownership with A7 (docs/41 header says A3/A7).** **RESOLVED —** A3 **freezes at IF-1**:
  the common envelope (§3, verbatim), the total-order/atomicity/hash-chain contract, and the *append/read/replay*
  API. The **event-type vocabulary** (docs/41 §2) is frozen as a shared enum in `charterhouse/contracts/`.
  A7 later *emits* the already-catalogued memory events (`lesson_written`, `consolidate`) and owns their
  *payload semantics*; it does **not** alter the envelope or the append mechanism. Adding a new event type
  is an additive, versioned change (docs/43 §7) — not an envelope change — so it does not reopen IF-1.
- **Q: Physical format choice (JSONL vs file-per-event).** **RESOLVED — JSONL segments** (human-readable,
  git-friendly, dependency-free per docs/32), with ULID for order so segmentation never affects global order.
- **Q: What is `WorldState`?** **RESOLVED —** the replay output feeding the Registry projection: per-venture
  records (docs/42 §6) + slot/lineage/clock accounting inputs. Its typed shape lives in `charterhouse/contracts/`
  and is the seam the Registry (same subsystem) reads. No business *rules* live in replay — only reconstruction.
