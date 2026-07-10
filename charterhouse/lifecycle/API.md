# Lifecycle (S5) — API
Owner: A4 Lifecycle Agent   ·   Matches docs/40 §3 exactly (frozen seam)   ·   This doc is **interface-freeze IF-4** (docs/43 §3: "Lifecycle transition API + `42` invariants") — frozen so S10 Capability Framework and S12 Conductor can build against it

## Exposed surface

### `Lifecycle.can_transition(v: Venture, to: State) -> GuardResult`
- **Preconditions:** `v` is a projected `Venture` (Registry record); `to` is a `State`.
- **Postconditions:** returns `GuardResult{ok, reasons[], needs_auth: AuthClass}` — a pure
  *check*, evaluating the full docs/42 §3 guard column for `(v.state, to)`: legality
  (INV-SM-1), slot/WIP headroom (INV-SM-2), ledger-fact guards (sub-gates, score, spec,
  partners, salvage — §"Guard facts" below), evidence TTL (INV-SM-6), and lineage caps
  (INV-SM-5). `needs_auth` is `RED` for gate rows, `GREEN` for internal rows (docs/42 §3
  Auth column). An illegal `(from, to)` returns `ok=False` with the legality reason —
  `can_transition` never raises on business grounds and never logs.
- **Errors:** none on business grounds (`ChainBroken` from a corrupt ledger propagates —
  fail closed). **Side effects:** none. **Determinism:** deterministic (ledger read +
  injected clock). **Auth class:** n/a (a check).

### `Lifecycle.transition(v: Venture, to: State, token: Token | None = None, *, express: bool = False, reason: str | None = None, payload: dict | None = None) -> Result`
- **Preconditions:** guard facts already in the ledger (appended by the acting
  subsystems/Conductor); for gate rows, `token` is a Gov grant scoped to the transition's
  action name (§"Auth scopes" below).
- **Postconditions:** re-evaluates the full guard (never trusts a prior `can_transition`),
  delegates token validation to Gov (`authorize`, IF-3 — S5 re-implements **no** S6 rule),
  enforces the express restriction (INV-SM-4: `express=True` only on rows marked
  Express=yes — exactly LAUNCHED→EARNING), then appends **one** state-changing event
  (§"Event mapping") with `from_state`/`to_state`/`active_time` stamped and the consumed
  token id as `authorization`. Returns `Result{ok=True, event_id, from_state, to_state}`.
- **Errors (fail closed — refusal appends an `error` event, then raises; venture state
  unchanged):** `IllegalTransition` for a `(from, to)` not in docs/42 §3 (INV-SM-1
  reject+log); `SlotLimitExceeded` (INV-SM-2); `GuardFailed` (a legal row whose guard
  fails, incl. missing `reason` on judgment-guard rows); `ExpressRefused` (INV-SM-4);
  `StaleEvidence` (INV-SM-6); `ForkCapExceeded` (INV-SM-5); `AuthorizationDenied`
  (Gov denial or missing token on a gate row — the Gov `Decision.reason` is carried).
- **Side effects:** exactly one ledger append on success; exactly one `error` append on
  refusal. **Determinism:** deterministic. **Auth class:** per row — gate rows are RED
  (token consumed by Gov), internal rows GREEN (autonomous, logged).
- **Additive kwargs note (docs/43 §7, no-bump):** `express`/`reason`/`payload` extend the
  frozen `transition(v, to, token?)` positional shape without altering it. `payload`
  carries row-specific event payload (e.g. FRAMED requires `{brief_ref, score, quotes}`).

### `Lifecycle.slots() -> SlotState`
- **Postconditions:** current WIP counts vs frozen limits, computed fresh from
  `Registry.query` (never cached): `SlotState{validating: (n,3), shaping: (n,1),
  building: (n,1), harvest: (n,3)}` plus `free(kind)` helpers. Pure projection read.
- **Errors:** `ChainBroken` propagates. **Side effects:** none. **Determinism:** deterministic.

