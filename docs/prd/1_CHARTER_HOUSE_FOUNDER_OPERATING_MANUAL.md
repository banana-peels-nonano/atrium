# CHARTER HOUSE — DOCUMENT 1
## Founder Operating Manual
### Standalone · v1.1 (incorporates Stress-Test Revision Register)

> Audience: the Founder, operating Charter House daily. This is the human-facing contract: what you do, what you decide, what you approve, and how much time it costs. The Conductor runs the machine; **your job is judgment, not operation.**
> v1.1 changes folded in from Document 4: spend envelopes (R-ENVELOPE), separate billing approval (R-CHARGE), founder-wide send budget + timezone send block (R-SEND-BUDGET, R-OUTREACH), pivot = kill-and-fork (R-PIVOT), alumni capacity ceiling (R-ALUMNI-CEILING), design-partner recruitment (R-PARTNERS), no express-advance into scarce slots (R-SLOT-GATE), override logging (R-OVERRIDE-LOG), enumerated salvage types (R-SALVAGE-TYPES), the Gate Brief (R-GATEBRIEF).

---

## 1. The founder's role in one paragraph
You read triaged briefs and pull levers at gates. You do **not** research, write copy, or write code — capabilities do that, the Conductor orchestrates it, and the ledger records it. You hold five things no machine may touch: **the gut-yes** (admit an idea), **the cut-list** (what the MVP excludes), **the verdict** (advance/kill), **the price** (what to charge), and **the send button** (who gets contacted). Target time: **~45–75 min/day**, spiking on Fridays.

## 2. The five levers you alone control
| Lever | Where | What it authorizes |
|---|---|---|
| **Gut-yes** | FRAMED → VALIDATING | Admit an idea into a scarce validating slot |
| **Cut-list** | SHAPING | Decide what the MVP deliberately excludes |
| **Verdict** | every gate (esp. Friday) | Advance, kill, or one-more-week |
| **Price** | EARNING | Set/raise/lower what customers pay |
| **Send/Publish** | any outreach, launch, billing-go-live | Authorize contact with real people / charging money |

Everything else is the machine's. If you find yourself doing research or writing copy, the machine has failed and that is a bug to file, not work to absorb.

## 3. The Gate Brief — the only thing you read to decide
Every gate decision is presented as a **Gate Brief** (fixed schema, assembled by the Conductor). You never hunt through files to decide. A Gate Brief always contains:
1. Venture + current state → proposed state
2. Evidence vs threshold (the numbers, plainly)
3. Cost-to-date (inference + real spend)
4. Reversibility class (GREEN/YELLOW/RED, and whether two-key)
5. Conductor's mechanical recommendation
6. The **Critic's** adversarial take + which critic tier produced it (tier-3 = "shallow, scrutinize")
7. One line: "why now"

If a Gate Brief is missing its Critic section, **do not decide** — the Conductor is required to attach one (even a deterministic tier-3 critique). A naked artifact is not a decision package.

---

## 4. Daily workflow — "The Morning Block" (~30–45 min, India morning)
| Step | What | You decide | Approvals |
|---|---|---|---|
| 1 | Read the **Daily Brief** (Conductor triages to the 2–3 things needing a human today) | nothing yet | — |
| 2 | Clear the **RED queue**: spend authorizations, deploy approvals, billing-go-live, pivot decisions | approve / hold / edit | RED tokens |
| 3 | Review the **send batch** the Conductor has staged for today (see §5) and approve it | which sends go | RED (batch) |
| 4 | Glance the **board**: each active venture's gate, deadline (in active-time), days-left, flags | note off-track | — |
| 5 | Capture new signals into inbox (optional) | — | — |

If the Daily Brief surfaces nothing RED and nothing off-track, the block can be <10 minutes. **Silence is a valid, healthy outcome** — async work is in flight.

## 5. The Send Block — decoupled from the morning (R-OUTREACH, R-SEND-BUDGET)
Outreach to US/EU audiences must land in *their* morning, which is your evening. So sending is a **separate, timezone-aware block**, not part of the decision morning-block.
- The Conductor stages approved sends into a queue scheduled for the **audience's** timezone, within a single **founder-wide daily send budget (default ≤40 sends/day across ALL ventures)** — not 25 per venture. The Conductor allocates the budget to active experiments by priority.
- In your morning block you **approve the day's batch**; the send-assist releases them on the audience's schedule. You authorize; you do not babysit. Drafts always come from Growth's outbox — you never compose, but the send is your authorized act.
- Domain reputation is protected by the global cap and per-domain warming status the Conductor tracks.

## 6. Weekly workflow
- **Mon–Thu:** morning blocks + approving the daily send batch.
- **Friday = Kill Day** (§9). The core ritual.
- **Sunday (optional, 15 min):** brain-dump signals → Scout sweeps them for Monday.
- Weekly time: **~5–7 hrs**, front-loaded into Friday.

## 7. Monthly workflow (~90 min, first Friday)
- Read the **Calibration Report** (Librarian): your overrides vs outcomes (admission, advance, AND kill overrides are all logged now — R-OVERRIDE-LOG), Scout score vs survival (cold-start-aware), capability quality vs golden set.
- Read **METRICS** trend; answer one question — *where is the jam: sourcing, traffic, or conversion?* Fix only that.
- Confirm backlog hygiene (park/archive sweep) and re-rank the top-K backlog.
- **Alumni check (R-ALUMNI-CEILING):** count HARVEST alumni. If at the cap (≤3), no new venture may graduate until one is EXITED or made genuinely low-touch.

