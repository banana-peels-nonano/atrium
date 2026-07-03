# CHARTER HOUSE — DOCUMENT 4
## Lifecycle Stress Test & Revision Register
### Design-risk elimination · runs three ventures Capture → Graduation · v1.0 of the test → v1.1 of the architecture

> Method: trace three realistic ventures, state by state, with concrete numbers and dates. At every gate ask four questions — *What artifact does the Conductor present? What decision is required? What could go wrong? Is the contract sufficient?* Collect every flaw into a numbered defect. Then produce a **Revision Register** that amends the architecture to v1.1. Documents 1–3 (Founder Manual, Conductor Spec, Capability Contracts) already incorporate these revisions; this document is the justification trail.
> The goal is not to prove the design works. The goal is to **break it on paper** so Claude Code never has to discover these failures in code.

---

## 0. The three test ventures (chosen to exercise different failure modes)

| | Codename | One-liner | Designed to stress |
|---|---|---|---|
| **A** | `battlecard` | Weekly competitor-review battlecards emailed to B2B SaaS founders | The **happy path** — surfaces missing artifacts and handoffs even when nothing "fails" |
| **B** | `hvac-route` | Cold-outreach scheduling tool for HVAC shop owners | A **messy validation death** — surfaces governance, spend, outreach-load, and kill-ambiguity flaws |
| **C** | `clipscribe` | Auto-transcribe + clip tool for podcasters | A **pivot + concurrency + incident** — surfaces regression paths, slot contention, PII leakage, and the alumni ceiling |

Assume the founder is on the **Consumer hardware stack** (Stack B), budget tier <$20/mo, operating per the Founder Manual.

---

## 1. Venture A — `battlecard` (the happy path that still leaks)

**CAPTURED (Day 0).** Founder notes "every B2B founder I know manually screenshots competitor G2 complaints before sales calls." → inbox note. *Fine.*

**FRAMED (Day 2).** Scout writes a brief with 3 linked G2/Reddit pain quotes. Factory Score 20/25 (Pain 5, Reachability 4 — founders are on LinkedIn/X, Build-cost 4, Money 4, Compounding 3). Founder gut-yes. A validating slot is free → admitted.
- 🟢 Works. **DEFECT A1 (Minor):** Scout's score depends on Reachability = "can contact 100 buyers this week." But the *proof* of reachability only arrives during validation. Scout is scoring a hypothesis as if it were evidence. → *Revision: Reachability at FRAMED is explicitly a hypothesis; the validation plan must include a reachability test as its first checkpoint, not just a conversion test.*

**VALIDATING (Days 2–14).** Analyst produces market (bottom-up: ~40k reachable B2B SaaS founders × $30/mo × 2% = ~$288k ceiling — labeled, not a kill), competitor teardown, 22 pain quotes. Validation plan: "≥4% of 300 targeted founders → email+title on a landing showing a $29/mo pre-order." Growth drafts a landing + a 3-touch LinkedIn sequence into the outbox.
- At the **spend gate**, founder authorizes $120 (landing is free on Cloudflare; spend is for a small LinkedIn boost). 🔴 RED token issued.
- **DEFECT A2 (Major):** the spec says "founder sends ≤25/day." Founder sends 25 LinkedIn DMs/day for ~12 days = manual labor, *and* it's the founder's India-evening = US-morning. The manual's "morning block" (India morning) is the wrong time to send US outreach. → *Revision R-OUTREACH: outreach sending is its own scheduled block decoupled from the decision morning-block; the Conductor schedules sends for the audience's timezone and the founder approves a batch, then a send-assist releases them on schedule within the approved cap (still founder-authorized, not auto-generated).*
- **DEFECT A3 (Major):** spend was authorized once as $120, but LinkedIn boost is spent incrementally over days. Is every daily $10 a new RED token? That's approval fatigue. → *Revision R-ENVELOPE: introduce the **spend envelope** — founder authorizes a capped amount once (RED); individual spends within the envelope are YELLOW (logged, budget-guarded); breaching the envelope re-triggers RED.*
- Day 14: 312 visitors, 17 email+title (5.4% > 4% threshold). **PASS.** Express advance to SHAPING (non-slot-consuming) is allowed mid-week.