### `Lifecycle.clock(v: Venture) -> ActiveTime`
- **Postconditions:** `ActiveTime{now_active, experiment_live_at, elapsed_experiment,
  elapsed_in_state, deadline_at, remaining, paused}` — all in **factory-active days**
  (INV-SM-3): deadlines run from `experiment_live_at` (never wall-clock, never state
  entry); state-window guards (SHAPING ≤10, BUILDING ≤15) run in active days from
  `state_entered_at` (which replay stamps in active time). While the factory is paused,
  `now_active` does not advance — deadlines freeze.
- **Errors:** none. **Side effects:** none. **Determinism:** deterministic (injected
  `FactoryClock`).

### `Lifecycle.pivot(v: Venture, token: Token | None, *, new_id: str, codename: str, inherited: dict, reason: str) -> PivotResult`  *(additive, v1 note below)*
- **Preconditions:** `v.state` ∈ {LAUNCHED, EARNING} (the docs/42 §3 pivot rows); `token`
  scoped `pivot`; `inherited` names the audience/segment refs that transfer (never the
  dead value prop); `new_id` unused.
- **Postconditions (docs/42 §5, INV-SM-5 — the kill-and-fork recipe, in order):**
  (1) lineage fork-cap check — walks the `forked_from` chain in the ledger; any existing
  `pivot_fork` anywhere in the lineage → `ForkCapExceeded`, nothing appended;
  (2) `kill{reason}` on `v` (its slots free by projection);
  (3) `pivot_fork{killed_id, new_id, inherited}`;
  (4) `capture` of the fork with `forked_from=v.id`;
  (5) the fork enters **FRAMED** for re-scoring (internal re-entry event; it joins the
  ranked backlog — it does NOT jump the queue, consume a slot, or inherit state).
  Returns `PivotResult{killed_id, new_id, events[]}`.
- **Errors (fail closed):** `ForkCapExceeded`, `IllegalTransition` (pivot from a non-pivot
  state), `AuthorizationDenied`. On any refusal nothing is appended.
- **Side effects:** the 4-event sequence above. **Determinism:** deterministic.
  **Auth class:** RED (`pivot`).

### `Lifecycle.grant_omw(v: Venture, token: Token | None) -> event_id`  *(additive, v1 note below)*
- **Preconditions:** `token` scoped `gate` (OMW is granted at the Friday kill gate).
- **Postconditions:** appends `omw_grant{}` for `v` — first-class ledger event
  (R-OMW-LEDGER). Refused (`OmwExhausted`) if any venture in `v`'s **lineage** already
  holds one — checked against the ledger, never memory; the S4 replay cap is the
  per-venture backstop.
- **Errors (fail closed):** `OmwExhausted`, `AuthorizationDenied`; nothing appended.
- **Side effects:** one append. **Determinism:** deterministic. **Auth class:** RED gate.

### `Lifecycle.pause(reason: str) -> event_id` / `Lifecycle.resume(reason: str) -> event_id`  *(additive, v1 note below)*
- **Postconditions:** freezes/restarts factory-active-time accumulation (INV-SM-3) on the
  injected `FactoryClock` and appends the factory-global `pause`/`resume` event
  (`venture_id=None`). Idempotent (pausing a paused factory is a no-op event-wise —
  refused with `GuardFailed` to keep the ledger honest).
- **Side effects:** one append. **Determinism:** deterministic. **Auth class:** GREEN
  (docs/40 §8 matrix).

## Auth scopes (gate rows → Gov action names, docs/40 §8 vocabulary)
`→VALIDATING` = `admit` · `→KILLED` = `kill` · `EARNING→GRADUATED` = `graduate` ·
pivot = `pivot` · LAUNCHED→EARNING with `express=True` = `advance.express` ·
every other gate row = `gate`. Internal rows (FRAMED→PARKED, VALIDATING→PARKED_SHOVEL_READY,
PARKED→ARCHIVED, KILLED→ARCHIVED, CAPTURED→FRAMED) need no token.

