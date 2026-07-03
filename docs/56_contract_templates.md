# 56 — IMPLEMENTATION CONTRACT TEMPLATES
## The four documents every subsystem produces BEFORE writing code
**Owner:** Program · **Status:** authoritative

> Hard rule: **no implementation code is written until a subsystem's four contract documents exist and are internally consistent.** They live in the subsystem's module folder (`<module>/IMPLEMENTATION.md`, `API.md`, `TESTPLAN.md`, `RISKS.md`). Program (or a peer agent) reviews them for consistency; only then does coding begin. This is the primary defense against future rewrites (priority #4).

Consistency check before coding: every API in `API.md` has a test in `TESTPLAN.md`; every risk in `RISKS.md` has a mitigation reflected in `IMPLEMENTATION.md` or `TESTPLAN.md`; every `MUST`/`INV-*` from the source spec appears in `IMPLEMENTATION.md` and is tested in `TESTPLAN.md`.

---

## Template A — `IMPLEMENTATION.md`
```
# <Subsystem> — IMPLEMENTATION
Owner: <agent>   Subsystem: <Sx>   Source of truth: <frozen doc(s)> + <IB doc(s)>

## 1. Responsibility (one paragraph)
What this subsystem owns, and — explicitly — what it MUST NOT do (boundary from `50` §3).

## 2. Invariants enforced
List every INV-* this subsystem is responsible for, verbatim, with how each is guaranteed.

## 3. Internal design
Modules/classes, data structures, algorithms. Deterministic vs LLM-path clearly marked.
State ownership: what durable state (if any) lives here vs the ledger.

## 4. Dependencies
Interfaces consumed (from `43`), with the exact version/signature relied on.

## 5. Failure behavior
Every failure mode → fail-closed response. No "guess/continue" paths.

## 6. Open questions → RESOLVED
Any ambiguity found in the spec, and its resolution (must be resolved before coding;
if physically impossible, raise a Blocking Impossibility per `70`, do not self-redesign).
```

## Template B — `API.md`
```
# <Subsystem> — API
Owner: <agent>

## Exposed surface
For each public function/method:
  name, signature (typed), preconditions, postconditions, errors raised,
  side effects (ledger writes? none?), determinism (pure/deterministic/LLM),
  authorization class if it triggers an action (GREEN/YELLOW/RED).

## Consumed surface
For each dependency API used: name, expected signature, failure handling.

## Interface stability
Which parts are frozen (breaking change = coordinated interface bump per `43`),
which are internal and free to change.
```

## Template C — `TESTPLAN.md`
```
# <Subsystem> — TESTPLAN
Owner: <agent>   (written BEFORE implementation)

## Unit tests
Each: what it asserts, the fake(s) used, the INV-* it covers.

## Integration tests
Each: which interface/partner subsystem, the scenario, expected ledger/state.

## Invariant coverage table
INV-*  ->  test name  ->  tier    (must cover 100% of this subsystem's MUSTs)

## Fixtures/fakes needed (from A11 shared harness)
FakeProvider / FakeEmbedder / Clock / PII corpus / golden set — which and why.

## Out of scope (test-safety)
Confirm no real spend/send/deploy/charge is exercised (INV-TEST-SAFE).
```

## Template D — `RISKS.md`
```
# <Subsystem> — RISKS
Owner: <agent>

## Risk register
For each risk: description, likelihood, impact, category
(architectural-integrity / ambiguity / refactor / security / performance),
mitigation, and where the mitigation is enforced (code/test/doc).

## Refactor-avoidance notes
Decisions taken specifically to minimize future rewrites (priority #4),
and the interface guarantees that make later change cheap.

## Assumptions
Everything assumed about other subsystems' behavior (must match their API.md).
```

---

## Review gate (before coding starts on a subsystem)
A subsystem is **cleared to implement** when: all four docs exist; the consistency check passes; every source-spec `MUST` is traced into `IMPLEMENTATION.md` + `TESTPLAN.md`; no unresolved ambiguity remains; interfaces consumed match the partners' frozen `API.md`. Program records the clearance as a ledger entry in the build tracker (`70`).