**SHAPING (Days 15–17).** Builder writes SPEC: one loop (connect competitor list → weekly battlecard email), 3 screens, cut-list (no integrations, no team seats, no dashboard), pricing hypothesis $29/mo. Founder approves; Builder confirms ≤10 days.
- **DEFECT A4 (Major):** the gate to enter BUILDING **consumes the single build slot** — a large, expensive commitment. The "express advance" rule allowed mid-week advances; if applied here it would let a venture grab the only build slot mid-week without the deliberation a slot-commitment deserves. → *Revision R-SLOT-GATE: express advance is permitted ONLY for transitions that do not consume a scarce slot. Entering BUILDING (consumes build slot) and admitting to VALIDATING (consumes a validating slot) always occur at a deliberate gate with explicit slot-awareness, never express.*
- **DEFECT A5 (Major, missing artifact):** SHAPING produces a SPEC, but BUILDING's exit requires "5 design-partner users." **Nobody recruited them.** Builder owns BUILDING but design-partner recruitment is distribution = Growth's job, and Growth "never sends." Who finds the 5 partners, and when? → *Revision R-PARTNERS: add a **Design-Partner Recruitment** sub-workflow that begins in SHAPING (parallel to spec): Growth drafts partner-recruitment outreach from the validation respondents (the 17 who gave email+title are warm leads!), founder sends within cap. The 5 partners must be lined up before BUILDING exit, ideally before it starts. Add artifact `partners.md` to the SHAPING outputs.*

**BUILDING (Days 18–27).** Builder scaffolds from `saas-starter`, builds the loop, wires Paddle + PostHog, deploys to staging. Critic reviews payment/data-loss paths. Founder approves production deploy (🔴 two-key: token + passing payment-path test). 5 of the 17 warm leads onboard and complete the loop.
- 🟢 Works, given R-PARTNERS. **DEFECT A6 (Minor):** "5 strangers complete the core loop unassisted" — but design partners from your validation list aren't *strangers*, they're warm. The exit criterion conflates design-partners (warm) with strangers (cold). → *Revision: BUILDING exit = "5 design partners complete the loop unassisted"; the *stranger* test belongs to LAUNCHED. Clarify wording in Lifecycle.*

**LAUNCHED (Days 28–41).** Growth drafts a Product Hunt + 4-community launch kit; founder publishes personally (🔴). 240 visitors, 14 activated, 2 payment-intents.
- 🟢 Passes (≥10 activated + payment-intent). **DEFECT A7 (Minor):** the "first payment-intent" on Paddle is a real charge attempt — is collecting money a RED action distinct from deploy? Yes, and it was bundled into the deploy approval. → *Revision R-CHARGE: "charging customers / going live with billing" is its own two-key RED action, separate from code deploy. You can deploy a build without billing enabled; enabling billing is a distinct authorized step.*

**EARNING (Days 42–95).** Pricing test $29 vs $39; channel (LinkedIn founder-outreach) repeats. Day 88: 12 paying customers, $390 MRR-ish, churn 8%. Crosses "10 paying customers in 60 days" (the 60-day clock ran from EARNING entry, Day 42 → Day 88 is 46 days). **GRADUATE.**
- **DEFECT A8 (Major, the real one):** graduation "reopens the build slot" and moves `battlecard` to Alumni as "self-sustaining." But the founder is *still the only person.* Battlecard now needs ongoing support, billing ops, churn-fighting. Graduation reduced *factory WIP* but **increased standing founder attention** with no cap. Run this 5 times and the founder drowns in alumni maintenance, never able to start new ventures. → *Revision R-ALUMNI-CEILING: the real long-term constraint is **alumni maintenance attention, not factory WIP.** Add a hard cap on concurrently-maintained HARVEST alumni a solo founder can hold (default ≤3). Exceeding it forces a decision: EXIT (sell/wind down) one alumnus before graduating another, or invest in making an alumnus genuinely low-touch (automation/contractor) before it counts as "harvested." Graduation is gated on alumni-capacity, exactly like BUILDING is gated on the build slot.*

**Venture A yield:** 8 defects from the *happy path alone* — proof that tracing even a success is worth it.

---

## 2. Venture B — `hvac-route` (the messy death)

