# Conductor (S12) — RISKS
Owner: A10 Conductor Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced |
|---|---|---|---|---|---|---|
| R1 | Rule drift: a convenience re-implementation of an S5/S6/S7 rule sneaks into a handler and later disagrees with the owner | medium | critical | architectural-integrity | handlers are thin call-throughs; static scan (no matrix/legality/AuthClass/PII-regex in `conductor/`) + call-path spy tests; refusal text is always the owner's | code + tests (INV-COND-1 pair) |
| R2 | Double consumption of a single-use token (conductor pre-authorizes AND the owner authorizes) | medium | high | correctness | tokens pass through to exactly one owner boundary (§6.1); proven by the consumed-once test | code (dispatch) + `test_single_use_token_consumed_once` |
| R3 | A conductor recorder append smuggles state (a `to_state` on a fact event) letting a command move a venture outside S5 | low | critical | architectural-integrity | recorder facts NEVER set `from_state`/`to_state` (replay-inert by construction — the A8 precedent); only S5 events carry state | code + replay asserts in tests |
| R4 | Partial multi-append commands (gate = spec_approved + transition + gate_decision) corrupt on crash | medium | medium | reliability | each append is atomic (S4); ordering puts the OWNER's state event at the decision point; a lost trailing recorder fact is re-issuable and replay stays clean (INV-COND-3 probe) | test (`test_crash_mid_command_zero_loss`) |
| R5 | The additive `artifact_produced` event type breaks an existing consumer/replay | low | medium | refactor | additive per IF-1's recorded evolution rule; state-neutral payload; docs/41 §2 updated same-PR (docs/62); full 676-test suite must stay green | docs + CI |
| R6 | Projections drift from the ledger (caching, hidden state) and lie to the founder | medium | high | architectural-integrity | S13 functions take the ledger and re-derive per call — no cache, no module state; purity tests recompute twice + after replay | code (pure fns) + S13 suite |
| R7 | GateBrief schema erosion (a brief without a critic reaches the founder) | low | critical | security/governance | `GateBrief.critic` is a required constructor field; assembly fails closed (`NoCriticForGate`); the `gate` command requires the brief | code-by-construction + tests (INV-COND-2) |
| R8 | The v1 no-real-effect boundary is forgotten later (a real deploy pipeline gets wired without its two-key path) | low | critical | security | the recorded events carry the token id — the future pipeline consumes ONLY token-carrying events; documented in API.md + IMPLEMENTATION §6.6 | doc (the integration contract) |
| R9 | Command-surface sprawl (new ad-hoc names bypassing the frozen matrix) | low | medium | ambiguity | the conductor validates names against S6's `is_known` (call-through — the matrix stays S6's); unknown → RED + denied | code + `test_unknown_command_refused` |
| R10 | The live-stack integration surfaces a mismatch in a merged subsystem (signature/semantic) | medium | medium | integration | per the founder's instruction: fix tests-first ON THIS BRANCH, document each fix in the tracker + the gate report — never a silent workaround | process (tracker row + gate report) |

## Refactor-avoidance notes
- One dispatch table = one place to add a command; handlers stay ≤ a dozen lines
  because owners do the work.
- Recorder payload builders isolated per event type — docs/41 payload evolution is
  additive and local.
- S13 functions are `events → dataclass` folds; new projections are new pure
  functions, no conductor change.
- The future real pipelines (deploy/billing/send) attach to recorded token-carrying
  events, not to conductor internals (R8) — the chokepoint API never changes for them.

## Assumptions
- S5 `transition` authorizes internally via its GovPort with `rule.auth_scope`
  (lifecycle/facade.py — verified); passing the token through is the correct single
  consumption path.
- S6 `authorize` consumes on ok only and denies with reasons (governance/API.md —
  verified); `envelope_open` mints+consumes its own receipt token.
- S4 `Ledger.append` is atomic, validates the envelope, and requires `authorization`
  presence for the gate/RED event set (`AUTHORIZATION_REQUIRED`) — hence the recorder
  facts for deploy/billing/launch/send/spec_approved always carry the token id.
- S10 `Workflow.run` mutates only at CHECKPOINT with state-neutral events (A8 —
  verified); the conductor's table rows inherit that guarantee.
- The A11 simulator's Stress-Test coverage remains the regression net for S5-level
  scenario fidelity; this suite covers the conductor-driven path.
