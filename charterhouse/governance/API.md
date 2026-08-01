# Governance (S6) — API
Owner: A5 Governance/Security Agent   ·   Matches docs/40 §4 exactly (frozen seam)   ·   Part of **interface-freeze IF-3** (with Security S7, docs/52 §12 / docs/43 §3)

## Exposed surface

### `Gov.classify(action: Action) -> AuthClass`
- **Preconditions:** none (total function).
- **Postconditions:** returns the frozen class per the docs/14 matrix: `AuthClass(color, two_key)`.
  *(Additive name, 2026-07-31: `advise` is YELLOW — it meters model spend like `build`, but it
  is an AI opinion, not a founder decision: it moves no venture and crosses no gate, so the RED
  set is unchanged. Adding a name to the matrix is additive per docs/43 §7; removing or
  reclassifying one is an ICR.)*
  Two-key: `deploy.prod`, `billing.enable`, and `send.stage` with `params["count"] >
  SCALED_SEND_THRESHOLD`. An **unknown** action name returns RED (fail closed).
- **Errors:** none raised. **Side effects:** none. **Determinism:** pure. **Auth class:** n/a (classification only).

### `Gov.authorize(action: Action, token: Token | None) -> Decision`
- **Preconditions:** for RED actions, `token` should be a grant from `Gov.grant`/`Gov.envelope_open`.
- **Postconditions:** GREEN/YELLOW → `ok` (autonomous/within-budget; no token needed, none consumed).
  RED → `ok` iff the token is issued-here ∧ unexpired ∧ unconsumed ∧ scope==`action.name` ∧
  venture matches (`INV-GOV-1/3`); two-key additionally requires `action.check.passed` (`INV-GOV-2`);
  `send.stage` additionally requires `params["count"] ≤ send_budget_remaining(today)` (`INV-GOV-5`).
  On `ok` for RED the token is **consumed** (single-use); a denial does not consume.
- **Errors:** none raised — refusals are `Decision(ok=False, reason=...)` (denial is a normal, logged outcome).
- **Side effects:** none (the *acting* subsystem appends the action event carrying the token id).
- **Determinism:** deterministic (injected clock + ledger read). **Auth class:** n/a — this *is* the authorization chokepoint.

### `Gov.envelope_open(venture_id: str, cap_usd: float) -> Token`
- **Preconditions:** called only at the founder-approval boundary (the call itself is the RED
  authorize-once act, exactly like `grant`; the Conductor invokes it only on a founder gate
  approval). `cap_usd > 0`.
- **Postconditions:** mints the **envelope token** (scope `spend.envelope`, `cap_usd` recorded)
  and appends `spend_envelope{cap_usd}` with `authorization` = that token id. The venture's
  running total resets to 0 (`INV-GOV-4` authorize-once).
- **Errors (fail closed):** non-positive cap → `ValueError`; nothing appended.
- **Side effects:** one ledger append. **Determinism:** deterministic. **Auth class:** RED (this
  call *is* the once-per-envelope RED authorization; signature frozen per docs/40 §4).

### `Gov.spend(venture_id: str, amount: float) -> SpendResult`
- **Preconditions:** an envelope was opened for the venture (else refused).
- **Postconditions:** within cap → `ok`, `color=YELLOW`, `spend_meter{amount_usd, running_total}`
  appended; `degrade=True` when the new total exceeds 80% of cap (docs/14 auto-degrade). Over cap →
  `ok=False`, `spend_breach{attempted, cap}` appended, reason says a fresh RED envelope is required
  (`INV-GOV-4` breach → re-RED). No envelope → `ok=False`, nothing appended.
- **Errors:** none raised (refusal is a `SpendResult`). **Side effects:** one ledger append (meter or breach).
- **Determinism:** deterministic. **Auth class:** YELLOW (within an authorized envelope).

### `Gov.send_budget_remaining(day: str) -> int`
- **Preconditions:** `day` is `YYYY-MM-DD`.
- **Postconditions:** returns `Config.budgets.send_daily − Σ send_batch.count` whose envelope
  `timestamp` falls on `day`, across **all** ventures (`INV-GOV-5` founder-wide); floor 0.
- **Errors:** none. **Side effects:** none (ledger read). **Determinism:** deterministic. **Auth class:** n/a.

### `Gov.grant(scope: str, venture_id: str | None, ttl_s: float, cap_usd: float | None = None) -> Token`  *(additive, v1 note below)*
- **Preconditions:** called only at the founder-approval boundary (Conductor gate); tests stop at
  this boundary (INV-TEST-SAFE).
- **Postconditions:** returns a single-use token scoped to `scope`+`venture_id`, expiring at
  `clock()+ttl_s` (`INV-GOV-1/3`).
- **Errors:** empty scope → `ValueError`. **Side effects:** none (issuance is recorded when the
  action event carrying the token id is appended). **Determinism:** deterministic. **Auth class:**
  n/a — this *mints* the RED credential; it performs nothing.

### `Gov.record_override(kind: str, recommendation: str, decision: str, reason: str, venture_id: str, old_score: int | None = None, new_score: int | None = None) -> event_id`  *(additive, v1 note below)*
- **Preconditions:** `reason` is non-empty (whitespace-only counts as empty); `kind` ∈
  {"admission","advance","kill","score"}.
- **Postconditions:** appends `override{recommendation, decision, reason}` (or
  `score_override{old_score, new_score, reason}` for `kind="score"`) — `INV-GOV-6`.
- **Errors (fail closed):** empty reason → `MissingReason`, nothing appended; unknown kind → `ValueError`.
- **Side effects:** one ledger append. **Determinism:** deterministic. **Auth class:** n/a (records a founder decision; performs nothing).

## Public value types
`Action{name, venture_id?, params, check?}` · `CheckResult{name, passed, detail}` ·
`Decision{ok, reason}` · `SpendResult{ok, color, amount, running_total, cap_usd, degrade, reason}`.
Shared (docs/43 §6, in `charterhouse/contracts/`): `AuthClass{color, two_key}`, `ActionColor`, `Token`.

## Consumed surface
- **Ledger (S4, IF-1):** `append(event) -> event_id` — failure propagates (no partial Gov state);
  `read(EventFilter) -> Iter[Event]` — broken chain raises (fail closed upstream).
- **Config (S3, IF-2 Config-half, frozen):** `budgets -> Budgets{monthly_usd, on_exceeded,
  send_daily}` — consumed via a `ConfigPort` protocol; **stubbed** until A2 lands (docs/43 §2).
  A missing/invalid budgets object at construction → refuse to construct (fail closed).

## Interface stability
- **Frozen (IF-3, this doc):** `classify/authorize/envelope_open/spend/send_budget_remaining`
  signatures per docs/40 §4, the `Action/Decision/SpendResult/CheckResult` shapes, and the
  GREEN/YELLOW/RED(+two-key) matrix semantics. Breaking change = ICR (docs/43 §4).
- **Additive v1 note (docs/43 §7, no-bump):** `grant` and `record_override` extend docs/40 §4
  (which defines no issuance/override seam). Additive: no frozen signature altered; consumers of
  the five frozen functions are unaffected. Recorded here per docs/43 §1.
- **Internal/free to change:** `SCALED_SEND_THRESHOLD` value, token id format, envelope-fold
  implementation, module layout.
