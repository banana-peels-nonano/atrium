# Projections (S13) — TESTPLAN
Owner: A10 Conductor Agent   (written BEFORE implementation)

Real tmp-path Ledger seeded by appending events (the A3/A4 helper conventions); no
fakes beyond the ledger dir; purity proven by recomputation, INV mapping in
docstrings. Support shared with S12 in `tests/unit/_a10_support.py`.

## Unit tests (`tests/unit/test_projections.py`)
| Test | Asserts | Covers |
|---|---|---|
| `test_pipeline_board_from_replay` | a seeded multi-venture ledger renders every venture's id/codename/state/score, rows sorted by id | docs/41 §3 board |
| `test_metrics_single_pass_counts` | frames/kills/graduations/experiment pass-fail/llm cost/spend/sends counted exactly from seeded events | docs/41 §3 metrics |
| `test_purity_recompute_and_replay_identical` | every projection called twice → identical values; after `snapshot`+`restore` into a fresh dir → identical again | **INV-COND-3** (S13 half) |
| `test_projections_write_nothing` | ledger event count and on-disk bytes unchanged by any projection call | purity |
| `test_gate_brief_schema_and_critic` | a venture with an `artifact_produced{critic_tier}` yields the full fixed schema; `critic.tier` matches; every schema field populated | **INV-COND-2** |
| `test_gate_brief_refused_without_critic` | a venture with NO artifact/gate history → `NoCriticForGate`; an unknown venture → typed refusal naming it | **INV-COND-2** fail-closed |
| `test_gate_brief_critic_falls_back_to_gate_decision` | no artifact events but a prior `gate_decision{critic_tier}` → that tier used | §6.1 resolution |
| `test_daily_brief_triage_and_silence` | pending gates surface as ≤3 decisions; an empty/quiet ledger yields `decisions == ()` (silence valid, INV-TRIAGE) | docs/05 |
| `test_killday_every_active_venture` | every non-terminal venture appears exactly once — briefed or in `unbriefable` (never dropped) | docs/05 kill-day |
| `test_recommendation_mechanics` | FAIL verdict → KILL; all-PASS forward facts → ADVANCE; mixed → HOLD (advisory fold, deterministic) | §6.2 |
| `test_calibration_overrides_vs_outcomes` | seeded `override`/`score_override` events pair with terminal outcomes; evidence verdicts pair with kill/graduate | docs/41 §3 |

## Integration
Covered by `tests/integration/test_conductor_stack.py::test_it_projections_reflect_the_run`
(the full dry-run's ledger rendered by all six functions — conductor/TESTPLAN.md).

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| INV-COND-2 schema + critic mandatory | `test_gate_brief_schema_and_critic`, `test_gate_brief_refused_without_critic`, fallback test | unit |
| INV-COND-3 pure/regenerable | `test_purity_recompute_and_replay_identical`, `test_projections_write_nothing` | unit |
| docs/41 §3 shapes | board/metrics/calibration tests | unit |
| docs/05 triage + kill-day + silence | `test_daily_brief_triage_and_silence`, `test_killday_every_active_venture` | unit |

## Fixtures/fakes needed
tmp-path real Ledger only, seeded via the `_a3/_a4` append helpers + `_a10_support`
extensions (artifact_produced/gate_decision/override seeders). No provider, no
embedder, no network (INV-TEST-SAFE trivially).

## Out of scope (test-safety)
Nothing here acts — S13 is read-only by contract; the write-nothing test enforces it.