## Guard facts (ledger event vocabulary consumed by guards)
Objective guards are evaluated **only** from the venture's ledger stream + projection +
clock: `frame`/`score_override` (score ≥18 / ≥14 bars; admission override = an `override`
event with `decision="admit"`), `evidence_gate` verdict PASS + `experiment_result` verdict
PASS (the two VALIDATING sub-gates), `spec_approved` (SHAPING→BUILDING), `partners`
recruited_count ≥5 (BUILDING→LAUNCHED), `experiment_result` PASS with metric `activation`
(LAUNCHED→EARNING) / `mrr`|`payers` within 60 active-days of EARNING entry
(EARNING→GRADUATED), `salvage` with ≥1 asset type (KILLED→ARCHIVED), `evidence_gate` PASS
newer than `evidence_ttl_at` (the INV-SM-6 re-confirmation signal). Judgment disjunctions
in docs/42 §3 (duplicate/dead-pattern, "can't fit after 2 cuts", "partners silent",
"steady state", "sold") are founder-gate judgments: S5 deterministically enforces the RED
gate token + a non-empty `reason`; recommending them is Conductor/projection territory.

## Event mapping (the one state-changing append per transition)
CAPTURED→FRAMED = `frame` (payload requires `brief_ref`, `score`, `quotes ≥2`) ·
`→VALIDATING` = `admit{slot:"validating"}` · FRAMED→PARKED = `park` ·
VALIDATING→PARKED_SHOVEL_READY = `shovel_ready{evidence_ttl_at}` (stamped now+TTL) ·
`→KILLED` = `kill{reason}` · EARNING→GRADUATED = `graduate` · alumni rows =
`alumni_transition{to}` · everything else = `transition{reason, gate_type:
"weekly"|"express"|"internal"}`. All carry `from_state`/`to_state`/`active_time`.

## Public value types
`GuardResult{ok, reasons[], needs_auth: AuthClass}` · `Result{ok, event_id, from_state,
to_state}` · `SlotState{validating, shaping, building, harvest: (count, limit)}` ·
`ActiveTime{now_active, experiment_live_at, elapsed_experiment, elapsed_in_state,
deadline_at, remaining, paused}` · `PivotResult{killed_id, new_id, events}` ·
`LifecycleLimits{validating_wip=3, shaping_wip=1, building_wip=1, harvest_cap=3,
evidence_ttl_days=60, shaping_max_days=10, building_max_days=15,
validating_window_days=14}` (frozen defaults from docs/42 §2/§4 + Stress Test).
Shared (docs/43 §6, `charterhouse/contracts/`): `State`, `Venture`, `AuthClass`, `Token`.

## Consumed surface
- **Ledger (S4, IF-1):** `append(event) -> event_id` (failure propagates — no partial S5
  state); `read(EventFilter) -> Iter[Event]` (guard facts; `ChainBroken` fail-closed);
  replay-checked once-per-lineage caps back up INV-SM-5.
- **Registry (S4, IF-1):** `get(venture_id)`, `query(state?)` — slot counts and lineage
  walks; projection only, never cached in S5.
- **Governance (S6, IF-3):** `Gov.authorize(Action, Token) -> Decision` via a `GovPort`
  protocol — the **only** token-validation path (no S6 rule re-implemented in S5). The
  real merged Gov is used in tests.
- **FactoryClock (S5-owned, injectable):** active-day counter with `pause`/`resume`;
  deterministic in tests (docs/55 §2 "Clock").

## Interface stability
- **Frozen (IF-4, this doc):** `can_transition/transition/slots/clock` signatures per
  docs/40 §3, the `GuardResult/Result/SlotState/ActiveTime` shapes, the docs/42 §3
  transition table + §2 WIP limits + §4 guard rules + §5 pivot semantics (INV-SM-1..6).
  Breaking change = ICR (docs/43 §4).
- **Additive v1 note (docs/43 §7, no-bump):** `pivot`, `grant_omw`, `pause`/`resume`, and
  the `express`/`reason`/`payload` kwargs extend docs/40 §3 (which defines no pivot/OMW/
  pause seam despite docs/42 §5 requiring them). No frozen signature altered.
- **Internal/free to change:** guard-function decomposition, table representation,
  module layout, `FactoryClock` internals.
