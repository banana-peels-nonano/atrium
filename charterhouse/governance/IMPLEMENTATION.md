# Governance (S6) — IMPLEMENTATION
Owner: A5 Governance/Security Agent   Subsystem: S6   Source of truth: docs/14_governance.md (frozen) + docs/40 §4, docs/41 §2 (money/sending), docs/43, docs/54 §S6, Stress-Test Revision Register (R-ENVELOPE, R-SEND-BUDGET, R-OVERRIDE-LOG, R-CHARGE)

## 1. Responsibility (one paragraph)
S6 classifies every proposed action into the frozen GREEN/YELLOW/RED(+two-key) classes and lets
nothing cross a money/deploy/contact/gate boundary without a valid founder authorization: it
issues, validates, and consumes single-use expiring scoped tokens, enforces the spend envelope
(authorize-once → within-cap YELLOW → breach re-RED) and the founder-wide daily send budget, and
records governance events (envelope/meter/breach/override) in the ledger. It **MUST NOT** perform
any action itself (no send, spend, deploy, charge, or state transition — it only classifies,
authorizes/denies, and records), MUST NOT hold payment or provider credentials (docs/24), MUST NOT
re-implement lifecycle guards (S5's) or redaction/scanning (S7's), and MUST NOT call an LLM
(deterministic, docs/61 §INV-DET).

## 2. Invariants enforced
- **`INV-GOV-1` — every RED action requires a valid, correctly-scoped token.** *Guaranteed by:*
  `authorize` denies any RED action unless the presented token was issued by this Gov's store, is
  unexpired on the injected clock, is unconsumed, and matches both the action name (scope) and the
  venture. Unknown action names classify RED and are denied unconditionally (fail closed).
- **`INV-GOV-2` — two-key set (prod payment-path deploy, `billing.enable`, scaled outreach)
  requires token AND passing automated check.** *Guaranteed by:* `classify` marks the two-key set;
  `authorize` additionally requires a `CheckResult(passed=True)` carried on the `Action`; a
  missing or failing check denies even with a valid token.
- **`INV-GOV-3` — tokens single-use + expiring; reuse refused.** *Guaranteed by:* consumption
  state lives in the Gov token store (never on the immutable `Token`); a consumed id is refused on
  re-presentation; expiry is checked against the injected clock at authorization time.
- **`INV-GOV-4` — spend envelope: authorize cap once (RED); within-cap = YELLOW; breach →
  re-RED.** *Guaranteed by:* `envelope_open` (RED) appends `spend_envelope{cap_usd}`; `spend`
  derives the active cap and running total from the ledger (latest `spend_envelope` + subsequent
  `spend_meter`s), appends `spend_meter` within cap (YELLOW, degrade flag past 80%), refuses and
  appends `spend_breach` past cap; spending again requires a fresh `envelope_open` (re-RED).
  Spending with no envelope ever opened is refused.
- **`INV-GOV-5` — send budget is founder-wide (≤ configured/day), Conductor-allocated by
  priority; never unbounded per venture.** *Guaranteed by:* `send_budget_remaining(day)` =
  `Config.budgets.send_daily` − Σ `send_batch.count` on that day across **all** ventures (ledger
  read); `authorize` of a `send.stage` action denies when `count` exceeds the remaining budget.
- **`INV-GOV-6` — every founder override (admission/advance/kill) logged with reason.**
  *Guaranteed by:* `record_override` appends `override{recommendation, decision, reason}` /
  `score_override{old_score, new_score, reason}`; an empty/whitespace reason raises `MissingReason`
  (fail closed) and nothing is written.

## 3. Internal design
**Deterministic throughout; no LLM path.** Durable state: **none here** — all governance facts
(envelopes, meters, breaches, sends, overrides) live in the ledger; token consumption state is
process-local by design (see §5, RISKS R4).

- `types.py` — public value types: `Action{name, venture_id?, params, check?}`,
  `CheckResult{name, passed, detail}`, `Decision{ok, reason}`,
  `SpendResult{ok, color, amount, running_total, cap_usd, degrade, reason}`. `AuthClass`,
  `ActionColor`, `Token` come from `charterhouse/contracts/authz.py` (shared, docs/43 §6).
- `classify.py` — the frozen action-class matrix as data: every docs/40 §8 command name →
  `AuthClass`. GREEN: capture, frame, validate.evidence, shape, recruit.partners, salvage,
  consolidate, calibrate, pause, resume, pipeline, brief, killday, gatebrief. YELLOW:
  spend.meter, validate.experiment, build (metered inference + staging deploy, docs/14 table).
  RED: admit, gate, advance.express, spend.envelope, send.stage, launch, pivot, graduate, kill;
  RED **two-key**: deploy.prod, billing.enable, and send.stage when
  `params["count"] > SCALED_SEND_THRESHOLD` (scaled outreach). Unknown name → RED (fail closed;
  `authorize` additionally always denies it).
