# Registry (S4) — IMPLEMENTATION
Owner: A3 Ledger/Registry Agent   Subsystem: S4 (with Ledger)   Source of truth: docs/32_database.md, docs/42 §6, docs/41 + docs/40 §2, docs/54 §S4
Scope note: the Registry is the **projection half** of S4. The event store is documented in
`charterhouse/ledger/`. The Registry holds **no source-of-truth state**.

## 1. Responsibility (one paragraph)
S4-Registry answers "what ventures exist and what state is each in?" as a **projection of the ledger**
(`INV-LEDGER`: `Registry == Ledger.replay()`). It exposes `get(venture_id)` and `query(state?)` over
per-venture records (docs/42 §6), powering the portfolio-as-view and the PIPELINE board. It **MUST NOT**
be a source of truth (it is always reconstructable from events), **MUST NOT** apply lifecycle *rules*
(legality/WIP/clocks are S5; Registry only reflects the replayed result), **MUST NOT** call an LLM, and
**MUST NOT** hold durable state that survives a rebuild — a cache/index is allowed but must be
byte-reproducible from `replay()`.

## 2. Invariants enforced
- **`INV-LEDGER` (docs/32, docs/54 §S4):** `Registry.get/query` results equal what `Ledger.replay()`
  produces for the same event set. *Guaranteed by:* the Registry is built *by* `replay()`; any cache is
  invalidated/rebuilt from events, never written independently.
- **Projection-only (docs/41 §3, `INV-COND-3` spirit):** no method mutates truth; the only way to change
  the Registry is to append an event to the Ledger and re-project.
- **`INV-DET` (docs/61):** deterministic; imports none of `router`/`memory`/`capabilities`.
- **`INV-FAILCLOSED`:** a query during a detected chain break fails closed (surfaces the Ledger error), never returns stale/guessed state.

## 3. Internal design
- **Deterministic**, pure over the replayed `WorldState`. The venture record (docs/42 §6):
  `id, codename, state, score, forked_from?, state_entered_at, experiment_live_at?, active_time_accum,
  omw_granted?(bool), evidence_ttl_at?, artifact_links[], event_stream_ptr`. This `Venture` type lives in
  `charterhouse/contracts/` (docs/43 §6), shared with S5/S12.
- Modules: `projection` (fold `WorldState` → venture records — invoked via `Ledger.replay()`), `index`
  (optional in-memory index by id and by state for `query`), `facade` (the `Registry.get/query` API).
- **Cache discipline:** the index is a derived accelerator. On any doubt (chain break, cold start) it
  rebuilds from `replay()`. It is never persisted as truth.

## 4. Dependencies
- **Consumes:** `Ledger.replay()` / `Ledger.read()` (same subsystem, docs/40 §2). No external subsystem API.
- **Consumed by:** A4 Lifecycle (reads current venture state to evaluate guards), A10 Conductor + A13
  Projections (portfolio views, PIPELINE board), A11 (simulator assertions).

## 5. Failure behavior
| Failure mode | Fail-closed response |
|---|---|
| `get`/`query` for a venture that never existed | return `None` / empty list (a defined, non-guessing answer) |
| Ledger chain break during projection | surface the Ledger error; refuse to serve stale/partial state |
| Index/cache inconsistency detected | discard cache; rebuild from `replay()`; never serve unverified state |
No path invents a venture, a state, or a slot count.

## 6. Open questions → RESOLVED
- **Q: Can the Registry be queried while the Ledger is mid-append?** **RESOLVED —** single-writer (docs/32);
  reads are over immutable committed segments, so a query reflects the last committed event. No dirty reads.
- **Q: Where do slot/WIP counts live?** **RESOLVED —** slot occupancy is *derived* from replayed venture
  states; the Registry exposes the states, and **S5 Lifecycle** computes/enforces WIP from them (`Lifecycle.slots()`,
  docs/40 §3). The Registry does not own slot rules.
- **Q: Is `query(state)` the only query shape?** **RESOLVED —** the frozen seam is `get(id)` + `query(state?)`
  (docs/40 §2). Richer queries (by lineage, by deadline) are built by S13 Projections over `read()`, not added here, to keep the seam minimal.
