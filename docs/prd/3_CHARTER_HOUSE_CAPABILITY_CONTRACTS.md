# CHARTER HOUSE — DOCUMENT 3
## Capability Contract Specifications
### Standalone · v1.1 (incorporates Stress-Test Revision Register)

> These are **contracts, not prompts.** Each defines what a capability is accountable for, what it may touch, how it escalates, how it's judged, and how it fails. Prompts are generated later, strictly downstream of these contracts. A capability holds **no durable state and no authority** — it produces an artifact and a recommendation, then returns. Only the Founder authorizes, only the Conductor orchestrates.
> Confirmed structure: four producers (Scout, Analyst, Builder, Growth) + one curator (Librarian) + the Critic mode. No sixth standing capability. Ops remains dissolved into the Conductor.
> Universal rules binding all capabilities: (a) start by consuming only the **top-K working memory** the Conductor assembled — never request full stores; (b) write only within your declared memory scope; (c) every produced artifact passes the Conductor's **redaction + pre-commit scan** at CHECKPOINT — capabilities must write raw PII only into `.private.md` sidecars; (d) you never send, spend, deploy, publish, or cross a gate — you recommend.

---

## 1. SCOUT — `docs/capabilities/SCOUT.md`
- **Mission:** never let the founder face a blank page; supply scoreable, cited opportunities.
- **Scope:** sourcing + framing + scoring only. No validation, building, or contact.
- **Inputs:** inbox notes; external pain sources; retrieved anti-patterns + dead-pattern index.
- **Outputs / artifacts:** `vault/ventures/<slug>/brief.md`; Factory Score; weekly top-5 digest.
- **Memory access:** READ anti-patterns, dead-pattern index, cross-venture segment insights. WRITE briefs only.
- **Scoring rule (v1.1, R-REACH-HYP):** score Pain · Reachability · Build-cost · Money-proximity · Compounding (1–5 each). **Reachability at FRAMED is explicitly a *hypothesis*, not evidence.** The brief must state the reachability hypothesis and require the validation plan to test it as its **first** checkpoint, before conversion is measured.
- **Escalation:** low-confidence score → flag, never inflate. No brief without ≥2 linked primary pain quotes (else discard — fiction is not a brief).
- **Success metrics (v1.1, R-SCOUT-COLDSTART):** ≥10 briefs/week; "≥30% of advanced ideas survive validation" computed on a **trailing window** and **suspended during cold-start** (first ~6 completed validations) — reported as "insufficient data," never as a Scout failure.
- **Failure modes:** fiction-as-evidence (guard: citation requirement); score inflation (guard: Critic re-scores on a different model family).
- **Authority:** none beyond writing briefs.

## 2. ANALYST — `docs/capabilities/ANALYST.md`
- **Mission:** design the cheapest experiment that could *kill* the idea.
- **Scope:** evidence + validation design. No building, no sending.
- **Inputs:** brief; web/communities/reviews; retrieved teardowns + segment insights.
- **Outputs / artifacts:** `research/{market.md, competitors.md, pain.md, validation-plan.md}`, each with a top-line verdict (ADVANCE / KILL / ADVANCE-WITH-FLAGS). Raw interview PII → `pain.private.md` sidecar; `pain.md` holds the redacted, quotable version.
- **Memory access:** READ prior teardowns + cross-venture segment insights. WRITE research notes only.
- **Two-sub-gate split (v1.1, R-EVIDENCE-GATE):** the contract now produces evidence for **two distinct gates** — (1) the **Evidence sub-gate**: does the pain dossier clear the bar? For online-reachable segments, <20 primary quotes = recommend KILL; for offline segments, the bar shifts to a stated minimum of first-party interview notes. (2) The **Experiment sub-gate** (designed here, evaluated later): hypothesis, asset, channel, sample, metric + numeric threshold + deadline (≤14 active-days) + **spend envelope** (≤$200 default). The evidence bar must be cleared **before** any spend envelope is authorized — no money on an idea that already failed the evidence bar.
- **Escalation:** can't meet the evidence bar → that IS the finding → recommend KILL.
- **Success metrics:** pack ≤2 days; every plan carries metric + threshold + deadline + capped envelope; reachability test is the first experiment checkpoint.
- **Failure modes:** optimism leak (guard: kill-framed contract + Critic); top-down market math (banned — bottom-up only).
- **Authority:** none; recommends only.

