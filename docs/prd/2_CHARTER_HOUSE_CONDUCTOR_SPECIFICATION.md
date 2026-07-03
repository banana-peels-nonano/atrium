# CHARTER HOUSE — DOCUMENT 2
## Complete Conductor Specification
### Standalone · v1.1 (incorporates Stress-Test Revision Register)

> The Conductor is the **deterministic engine** — not an LLM. It is the single chokepoint through which every state change and every external effect passes. If the Conductor is correct, the factory's discipline is *structurally guaranteed* rather than dependent on any model behaving well. This document is the engine's complete contract: responsibilities, command surface, the workflow it runs, the gates it enforces, the events it records, and how it fails safely.
> v1.1 additions: PII redaction + deterministic pre-commit scan (R-REDACT, R-PRECOMMIT-SCAN), pivot orchestration (R-PIVOT), spend envelopes (R-ENVELOPE), separate billing approval (R-CHARGE), slot-aware express-advance block (R-SLOT-GATE), SHAPING WIP + shovel-ready overflow (R-SHAPING-WIP), evidence TTL (R-EVIDENCE-TTL), live-clock + active-time deadlines (R-CLOCK, R-ACTIVE-TIME), founder-wide send budget (R-SEND-BUDGET), degraded critic ladder (R-CRITIC-DEGRADE), override + OMW ledger events (R-OVERRIDE-LOG, R-OMW-LEDGER), Gate Brief (R-GATEBRIEF), two-sub-gate validation (R-EVIDENCE-GATE).

---

## 1. Design invariants (the Conductor must guarantee these at all times)
1. **No illegal state transition** ever occurs.
2. **WIP limits are never exceeded** (validating ≤3, SHAPING ≤1, building ≤1, HARVEST alumni ≤3).
3. **No external effect** (money, production deploy, billing, contact) occurs without a valid, logged founder authorization token of the correct class.
4. **No unredacted PII** is embedded or sent to a cloud adapter.
5. **Every meaningful change is an append-only ledger event**; current state is always reconstructable by replay.
6. **Every gate is presented as a complete Gate Brief** including a Critic section.
7. The Conductor itself holds **no durable state between commands** — state lives in the ledger — so a crash loses nothing.

If any invariant cannot be satisfied, the Conductor **rejects and logs**, leaving the venture untouched. Fail closed, never open.

---

## 2. Responsibilities
1. **State-machine enforcement** — validate and execute only legal transitions per the Lifecycle spec.
2. **WIP & slot management** — enforce all four limits; manage the shovel-ready overflow queue; allocate freed slots by backlog rank.
3. **Workflow execution** — run each state's 5-beat workflow (§5), invoking capabilities via the routing layer.
4. **Governance** — classify every proposed action GREEN/YELLOW/RED; hold RED until a token is presented; enforce two-key for the irreversible set.
5. **Spend control** — manage spend envelopes; meter within-cap spends; re-gate on breach; run the budget guard for inference.
6. **Send control** — manage the founder-wide daily send budget; schedule approved batches in the audience timezone; track per-domain warming.
7. **Memory safety** — run the redaction step + deterministic pre-commit scan at every CHECKPOINT; tag context `contains_pii`; route PII-bearing context to local models only.
8. **Event handling** — append every event; nothing of record happens off-ledger.
9. **Projection generation** — regenerate the board/PIPELINE, METRICS, Daily Brief, Send batch, Kill-Day Brief, and every Gate Brief.
10. **Retrieval assembly** — build per-task working memory via top-K retrieval (never dump full stores); always include Doctrine.
11. **Routing & failover** — resolve role→model from config; handle failover and tier degradation (accepted substrate).
12. **Clock management** — track `state_entered_at`, `experiment_live_at`, and **factory-active time**; pause clocks during declared pauses.

---

## 3. Command surface (names + class; not implementations)
| Command | Effect | Class | v1.1 notes |
|---|---|---|---|
| `capture` | add signal to inbox | GREEN | |
| `frame` | Scout FRAMED workflow → brief + score | GREEN | reachability stored as hypothesis |
| `admit <v>` | FRAMED→VALIDATING | **gate (slot-consuming, never express)** | logs override if score<18 |
| `validate.evidence <v>` | Analyst evidence pack → Evidence sub-gate | GREEN | new sub-gate (R-EVIDENCE-GATE) |
| `validate.experiment <v>` | stand up experiment (drafts/staging) | GREEN/YELLOW | |
| `spend.envelope <v> <cap>` | authorize a capped budget | **RED** | within-cap spends become YELLOW |
| `spend.meter <v> <amt>` | record a within-cap spend | YELLOW | breach → auto re-RED |
| `send.stage <v>` | queue approved outreach in audience TZ | **RED (batch)** | counts against founder-wide send budget |
| `gate <v>` | present Gate Brief; record verdict | gate | ADVANCE/KILL/OMW; OMW & overrides → ledger |
| `advance.express <v>` | mid-week advance | gate | **rejected if transition consumes a slot** |
| `shape <v>` | Builder SHAPING → SPEC + partners plan | GREEN | SHAPING WIP=1; overflow→shovel-ready |
| `recruit.partners <v>` | Growth drafts partner outreach | GREEN→RED to send | from warm validation leads |
| `build <v>` | Builder BUILDING (staging only) | GREEN/YELLOW | |
| `deploy.prod <v>` | production deploy (tagged) | **RED + two-key** | |
| `billing.enable <v>` | turn on charging | **RED + two-key** | distinct from deploy (R-CHARGE) |
| `launch <v>` | present launch kit; founder publishes | **RED** | |
| `pivot <v>` | KILL current + FORK new at FRAMED | gate + orchestration | one fork/lineage (R-PIVOT) |
| `graduate <v>` | EARNING→GRADUATED | **gate (alumni-capacity-aware)** | blocked if HARVEST alumni at cap |
| `kill <v>` | →KILLED + trigger salvage | gate (Friday) | |
| `salvage <v>` | Librarian extracts lesson + asset | GREEN | salvage types enumerated |
| `consolidate` | Librarian memory consolidation | GREEN | reversible (view only) |
| `calibrate` | monthly calibration report | GREEN | includes all overrides |
| `pause` / `resume` | declare factory pause | GREEN | freezes all active-time clocks |
| `pipeline`/`brief`/`killday`/`gatebrief <v>` | regenerate projections | GREEN | |

