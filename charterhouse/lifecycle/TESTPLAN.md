# Lifecycle (S5) — TESTPLAN
Owner: A4 Lifecycle Agent   (written BEFORE implementation)

Conventions per the A3/A5 suites: real tmp-path Ledger + Registry + merged Gov (no fakes
for merged subsystems), injected deterministic `FactoryClock`, typed fail-closed errors
via `pytest.raises`, INV mapping in every test docstring, seeded-`parametrize` property
tests against an independent oracle (no hypothesis). Support in `tests/unit/_a4_support.py`.

## Unit tests (`tests/unit/test_lifecycle.py`)
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_table_matches_docs42_verbatim` | the implemented `TRANSITIONS` row set equals the docs/42 §3 table exactly — same (from,to) pairs, same auth kind (gate/internal), same express marking; no extra rows | none (pure) | **INV-SM-1** (table fidelity) |
| `test_full_matrix_legal_vs_illegal` | for **all 15×15 (from,to) pairs**: legal rows pass `can_transition` legality (guards may still refuse for other reasons); every pair NOT in §3 → `can_transition.ok=False` AND `transition` raises `IllegalTransition` AND appends `error{kind:"illegal_transition"}` (reject+log) | real ledger/registry/gov, clock | **INV-SM-1** |
| `test_illegal_reject_leaves_state_unchanged` | after a rejected transition the venture's projected state, `slots()`, and event count (bar the `error` event) are unchanged | real stack | INV-SM-1 fail-closed |
| `test_validating_wip_le_3` | 3 ventures admitted to VALIDATING ok; the 4th admission → `SlotLimitExceeded`, overflow path FRAMED→PARKED works | real stack | **INV-SM-2** |
| `test_shaping_wip_eq_1` | one venture in SHAPING; a second VALIDATING pass → `→SHAPING` refused, `→PARKED_SHOVEL_READY` succeeds and stamps `evidence_ttl_at = now+60` | real stack | **INV-SM-2** (R-SHAPING-WIP) |
| `test_building_wip_le_1` | BUILDING occupied → second `SHAPING→BUILDING` → `SlotLimitExceeded` | real stack | **INV-SM-2** |
| `test_harvest_alumni_cap_le_3` | 3 HARVEST alumni → a 4th `EARNING→GRADUATED` refused (alumni-capacity gate) AND a 4th `SCALING→HARVEST` refused | real stack | **INV-SM-2** (R-ALUMNI-CEILING) |
| `test_slots_projection_matches_registry` | `slots()` counts equal `Registry.query` counts per slot state, before and after transitions (never cached) | real stack | INV-SM-2 |
| `test_deadline_from_experiment_live_not_entry` | admit day 3, `experiment_live` day 8 → `clock(v).deadline_at == 8+14`, not `3+14` (R-CLOCK) | clock | **INV-SM-3** |
| `test_pause_freezes_active_time` | advance 2 days, `pause()`, advance 5 wall-days, `resume()` → `now_active` grew 0 during pause; deadline/remaining unchanged across the pause; `pause`/`resume` events appended (R-ACTIVE-TIME) | clock | **INV-SM-3** |
| `test_state_windows_in_active_days` | SHAPING >10 active-days → `SHAPING→BUILDING` guard refuses; a pause inside the window does not consume it | real stack, clock | INV-SM-3 |
| `test_express_only_launched_to_earning` | `express=True` on LAUNCHED→EARNING (facts in place, `advance.express` token) → ok; `express=True` on every slot-consuming row (→VALIDATING, →SHAPING, →BUILDING, →GRADUATED) → `ExpressRefused` before any token consumption (R-SLOT-GATE) | real stack | **INV-SM-4** |
| `test_pivot_kill_and_fork` | `pivot(v)` from LAUNCHED: v→KILLED, `pivot_fork{killed_id,new_id,inherited}` + `capture{forked_from}` appended, fork projected at FRAMED, v's slots freed, fork consumes no slot (R-PIVOT) | real stack | **INV-SM-5** |
| `test_second_fork_in_lineage_refused` | pivoting the fork (or any lineage member) → `ForkCapExceeded`, **nothing appended** — checked via ledger lineage walk on a fresh `Lifecycle` instance (never memory) | real stack | **INV-SM-5** |
| `test_omw_once_per_lineage` | `grant_omw` ok once; second grant on the same venture AND on its fork → `OmwExhausted`, ledger-checked across restart (R-OMW-LEDGER) | real stack | INV-SM-5/OMW |
| `test_ttl_stale_shovel_ready_blocked` | shovel-ready venture waits past `evidence_ttl_at` → `→SHAPING` raises `StaleEvidence`; fresh `evidence_gate` PASS after the stamp (re-confirmation) → `→SHAPING` ok; the `→VALIDATING` mini-re-validation row also open (R-EVIDENCE-TTL) | real stack, clock | **INV-SM-6** |
| `test_gate_rows_require_valid_token` | a gate transition with `token=None` / wrong scope / reused token → `AuthorizationDenied` (Gov's reason carried), nothing state-changing appended; valid scoped grant → ok with `authorization` stamped on the event | real Gov | gate auth (IF-3 delegation) |
| `test_internal_rows_need_no_token` | FRAMED→PARKED, VALIDATING→PARKED_SHOVEL_READY, KILLED→ARCHIVED execute with `token=None` | real stack | Auth column fidelity |
| `test_guard_facts_from_ledger` | FRAMED→VALIDATING refused at score 17 (no override), ok after `record_override(decision="admit")`; VALIDATING→SHAPING refused until BOTH `evidence_gate` PASS and `experiment_result` PASS exist (R-EVIDENCE-GATE); SHAPING→BUILDING refused without `spec_approved`; BUILDING→LAUNCHED refused without `partners ≥5`; KILLED→ARCHIVED refused without `salvage ≥1 asset` (R-SALVAGE-TYPES) | real stack | guard-fact matrix |
| `test_judgment_kill_requires_reason` | `→KILLED` at a gate with a token but empty/missing `reason` → `GuardFailed`; with reason → ok, `kill{reason}` appended | real stack | guard rules §4 |
| `test_property_random_walks_never_violate` (property, `seed` in `range(30)`) | seeded random op scripts (admits, advances, parks, kills, pivots, OMWs, pauses, clock jumps across ≥4 ventures): after every op the engine's accept/reject matches an **independent oracle** (own table + slot/fork bookkeeping, never S5 internals); projected states always ∈ legal set; WIP limits never exceeded; ≤1 fork+OMW per lineage | real stack, oracle | INV-SM-1/2/4/5 (property) |
| `test_property_replay_equals_projection` (property, same seeds) | after each script, a **fresh** `Lifecycle`+`Registry` over the same ledger dir projects identical states/slots (no hidden S5 state; INV-LEDGER inherited) | real stack | ledger-as-truth |

## Integration tests (`tests/integration/test_lifecycle_sim.py`) — the docs/55 §3 simulator
Deterministic driver (`_a4_support.Simulator`) over real Ledger+Registry+Gov+Lifecycle,
asserting end states, key events, and invariant side-conditions:
| Test | Scenario (docs/prd/4) | Expected end state |
|---|---|---|
| `test_sim_a_battlecard_happy_path` | Stress-Test A: capture→frame(20)→admit→experiment live→both sub-gates PASS→SHAPING→spec+partners→BUILDING→LAUNCHED→**express**→EARNING→GRADUATED→SCALING→HARVEST | `battlecard` ∈ HARVEST; express only on LAUNCHED→EARNING; alumni cap respected |
| `test_sim_b_hvac_route_messy_death` | Stress-Test B: frame(17)→admission override (logged)→admit→domain delay→live day 8 (deadline from live, not entry)→experiment FAIL→OMW grant→FAIL again→KILL→salvage(anti-pattern)→ARCHIVED; second OMW refused | `hvac-route` = ARCHIVED; exactly one `omw_grant`; override event present |
| `test_sim_c_clipscribe_pivot_concurrency` | Stress-Test C: build slot held by `battlecard`; `clipscribe` passes validation→SHAPING (WIP 1); third venture passes→PARKED_SHOVEL_READY+TTL; slot frees→`clipscribe` BUILDING→LAUNCHED→misses bar→**pivot** (kill-and-fork, fork at FRAMED, inherits audience, no queue jump); second pivot refused; stale shovel-ready venture blocked until re-confirmation | `clipscribe` = KILLED; fork = FRAMED with `forked_from`; parked venture blocked stale / admitted after re-confirm |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| INV-SM-1 legality (full matrix, reject+log) | `test_table_matches_docs42_verbatim`, `test_full_matrix_legal_vs_illegal`, `test_illegal_reject_leaves_state_unchanged`, property | unit |
| INV-SM-2 WIP/slots | `test_validating_wip_le_3`, `test_shaping_wip_eq_1`, `test_building_wip_le_1`, `test_harvest_alumni_cap_le_3`, `test_slots_projection_matches_registry`, property | unit |
| INV-SM-3 active-time clocks | `test_deadline_from_experiment_live_not_entry`, `test_pause_freezes_active_time`, `test_state_windows_in_active_days`, sim B | unit + integration |
| INV-SM-4 express restriction | `test_express_only_launched_to_earning`, sim A, property | unit + integration |
| INV-SM-5 pivot/OMW lineage caps | `test_pivot_kill_and_fork`, `test_second_fork_in_lineage_refused`, `test_omw_once_per_lineage`, sim B/C, property | unit + integration |
| INV-SM-6 evidence TTL | `test_ttl_stale_shovel_ready_blocked`, sim C | unit + integration |
| Gate auth via IF-3 (no S6 re-implementation) | `test_gate_rows_require_valid_token`, `test_internal_rows_need_no_token` | unit |
| Guard-fact fidelity (R-EVIDENCE-GATE etc.) | `test_guard_facts_from_ledger`, `test_judgment_kill_requires_reason` | unit |
| Ledger-as-truth (INV-LEDGER inherited) | `test_property_replay_equals_projection` | unit |
| Stress-Test A/B/C reproduce (docs/54 phase-exit row) | the three `test_sim_*` | integration |

## Fixtures/fakes needed (A4-local until the A11 harness lands)
- **FactoryClock** (`_a4_support`) — the docs/55 §2 injectable active-time clock
  (S5-owned type; the test module drives it).
- **tmp-path real Ledger + Registry + Gov** — merged S4/S6 implementations (A3/A5
  convention: no fakes for merged subsystems); Gov takes the A5 `FakeConfig` budgets
  stub until A2 lands.
- **Fact helpers** (`_a4_support`) — acting-subsystem event builders (`evidence_pass`,
  `experiment_result`, `spec_approved`, `partners`, `salvage`, `experiment_live`) —
  what S12/S10 will append in production.
- **LifecycleOracle + seeded script generator** (`_a4_support`) — the property tests'
  independent re-derivation of legality/slots/caps (never calls S5 internals).
- **Simulator** (`_a4_support`) — the docs/55 §3 deterministic driver (S5-scope slice:
  states/slots/clocks/pivot; capability beats arrive with S10).

## Out of scope (test-safety, INV-TEST-SAFE)
No real spend/send/deploy/charge anywhere: gate tokens are minted with `Gov.grant` (the
authorization boundary), experiments/launches exist only as ledger fact events. S5 has no
network, no LLM, no side-effect surface beyond ledger appends.
