# Registry (S4) — RISKS
Owner: A3 Ledger/Registry Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced in |
|---|---|---|---|---|---|---|
| R1 | The Registry becomes a second source of truth (state written independently of the ledger) | Med | Critical | architectural-integrity | projection-only; the only mutation path is Ledger append + re-project; no persisted registry truth | `test_projection_only_no_mutation`, `test_registry_equals_replay` |
| R2 | A stale/inconsistent cache serves state that diverges from `replay()` | Med | High | correctness | cache is a derived accelerator, rebuilt from `replay()` on any doubt; never persisted as truth | `test_cache_rebuilds_from_replay` |
| R3 | The Registry starts enforcing lifecycle rules (WIP/legality), duplicating S5 | Med | High | architectural-integrity | Registry reflects replayed states only; slot/WIP owned by S5 `Lifecycle.slots()` (docs/40 §3) | IMPLEMENTATION §6 + ownership check |
| R4 | A chain break yields stale reads instead of failing closed | Low | High | integrity | queries surface the Ledger chain error; no stale fallback | `test_chain_break_fails_closed` |
| R5 | `Venture` record shape drifts from docs/42 §6, breaking S5/S12 consumers | Low | High | interface | `Venture` frozen in `charterhouse/contracts/`; change = ICR (docs/43 §4) | clearance package + doc-sync gate |

## Refactor-avoidance notes
- Because the Registry is *pure projection*, any performance work (indexes, snapshots-of-projection) is
  free to change without touching the seam — the frozen surface is only `get`/`query` + the `Venture` type.
- Keeping WIP/slot logic out of the Registry (S5 owns it) means the lifecycle rules live in exactly one
  place (priority #1, no invariant enforced twice).

## Assumptions
- `Ledger.replay()`/`read()` behave per the Ledger `API.md` (same subsystem) — total order, chain-verified, deterministic.
- The `Venture` record and `State` enum in `charterhouse/contracts/` match docs/42 §6 and are consumed identically by S5/S12.
