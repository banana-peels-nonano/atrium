# Capability Framework (S10) — RISKS
Owner: A8 Framework Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced |
|---|---|---|---|---|---|---|
| R1 | A future workflow definition smuggles authority through CHECKPOINT (gate/RED event type in a spec) | medium | critical | security | `WorkflowRegistry` refuses any `event_type` in `AUTHORIZATION_REQUIRED` (or unknown) at construction — before anything can run | code (`registry.py`) + parametrized test |
| R2 | A model failure mid-beat corrupts venture state | medium | critical | architectural-integrity | PRODUCE/CRITIQUE structurally cannot reach the vault or `Ledger.append` (no handle passed); CHECKPOINT is write-then-append with artifact rollback on append failure | code (beat decomposition) + `test_produce_exhausted_never_mutates_state`, `test_checkpoint_failure_leaves_no_partial_state` |
| R3 | ~~Family derivation misclassifies a model id, silently weakening the cross-family guarantee~~ **RETIRED 2026-07-19 (feat/a2-accessors, founder follow-up at the A8 gate):** the tier decision follows the catalog's additive `Model.family` field via the injected `family_of` lookup (wiring: `config.get_model(mid).family`); the critic's id parse is deleted — the only derivation is `contracts.default_family`, used by S3's loader to default the field (and as the standalone fallback). Proven authoritative in both disagree directions (`test_critic_family_from_catalog_field`) | — | — | ambiguity | additive `Model.family` + `family_of` seam landed with A2's accessors branch | code (`critic.py`) + test |
| R4 | Critic degrade masks a systemically dead critic route (every run quietly tier-3) | medium | medium | architectural-integrity | the tier is stamped on the result AND the CHECKPOINT event payload — projections/calibration (S13) can alert on tier drift; never silent | code (payload) + test (tier in event) |
| R5 | The tier-3 checklist is too weak to catch bad artifacts (rubber-stamp critique) | medium | medium | ambiguity | checklist derives findings from the SPEC's declared outputs (missing output = finding), not generic fluff; verdict is "flag" whenever findings exist; strengthening the rule set is internal (no ICR) | code (`critic.py::_checklist`) + test |
| R6 | Non-determinism sneaks into PREPARE/CHECKPOINT (wall clock, env, dict order) | low | high | architectural-integrity | PREPARE uses venture facts + active-time only; message assembly sorts collections; A1's env-boundary scan sweeps the package; determinism asserted by equality tests | tests (`test_prepare_deterministic_no_writes`, generator determinism) + static scan |
| R7 | The neutral-spec format drifts from what A9 writes in Phase 5 (loader rejects the real specs) | medium | medium | refactor | the format is frozen in API.md §loader with fixture specs as executable examples; A9 builds against the frozen parser (IF-5 unlock), not vice versa; empty stubs already fail loudly (`SpecInvalid`), never silently | doc (API.md) + test (format + stub) |
| R8 | Generated OpenCode files get hand-edited and drift from the neutral specs | medium | low | refactor | GENERATED-DO-NOT-EDIT stamp + byte-deterministic regeneration (a regen diff exposes drift); neutral specs remain the single source of truth | code (generator) + determinism test |
| R9 | Retry loops hide a systemic provider outage (long silent retries) | low | medium | performance | retries are few and bounded (`spec.retries`, default 2 total attempts); exhaustion surfaces `BeatFailed` (produce) or tier-3 (critique) immediately — S8's own `ProvidersExhausted` pause signal still fires underneath for the Conductor | code (bounded loop) + property test |
| R10 | The runner is asked to run a workflow for a stale venture snapshot (state changed since read) | low | medium | ambiguity | `venture.state == state` guard at entry (`StateMismatch`); the authoritative state remains the replay — S12 re-reads before GATE; the runner never caches ventures | code (guard) + test |

## Refactor-avoidance notes
- IF-5 freezes exactly the docs/40 §7 trio + value shapes; retry internals, family
  heuristic, checklist rules, message templates, and generator layout are all declared
  internal — the likely-to-evolve parts can change with no ICR.
- The state→workflow table as injected DATA keeps S12/A9 additions zero-code here.
- One refusal type per rule reused across seams (S9 `ScopeViolation`, S7
  `CheckpointError`) — no parallel error vocabularies to reconcile later.
- The harness adapter is a generator with one narrow input (`CapabilitySpec`) — adding
  claude-code/aider generators is additive file-per-harness (docs/30's plan).

## Assumptions
- S8 `LLMClient.call` resolves roles via Config only, fails typed, and appends its own
  telemetry (router/API.md — matches); the `critic` role exists in the committed routes
  (config/routes.yaml — it does).
- S7 `Security.checkpoint` is deterministic, fail-closed, and returns
  `{clean, sidecar_ref, contains_pii}` (security/API.md — matches).
- S9 `Memory.retrieve` always includes Doctrine and never dumps the store;
  `write_lesson(scope=)` refuses out-of-scope tags with `ScopeViolation`
  (memory/API.md — matches).
- S4 `Ledger.append` validates the envelope, requires authorization for gate/RED types
  (hence R1's refusal set is exactly `AUTHORIZATION_REQUIRED`), and is atomic
  (ledger/API.md — matches).
- A11 `FakeProvider.complete` matches the IF-2 adapter transport shape (it does — the
  A6 suite runs every transport through it).
- `agents/*.agent.md` are empty Phase-0 stubs owned by A9; A8 must not fill them
  (docs/51 ownership), only freeze the format.
