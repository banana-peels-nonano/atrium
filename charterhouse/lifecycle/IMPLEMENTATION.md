# Lifecycle (S5) — IMPLEMENTATION
Owner: A4 Lifecycle Agent   Subsystem: S5   Source of truth: docs/42 (formal machine) + docs/15 (build card) + docs/40 §3 + docs/41 + Stress Test (docs/prd/4)

## 1. Responsibility (one paragraph)
S5 enforces the venture state machine — the complete docs/42 §3 transition table and
nothing more — plus all slot/WIP rules, factory-active-time clocks, the express
restriction, the pivot kill-and-fork recipe, and the evidence TTL. It is pure rule
enforcement over ledger facts. It MUST NOT: call an LLM or import
`router`/`memory`/`capabilities` (INV-DET); re-implement any S6 rule (tokens, classes,
budgets — it delegates to `Gov.authorize` via a port); produce or judge artifacts
(briefs, specs, evidence are appended by the acting subsystems — S5 only *reads* them as
guard facts); own durable state (the ledger is the only truth; slots and lineage are
projections, recomputed per call); or perform any real side effect beyond ledger appends.

## 2. Invariants enforced (verbatim from docs/42 §7 / docs/54 §S5)
- **INV-SM-1** — "only legal transitions execute; anything not listed is illegal and MUST
  be rejected + logged." Guaranteed by a single frozen `TRANSITIONS` table keyed
  `(from, to)`; a miss appends `error{kind:"illegal_transition"}` and raises
  `IllegalTransition`. There is no second dispatch path.
- **INV-SM-2** — "WIP: validating ≤3, SHAPING =1, building ≤1, HARVEST alumni ≤3."
  Guaranteed by `slots()` recomputed from `Registry.query` inside every guarded
  transition into a slot state (any `→VALIDATING/→SHAPING/→BUILDING`, and the HARVEST cap
  at `EARNING→GRADUATED` [alumni-capacity gate] and `SCALING→HARVEST`); breach raises
  `SlotLimitExceeded` before any append.
- **INV-SM-3** — "deadlines in factory-active time from `experiment_live_at`; `pause`
  freezes clocks." Guaranteed by the injectable `FactoryClock` (active-day counter that
  stops accumulating while paused; `pause`/`resume` are ledger events); `clock(v)`
  derives every deadline from `experiment_live_at` (experiment window) or
  `state_entered_at` in *active* days (state windows: SHAPING ≤10, BUILDING ≤15) — never
  wall-clock.
- **INV-SM-4** — "express-advance only for non-slot-consuming transitions." Guaranteed by
  an `express_ok` flag on each table row — true ONLY for LAUNCHED→EARNING (docs/42 §3);
  `transition(..., express=True)` on any other row raises `ExpressRefused` before auth.
- **INV-SM-5** — "pivot = kill-and-fork; one fork/lineage (ledger-checked); fork
  re-enters at FRAMED." Guaranteed by `pivot()` walking the full `forked_from` lineage in
  the ledger for a prior `pivot_fork` (memory is never consulted); the S4 replay
  once-per-lineage cap is the backstop. Same lineage walk gates `grant_omw`
  (R-OMW-LEDGER).
