# Logging & Test Harness (S14 + S15) — RISKS
Owner: A11 Test/Logging Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced in |
|---|---|---|---|---|---|---|
| R1 | A secret or PII value is written to a log (`K:\Logs\`) | Med | Critical | security | deterministic field filter strips/refuses secret/PII shapes before write; CI secret scan | `test_log_strips_secret_fields`, `test_log_strips_pii_fields` + CI gate |
| R2 | A test performs a real side effect (spend/send/deploy/charge) | Low | Critical | security/test-safety | fakes have no real backends; harness guard fails any test reaching a real action (`INV-TEST-SAFE`) | `test_test_safe_guard_blocks_real_action` |
| R3 | A fake drifts from the real subsystem it doubles, so tests validate a fiction (esp. `InMemoryLedger`) | Med | High | architectural-integrity | signature-parity contract test binds each fake to the real `API.md` | `test_inmemory_ledger_signature_parity` |
| R4 | An `INV-*`/`MUST` ships with no mapped test, eroding the invariant guarantee | Med | High | architectural-integrity | invariant-harness manifest; unmapped `MUST` blocks the phase-exit gate (docs/55 §4) | `test_invariant_manifest_flags_unmapped_must` |
| R5 | Over-promising the lifecycle simulator before its dependencies exist | Med | Med | ambiguity/scope | freeze interface/shape only now; body lands with S4/S5/S10/S12 (IMPLEMENTATION §6) | `it_simulator_shape_available` (shape only) |
| R6 | `Log` and `Telemetry` conflated → audit trail (ledger) and ops logs entangle | Low | Med | architecture | distinct sinks by contract: ops→`K:\Logs\`, telemetry→ledger events | `test_log_and_telemetry_distinct_sinks` |
| R7 | Telemetry append failure silently loses observability | Low | Med | reliability | surface the error + operationally log the attempt; never silent drop | IMPLEMENTATION §5 |

## Refactor-avoidance notes
- Binding every fake to its real subsystem's `API.md` via a parity test means downstream tests are always built
  on a truthful interface — the single most important guard against "green tests over a lie" as the build grows.
- Freezing the simulator/fakes *signatures* now (bodies later) lets A8/A10 build against a stable harness surface
  without waiting for the simulator implementation — keeping A11 off the critical path (docs/52 §9).
- Splitting ops-logs from ledger-telemetry keeps the audit trail replayable (part of `INV-LEDGER`/`INV-COND-3`) independent of log rotation.

## Assumptions
- A3 Ledger's `append` and the `llm_call` event shape match docs/40 §2/§10 + docs/41 §2.
- A1's `EnvContext` supplies a writable `K:\Logs\` path (docs/23). Secret/PII field *shapes* are detectable by
  the deterministic filter; the authoritative PII redactor remains S7 at CHECKPOINT (defense in depth, docs/24).
