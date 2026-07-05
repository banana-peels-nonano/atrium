# Ledger (S4) — API
Owner: A3 Ledger/Registry Agent   ·   Matches docs/40 §2 exactly (frozen seam)   ·   **This is interface-freeze IF-1** (docs/52 §12)

## Exposed surface

### `Ledger.append(event: Event) -> event_id`
- **Preconditions:** `event` conforms to the common envelope (below); `type` ∈ the frozen catalog
  (docs/41 §2); gate/RED events carry a non-null `authorization`; payload contains no raw PII/secret.
- **Postconditions:** the event is durably appended, atomically and in total order, with `prev_hash`
  linking the prior event; returns the assigned monotonic `event_id` (ULID). The event is now immutable.
- **Errors (fail closed):** invalid envelope, unknown `type`, missing required `authorization`,
  structural PII/secret in payload, I/O failure. On any error the event is **not** written.
- **Side effects:** one durable ledger write (the system's only durable state). **Determinism:** deterministic (no LLM).
- **Auth class:** n/a — the Ledger *records* actions; it never *performs* a GREEN/YELLOW/RED action.

### `Ledger.read(filter: EventFilter) -> Iter[Event]`
- **Filter:** by `venture_id` / `type` / time (`active_time` or `timestamp`) range; all optional.
- **Postconditions:** yields events in total order, verifying the hash chain as it streams.
- **Errors:** broken chain → raise immediately (fail closed). **Side effects:** none. **Determinism:** deterministic.

### `Ledger.replay(upto: event_id | None = None) -> WorldState`
- **Postconditions:** returns the deterministic reconstruction of world state from all events
  (or up to `upto`), enforcing replay-checked caps (`omw_grant`/`pivot_fork`). `Registry == replay()` (`INV-LEDGER`).
- **Errors:** broken chain / cap violation → raise (fail closed); no partial state returned. **Determinism:** pure.

### `Ledger.snapshot() -> snapshot_ref`  ·  `Ledger.restore(snapshot_ref) -> None`
- **snapshot:** copies ledger(+vault+vectors) to a dated `K:\Backups\YYYY-MM-DD\` folder (CRITICAL class, docs/23).
- **restore:** reproduces state such that `restore(); replay()` yields byte-identical registry state.
- **Errors:** corrupt snapshot (chain fails) → restore refused; prior state retained. **Determinism:** deterministic.

## Common envelope (frozen at IF-1 — every event; docs/41 §1)
```
event_id | schema_version | timestamp | active_time | venture_id | actor |
type | from_state | to_state | payload | authorization | prev_hash
```
Event `type` vocabulary is the frozen catalog in docs/41 §2 (shared enum in `charterhouse/contracts/`).

## Consumed surface
- **None.** A3 consumes no subsystem API (docs/51). It uses resolved paths from A1's `EnvContext`
  (`data/ledger/`, `K:\Backups`) and stdlib only.

## Interface stability
- **Frozen (IF-1):** the common envelope, the event-type vocabulary, and `append/read/replay/snapshot/restore`.
  Consumers A4, A5, A7, A10, A11 build against these. Recorded as frozen in the Build Tracker
  **only on founder clearance**.
- **Evolution:** adding an event **type** or an additive payload field is versioned (`schema_version`),
  additive, and does **not** bump consumers (docs/43 §7). Removing/renaming a type or field, or changing
  the envelope, is a **breaking change** requiring an ICR + consumer sign-off (docs/43 §4).
- Internal/free to change: file segmentation/rotation, on-disk serialization details (order/atomicity/chain preserved).