**CAPTURED→FRAMED (Days 0–3).** Scout brief, score 17/25 (Reachability only 3 — HVAC owners aren't on LinkedIn; Pain 4, Build 4, Money 4, Compounding 2). 17 is backlog, not auto-advance (≥18). Founder *gut-overrides* and admits it anyway ("I have a contact in the trade").
- **DEFECT B1 (Major, governance):** the founder can override the score gate on a gut feeling, which is allowed — but the override is the *exact* behavior the doctrine warns against ("founder optimism"). Is the override logged? The spec logs *kill* overrides but not *admission* overrides. → *Revision R-OVERRIDE-LOG: every founder override of a Conductor recommendation — admission, advance, OR kill — is logged with a reason and surfaced in the monthly calibration report. Admission overrides are the most dangerous and must be tracked for calibration.*

**VALIDATING (Days 3–17).** Analyst can only find 11 primary pain quotes (HVAC owners don't post online). Per contract, "<20 quotes = the finding = KILL." But the experiment is already designed: cold email to 100 shops, threshold ≥5 booked calls.
- **DEFECT B2 (Major, contradiction):** the Analyst contract says <20 quotes → recommend KILL, but the *lifecycle* lets validation proceed to a live experiment. Do we kill at the evidence step, or run the experiment anyway? The two contracts disagree on *when* the quote-count kill fires. → *Revision R-EVIDENCE-GATE: split VALIDATING into two sub-gates — (1) **Evidence sub-gate** (does the pain dossier clear the bar? <20 quotes for an online-reachable segment = kill; for an offline segment, the bar shifts to N interview notes). (2) **Experiment sub-gate** (did the live experiment hit threshold?). A venture can die at either. This removes the contradiction and prevents spending outreach budget on an idea that already failed the evidence bar.*
- Founder insists on running it anyway (another override, now logged per R-OVERRIDE-LOG). Needs a fresh outreach domain; it isn't warmed. Sends start Day 8.
- **DEFECT B3 (Major):** the validation deadline is Day 17 (14 days from admission), but the outreach domain needed ~7 days of warming, so real sends only began Day 8 — leaving 9 days for a B2B sales cycle that needs longer. The **deadline clock ignores setup latency.** → *Revision R-CLOCK: the experiment deadline starts when the experiment goes *live* (first send/first traffic), not at state entry. The Conductor tracks `experiment_live_at` separately from `state_entered_at`. Setup time (domain warming, build) is bounded separately and does not consume the experiment window.*
- Day 17 (now Day 24 with the corrected clock): 3 booked calls from 100 emails (threshold was 5). **FAIL → KILL.**
- **DEFECT B4 (Minor):** 3/100 is "INCONCLUSIVE-ish" — the founder feels "one more week with a better subject line would hit 5." The ONE-MORE-WEEK escape exists (max one ever). Founder uses it. → This is *working as designed*, but **DEFECT B5 (Major):** nothing tracks that this venture has *already consumed* its single ONE-MORE-WEEK if it's requested again after a future regression. The spec says "max one, ever, tracked" but doesn't say *where.* → *Revision R-OMW-LEDGER: ONE-MORE-WEEK grants are first-class ledger events keyed to the venture; the Conductor refuses a second grant by checking the ledger, not memory. Same for pivots (see Venture C).*

**KILL + SALVAGE (Day 31).** One-more-week yields 4/100. Still fail. KILL. Librarian must salvage.
- **DEFECT B6 (Major, the asset-salvage gap):** doctrine says "every kill banks an asset." But what asset does a *failed cold-email-to-HVAC* leave? The lesson ("offline trades are unreachable by cold email") is real. But the spec assumes salvage = template/dataset/audience/channel; here the only salvage is a *negative lesson + an anti-pattern.* Is a negative lesson a valid "asset"? → *Revision R-SALVAGE-TYPES: formally enumerate salvage types and make **negative lessons / anti-patterns first-class salvage.** A kill that produces a sharp, reusable "don't do X" is a banked asset. Salvage is satisfied by ANY of: anti-pattern lesson, reusable template improvement, dataset, audience list, or channel finding. Only a kill that produces *none* of these — i.e., we learned nothing — is the process failure.*
- The 11 quotes + the dead domain reputation + the "trades are offline" anti-pattern are banked. Slot frees.

**Venture B yield:** 6 defects, mostly governance and timing — exactly where a messy death exposes the machine.

---

## 3. Venture C — `clipscribe` (pivot, concurrency, incident)

**CAPTURED→VALIDATING (Days 0–14).** Score 19. Validation: ≥8% of 250 podcasters → waitlist with $19/mo shown. Result: 9.1%. PASS. Meanwhile **Venture A is in BUILDING (build slot occupied)** and two other ventures are VALIDATING.

**SHAPING (Day 15) — CONCURRENCY STRESS.** `clipscribe` passes validation and is hot, but the **single build slot is occupied by `battlecard`** until Day 27. `clipscribe` sits in SHAPING.
- **DEFECT C1 (Major, missing WIP rule):** SHAPING has **no WIP limit.** If three ventures pass validation while one is building, three pile up in SHAPING, specs going stale, founder attention fragmented. → *Revision R-SHAPING-WIP: SHAPING is the "on-deck" state and is WIP-limited to **1** (the single venture next in line for the build slot). A second venture that passes validation while SHAPING is occupied goes to **PARKED-SHOVEL-READY** (validated, spec-pending) and is re-admitted when the build slot frees. This prevents spec rot and protects focus.*
- **DEFECT C2 (Major, starvation):** what if `battlecard`'s build overruns (it's allowed up to 15 days)? `clipscribe`'s validated evidence decays while it waits. Validation has a shelf life. → *Revision R-EVIDENCE-TTL: validated evidence carries a **time-to-live** (default 60 days). If a shovel-ready venture waits past TTL for a slot, it must re-confirm a cheap signal before BUILDING (a mini re-validation), not build on stale conviction.*

**BUILDING (Days 28–40).** Slot frees (A graduates). `clipscribe` builds. During build, Builder ingests 30 podcaster interview notes into `pain.md`, which the Librarian embeds for retrieval.
- **DEFECT C3 (Critical, PII/security leak):** the interview notes contain real names, emails, and a podcaster's unreleased financials. These get **embedded into the vector store and retrieved into prompts that route to *cloud* models** (analyst/scout escalations). The doctrine says "PII stays local unless flagged shareable," but **retrieval silently exfiltrates it to the cloud** the moment any capability retrieves that lesson on a cloud route. The governance model never inspected the *retrieval* path. → *Revision R-REDACT (Critical): redaction is mandatory at the CHECKPOINT beat. Raw PII is written to a **local-only sidecar** (`*.private.md`, never embedded, never cloud-routed). A **redacted** version (names/emails/financials → tokens) is what gets embedded and retrieved. The router enforces a `contains_pii` flag: any context carrying unredacted PII is hard-blocked from cloud adapters and may only run on local models. This closes the single most dangerous hole in the design.*

**LAUNCHED (Days 41–54) — THE PIVOT.** 300 visitors, 6 activated, 0 payment-intent. Below the bar (≥10 + payment-intent). But onboarding interviews reveal podcasters don't want clips — they want **automated show-notes**. The founder wants to pivot, not kill.
- **DEFECT C4 (Critical, missing path):** the lifecycle offers LAUNCHED → EARNING or → KILLED. **There is no pivot transition.** Real founders pivot constantly. Without a defined path, the founder will either (a) zombie the venture by informally "pivoting" inside BUILDING and corrupting its state/metrics, or (b) lose the validated audience and assets by killing cleanly. Both are bad. → *Revision R-PIVOT (Critical): define pivot explicitly. A **pivot = KILL-and-FORK**: the current venture is KILLED (assets/audience/lessons salvaged), and a NEW venture is auto-CAPTURED that **inherits** the prior venture's audience list, validated segment, and relevant assets via a `forked_from` link. This preserves discipline (no zombie states, metrics stay clean, WIP honest) while preserving the compounding asset (the warm podcaster audience transfers). Hard cap: **one fork per lineage** — a second pivot of the same lineage must clear a full fresh validation, preventing endless pivot-zombies. The fork enters at FRAMED (re-scored), not mid-pipeline, because a new value prop is a new hypothesis.*
- **DEFECT C5 (Major):** when `clipscribe` is KILLed-to-fork, does it free the build slot immediately, and does the fork jump the queue? If the fork inherits a warm audience it's high-value, but auto-jumping the backlog violates the ranked-queue discipline. → *Revision: a fork re-enters the ranked backlog like any FRAMED venture (scored, with its inherited-audience boost reflected in Reachability). It does not auto-jump. The freed slots (build + the lineage's validating slot) reopen normally.*

