# 55 — TESTING STRATEGY
## Designed before implementation; nothing is built without a validation path
**Owner:** Test Agent (A11) · **Source of truth:** all subsystem docs, Stress Test · **Status:** authoritative

> Rule: **no functionality is implemented without a known validation.** Each subsystem's `TESTPLAN.md` (`56`) is written and reviewed *before* its implementation code. CI blocks any merge with red or missing tests for touched `MUST` clauses.

## 1. Test tiers (what, who, when)
| Tier | Purpose | Owner | Runs |
|---|---|---|---|
| **Unit** | one function/guard/adapter in isolation, using fakes | each agent | every commit |
| **Integration** | two+ subsystems across a frozen interface | each agent (pairwise) | every PR |
| **Lifecycle simulation** | a venture (or three) walked through the state machine | A11 | every PR touching S4/S5/S10/S12 |
| **Regression** | locked behaviors + every fixed Stress-Test defect | A11 | every PR |
| **State-machine verification** | property/model-based transition + invariant checks | A4/A11 | every PR touching S5 |
| **Governance verification** | action-class, tokens, envelope, send-budget, two-key | A5/A11 | every PR touching S6 |
| **Security/PII verification** | redaction, deterministic scan, cloud-block | A5/A11 | every PR touching S7/S8/S9 |
| **Provider failover** | primary down / rate-limited / exhausted → chain + degrade | A6/A11 | every PR touching S8 |
| **Model routing** | role→model per profile; profile switch reroutes | A6/A11 | every PR touching S8 |
| **Rate-limit** | free-tier limit → fallback / queue; no crash | A6/A11 | nightly + PR touching S8 |
| **Performance benchmark** | retrieval latency, replay time, embed throughput | A11 | nightly |
| **Acceptance** | the `54` criteria per subsystem | A11 | phase-exit gate |

## 2. Test doubles (owned by A11, shared)
- **FakeProvider:** deterministic LLM stand-in with programmable latency, errors, rate-limits, and canned outputs — so LLM-dependent code is testable with zero cost and full determinism.
- **FakeEmbedder:** fixed-dimension deterministic vectors for retrieval tests (no model needed).
- **In-memory Ledger:** fast ledger for unit tests; the real file ledger is used in integration.
- **Clock:** injectable factory-active-time clock to test deadlines, TTL, and `pause`.
- **PII corpus:** a fixture of names/emails/secrets/financials to test the deterministic scanner's precision/recall.
- **Golden set:** saved real tasks (5 scout briefs, 2 analyst packs, 1 builder task) to detect capability/model drift across model changes (frozen future-proofing).

## 3. The lifecycle simulator (the crown-jewel test)
A deterministic driver that instantiates ventures and issues Conductor commands with FakeProvider/FakeEmbedder/Clock, then asserts states, ledger events, and invariants. It **must reproduce Stress-Test scenarios A (`battlecard`, happy path), B (`hvac-route`, messy death), and C (`clipscribe`, pivot + concurrency + PII)** and assert the v1.1 fixes: envelope (R-ENVELOPE), separate billing (R-CHARGE), SHAPING WIP + shovel-ready (R-SHAPING-WIP), evidence TTL (R-EVIDENCE-TTL), active-time clock (R-ACTIVE-TIME), pivot fork cap (R-PIVOT), PII cloud-block (R-REDACT/R-PRECOMMIT-SCAN), send budget (R-SEND-BUDGET), critic degrade (R-CRITIC-DEGRADE), override log (R-OVERRIDE-LOG), OMW ledger (R-OMW-LEDGER).

## 4. Invariant harness
Every `INV-*` (`02`,`14`,`42`,`54`) has a named test. A CI report lists each invariant → its test → pass/fail. **A `MUST` with no mapped invariant test blocks the phase-exit gate.** This is the single most important quality mechanism: it makes "did we preserve the architecture?" a green/red signal, not a judgment call.

## 5. Fault injection (resilience)
- Kill the primary provider mid-call → failover asserted.
- Exhaust all providers → `pause` declared, clocks freeze, vault stays usable.
- Corrupt a ledger record → detected on read, replay refuses.
- Fail redaction → CHECKPOINT fails closed, venture unchanged.
- Crash mid-command → restart, replay, zero loss.

## 6. What is explicitly NOT tested with real side effects
No test performs a real spend, real outreach send, real production deploy, or real customer charge. These are asserted only up to the **authorization boundary** (the token request), never executed. This is a permanent test-safety invariant (`INV-TEST-SAFE`).

## 7. Coverage policy
- 100% of `MUST` clauses covered by an invariant test (hard gate).
- Deterministic subsystems (S1–S7,S12–S15): high line/branch coverage expected (they're pure logic).
- LLM-path subsystems (S8–S11): behavior tested via FakeProvider; live smoke is optional and never gates a merge (avoids flakiness + cost).

## 8. Test execution order (CI)
lint+types+determinism → unit → integration → security/PII → governance → state-machine → routing/failover → lifecycle simulation → regression → (nightly: rate-limit, perf). Fast, deterministic checks first; anything touching a network is optional and last.
