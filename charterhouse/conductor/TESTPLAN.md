# Conductor (S12) — TESTPLAN
Owner: A10 Conductor Agent   (written BEFORE implementation)

Conventions per the merged suites: the FULLY LIVE stack (real Config/Ledger/Registry/
Lifecycle/Gov/Security/Router/Memory/Workflow — no stubs; A11 `FakeProvider` is every
transport, `FakeEmbedder` behind Memory — **no network anywhere**, INV-TEST-SAFE),
typed fail-closed errors via `pytest.raises`, INV mapping in docstrings, founder tokens
minted only at the Gov boundary (`gov.grant`). Support in `tests/unit/_a10_support.py`.

## Unit tests (`tests/unit/test_conductor.py`)
| Test | Asserts | Covers |
|---|---|---|
| `test_pipeline_classify_guard_act_append` | one `capture` command walks all five steps: classified GREEN (spy sees S6), acted, ONE `capture` event appended, projections reflect it on next read | the docs/10 pipeline |
| `test_call_through_no_local_rules` (static) | `conductor/` contains no classify matrix, no transition-legality data, no `AuthClass(` construction, no PII `re.compile` — the rules live with their owners | **INV-COND-1** (static) |
| `test_call_path_transits_owners` (spies) | `admit` with a token: the decision provably transits S5 (`transition` spy) and S6 (`authorize` spy, called ONCE — single consumption at the owner); `send.stage`: S6 `authorize` spy hit; the conductor added no decision of its own (denial reasons are owner text verbatim) | **INV-COND-1** (call-path) |
| `test_red_without_token_refused_by_owner` | `admit`/`kill`/`gate`/`graduate` without a token → `CommandRefused` whose reason is S5/S6's own text; ledger untouched | INV-GOV-1 pass-through |
| `test_unknown_command_refused` | `command("made.up")` → RED classify + S6 denial → `CommandRefused`; nothing appended | fail closed |
| `test_single_use_token_consumed_once` | a granted `admit` token: the command succeeds; replaying the SAME token on a second `admit` → refused by S6 (already consumed) — proving exactly-once consumption at the owner | §6.1 resolution |
| `test_two_key_commands_demand_check` | `deploy.prod`/`billing.enable` with a token but no passing `CheckResult` → refused (S6 INV-GOV-2 text); with token+check → event appended carrying the token id; **no other side effect exists** | two-key + INV-TEST-SAFE |
| `test_send_stage_records_batch_under_budget` | authorized `send.stage{count}` appends `send_batch` with the token id; an over-budget batch is refused by S6's budget text | INV-GOV-5 pass-through |
| `test_salvage_requires_asset_types` | `salvage` with empty `asset_types` → `CommandRefused` naming the field (docs/41 shape); with `["anti_pattern"]` → appended | R-SALVAGE-TYPES shape |
| `test_workflow_commands_run_s10` | `shape` (SHAPING) / `build` (BUILDING) run the real Workflow: `artifact_produced` appended (state-neutral, critic_tier in payload), artifact in the vault | §6.3/§6.4 + IF-5 |
| `test_consolidate_calls_s9` | `consolidate` → S9's pass + its ONE `consolidate` event | call-through |
| `test_gate_requires_critic_take` | `gate` on a venture with NO artifact/critique history → `NoCriticForGate`; nothing appended, state unchanged | **INV-COND-2** |
| `test_gate_appends_decision_with_critic_tier` | a full `gate(ADVANCE)` on a briefed venture: S5's transition event + ONE `gate_decision{brief_ref, recommendation, decision, critic_tier}` | **INV-COND-2** + docs/41 |
| `test_gate_spec_approval_path` | `gate(ADVANCE→BUILDING, spec_ref)` appends `spec_approved` under the SAME token id then transitions (guard satisfied); the token was consumed exactly once | §6.2 resolution |
| `test_crash_mid_command_zero_loss` | run a sequence; construct a FRESH Conductor over the same ledger dir → identical replay/projections; a probe killing the `gate_decision` recorder append after a successful transition → the transition survives, replay clean, re-issuable | **INV-COND-3** |
| `test_conductor_holds_no_durable_state` (static+behavioral) | no mutable attribute is written by handlers after `__init__` (dispatch is stateless); two interleaved Conductors over one ledger see identical truth | **INV-COND-3** |
| `test_projection_commands_pure_reads` | `pipeline`/`brief`/`killday`/`gatebrief`/`calibrate` append NOTHING and return schema-shaped data | INV-COND-3 + S13 purity |

## Integration tests (`tests/integration/test_conductor_stack.py`)
| Test | Scenario | Expected |
|---|---|---|
| `test_it_full_venture_dry_run_capture_to_graduate` | the docs/10 DoD: capture → frame → admit(tok) → evidence PASS → experiment live+result PASS → gate ADVANCE→SHAPING(tok) → shape (S10 workflow) → gate ADVANCE→BUILDING(tok, spec_ref) → build (workflow) → recruit.partners → gate ADVANCE→LAUNCHED(tok) → activation result PASS → gate ADVANCE→EARNING(tok) → traction PASS → graduate(tok) — every RED point halts first WITHOUT a token (refused, zero effect) then passes WITH one; deploy.prod/billing.enable/launch each authorized with two-key/token and recorded | the venture reaches GRADUATED on the live registry; **zero real spend/send/deploy** (nothing but ledger appends + tmp vault files exist — INV-TEST-SAFE); every gate carried a critic take |
| `test_it_projections_reflect_the_run` | after the dry run: `pipeline` shows the venture's state history end-state; `metrics` counts the kills/frames/llm_calls/spend; `brief` triages (silence-valid when nothing pending); `killday` renders every active venture as a GateBrief; `calibration` shows overrides-vs-outcomes | S13 purity + docs/05 shapes |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| INV-COND-1 call-through only | `test_call_through_no_local_rules`, `test_call_path_transits_owners`, `test_red_without_token_refused_by_owner`, `test_single_use_token_consumed_once` | unit |
| INV-COND-2 gate brief schema + critic | `test_gate_requires_critic_take`, `test_gate_appends_decision_with_critic_tier`, S13 suite's schema tests | unit |
| INV-COND-3 crash → replay, zero loss | `test_crash_mid_command_zero_loss`, `test_conductor_holds_no_durable_state`, `test_projection_commands_pure_reads` | unit |
| docs/10 pipeline per command | `test_pipeline_classify_guard_act_append` + per-command tests | unit |
| No effect without correct-class token | `test_red_without_token_refused_by_owner`, `test_two_key_commands_demand_check`, e2e RED halts | unit + integration |
| docs/10 DoD full dry-run | `test_it_full_venture_dry_run_capture_to_graduate` | integration |
| INV-TEST-SAFE | the dry run's zero-real-effect assert + v1's no-transport code fact | integration |

## Fixtures/fakes needed
A11 `FakeProvider` (all transports), `FakeEmbedder` (memory), tmp-path real everything
else; `_a10_support.make_factory(tmp_path)` wiring the WHOLE live stack + a founder
helper minting tokens via `gov.grant`; spy wrappers (call-counting, delegating) for
S5/S6 facades; the `FailingAppendLedger` probe (A7 pattern) for the mid-command crash.

## Out of scope (test-safety, INV-TEST-SAFE)
No real spend, send, deploy, or charge — v1 has no transport/pipeline code at all;
RED/two-key commands stop at the recorded, token-carrying event. Live model calls are
FakeProvider everywhere. The docs/55 §3 Stress-Test A/B/C reproduction stays owned by
the A11 simulator suite (already green); this suite adds the conductor-driven path.
