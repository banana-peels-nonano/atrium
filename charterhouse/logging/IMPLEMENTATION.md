# Logging & Test Harness (S14 + S15) — IMPLEMENTATION
Owner: A11 Test/Logging Agent   Subsystems: S14 (Logging/Observability) + S15 (Testing Harness)
Source of truth: docs/55_testing_strategy.md, docs/40 §10, docs/24, docs/61 + docs/54 §S14/S15
Scope note: this single contract set covers **both** of A11's subsystems (one agent, docs/51 A11). The
Logging API + telemetry live in `charterhouse/logging/`; the shared fakes/fixtures/simulator/invariant-harness
live in `tests/` (A11-owned, docs/60). Resolved in §6.

## 1. Responsibility (one paragraph)
A11 ensures **nothing is implemented without a validation path** and provides the observability spine.
**S14 Logging:** structured operational logs to `K:\Logs\` via `Log`, and per-role/venture telemetry
(tokens/$/latency) recorded as ledger `llm_call` events via `Telemetry`. **S15 Testing:** the shared test
harness — `FakeProvider`, `FakeEmbedder`, in-memory `Ledger`, `Clock`, PII corpus, golden set — plus the
lifecycle simulator and the invariant harness (every `INV-*` → a named test; an unmapped `MUST` blocks the
phase-exit gate). It **MUST NOT**: log secrets or PII (docs/24), perform or permit any real
spend/send/deploy/charge in a test (`INV-TEST-SAFE`, docs/55 §6), call an LLM from the deterministic logging
path, or let a fake's interface drift from the real subsystem it doubles.

## 2. Invariants enforced
- **`INV-TEST-SAFE` (docs/55 §6):** no test performs a real spend/send/deploy/charge; these are asserted only
  up to the authorization boundary. *Guaranteed by:* fakes have no real side-effect backends; a harness guard
  fails any test that reaches a real network action.
- **No secret/PII in logs (docs/24, docs/54 §S14):** `Log`/`Telemetry` strip/refuse secret- and PII-shaped
  fields before write. *Guaranteed by:* a deterministic field filter on the log path + the CI secret scan.
- **Invariant-harness completeness (docs/55 §4):** every `INV-*` maps to a named test; a `MUST` with no mapped
  test **blocks the phase-exit gate**. *Guaranteed by:* a harness manifest (INV → test) checked in CI.
- **Fake↔real interface parity (docs/43):** each fake exposes the *same signature* as the subsystem it doubles
  (esp. in-memory `Ledger` == docs/40 §2). *Guaranteed by:* a contract test that imports both and asserts signature parity.
- **`INV-FAILCLOSED` / `INV-DET` (docs/61):** logging is deterministic and side-effect-isolated; the telemetry
  path's only durable write is a ledger append.

## 3. Internal design
- **S14 Logging** (`charterhouse/logging/`), deterministic, no LLM:
  - `Log.event(level, where, fields)` → structured line to `K:\Logs\` (path from `EnvContext`); field filter drops secret/PII shapes.
  - `Telemetry.record(llm_call_fields)` → builds an `llm_call` event and appends via `Ledger.append` (docs/41 §2, docs/40 §10).
  - Split discipline (per advisor): **operational logs → `K:\Logs\` (S14)**; **auditable telemetry → ledger events (via A3)**. Not conflated.
- **S15 Test harness** (`tests/`), owned by A11, imported by every other agent's tests:
  - **Fakes/doubles (docs/55 §2):** `FakeProvider` (programmable latency/errors/rate-limits/canned outputs),
    `FakeEmbedder` (fixed-dim deterministic vectors), **in-memory `Ledger`** (fast, same `Ledger` signature),
    `Clock` (injectable factory-active-time), PII corpus, golden set.
  - **Lifecycle simulator (docs/55 §3):** the deterministic driver that issues Conductor commands with the
    fakes and asserts states/events/invariants; reproduces Stress-Test A/B/C. **Interface + shape frozen now;
    body lands as S4/S5/S10/S12 arrive** (§6).
  - **Invariant harness (docs/55 §4):** the INV→test manifest + CI reporter.

## 4. Dependencies
- **Consumes:** `Ledger.append` (A3, docs/40 §2/§10) for telemetry; `EnvContext` (A1) for `K:\Logs\` path.
  As test doubles, the harness *stands in for* all subsystems (docs/51 A11 "APIs consumed: all (as test doubles)").
- **Consumed by:** every subsystem (each writes its tests into this harness; each emits `Log`/`Telemetry`).
- Active from Phase 0 (cross-cutting) — the harness ran green from the Phase-0 structure test onward and
  now carries every subsystem's suite; `Log`/`Telemetry` have real bodies (merged 2026-07-11, S14+S15).

## 5. Failure behavior
| Failure mode | Fail-closed response |
|---|---|
| A field passed to `Log`/`Telemetry` looks like a secret/PII | strip/refuse the field; log a redacted marker; never write raw |
| A test reaches a real spend/send/deploy/charge path | harness guard fails the test (`INV-TEST-SAFE`) |
| A fake's signature diverges from the real subsystem | signature-parity contract test fails |
| An `INV-*` has no mapped test | invariant-harness manifest check fails the phase-exit gate |
| Ledger append fails during telemetry | surface the error; operational log still records the attempt (no silent drop) |

## 6. Open questions → RESOLVED
- **Q: Where do A11's contract docs live given two subsystems + a non-`charterhouse/` `tests/` tree?**
  **RESOLVED —** one contract set in `charterhouse/logging/` covers both S14 and S15 (one owning agent). The
  `tests/` deliverables are specified here and in TESTPLAN; `tests/` carries no separate contract docs (it is
  not a `charterhouse/` subsystem folder in docs/31). Ownership stays disjoint (A11 owns `tests/` + `logging/`).
- **Q: Can the lifecycle simulator be delivered now?** **RESOLVED — No; interface-only now.** It needs S4/S5/S10/S12.
  This contract freezes the simulator's *shape* and the fakes' *signatures* (IF-5-adjacent for the runner);
  bodies land with their dependencies. Stated so as not to over-promise (advisor note).
- **Q: Log vs Telemetry — same sink?** **RESOLVED — No.** `Log` → `K:\Logs\` files (operational); `Telemetry` →
  ledger `llm_call` events (auditable, replayable). Distinct sinks by design (docs/40 §10, docs/41 §2).
- **Q: How is `InMemoryLedger` kept from drifting from the real `Ledger` (RISKS R3)?** **RESOLVED —** it is a
  **subclass of the real `Ledger`** over a per-instance ephemeral temp dir (removed on `close()`). "In-memory"
  = ephemeral + auto-managed (no persistent K: state), not a reimplementation of the hash-chain fold — so it
  cannot drift in signature *or* semantics (the strongest form of the docs/55 §2 fake). The parity self-test
  still asserts signature equality. **Founder consistency note** (lighter review): confirm this reading of
  "in-memory" is acceptable vs a pure-RAM reimplementation.
- **Q: Gate 2 (INV-SM harness) — is it live now that S5 is merged?** **RESOLVED — Yes.** `scripts/invariant_check.py`
  drives `tests/invariants/manifest.py`: it verifies every INV-SM-1..6 maps to a **collectable** test and fails
  the gate on any unmapped/renamed/deleted invariant test (docs/55 §4). ci.ps1 gate 2 now runs it (placeholder
  removed). The manifest is authoritative for the INV-SM family today; INV-GOV/PII/LEDGER families are declared
  in `REQUIRED_INVARIANTS` and mapped as A11 hoists those suites into the shared harness (future, not gate-2-blocking).
- **Q: Simulator body — deliverable now that S4/S5 exist?** **RESOLVED — Still shape-only.** It drives Conductor
  commands (S12) over capability beats (S10), neither of which exists yet. The *shape* is frozen; S5's Stress-Test
  A/B/C reproduction already runs against the real stack in `tests/integration/test_lifecycle_sim.py`. `run()`
  raises a precise not-yet-executable error rather than a silent stub.