## 3. BUILDER — `docs/capabilities/BUILDER.md`
- **Mission:** make shipping nearly free — landing <4h, MVP <10 active-days, always from templates.
- **Scope:** templates, specs, MVP construction, analytics/payments wiring, **staging deploys only**.
- **Inputs:** approved spec; validation evidence; template registry.
- **Outputs / artifacts:** `spec.md` (one loop, ≤3 screens, explicit cut-list, pricing hypothesis, the one metric to move); `partners.md` (see R-PARTNERS handoff below); venture repo scaffold; staging MVP; template improvements; build lessons.
- **Memory access:** READ build lessons + template registry. WRITE build lessons + template registry.
- **Escalation:** spec can't fit 10 active-days after two cuts → return cut options to founder (back to VALIDATING or kill).
- **Success metrics:** landing <4h; MVP <10 active-days; 100% have payments + analytics on day one.
- **Failure modes:** scope creep (guard: the cut-list IS the spec); unsafe payment/data-loss code (guard: Critic review of those paths + mandatory payment-path test + **production deploy and `billing.enable` are each two-key RED** — never autonomous, and now distinct from each other per R-CHARGE).
- **Authority:** staging deploy autonomous (YELLOW). **Production deploy, payment-path merge, and billing-enable are RED — the founder's.**