- `tokens.py` — `TokenStore`: `grant(scope, venture_id, ttl_s, cap_usd?) -> Token` (monotonic ids
  via injected factory; issued/expiry stamped from injected clock), `validate(token, action)`
  (issued-here ∧ unexpired ∧ unconsumed ∧ scope==action.name ∧ venture match), `consume(token_id)`.
  Consumption is recorded on **success only** — a denial never burns a founder grant.
- `envelope.py` — pure fold over one venture's ledger events → `EnvelopeState{cap_usd,
  running_total, open}`: `spend_envelope` (re)sets cap and zeroes the total; `spend_meter` adds.
  The **latest** envelope is the active one (re-RED after a breach = a fresh `spend_envelope`).
- `send_budget.py` — pure fold over `send_batch` events filtered to a `YYYY-MM-DD` day (envelope
  `timestamp` date) → units sent; remaining = `budgets.send_daily` − sent.
- `facade.py` — `Gov(ledger, config: ConfigPort, clock, new_id)` wiring the frozen surface
  (`classify/authorize/envelope_open/spend/send_budget_remaining`) + the two documented additive
  seams (`grant`, `record_override`). `ConfigPort` is a `Protocol` with `budgets -> Budgets`
  (stubbed until S3 lands, docs/43 §2). Gov appends **only** governance events
  (`spend_envelope`, `spend_meter`, `spend_breach`, `override`, `score_override`); action events
  (`send_batch`, `deploy_prod`, …) are appended by the acting subsystem carrying the consumed
  token id — Gov *accounts* for them by reading the ledger.

## 4. Dependencies
- **Ledger (S4, IF-1 frozen):** `Ledger.append(event) -> event_id`, `Ledger.read(EventFilter)
  -> Iter[Event]` per docs/40 §2 — real implementation (merged), no stub.
- **Config (S3, IF-2 Config-half frozen):** `Config.budgets -> Budgets{monthly_usd, on_exceeded,
  send_daily}` per docs/40 §1 — **stubbed** (`ConfigPort` protocol + test double) until A2 lands;
  the consumed shape is the frozen `charterhouse/contracts/config_types.Budgets`.
- **Shared types (docs/43 §6):** `AuthClass`, `ActionColor`, `Token` from
  `charterhouse/contracts/authz.py`; `Event`, `EventType` from `contracts/events.py`.

## 5. Failure behavior
| Failure mode | Fail-closed response |
|---|---|
| RED action with no/forged/expired/consumed/mis-scoped/mis-ventured token | `Decision(ok=False)` naming the reason; the token is not consumed by a denial |
| Two-key action with valid token but missing/failing check | denied; token **not** consumed (the grant survives for a retry with a passing check) |
| Unknown action name | classifies RED; `authorize` denies regardless of token |
| `spend` with no envelope ever opened | refused (`re-RED required`); no event written |
| `spend` that would exceed the active cap | refused; `spend_breach{attempted, cap}` appended; fresh `envelope_open` (RED) required |
| `send.stage` batch exceeding the founder-wide remaining budget | denied; nothing appended |
| Override with empty/whitespace reason | `MissingReason` raised; nothing appended |
| Ledger append fails mid-operation | the exception propagates; Gov holds no partial state (all accounting is re-derived from the ledger) |
| Process restart | outstanding tokens are void (store is process-local — an unknown token is invalid, which errs closed); envelope/send accounting unaffected (ledger-derived) |
No "guess/continue" path: every deny carries a reason string; every governance fact that must
survive is a ledger event, never memory.

## 6. Open questions → RESOLVED
- **Q: docs/40 §4 has no token-issuance or override-logging function — where do tokens come from
  and how is INV-GOV-6 exercised?** **RESOLVED —** two documented **additive** surfaces (docs/43
  §7 additive-no-bump): `Gov.grant(...)` (the founder-approval boundary; tests stop here per
  INV-TEST-SAFE) and `Gov.record_override(...)`. Neither alters a frozen signature; both are in
  API.md with a version note.
- **Q: is `deploy.prod` two-key only for payment-path deploys (docs/14 wording)?** **RESOLVED —**
  always two-key, matching the unconditional docs/41 §2 annotation `deploy_prod (RED two-key)`;
  the stricter reading errs closed.
- **Q: what is "scaled outreach"?** **RESOLVED —** `send.stage` with `count >
  SCALED_SEND_THRESHOLD` (default **25**, one founder-day of manual sends per the Stress Test §1;
  a constant, changeable without an ICR since it alters no frozen signature).
- **Q: who appends `send_batch`?** **RESOLVED —** the acting subsystem (send-assist via
  Conductor), carrying the consumed token id; Gov accounts by ledger read. Gov appending it would
  double-count and would cross the "performs no action" boundary. The authorize→append gap is
  RISKS R5.
- **Q: does a breach close the envelope?** **RESOLVED —** the breach *attempt* is refused and
  recorded (`spend_breach`); the envelope stays at its cap (unspent headroom remains spendable);
  raising the cap = a **new** `spend_envelope` (the "re-RED"), which resets the running total.
