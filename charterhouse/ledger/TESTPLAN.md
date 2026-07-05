# Ledger (S4) — TESTPLAN
Owner: A3 Ledger/Registry Agent   (written BEFORE implementation)

## Unit tests
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_append_atomic_ordered` | sequential appends get monotonic ULIDs; total order preserved across segments | tmp ledger dir | atomic+ordered (docs/54 §S4) |
| `test_partial_write_never_corrupts` | an interrupted/partial write is never visible on read; last good state stands | fault-injected writer | atomic append |
| `test_concurrent_append_no_interleave` | serialized single-writer: records never interleave under concurrent callers | threads + tmp ledger | docs/54 §S4 |
| `test_hash_chain_links` | each event's `prev_hash` matches the prior event's canonical hash | tmp ledger | tamper-evidence |
| `test_tamper_detected_on_read` | mutating a historical record → chain break raised on read; replay refuses | tmp ledger | **tamper detection** (docs/54 §S4) |
| `test_replay_deterministic_state` (property) | for arbitrary legal event sequences, `replay()` == expected world state; re-running is identical | generated sequences | **`INV-LEDGER`** |
| `test_replay_refuses_broken_chain` | a broken chain → `replay` raises, returns no partial state | corrupted fixture | fail-closed |
| `test_reject_raw_pii_payload` | a payload with structural PII/secret → append rejected; field named | PII corpus (A11) | **`INV-PII-1`** (defense in depth) |
| `test_reject_gate_event_without_token` | a gate/RED-typed event missing `authorization` → append rejected | fixture | docs/41 §4.2 |
| `test_reject_unknown_event_type` | a `type` not in the frozen catalog → append rejected | fixture | catalog integrity |
| `test_omw_grant_cap_replay_checked` | a second `omw_grant` in a lineage → replay flags violation | fixture | `INV-SM-5`/OMW-LEDGER (docs/41 §4.3) |
| `test_pivot_fork_cap_replay_checked` | a second `pivot_fork` in a lineage → replay flags violation | fixture | `INV-SM-5` |
| `test_schema_version_stamped_and_read` | every event carries `schema_version`; reader accepts prior versions | mixed-version fixture | docs/41 §5 |

## Integration tests
| Test | Partner | Scenario | Expected ledger/state |
|---|---|---|---|
| `it_lifecycle_transition_replays` | A4 Lifecycle (stub against docs/40 §3) | a `transition` event appended → `replay()` reproduces the venture's new state | `Registry == replay()` after the transition |
| `it_snapshot_restore_replay_identical` | ops / A1 paths | `snapshot()` → mutate → `restore()` → `replay()` | byte-identical registry state (docs/54 §S4) |
| `it_telemetry_llm_call_event` | A11 Telemetry (docs/40 §10) | `Telemetry.record(...)` → `append(llm_call)` | an `llm_call` event present, no secrets/PII in payload |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| `INV-LEDGER` (state == replay) | `test_replay_deterministic_state` (property) | unit |
| Atomic + totally-ordered append | `test_append_atomic_ordered`, `test_partial_write_never_corrupts`, `test_concurrent_append_no_interleave` | unit |
| Tamper-evidence / fail-closed read | `test_tamper_detected_on_read`, `test_replay_refuses_broken_chain` | unit |
| Snapshot→restore identical | `it_snapshot_restore_replay_identical` | integration |
| No raw PII in payload (`INV-PII-1`) | `test_reject_raw_pii_payload` | unit |
| Token id on gate/RED (docs/41 §4.2) | `test_reject_gate_event_without_token` | unit |
| Once-per-lineage caps (docs/41 §4.3) | `test_omw_grant_cap_replay_checked`, `test_pivot_fork_cap_replay_checked` | unit |
| `schema_version` evolution (docs/41 §5) | `test_schema_version_stamped_and_read` | unit |
| `INV-DET` | anti-coupling import check (A11) | static |

## Fixtures/fakes needed (from A11 shared harness)
- **In-memory Ledger fake** — MUST expose the **same signature** as this `Ledger` API (docs/40 §2) so
  downstream unit tests run fast against a real interface (A11 owns it; consistency asserted in the clearance package).
- **PII corpus** — for `test_reject_raw_pii_payload`. **Clock** — for `active_time` stamping tests.
- Property-based sequence generator for `test_replay_deterministic_state`.

## Out of scope (test-safety)
No real spend/send/deploy/charge (`INV-TEST-SAFE`). The Ledger only records events; it performs no action.
Backup tests write only under a temp dir / `K:\Backups` fixture, never off-machine.