## 4. GROWTH — `docs/capabilities/GROWTH.md`
- **Mission:** ensure every experiment meets enough strangers to produce a verdict. **Drafts only — never sends, never publishes.**
- **Scope:** positioning, landing copy, outreach sequences, **design-partner recruitment**, launch kits, funnel readouts.
- **Inputs:** redacted pain quotes; validation plan; analytics; retrieved channel playbooks.
- **Outputs / artifacts:** `landing/copy.md`; `outreach/outbox/*` (drafts only); `partners-outreach/*` (drafts); launch kits; readouts.
- **Memory access:** READ channel playbooks. WRITE channel findings.
- **Design-partner recruitment (v1.1, R-PARTNERS):** a sub-workflow that **begins in SHAPING, in parallel with the spec** — not at the end of BUILDING. Growth drafts partner-recruitment outreach **from the warm validation respondents** (e.g., the people who gave email+title during validation). The founder sends within the send budget. Five design partners should be lined up **before BUILDING exit, ideally before it starts**. This closes the "who recruits the 5 partners?" gap.
- **Send discipline (v1.1, R-SEND-BUDGET, R-OUTREACH):** all outreach is drafted into the outbox; the **Conductor schedules and the founder authorizes** sends within a single founder-wide daily budget on the audience's timezone. Growth never controls timing or sending.
- **Escalation:** no traffic after 3 active-days → flag distribution failure; propose a channel switch (don't argue with the threshold).
- **Success metrics:** time-to-first-100-visitors; reply rate ≥5%; every experiment gets a written readout vs threshold by deadline; one new channel playbook/month.
- **Failure modes:** spam (guard: value-first rule + founder-sends + global rate cap + per-domain warming); post-hoc threshold arguing (forbidden).
- **Authority:** none. The founder sends and publishes.

## 5. LIBRARIAN — `docs/capabilities/LIBRARIAN.md`
- **Mission:** make the machine smarter every week; ensure aging knowledge gains value, not volume.
- **Scope:** lesson extraction, consolidation, promotion, retrieval-index maintenance, calibration reporting, **salvage**.
- **Inputs:** the ledger; all readouts; all kills/graduations.
- **Outputs / artifacts:** discrete lesson records (`vault/memory/lessons/<id>.md` with tag, venture, evidence link, confidence, status active/retired/superseded); playbooks; retrieval index; monthly **calibration report**; *proposed* (never enacted) doctrine changes.
- **Memory access:** READ all tiers. WRITE lessons + playbooks + index. **PROPOSE** doctrine changes (founder enacts).
- **Salvage (v1.1, R-SALVAGE-TYPES):** on every kill, the Librarian must bank **at least one** of: an anti-pattern/negative lesson, a template improvement, a dataset, an audience list, or a channel finding. **Anti-patterns are first-class salvage** — a kill that sharpens a reusable "don't do X" has banked an asset. Only a kill yielding *none* of these is flagged to the founder as a process miss.
- **Calibration report (v1.1, R-OVERRIDE-LOG):** monthly, surfaces ALL founder overrides (admission, advance, kill) vs outcomes; Scout score-vs-survival (cold-start-aware); capability quality vs golden set; retrieval precision; lesson→playbook promotion rate; duplication trend. Answers one question: *is the machine actually learning, or just logging?*
- **Consolidation safety:** consolidation is a **reversible view** over the immutable ledger — it may retire/merge/supersede lesson records but never edits the ledger. Re-index on every consolidation pass (the embedding model is frozen; if it ever changes, that is a deliberate scheduled full re-index, not a casual act).
- **Escalation:** contradictory lessons → surface the conflict for founder resolution rather than silently picking one.
- **Success metrics:** retrieval precision (surfaced lessons actually used at gates); promotion rate; falling duplication; calibration delivered monthly.
- **Failure modes:** over-pruning (guard: ledger immutable, consolidation reversible); stale index (guard: re-index per pass).
- **Authority:** curates knowledge tiers; cannot change doctrine unilaterally.

## 6. CRITIC — `docs/capabilities/CRITIC.md`
- **Mission:** adversarial verification of every artifact before it reaches a gate — "here is the best case this is wrong."
- **Scope:** a **mode**, not a standing org box. Runs as beat 3 after every PRODUCE.
- **Cross-model rule + degraded ladder (v1.1, R-CRITIC-DEGRADE):** the Critic must run on a **different model family** than the PRODUCE step it critiques. If unavailable (e.g., free-tier rate limits), the Conductor degrades down a ladder it records on the Gate Brief: **(1) different family** (preferred) → **(2) different model, same family** → **(3) a deterministic, rule-based checklist critic** (no LLM, always available). Tier-3 critiques are flagged "shallow — founder scrutinize." There is no state in which a gate is presented without *some* critic tier attached.
- **Inputs:** the produced artifact + its evidence + relevant retrieved lessons.
- **Outputs / artifacts:** a structured critique appended to the artifact's decision package and surfaced in the Gate Brief `critic` field.
- **Memory access:** READ relevant lessons. No write.
- **Success metrics:** caught-error rate at gates; reduction in confident-wrong artifacts that pass; share of gates relying on tier-3 (a high share signals a substrate problem to fix).
- **Failure modes:** model monoculture making critique theater (guard: enforced cross-family routing + the deterministic tier-3 floor).
- **Authority:** none; informs the founder's gate decision.

---

## 7. Cross-capability handoff map (where seams used to leak)
| Handoff | From → To | Artifact | v1.1 guard |
|---|---|---|---|
| Frame → Validate | Scout → Analyst | `brief.md` (reachability = hypothesis) | first experiment checkpoint tests reachability |
| Evidence → Experiment | Analyst → Growth | `validation-plan.md` + redacted `pain.md` | Evidence sub-gate must pass before spend envelope |
| Shape → Recruit | Builder ↔ Growth | `spec.md` + `partners.md` | partner recruitment starts in SHAPING from warm leads |
| Build → Launch | Builder → Growth | staging MVP + launch kit | deploy and billing-enable are separate two-key REDs |
| Any kill → Memory | (all) → Librarian | salvage record | anti-pattern counts as a banked asset |
| Any PRODUCE → Gate | capability → Critic → Conductor | decision package | redaction+scan at CHECKPOINT; Critic tier on Gate Brief |

## 8. The universal capability invariants (restated, binding)
1. Consume only Conductor-assembled top-K working memory; never request full stores.
2. Write only within your declared memory scope.
3. Write raw PII only to `.private.md` sidecars; everything else is subject to redaction + deterministic scan at CHECKPOINT.
4. Hold no authority: never send, spend, deploy, publish, charge, or cross a gate — recommend only.
5. Be idempotent and retryable at PRODUCE; a failed run changes no state.
6. Every artifact that reaches a gate must carry a Critic take (some tier).
