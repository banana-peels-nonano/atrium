# Registry (S4) — API
Owner: A3 Ledger/Registry Agent   ·   Matches docs/40 §2 exactly (frozen seam, part of IF-1)

## Exposed surface

### `Registry.get(venture_id) -> Venture | None`
- **Postconditions:** returns the current projected venture record (docs/42 §6) or `None` if no such
  venture exists in the replayed history. Equals the `replay()` result for that id (`INV-LEDGER`).
- **Errors:** Ledger chain break → surface the error (fail closed), do not return stale state.
- **Side effects:** none (may lazily build/refresh a derived index). **Determinism:** deterministic. **Auth:** n/a.

### `Registry.query(state: State | None = None) -> list[Venture]`
- **Postconditions:** returns all ventures (optionally filtered to `state`) as projected from the ledger;
  the portfolio-as-view. Order is deterministic (by `event_stream_ptr`/id).
- **Errors:** chain break → fail closed. **Side effects:** none. **Determinism:** deterministic.

## Shared type — `Venture` (docs/42 §6; defined in `charterhouse/contracts/`)
```
id, codename, state, score, forked_from?, state_entered_at, experiment_live_at?,
active_time_accum, omw_granted?(bool), evidence_ttl_at?, artifact_links[], event_stream_ptr
```

## Consumed surface
- `Ledger.replay()` / `Ledger.read(filter)` (docs/40 §2, same subsystem). No external subsystem API consumed.

## Interface stability
- **Frozen (part of IF-1):** `get`, `query`, and the `Venture` shared type. Consumers A4/A10/A13 depend on these.
  Recorded frozen in the Build Tracker **only on founder clearance**.
- Internal/free to change: the indexing strategy, cache layout, and any acceleration — all must remain
  byte-reproducible from `replay()`.