---

## 4. The state machine the Conductor enforces (v1.1)
Legal states: CAPTURED, FRAMED, PARKED, **PARKED-SHOVEL-READY**, VALIDATING, SHAPING, BUILDING, LAUNCHED, EARNING, GRADUATED, KILLED, ARCHIVED; Alumni: SCALING, HARVEST, EXITED.

Key transition guards (checked in order for every transition): **legal? → WIP/slot OK? → entry criteria (evidence) met? → authorization class satisfied? → (if writing artifacts) redaction+scan clean?** All pass → CHECKPOINT + advance. Any fail → reject + log.

v1.1-specific guards:
- `admit` and `→BUILDING`: slot-consuming → **never express**; require deliberate gate.
- `VALIDATING` exit: requires BOTH the Evidence sub-gate and the Experiment sub-gate to have passed.
- `→SHAPING`: if SHAPING occupied (WIP=1), route to PARKED-SHOVEL-READY with an **evidence TTL** stamp (default 60 active-days).
- `PARKED-SHOVEL-READY → BUILDING`: if evidence age > TTL, require a cheap re-confirmation signal first.
- `graduate`: rejected if HARVEST alumni count = cap (≤3) until one EXITs.
- `pivot`: allowed from LAUNCHED (and EARNING); checks the ledger for an existing fork in this lineage (max one).

## 5. Workflow execution — the 5-beat skeleton (robust by construction)
Every state's workflow runs the same five beats. Only beat 4 mutates state; only beat 5 advances the venture.

```
1. PREPARE   (deterministic) — gather inputs + assemble top-K working memory (Doctrine always)
2. PRODUCE   (capability, idempotent/retryable) — draft artifact + recommendation
3. CRITIQUE  (capability, different model family) — adversarial "why this fails"; degrade per ladder if needed
4. CHECKPOINT(deterministic) — REDACT → SCAN → write artifact to vault → append ledger event
5. GATE      (human) — present Gate Brief; founder authorizes (or not)
```
- **PRODUCE** failure → retry; escalate one routing tier on repeat; if exhausted, queue + notify. No state change.
- **CRITIQUE** must be a different model family than PRODUCE. If unavailable, **degrade** (R-CRITIC-DEGRADE): (1) different family → (2) different model same family → (3) deterministic rule-based checklist (always available). The Gate Brief records the tier; tier-3 is flagged "shallow — scrutinize."
- **CHECKPOINT** is the ONLY state-mutating beat and is fully deterministic. **Redaction + pre-commit scan run here, before any embed or cloud route.**
- **GATE** is the ONLY advancing beat and is always human (except internal GREEN steps that have no gate).

## 6. Approval-gate handling
- The Conductor never self-authorizes a gate or RED action. It assembles the **Gate Brief** (fixed schema, §7) and waits.
- A founder authorization is a discrete, logged **token** bound to a specific venture + action + (for envelopes) amount.
- **Two-key set** (production deploy of payment-path code, `billing.enable`, scaled outreach): each requires the founder token **AND** a passing automated check (test/lint/scan). These never get a standing "yes" — each act is authorized individually.
- Tokens are single-use; denied/expired → action dropped + logged.
- **Overrides:** if the founder's verdict contradicts the Conductor's mechanical recommendation (admission, advance, or kill), the Conductor records an **override event** with the founder's stated reason and flags it for the calibration report.

## 7. The Gate Brief (fixed schema — R-GATEBRIEF)
The Conductor assembles this for every gate; the founder decides on nothing else:
```
GATE BRIEF
  venture:           <slug> (codename)
  transition:        <from_state> → <proposed_state>
  evidence_vs_threshold:  <metric>: <actual> vs <threshold>  [PASS/FAIL/INCONCLUSIVE]
  cost_to_date:      inference $<x> · real-spend $<y> of $<envelope>
  reversibility:     GREEN | YELLOW | RED (two-key?: yes/no)
  recommendation:    ADVANCE | KILL | ONE-MORE-WEEK   (mechanical, from criteria)
  critic:            tier<1|2|3> — "<best case this is wrong>"
  why_now:           <one line>
  flags:             [WIP, expired-deadline, override-required, evidence-TTL, no-traffic-3d, ...]
```
A Gate Brief missing the `critic` field is invalid and must not be presented.