**Post-incident review.** The PII leak (C3) would, in reality, be discovered too late. → *Revision R-PRECOMMIT-SCAN: a deterministic PII/secret scanner runs at every CHECKPOINT before anything is embedded or cloud-routed, independent of capability behavior. Defense in depth: the scanner (deterministic) backs up the redaction step (capability-driven).*

**Venture C yield:** 5 defects including the **2 most severe in the entire test** (PII leak, missing pivot path).

---

## 4. Cross-cutting findings (visible only across all three)

- **DEFECT X1 (Major, outreach load):** with 3 ventures validating simultaneously, "≤25 sends/day/venture" = 75 founder-sends/day. That's not a morning block; that's a job. The per-venture cap is wrong; the constraint is **total founder send capacity.** → *Revision R-SEND-BUDGET: the send cap is a single **founder-wide daily budget** (default ≤40/day across all ventures), allocated by the Conductor to active experiments by priority, not ≤25 per venture. Protects the real bottleneck (the founder) and domain reputation.*
- **DEFECT X2 (Major, Critic deadlock on free tier):** the cross-model Critic requires a *different model family* than PRODUCE. On the zero-cost stack with free-tier rate limits, both may be unavailable simultaneously → the gate can't be assembled → the venture stalls. → *Revision R-CRITIC-DEGRADE: define a **degraded critic ladder**: (1) different family (preferred) → (2) different model same family → (3) a deterministic rule-based checklist critic (no LLM) → always at least (3) is available. The gate brief records which critic tier was used; tier-3 critiques are flagged "shallow — founder scrutinize."*
- **DEFECT X3 (Major, deadline vs outage):** during a multi-day provider/local outage, venture deadlines kept ticking (wall-clock), risking false KILLs for ventures that simply couldn't be worked. → *Revision R-ACTIVE-TIME: all deadlines are measured in **factory-active time**, not wall-clock. The Conductor pauses every venture's clock during a declared factory pause (outage, founder vacation) and resumes on restart. Deadlines measure *opportunity to produce signal*, not calendar days.*
- **DEFECT X4 (Minor, gate-brief undefined):** every gate references "artifact + critique + recommendation," but the **Gate Brief was never a defined artifact.** Three ventures, three slightly different decision packages, inconsistent founder experience. → *Revision R-GATEBRIEF: formalize the **Gate Brief** as a first-class, fixed-schema artifact the Conductor assembles for every gate: {venture, current state→proposed state, evidence vs threshold, cost-to-date, reversibility class, Conductor recommendation, critic tier + critique, one-line "why now"}. Uniform, scannable, logged.*
- **DEFECT X5 (Minor, scout cold-start):** Scout's KPI "≥30% of advanced ideas survive validation" can't be computed until weeks of completed validations exist. → *Revision: Scout's KPI is evaluated on a **trailing window** and explicitly disabled for the first ~6 completed validations (cold-start grace). Calibration report notes "insufficient data" rather than flagging Scout as broken.*