## 8. Quarterly workflow (~half day)
- **Doctrine review:** any playbook earned promotion? Any doctrine line contradicted by evidence?
- **Substrate review:** run the golden-set against current models; re-route via config if a better $/quality option exists (config-only). Decide hardware/budget tier changes.
- **Alumni review:** each alumnus → SCALING / HARVEST / EXITED. Enforce the no-zombie rule and the ≤3 cap.
- **Portfolio P&L:** asset base, alumni cash, factory cost.

## 9. Friday Kill Day (~2–3 hrs) — the core ritual
1. Conductor produces the **Kill-Day Brief**: every active venture as a Gate Brief + mechanical recommendation (KILL / ADVANCE / ONE-MORE-WEEK).
2. For each, read the artifact **and its Critic take side-by-side**. Issue the verdict. **Default = KILL. Inconclusive = FAIL.**
3. **Every KILL triggers salvage before archival.** Salvage is satisfied by ANY of (R-SALVAGE-TYPES): an anti-pattern/negative lesson, a template improvement, a dataset, an audience list, or a channel finding. A kill that yields *none* of these is flagged as a process miss.
4. Advances free/consume slots; the Conductor admits the top shovel-ready/backlog venture into any freed slot.
5. **ONE-MORE-WEEK** is max one per venture *ever* — enforced by the ledger (R-OMW-LEDGER), not your memory. The Conductor will refuse a second.
6. **Overrides are allowed but logged with reasons** and reviewed monthly. Overriding a KILL into a survival is the most-watched signal of founder optimism.
> **Kills happen only on Friday.** Advances may happen Friday or mid-week via **express advance** — but express advance is **forbidden for any transition that consumes a scarce slot** (admitting to VALIDATING, entering BUILDING). Those always wait for a deliberate, slot-aware gate (R-SLOT-GATE).

## 10. Venture review workflow (on demand)
Open the venture's folder: brief → research → validation readout → spec → partners → build status, all linked from the venture record, Critic pass always attached. Decision artifacts you may issue here: approve spec, approve cut-list, approve the design-partner recruitment batch.

## 11. Venture launch workflow (LAUNCHED)
1. Builder confirms the MVP is stranger-usable (payments wired, analytics live, 5 **design partners** — warm, from your validation respondents — passed the loop).
2. Growth presents **launch-kit drafts** (PH/HN/directories/communities, scheduled order, first-comment replies) on an India-timezone schedule covering US-morning/EU-afternoon.
3. You **publish/send personally** (RED). Nothing auto-publishes.
4. **Enabling billing is a separate two-key RED action** (R-CHARGE) — deploying the build and turning on charging are distinct approvals. You can have a live MVP before you flip billing on.
5. Gate: ≥10 activated + payment-intent → EARNING; else kill or pivot.

## 12. The pivot decision (R-PIVOT) — new in v1.1
When a launched venture misses its bar but the market is telling you to build something adjacent, you do **not** quietly redirect the build (that creates a zombie with corrupted metrics). You **pivot = kill-and-fork**:
- The current venture is **KILLED** (assets, audience, and lessons salvaged).
- A **new venture is auto-created at FRAMED**, inheriting the prior audience list and validated segment via a `forked_from` link — so the warm audience transfers but the new value prop is re-scored as the new hypothesis it is.
- **One fork per lineage.** A second pivot of the same lineage must clear a fresh full validation — no endless pivot-zombies.
- The fork re-enters the ranked backlog (its inherited audience shows up as higher Reachability); it does not jump the queue.

## 13. Spending — the envelope model (R-ENVELOPE)
You authorize a **capped budget once** per experiment (RED token). Individual spends within that cap are automatic and logged (YELLOW), so you are not approving every $10 ad charge. The moment a spend would **breach the envelope**, the Conductor stops and asks you again (RED). Real money leaving is always either a fresh envelope or a breach approval — never silent.

## 14. The 30-day mental simulation (v1.1)
- **Days 1–2:** dump 20+ signals; Scout returns scored briefs; gut-admit 3. Morning blocks ~40 min. Any admission below the score bar is logged as an override.
- **Days 3–7:** Analyst packs land (each clears an Evidence sub-gate before any money is spent). You authorize spend *envelopes*, and approve daily *send batches* in your evening block on the audience's clock. First Friday Kill Day on day 7 regardless.
- **Days 8–21:** verdicts arrive in active-time. ~2 of 3 die; each banks an asset (including pure anti-patterns). One survivor enters SHAPING (WIP=1) — and you also approve the **design-partner recruitment batch** drawn from its warm validation leads.
- **Days 22–30:** survivor builds; you approve the production deploy (two-key) and, separately, billing-go-live. You publish the launch kit personally. Day-30 trophy: strangers on a deployed MVP + a first payment-intent. Your time: ~1 hr/day, Friday spikes.
- **Throughout:** you never opened a research tab, wrote copy, or touched code, and no PII left your machine. You read Gate Briefs, approved envelopes and send batches, and pulled five levers. That is the design working.

## 15. What you must never do (founder discipline)
- Never compose or send outreach the Conductor didn't stage from a Growth draft.
- Never advance a kill-recommended venture without logging why.
- Never pivot inside a build — always kill-and-fork.
- Never graduate past the alumni cap — exit one first.
- Never override the WIP *count* (you may choose *which* venture fills a slot; never how many).
- Never decide on a Gate Brief that lacks a Critic section.