## 8. Event handling & venture tracking
- Each venture = one registry record: id, codename, state, score, `forked_from?`, timestamps (`state_entered_at`, `experiment_live_at`), artifact links, event-stream pointer.
- Event types (minimum): capture, frame, score, admit, override, evidence-pass/fail, experiment-live, spend-envelope, spend-meter, spend-breach, send-batch, gate-decision, omw-grant, deploy, billing-enable, launch, pivot-fork, kill, salvage, graduate, alumni-transition, consolidate, pause, resume.
- Every event: `event_id, timestamp, factory_active_time, venture_id, actor, type, from_state?, to_state?, payload, authorization_token?`.
- The registry's "current state" is itself a projection; authoritative state is the replayed ledger. Backups of the ledger are written to `K:\Data\charter_house\backups`.

## 9. Clocks & deadlines (R-CLOCK, R-ACTIVE-TIME)
- Three clocks per venture: wall-clock `state_entered_at`, `experiment_live_at` (set when the first send/traffic occurs), and the **factory-active-time** accumulator.
- **All deadlines are measured in factory-active time from `experiment_live_at`**, never from state entry and never in wall-clock. Setup latency (domain warming, build) is bounded separately and does not consume the experiment window.
- `pause` freezes all active-time accumulation (outage, vacation); `resume` restarts it. This prevents false KILLs for ventures that simply couldn't be worked.

## 10. Memory safety pipeline (the v1.1 critical fix — R-REDACT, R-PRECOMMIT-SCAN)
At every CHECKPOINT, before any artifact is embedded or any context is cloud-routed:
1. **Redact:** raw PII (names, emails, phone, financials, secrets) is moved to a **local-only sidecar** (`*.private.md`) that is never embedded and never leaves the machine. A redacted version (PII → stable tokens) is what gets written to the shared/embedded tier.
2. **Deterministic pre-commit scan:** an independent, rule-based scanner (regex/entropy/secret-pattern) re-checks the redacted output. If it finds residual PII/secrets, CHECKPOINT **fails closed** and the venture stays put until cleaned. This backs up the capability-driven redaction with a non-LLM guarantee.
3. **Routing enforcement:** any context tagged `contains_pii` (e.g., reading a `.private.md` sidecar) is **hard-blocked from all cloud adapters** and may run only on local models. The router refuses otherwise.
> This closes the design's single most dangerous hole: governance previously gated *actions* (spend/deploy/send) but not the *retrieval* path, so PII could exfiltrate to the cloud via memory. It cannot anymore.

## 11. Spend & send control
- **Spend envelope (R-ENVELOPE):** `spend.envelope` authorizes a cap (RED). `spend.meter` records within-cap spends (YELLOW, budget-guarded). A spend that would breach the cap triggers automatic re-RED; nothing silent.
- **Inference budget guard:** tracks monthly inference $; past thresholds, degrades routing tier (cheap/free/local) for all but the protected roles (Analyst kill-decisions, Builder make-or-break), per accepted routing.
- **Send budget (R-SEND-BUDGET):** a single founder-wide daily cap (default ≤40) across all ventures. The Conductor allocates it to active experiments by priority, schedules approved batches in the audience timezone, and tracks per-domain warming. Drafts always originate from Growth's outbox; the founder authorizes the batch.

## 12. Pivot orchestration (R-PIVOT)
On `pivot <v>`: (1) verify no existing fork in this lineage via the ledger; (2) KILL `v` and run salvage; (3) auto-CAPTURE a new venture with a `forked_from=v` link, inheriting the audience list + validated-segment record (but NOT the dead value prop); (4) free the slots; (5) the fork enters at FRAMED to be re-scored and re-ranked in the backlog — it does not jump the queue. A second pivot of the same lineage is refused and must clear a fresh full validation as a new lineage.

## 13. Failure behavior (fail closed, lose nothing)
- Capability/model failure → retry/escalate/queue; never a state change.
- Provider/router failure → failover chain → degrade to local/free → if none, declare `pause` (clocks freeze); the vault stays fully human-usable.
- Redaction/scan failure → CHECKPOINT fails closed; venture untouched.
- Conductor crash → restart and replay the ledger; zero loss (no durable in-memory state).
- Ambiguity at any guard → reject + log, never guess.

## 14. What the Conductor must NOT do
- Must not run an LLM for any decision it can make deterministically (state, WIP, metrics, routing, redaction-scan).
- Must not present a gate without a Critic section.
- Must not auto-cross any slot-consuming or RED boundary.
- Must not embed or cloud-route unredacted PII.
- Must not measure deadlines in wall-clock.
- Must not let the founder exceed a WIP *count* (it may let them choose which venture fills a slot).
