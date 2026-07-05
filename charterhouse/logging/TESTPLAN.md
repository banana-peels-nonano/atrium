# Logging & Test Harness (S14 + S15) — TESTPLAN
Owner: A11 Test/Logging Agent   (written BEFORE implementation)
Note: A11 owns the harness that other agents test *into*; these are the harness's **self-tests** (docs/51 A11).

## Unit tests
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_log_strips_secret_fields` | a secret-shaped field passed to `Log.event` is dropped/redacted, never written raw | — | no-secret-in-logs (docs/24) |
| `test_log_strips_pii_fields` | a PII-shaped field is redacted before write | pii_corpus | no-PII-in-logs |
| `test_telemetry_appends_llm_call_event` | `Telemetry.record` appends a well-formed `llm_call` event; no secret/PII in payload | InMemoryLedger | docs/40 §10 / docs/41 §2 |
| `test_log_and_telemetry_distinct_sinks` | `Log`→`K:\Logs\`, `Telemetry`→ledger; not conflated | temp logs dir + InMemoryLedger | design split |
| `test_inmemory_ledger_signature_parity` | `InMemoryLedger` exposes the same public signature as the real `Ledger` (docs/40 §2) | import both | **fake↔real parity** |
| `test_fakeprovider_deterministic` | same inputs → same canned output; programmable error/rate-limit/latency honored | — | docs/55 §2 |
| `test_fakeembedder_deterministic_dim` | fixed-dim, deterministic vectors for a given text | — | docs/55 §2 |
| `test_clock_pause_resume` | active-time freezes on pause, resumes on resume | — | supports `INV-SM-3` tests |
| `test_invariant_manifest_flags_unmapped_must` | a `MUST` with no mapped test → manifest check fails | synthetic manifest | **docs/55 §4** |
| `test_test_safe_guard_blocks_real_action` | a test reaching a real spend/send/deploy/charge path → harness guard fails it | — | **`INV-TEST-SAFE`** |

## Integration tests
| Test | Partner | Scenario | Expected |
|---|---|---|---|
| `it_telemetry_roundtrip_real_ledger` | A3 Ledger (real, file) | `Telemetry.record` → `Ledger.read({type:llm_call})` | event present; replay includes it; no PII |
| `it_harness_hosts_a_subsystem_test` | any Wave-0 subsystem | a subsystem's unit test imports the shared fakes and runs | green under the shared harness/conftest |
| `it_simulator_shape_available` | (shape only) | the `Simulator` interface can be instantiated with fakes; body deferred | interface present; documented as not-yet-executable (§ IMPLEMENTATION §6) |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| `INV-TEST-SAFE` (docs/55 §6) | `test_test_safe_guard_blocks_real_action` | unit |
| No secret/PII in logs (docs/24, §S14) | `test_log_strips_secret_fields`, `test_log_strips_pii_fields` | unit |
| Invariant-harness completeness (docs/55 §4) | `test_invariant_manifest_flags_unmapped_must` | unit/meta |
| Fake↔real parity (docs/43) | `test_inmemory_ledger_signature_parity` | unit |
| Telemetry→ledger event (docs/40 §10) | `test_telemetry_appends_llm_call_event`, `it_telemetry_roundtrip_real_ledger` | unit + integration |
| `INV-DET` | anti-coupling import check (self) | static |

## Fixtures/fakes needed (from A11 shared harness — A11 owns these)
- The fakes are the deliverable; the self-tests exercise them. `pii_corpus` and a temp `K:\Logs\` fixture are used here.

## Out of scope (test-safety)
No real spend/send/deploy/charge (`INV-TEST-SAFE`) — this subsystem *defines and enforces* that guard. The
lifecycle simulator body is out of scope until S4/S5/S10/S12 exist; only its interface/shape is delivered now.