---

## 5. Revision Register (architecture v1.0 → v1.1)

| ID | Severity | Defect | Revision | Lands in |
|---|---|---|---|---|
| R-REDACT | **Critical** | PII embedded + cloud-routed via retrieval | Mandatory redaction at CHECKPOINT; raw PII in local-only sidecar; `contains_pii` hard-blocks cloud adapters | Conductor §, Memory §, Capability(Librarian) |
| R-PRECOMMIT-SCAN | **Critical** | Redaction relies on capability behavior | Deterministic PII/secret scanner at every CHECKPOINT (defense in depth) | Conductor § |
| R-PIVOT | **Critical** | No pivot path → zombie ventures | Pivot = KILL-and-FORK with asset inheritance; 1 fork/lineage; fork re-enters at FRAMED | Lifecycle, Conductor, Founder Manual |
| R-ALUMNI-CEILING | Major | Alumni maintenance is the true scaling ceiling | Hard cap on concurrent HARVEST alumni (≤3); graduation gated on alumni capacity | Lifecycle, Portfolio, Founder Manual |
| R-PARTNERS | Major | Design-partner recruitment unowned | Recruitment sub-workflow starts in SHAPING; Growth drafts from warm validation leads; `partners.md` artifact | Workflows, Capability(Growth), Founder Manual |
| R-EVIDENCE-GATE | Major | Quote-count kill vs experiment timing contradiction | Split VALIDATING into Evidence sub-gate + Experiment sub-gate | Lifecycle, Conductor, Capability(Analyst) |
| R-ENVELOPE | Major | Per-spend RED = approval fatigue | Spend envelope: authorize cap once (RED); within-cap spends YELLOW; breach re-RED | Governance, Conductor, Founder Manual |
| R-CHARGE | Major | Billing-go-live bundled into deploy | Enabling billing is a distinct two-key RED action | Governance, Conductor |
| R-SLOT-GATE | Major | Express advance could grab scarce slots mid-week | Express advance forbidden for slot-consuming transitions | Lifecycle, Conductor, Founder Manual |
| R-SHAPING-WIP | Major | SHAPING unbounded → spec rot | SHAPING WIP = 1; overflow → PARKED-SHOVEL-READY | Lifecycle, Conductor, Portfolio |
| R-EVIDENCE-TTL | Major | Validated evidence decays while waiting for slot | Evidence TTL (60d); stale shovel-ready re-confirms before BUILD | Lifecycle, Conductor |
| R-CLOCK | Major | Deadline clock ignores setup latency | Deadline starts at `experiment_live_at`, not state entry | Conductor, Lifecycle |
| R-ACTIVE-TIME | Major | Deadlines tick during outages → false kills | Deadlines in factory-active time; Conductor pauses clocks | Conductor |
| R-SEND-BUDGET | Major | ≤25/venture × N = founder overload | Single founder-wide daily send budget (≤40), Conductor-allocated | Governance, Founder Manual, Capability(Growth) |
| R-CRITIC-DEGRADE | Major | Cross-model critic deadlocks on free tier | Degraded critic ladder; tier-3 deterministic always available; tier logged | Conductor, Capability(Critic) |
| R-OVERRIDE-LOG | Major | Admission/advance overrides untracked | All founder overrides logged + in calibration report | Conductor, Governance, Founder Manual |
| R-OMW-LEDGER | Major | ONE-MORE-WEEK "tracked" but no store | OMW grants are ledger events; Conductor checks ledger | Conductor, Lifecycle |
| R-SALVAGE-TYPES | Major | Is a negative lesson a valid asset? | Enumerate salvage types; anti-patterns are first-class salvage | Lifecycle, Capability(Librarian), Founder Manual |
| R-GATEBRIEF | Minor | Gate decision package undefined | Formalize Gate Brief fixed schema | Conductor, Founder Manual |
| R-OUTREACH | Major | Send timing tied to wrong block / timezone | Sends are a separate scheduled, timezone-aware block | Founder Manual, Conductor |
| R-REACH-HYP | Minor | Reachability scored as evidence at FRAMED | Reachability is a hypothesis; first validation checkpoint tests it | Capability(Scout), Lifecycle |
| R-SCOUT-COLDSTART | Minor | Scout KPI uncomputable early | Trailing-window KPI; cold-start grace (~6 validations) | Capability(Scout) |
| R-STRANGER | Minor | "5 strangers" conflates warm partners | BUILDING exit = design partners; stranger test = LAUNCHED | Lifecycle |

