# Registry (S4) — TESTPLAN
Owner: A3 Ledger/Registry Agent   (written BEFORE implementation)

## Unit tests
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_registry_equals_replay` (property) | for arbitrary event sequences, `get`/`query` results == `Ledger.replay()` projection | in-mem Ledger + generated events | **`INV-LEDGER`** |
| `test_get_unknown_returns_none` | `get(id)` for a never-seen venture → `None` (no guess) | in-mem Ledger | fail-closed/defined answer |
| `test_query_by_state_filters` | `query(state)` returns exactly the ventures in that state; order deterministic | fixture events | portfolio-as-view (docs/32) |
| `test_query_all_when_no_filter` | `query()` returns every venture | fixture events | docs/40 §2 |
| `test_venture_record_shape` | projected records carry all docs/42 §6 fields | fixture | record shape |
| `test_projection_only_no_mutation` | Registry exposes no method that changes state without an appended event | API introspection | projection-only |
| `test_cache_rebuilds_from_replay` | corrupting/dropping the derived index → next query rebuilds identical result from `replay()` | in-mem Ledger | cache discipline |
| `test_chain_break_fails_closed` | a Ledger chain break during projection → query surfaces the error, no stale state | corrupted fixture | `INV-FAILCLOSED` |

## Integration tests
| Test | Partner | Scenario | Expected |
|---|---|---|---|
| `test_it_lifecycle_transition_replays` | A4 Lifecycle (stub, docs/40 §3) | append a `transition`, then `Registry.get(v)` | reflects the new state; matches `replay()` |
| _(pipeline view deferred)_ | A13 Projections (stub) | build a PIPELINE board from `query()` | board equals a direct replay-derived board — lands with A13 |

> The lifecycle-reads-current-state scenario is realized by the shared S4 integration test
> `test_it_lifecycle_transition_replays` (in `tests/integration/`). The PIPELINE-view scenario is
> deferred to A13 Projections (its stub does not exist on this branch).

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| `INV-LEDGER` (Registry == replay) | `test_registry_equals_replay` (property) | unit |
| Projection-only / no independent truth | `test_projection_only_no_mutation`, `test_cache_rebuilds_from_replay` | unit |
| Defined answer for unknown id | `test_get_unknown_returns_none` | unit |
| Query filtering + determinism | `test_query_by_state_filters`, `test_query_all_when_no_filter` | unit |
| Fail-closed on chain break | `test_chain_break_fails_closed` | unit |
| `INV-DET` | anti-coupling import check (A11) | static |

## Fixtures/fakes needed (from A11 shared harness)
- **In-memory Ledger fake** (shared with A3 Ledger tests; same `Ledger` signature). Event-sequence generator
  for the property test. No FakeProvider/Embedder needed (no LLM path).

## Out of scope (test-safety)
No real spend/send/deploy/charge (`INV-TEST-SAFE`). The Registry is read-only over the ledger.