- **INV-SM-6** — "shovel-ready evidence past TTL requires re-confirmation before
  BUILDING." Guaranteed by `shovel_ready` stamping `evidence_ttl_at = now_active +
  evidence_ttl_days` (default 60); `PARKED_SHOVEL_READY→SHAPING` past that stamp raises
  `StaleEvidence` unless a fresh `evidence_gate` PASS (the re-confirmation signal) was
  appended after `evidence_ttl_at`; the `→VALIDATING` mini-re-validation row remains open.

## 3. Internal design (all deterministic; no LLM path exists in S5)
- `types.py` — `GuardResult/Result/SlotState/ActiveTime/PivotResult/LifecycleLimits` +
  the error taxonomy (`LifecycleError` base; `IllegalTransition`, `SlotLimitExceeded`,
  `GuardFailed`, `ExpressRefused`, `StaleEvidence`, `ForkCapExceeded`, `OmwExhausted`,
  `AuthorizationDenied`).
- `table.py` — the docs/42 §3 table **verbatim** as data: `(from, to) -> Rule{guards:
  tuple[guard-name], auth_scope: str | None, slot: SlotKind | None, express_ok: bool,
  event_type, gate_type}`. The table is the single source of legality; tests assert its
  row set 1:1 against docs/42 §3.
- `guards.py` — one pure function per named guard, `(facts) -> reason | None`, over a
  `Facts` bundle (venture, ledger stream for the venture, slots, clock, payload, reason).
  Objective guards read ledger events (API.md §Guard facts); judgment guards check
  non-empty `reason`.
- `slots.py` — `SlotState` from `Registry.query` counts; `free(kind)`.
- `clock.py` — `FactoryClock` (active-day accumulator with pause flag) + `ActiveTime`
  derivation.
- `pivot.py` — the §5 recipe (lineage walk, kill, fork, capture, FRAMED re-entry).
- `facade.py` — `Lifecycle` wiring the frozen surface; `transition()` order: legality →
  express check → guard evaluation (slots included) → Gov authorize → single append.
  Refusals append `error` then raise. State ownership: **none** — every answer is
  recomputed from ledger/registry/clock.

## 4. Dependencies (docs/43)
- **IF-1 (frozen, real):** `Ledger.append/read`, `Registry.get/query`,
  `contracts.events.Event/EventType`, `contracts.state.State/Venture`.
- **IF-3 (frozen, real):** `Gov.authorize(Action, Token) -> Decision` behind `GovPort`
  (protocol: `authorize` only — S5 never mints tokens or classifies).
- **Shared types (docs/43 §6):** `AuthClass`, `Token` from `contracts.authz`.
- No S3 Config dependency: the docs/42 §2/§4 limits are lifecycle-owned frozen defaults
  (`LifecycleLimits`), constructor-injectable for tests.

## 5. Failure behavior (every mode fail-closed; no guess/continue paths)
- Illegal `(from, to)` → `error` event + `IllegalTransition`; nothing else appended.
- `error` details mask long digit runs (token/event ids quoted in partner refusal
  reasons) before append, so a refusal log can never trip the Ledger's structural PII
  pre-check (docs/41 §4.4) and fail the logging itself.
- Pivot/OMW refusals append **nothing** (all-or-nothing seams, API.md): a refused pivot
  leaves the ledger byte-identical; only `transition`/`pause`/`resume` refusals log.
- Any guard failure (slot, fact, TTL, express, reason-missing) → `error` event + typed
  raise; the venture stays put (docs/42 §4 "reject + log. No exceptions.").
- Missing/denied/mis-scoped/expired token on a gate row → `AuthorizationDenied` carrying
  Gov's reason; token consumption follows Gov (denial does not consume).
- Ledger `ChainBroken`/append failure propagates — S5 never returns state derived from an
  unverified chain and never retries an append.
- `pivot` is refused whole on any step-0 check; the event sequence is only emitted after
  every check passes (kill-first ordering documented in RISKS R2).
- `can_transition` never mutates: a refused check is `GuardResult(ok=False, reasons=[...])`.

## 6. Open questions → RESOLVED
1. *How do guards learn business facts (quotes, spec, partners, metrics) when the frozen
   `transition(v, to, token?)` takes no facts argument?* → Facts are **ledger events**
   appended by the acting subsystems (docs/41 vocabulary); S5 reads them. Additive
   `payload` kwarg covers row-payload needs (docs/43 §7 no-bump). No stub facts object.
2. *Judgment guards ("duplicate", "can't fit after 2 cuts", "steady state", "sold",
   "partners silent") cannot be computed deterministically.* → Resolved per the gate
   model (docs/04): S5 enforces the deterministic envelope — RED gate token + non-empty
   `reason` — and the objective conjuncts; the judgment itself is the founder's, recorded
   in the event. Recommendation logic (score <14 ⇒ recommend kill) is Conductor/
   projection territory (INV-COND-1 kept clean).
3. *docs/42 §5 requires `pivot(v)`, OMW grants, and pause/resume, but docs/40 §3 freezes
   only four functions.* → Additive methods with a v1 note (A5 precedent: `Gov.grant`).
4. *Units of active time?* → Integer **active-days** (the unit every docs/42 §3/§4 bound
   uses; Stress-Test day numbering maps 1:1; envelope `active_time` field is int).
5. *`PARKED_SHOVEL_READY→VALIDATING` and `SHAPING→VALIDATING` are labeled "gate" without
   "slot", but both enter a slot state.* → INV-SM-2 says limits are **never** exceeded;
   slot checks apply on every entry into a slot state regardless of the Auth-column
   shorthand.
6. *What is the INV-SM-6 "re-confirmation signal"?* → A fresh `evidence_gate` PASS event
   appended after `evidence_ttl_at` (cheap signal, R-EVIDENCE-TTL), or the explicit
   `→VALIDATING` mini-re-validation row. Either satisfies docs/42 §3.
7. *Lineage cap scope: the S4 replay cap is keyed on `venture_id` (A3 RISKS accepted
   finding).* → S5 owns the true **lineage** rule: walk `forked_from` links and refuse a
   second `pivot_fork`/`omw_grant` anywhere in the chain; the S4 cap remains the
   per-venture backstop.