### Updated lifecycle (v1.1) — changes only
```
... VALIDATING ──[Evidence sub-gate]──[Experiment sub-gate]──► SHAPING(WIP=1) ──► BUILDING ...
        │                                                          │
  PARKED-SHOVEL-READY ◄── overflow if SHAPING busy (carries Evidence TTL)
LAUNCHED ──(pivot)──► KILL-and-FORK ──► new venture at FRAMED (forked_from, inherits audience)
EARNING ──► GRADUATED  [gated on alumni-capacity ≤3 HARVEST]
All deadlines: factory-active time, from experiment_live_at. All PII: redacted at CHECKPOINT.
```

---

## 6. Severity tally & verdict
- **Critical: 3** (PII leak via retrieval, deterministic scan backstop, missing pivot path) — all would have caused real damage (data exfiltration; corrupted venture state) and none were visible in the operating model until traced.
- **Major: 16.** **Minor: 4.** Total **23 defects** found *before a line of code.*
- The architecture's *bones* survived — the state machine, Conductor-as-chokepoint, governance classes, tiered memory all held. Every defect was a **gap or an underspecification at a seam**, not a wrong primitive. That is the best possible stress-test outcome: the design is structurally sound and the fixes are additive (new sub-gates, new artifacts, tighter rules), not foundational rewrites.
- **The single most important discovery:** governance inspected the *action* path (spend/deploy/send) but not the *retrieval* path — PII could leave via memory even though every explicit action was gated. v1.1 closes this with redaction + a deterministic scan. **Any system that gates actions but not retrieval has this hole; finding it on paper is the entire point of this exercise.**

**v1.1 is implementation-ready once Documents 1–3 (which already incorporate this register) are accepted.**
