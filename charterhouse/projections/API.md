# Projections (S13) — API
Owner: A10 Conductor Agent   ·   Matches docs/40 §9 exactly (frozen seam)   ·   All pure functions of the ledger — deterministic, regenerable, never a source of truth (INV-COND-3)

## Exposed surface
Every function takes the live `Ledger` (IF-1), reads events fresh, and returns a
frozen dataclass. **No cache, no module state, no writes, no LLM** — calling twice, or
after a snapshot/restore, yields the identical value (purity is tested, not asserted).

### `Projections.pipeline(ledger) -> Board`
- The PIPELINE board (docs/41 §3): every venture from replay — id, codename, state,
  score, active-time entered, deadline flags (evidence TTL, shaping window) — rows
  sorted by venture id (deterministic).

### `Projections.metrics(ledger) -> Metrics`
- Counts/rates over the event stream (docs/41 §3): ventures by state, frames, kills,
  graduations, experiment pass/fail, `llm_call` cost totals, spend totals vs
  envelopes, sends by day. Pure fold; no wall clock.

### `Projections.daily_brief(ledger, day?) -> DailyBrief`
- The docs/05 triaged brief: the 2–3 decisions needing a human (ventures whose gates
  are ready per ledger facts), the RED queue (recorded-but-unactioned authorization
  points), pending send batches, and a board glance. **Silence is a valid, correct
  output** (INV-TRIAGE): an empty decisions tuple when nothing needs the founder.

### `Projections.gate_brief(ledger, venture_id) -> GateBrief`
- **The fixed schema (INV-COND-2), by construction:**
  `GateBrief{venture_id, codename, state, score, active_in_state, evidence,
  artifacts, critic: CriticTake, recommendation}` — `critic` is a REQUIRED
  `CriticTake{tier, artifact_ref}` drawn from the venture's latest
  `artifact_produced`/`gate_decision`; **assembly raises `NoCriticForGate` when no
  critic take exists** — no gate is presentable without one. `recommendation` is the
  mechanical ADVANCE/HOLD/KILL advisory derived from ledger facts only (evidence
  verdicts, windows) — the founder's decision is the authority.

### `Projections.killday_brief(ledger) -> KillDayBrief`
- Every ACTIVE venture (docs/05: kill-day walks the whole factory) as a GateBrief +
  its mechanical recommendation; ventures with no critic take yet are listed in a
  separate `unbriefable` tuple (named, never silently dropped — fail loud, and the
  gate command will refuse them anyway).

### `Projections.calibration(ledger) -> CalibrationReport`
- Overrides vs outcomes (docs/41 §3): every `override`/`score_override` event paired
  with its venture's terminal outcome so far, plus evidence-gate verdicts vs
  subsequent kill/graduate — the founder's judgment audit (docs/05 monthly report).

## Public value types
`Board{rows: tuple[BoardRow, ...]}` · `BoardRow{venture_id, codename, state, score,
state_entered_at, flags}` · `Metrics{by_state, frames, kills, graduations,
experiments_pass, experiments_fail, llm_cost_usd, spend_usd, sends_by_day}` ·
`DailyBrief{decisions, red_queue, pending_sends, board}` · `CriticTake{tier,
artifact_ref}` · `GateBrief{venture_id, codename, state, score, active_in_state,
evidence, artifacts, critic, recommendation}` · `KillDayBrief{rows:
tuple[(GateBrief, recommendation)], unbriefable}` · `CalibrationReport{overrides,
evidence_vs_outcome}` · error `NoCriticForGate` (shared with S12 — one INV-COND-2
refusal type).

## Consumed surface
- **Ledger (S4, IF-1, real):** `read(EventFilter?)` + `replay()` — the ONLY input.
  Nothing else: no Config, no clock (time comes from event `active_time` fields), no
  env, no LLM, no writes.

## Interface stability
- **Frozen (docs/40 §9):** the six function signatures + the `GateBrief` schema
  (INV-COND-2) + purity semantics. Breaking change = ICR (docs/43 §4).
- **Additive v1 notes (docs/43 §7):** extra fields on `Metrics`/`BoardRow.flags`;
  richer `evidence`/`artifacts` detail on `GateBrief`.
- **Internal/free to change:** fold implementations, recommendation heuristics
  (advisory), row ordering beyond the documented sorts.
