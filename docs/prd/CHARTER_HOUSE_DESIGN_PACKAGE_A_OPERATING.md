# CHARTER HOUSE — DESIGN PACKAGE A
## Operating Specifications (Parts 1–5)
### Design Freeze · v1.0 · source material for Claude Code implementation

> Status: **DESIGN FREEZE**. This package and Package B (Infrastructure & Build) together constitute the complete pre-implementation design. No code, prompts, scripts, or repo files are produced here — these are **specifications and contracts**.
> Repository root (frozen): `K:\the_charter_house`
> Storage law (frozen): all software, models, caches, databases, vector stores, embeddings, logs, and assets live on `K:\` wherever Windows permits. `C:\` is constrained storage, used only where an installer or Windows component cannot be relocated (each such case is justified explicitly in Package B).
> Inherited and not re-argued: model/provider abstraction, neutral capability specs, routing layer, retrieval-based memory, OpenCode-first harness, local/cloud hybrid, future-proofing, and the v2 operating model (state-machine-over-ventures; five primitives; Conductor + Founder; GREEN/YELLOW/RED governance).

---

# PART 1 — Design Package Inventory (the document map)

This is the canonical list of every Markdown document that must exist before and during implementation. Claude Code will consume the **design docs** (this package) and **create the operational docs** (those marked *Owner: Claude Code*) during build. Filenames are relative to `K:\the_charter_house\`.

**Priority key:** P0 = must exist before any build · P1 = needed for first venture loop · P2 = needed at portfolio scale · P3 = polish/optional.

### 1.1 Doctrine & top-level
| # | Filename | Purpose | Depends on | Owner | Priority |
|---|---|---|---|---|---|
| D1 | `docs/00_DOCTRINE.md` | The one-page constitution (Part 1 of operating model). Supreme authority. | — | Architect | **P0** |
| D2 | `docs/01_OPERATING_MODEL.md` | The v2 operating model (five primitives, lifecycle, governance summary). | D1 | Architect | **P0** |
| D3 | `docs/02_GLOSSARY.md` | Frozen vocabulary: Venture, Capability, Conductor, Ledger, gate, GREEN/YELLOW/RED, etc. | D1 | Architect | **P0** |
| D4 | `README.md` (root) | Entry point: what this repo is, how to read the docs, links to all specs. | D1–D3 | Claude Code | P1 |

### 1.2 Lifecycle, workflow, governance
| # | Filename | Purpose | Depends on | Owner | Priority |
|---|---|---|---|---|---|
| L1 | `docs/10_VENTURE_LIFECYCLE.md` | The state machine: states, transitions, entry/exit/kill criteria, metrics, owners. | D2 | Architect | **P0** |
| L2 | `docs/11_WORKFLOWS.md` | Per-state workflow definitions (5-beat skeleton, tasks, artifacts, approvals). | L1 | Architect | **P0** |
| G1 | `docs/12_GOVERNANCE.md` | Action-class policy (GREEN/YELLOW/RED), spend/deploy/outreach/legal/security controls, two-key rule. | D2 | Architect | **P0** |

### 1.3 Conductor & capabilities (contracts)
| # | Filename | Purpose | Depends on | Owner | Priority |
|---|---|---|---|---|---|
| C0 | `docs/20_CONDUCTOR_SPEC.md` | The engine contract: responsibilities, commands, transitions, event handling, workflow execution. (Part 3) | L1,L2,G1 | Architect | **P0** |
| C1 | `docs/capabilities/SCOUT.md` | Scout contract. | L2 | Architect | **P0** |
| C2 | `docs/capabilities/ANALYST.md` | Analyst contract. | L2 | Architect | **P0** |
| C3 | `docs/capabilities/BUILDER.md` | Builder contract. | L2 | Architect | **P0** |
| C4 | `docs/capabilities/GROWTH.md` | Growth contract. | L2 | Architect | **P0** |
| C5 | `docs/capabilities/LIBRARIAN.md` | Librarian contract (memory compounding). | L2,M1 | Architect | **P0** |
| C6 | `docs/capabilities/CRITIC.md` | Critic mode contract (cross-model verification). | L2 | Architect | **P1** |

### 1.4 Memory & knowledge
| # | Filename | Purpose | Depends on | Owner | Priority |
|---|---|---|---|---|---|
| M1 | `docs/30_MEMORY_ARCHITECTURE.md` | Tiered memory, ledger, retrieval, summarization, archival, promotion. (Part 5) | D2 | Architect | **P0** |
| M2 | `docs/31_LEDGER_SCHEMA.md` | Event types and record shape (specification, not code). | M1,C0 | Architect | **P1** |
| M3 | `docs/32_RETRIEVAL_SPEC.md` | Top-K retrieval policy: signals, weighting, freeze rules (embedding model is frozen). | M1 | Architect | **P1** |

### 1.5 Portfolio & founder
| # | Filename | Purpose | Depends on | Owner | Priority |
|---|---|---|---|---|---|
| P1d | `docs/40_PORTFOLIO.md` | Registry-as-view, WIP, prioritization, graduation, archival, scale behavior. | L1 | Architect | P1 |
| F1 | `docs/50_FOUNDER_MANUAL.md` | Daily/weekly/monthly/quarterly/kill-day/review/launch workflows. (Part 2) | L1,L2,G1,C0 | Architect | **P0** |

### 1.6 Infrastructure (full content in Package B)
| # | Filename | Purpose | Depends on | Owner | Priority |
|---|---|---|---|---|---|
| R1 | `docs/60_REPOSITORY_STRUCTURE.md` | Canonical filesystem layout under `K:\the_charter_house`. (Part 6) | all P0 | Architect | **P0** |
| I1 | `docs/61_LOCAL_AI_STACK.md` | Local AI infra: serving, embeddings, vector store, paths. (Part 7) | — | Architect | **P0** |
| I2 | `docs/62_MODEL_STRATEGY.md` | Model stacks A/B/C, roles, VRAM/RAM, quant. (Part 8) | I1 | Architect | **P0** |
| I3 | `docs/63_DEV_ENVIRONMENT.md` | Required software, mandatory vs optional, install paths, disk. (Part 9) | I1,I2 | Architect | **P0** |
| I4 | `docs/64_INSTALLATION_GUIDE.md` | Fresh-Windows → operational, step-by-step. (Part 10) | I1,I2,I3,R1 | Architect | **P0** |
| RM | `docs/70_IMPLEMENTATION_ROADMAP.md` | Build order for Claude Code, phases 1–4. (Part 11) | all | Architect | **P0** |

### 1.7 Operational docs Claude Code generates during build (not authored now)
| Filename | Purpose | Owner | Priority |
|---|---|---|---|
| `AGENTS.md` (root) | Harness-neutral constitution pointer (generated from D1/D2). | Claude Code | P1 |
| `vault/PIPELINE.md` | Daily board (projection from ledger). | Conductor | P1 |
| `vault/playbooks/LESSONS_INDEX.md` | Index of discrete lesson records. | Librarian | P1 |
| `data/metrics/METRICS.md` | Weekly factory metrics (projection). | Conductor | P1 |
| `templates/*` | Landing + saas-starter (built, not designed here). | Builder | P1 |

**Total design documents to author in this freeze: 26** (D1–D4, L1–L2, G1, C0–C6, M1–M3, P1d, F1, R1, I1–I4, RM). Packages A and B contain the full content for all of them; when implementation begins, Claude Code splits this content into the individual files above. The split is mechanical — the *content is frozen here*.

---

# PART 2 — Founder Operating Manual
### (`docs/50_FOUNDER_MANUAL.md`)

The design intent: **the founder's job is judgment, not operation.** The Conductor runs the machine; the founder reads triaged briefs and pulls levers at gates. Target total active time: **~45–75 min/day**, concentrated in a morning decision block.

### 2.1 The daily workflow — "The Morning Block" (~30–45 min)
| Step | What | Artifact reviewed | Decision | Approvals |
|---|---|---|---|---|
| 1 | Read the **Daily Brief** (Conductor-generated, triaged to the 2–3 things that need a human today). | `vault/PIPELINE.md` + brief | none yet | — |
| 2 | Clear the **RED queue**: outreach drafts to send, spends to authorize, deploys to approve. | outbox drafts, spend requests | send / hold / edit | **RED tokens** |
| 3 | Glance the **active board**: each active venture's gate, deadline, days-left, flags. | board | note anything off-track | — |
| 4 | Optional: **capture** new signals into inbox (phone/desktop). | inbox notes | — | — |

The founder does **not** do research, write copy, or code. If the brief surfaces nothing RED and nothing off-track, the morning block can be <10 minutes. **Silence in the brief is a valid outcome** — it means the machine is healthy and async work is in flight.

### 2.2 The weekly workflow
- **Mon–Thu:** morning blocks only. Manual outreach sends (≤25/day/idea) happen here, founder-initiated from the outbox.
- **Friday = Kill Day** (see 2.5). The single most important ritual.
- **Sunday (optional, 15 min):** brain-dump signals into inbox; Scout sweeps them into briefs for Monday.
- Weekly time: **~5–7 hours total**, front-loaded into Friday.

### 2.3 The monthly workflow (~90 min, first Friday)
- Review the **Calibration Report** (Librarian): founder overrides vs outcomes, Scout score vs survival rate, capability quality vs golden set.
- Review **METRICS** trend (throughput, cost-per-verdict, kill ratio, MRR by alumni).
- Answer the one question: **where is the jam — sourcing, traffic, or conversion?** Fix only that.
- Backlog hygiene: confirm the Conductor's park/archive sweep; re-rank top-K backlog.

### 2.4 The quarterly workflow (~half day)
- **Doctrine review:** has any playbook earned promotion to doctrine? Has any doctrine line been contradicted by evidence? (Doctrine changes are rare and deliberate.)
- **Substrate review:** run the golden-set against current models; consider re-routing (config-only, per future-proofing). Decide on hardware/budget tier changes.
- **Alumni review:** each alumnus → SCALING / HARVEST / EXITED. Enforce the no-zombie rule.
- **Portfolio P&L:** total asset base, cash from alumni, cost of the factory.

### 2.5 Friday Kill Day workflow (~2–3 hours) — the core ritual
1. Conductor produces the **Kill-Day Brief**: every active venture with its gate, evidence vs threshold, and a mechanical recommendation (KILL / ADVANCE / ONE-MORE-WEEK — max one ever, tracked).
2. For each venture, founder reads the artifact **and its attached cross-model Critique side-by-side**, then issues the verdict. Default verdict is **KILL**. Inconclusive = FAIL.
3. **Every KILL triggers salvage** before archival: the Librarian extracts ≥1 lesson and identifies the reusable asset (template/dataset/audience/channel). A kill with no salvaged asset is flagged as a process miss.
4. Advances consume/free slots; the Conductor admits the top backlog venture into any freed validating slot.
5. Overrides of the mechanical recommendation are **allowed but logged with reasons** and reviewed monthly.
> Kills happen **only** here. Advances may also happen here, or mid-week via an **express advance gate** (advancing is low-risk; killing stays slow and ritualized).

### 2.6 Venture review workflow (per-venture, on demand)
Used when a venture needs a focused look (e.g., before a build decision). Founder opens the venture's vault folder: brief → research pack → validation readout → spec → build status, all linked from the venture record. The Critic's adversarial pass is always attached. Decision artifacts: approve spec / approve cut-list / approve graduate.

### 2.7 Venture launch workflow (Stage LAUNCHED)
1. Builder confirms MVP is stranger-usable (payments + analytics live, 5 design partners passed).
2. Growth presents the **launch kit drafts** (PH/HN/directories/communities posts, scheduled order, first-comment replies) + India-timezone schedule for US-morning/EU-afternoon.
3. Founder approves and **publishes/sends personally** (RED). Nothing auto-publishes.
4. Conductor tracks the funnel; Growth writes the onboarding readout at deadline.
5. Gate: ≥10 activated + payment-intent → EARNING; else kill path.

### 2.8 30-day mental simulation (what it feels like)
- **Days 1–2:** dump 20+ signals; Scout returns scored briefs; you gut-admit 3 into VALIDATING. Morning blocks ~40 min.
- **Days 3–7:** Analyst packs land; Growth drafts outreach; you *send* ≤25/day per idea from the outbox (the only "manual labor"). First Friday Kill Day on day 7 regardless of progress — the ritual installs.
- **Days 8–21:** experiments return verdicts. Expect ~2 of 3 to die — that's the machine working; each kill banks a lesson. One survivor enters SHAPING; you approve a spec; Builder builds; you approve the production deploy and payment merge (two-key RED).
- **Days 22–30:** survivor LAUNCHED; you personally publish the launch kit; activation measured. Day-30 trophy = strangers touching a deployed MVP and a first payment-intent signal. Your total time: ~1 hr/day, spiking on Fridays.
- **Throughout:** you never opened a research tab, wrote copy, or touched code. You read briefs, sent messages, and pulled levers. That is the design working.

---

# PART 3 — Conductor Specification
### (`docs/20_CONDUCTOR_SPEC.md`)

The Conductor is the **deterministic engine** (not an LLM). It is the single chokepoint through which all state changes and external effects pass. If the Conductor is sound, the factory's discipline is structurally guaranteed rather than dependent on any model behaving.

### 3.1 Responsibilities
1. **State-machine enforcement** — only legal transitions (per Lifecycle spec) may occur; illegal transitions are rejected.
2. **WIP enforcement** — hard-block admission past ≤3 validating / ≤1 building. The count is never overridable; only *which* venture fills a slot is the founder's choice.
3. **Workflow execution** — run each state's 5-beat workflow (PREPARE · PRODUCE · CRITIQUE · CHECKPOINT · GATE), invoking capabilities via the routing layer.
4. **Governance** — classify every proposed action GREEN/YELLOW/RED and enforce the policy (Part 8 / Governance spec). Hold RED actions until a founder token is presented.
5. **Event handling** — append every meaningful event to the Ledger; nothing of record happens off-ledger.
6. **Projection generation** — regenerate PIPELINE, METRICS, the Daily Brief, and the Kill-Day Brief from the ledger.
7. **Budget guard** — track inference spend; degrade routing tier past thresholds (per accepted routing layer).
8. **Retrieval assembly** — assemble per-task working memory via top-K retrieval (never dump full stores).
9. **Routing** — resolve role→model per config; handle failover (accepted substrate).

### 3.2 Command surface (conceptual — names, not implementations)
| Command | Effect | Class |
|---|---|---|
| `capture` | add a signal to inbox | GREEN |
| `frame` | run Scout's FRAMED workflow on captured signals | GREEN |
| `admit <venture>` | move FRAMED→VALIDATING if slot free + founder gut-yes | gate |
| `validate <venture>` | run Analyst+Growth VALIDATING workflow (drafts only) | GREEN/YELLOW |
| `experiment.spend <venture>` | authorize budget for a live experiment | **RED** |
| `experiment.send <venture>` | release approved outreach from outbox (founder action) | **RED** |
| `gate <venture>` | present artifact + critique; record ADVANCE/KILL/OMW | gate |
| `shape <venture>` | run Builder SHAPING workflow → SPEC | GREEN |
| `build <venture>` | run Builder BUILDING workflow (staging only) | GREEN/YELLOW |
| `deploy.prod <venture>` | production deploy (tagged) | **RED + two-key** |
| `launch <venture>` | present launch kit; founder publishes | **RED** |
| `graduate <venture>` | EARNING→GRADUATED; reopen build slot | gate |
| `kill <venture>` | move to KILLED; trigger salvage | gate (Fri) |
| `salvage <venture>` | Librarian extracts lesson + asset | GREEN |
| `pipeline` / `brief` / `killday` | regenerate projections | GREEN |
| `consolidate` | Librarian memory consolidation pass | GREEN |
| `calibrate` | monthly calibration report | GREEN |

### 3.3 State-transition handling
For each transition the Conductor checks, in order: (1) is the transition legal from the current state? (2) are WIP limits satisfied? (3) are entry criteria met (evidence present)? (4) is the required authorization class satisfied (gate token for transitions, RED token for external effects)? Only if all pass does it CHECKPOINT (write artifact + append event) and advance. Any failure → reject with a logged reason; venture stays put.

### 3.4 Approval-gate handling
- The Conductor **never** self-authorizes a gate or a RED action. It assembles the decision package (artifact + cross-model critique + recommendation + evidence-vs-threshold) and waits.
- A founder authorization is a discrete, logged token tied to a specific venture and action. Tokens are **single-use and non-standing** for the two-key set (production payment-path deploy, charging customers, scaled outreach).
- Denied or expired tokens → action dropped, logged.

### 3.5 Event handling & venture tracking
- Every venture is one registry record: id, codename, current state, score, timestamps, links to artifacts, and a pointer to its event stream.
- Every command outcome is an append-only event (see `31_LEDGER_SCHEMA.md`). The registry's "current state" is itself a projection — authoritative state can always be rebuilt by replaying events.
- The Conductor exposes the board (all ventures by state) and per-venture history purely as ledger projections.

### 3.6 Failure behavior (robust by construction)
- Capability (LLM) failure at PRODUCE/CRITIQUE → retry (idempotent); no state change; escalate one routing tier on repeated failure; if all fail, queue and notify founder.
- Provider/router failure → failover chain (accepted substrate); if exhausted, degrade to local/free; if none, factory pauses gracefully — the vault remains fully human-usable.
- The Conductor itself is deterministic and stateless between commands (state lives in the ledger), so a crash loses nothing: restart and replay.

---

# PART 4 — Capability Specifications (contracts)
### (`docs/capabilities/*.md`)

These are **contracts**, not prompts: what each capability is accountable for, what it may touch, and how it's judged. Prompts are generated later, downstream of these contracts. The five-producer + Librarian + Critic structure from the operating model **remains valid and is confirmed**; the only refinement at freeze is making memory-access scopes explicit (read/write boundaries) so the Conductor can enforce them.

### 4.1 SCOUT — `docs/capabilities/SCOUT.md`
- **Mission:** never let the founder face a blank page; supply scoreable, cited opportunities.
- **Scope:** sourcing + framing + scoring only. Does not validate, build, or contact anyone.
- **Inputs:** inbox notes, external pain sources, retrieved anti-patterns.
- **Outputs / artifacts:** `vault/ventures/<slug>/brief.md`, Factory Score, weekly top-5 digest.
- **Memory access:** READ anti-patterns + dead-pattern index + segment insights; WRITE briefs only. No write to lessons/doctrine.
- **Escalation:** low-confidence score → flag, never inflate; no brief without ≥2 linked primary quotes (else discard).
- **Success metrics:** ≥10 briefs/week; ≥30% of advanced ideas survive validation (calibration).
- **Failure modes:** fiction-as-evidence (guard: citation requirement), score inflation (guard: Critic re-scores on a different model).
- **Authority:** none beyond writing briefs. No gate, spend, deploy, or contact.

### 4.2 ANALYST — `docs/capabilities/ANALYST.md`
- **Mission:** design the cheapest experiment that could *kill* the idea.
- **Scope:** evidence + validation design. No building, no sending.
- **Inputs:** brief, web/communities/reviews, retrieved teardowns + segment insights.
- **Outputs / artifacts:** `research/{market.md, competitors.md, pain.md, validation-plan.md}` with a top-line verdict (ADVANCE / KILL / ADVANCE-WITH-FLAGS).
- **Memory access:** READ prior teardowns + cross-venture segment insights; WRITE research notes only.
- **Escalation:** can't find 20 real pain quotes → that is the finding → recommend KILL.
- **Success metrics:** pack ≤2 days; every plan has metric + numeric threshold + deadline (≤14d) + capped budget (≤$200 default).
- **Failure modes:** optimism leak (guard: kill-framed contract + Critic), top-down market math (banned).
- **Authority:** none; recommends only.

### 4.3 BUILDER — `docs/capabilities/BUILDER.md`
- **Mission:** make shipping nearly free — landing <4h, MVP <10 days, always from templates.
- **Scope:** templates, specs, MVP construction, analytics/payments wiring, staging deploys.
- **Inputs:** approved spec, validation evidence, template registry.
- **Outputs / artifacts:** `SPEC.md`, venture repo scaffold, deployed-to-staging MVP, template improvements, build lessons.
- **Memory access:** READ build lessons + template registry; WRITE build lessons + template registry.
- **Escalation:** spec can't fit 10 days → return cut options to founder.
- **Success metrics:** landing <4h; MVP <10 days; 100% have payments+analytics on day one.
- **Failure modes:** scope creep (guard: cut-list IS the spec), unsafe payment code (guard: Critic + payment-path test + **RED merge** + production = two-key).
- **Authority:** staging deploy autonomous; **production deploy and payment-path merge are RED — never autonomous.**

### 4.4 GROWTH — `docs/capabilities/GROWTH.md`
- **Mission:** ensure every experiment meets enough strangers to produce a verdict.
- **Scope:** positioning, copy, outreach sequences, launch kits, funnel readouts. **Drafts only.**
- **Inputs:** pain quotes, validation plan, analytics, retrieved channel playbooks.
- **Outputs / artifacts:** `landing/copy.md`, `outreach/outbox/*` (drafts), launch kits, readouts.
- **Memory access:** READ channel playbooks; WRITE channel findings.
- **Escalation:** no traffic after 3 days → flag distribution failure, propose channel switch.
- **Success metrics:** time-to-first-100-visitors; reply rate ≥5%; every experiment gets a written readout vs threshold.
- **Failure modes:** spam (guard: value-first rule + founder-sends + rate caps), arguing with the threshold post-hoc (forbidden).
- **Authority:** none. **Never sends, never publishes** — the founder does (RED).

### 4.5 LIBRARIAN — `docs/capabilities/LIBRARIAN.md`
- **Mission:** make the machine smarter every week; ensure aging knowledge gains value, not volume.
- **Scope:** lesson extraction, consolidation, promotion, retrieval-index maintenance, calibration reporting.
- **Inputs:** the ledger, all readouts, all kills/graduations.
- **Outputs / artifacts:** discrete lesson records, playbooks, retrieval index, monthly calibration report, proposed (not enacted) doctrine changes.
- **Memory access:** READ all tiers; WRITE lessons + playbooks + index; **PROPOSE** doctrine changes (founder enacts).
- **Escalation:** contradictory lessons → surface conflict for founder resolution.
- **Success metrics:** retrieval precision (surfaced lessons actually used); lesson→playbook promotion rate; falling duplication; "is the machine learning?" answered monthly.
- **Failure modes:** over-pruning (guard: ledger immutable, consolidation is a reversible view), stale index (guard: re-index on each consolidation).
- **Authority:** curates knowledge tiers; cannot change doctrine unilaterally.

### 4.6 CRITIC — `docs/capabilities/CRITIC.md`
- **Mission:** adversarial verification of every artifact before it reaches a gate.
- **Scope:** a **mode**, not a standing org box. Runs after every PRODUCE step.
- **Constraint (frozen):** must run on a **different model family** than the PRODUCE step it critiques. The Conductor refuses to present any artifact at a gate without an attached completed critique.
- **Inputs:** the produced artifact + its evidence.
- **Outputs / artifacts:** a "best case this is wrong" critique appended to the artifact's decision package.
- **Memory access:** READ relevant lessons; no write.
- **Success metrics:** caught-error rate at gates; reduction in confident-wrong artifacts passing.
- **Failure modes:** model monoculture making it theater (guard: enforced cross-family routing).
- **Authority:** none; informs the founder's gate decision.

> **Confirmed:** no sixth standing capability is added. Ops stays dissolved into the Conductor. This is the effectiveness-optimal set.

---

# PART 5 — Knowledge & Memory Architecture
### (`docs/30_MEMORY_ARCHITECTURE.md`, `31_LEDGER_SCHEMA.md`, `32_RETRIEVAL_SPEC.md`)

### 5.1 The governing principle (frozen)
**Memory consolidates like a mind, not a log.** Aging *promotes* knowledge upward through tiers, shedding volume while concentrating signal. Per-call cost stays flat because retrieval is top-K, never all-of-store. This permanently solves the LESSONS.md problem.

### 5.2 The tiers and storage map
| Tier | What it holds | Storage (under `K:\the_charter_house`) | Mutability |
|---|---|---|---|
| **Episodic — Ledger** | every event: transitions, experiment outcomes, gate decisions+rationale, spends, kills, graduations | `data/ledger/` (append-only event records) | immutable |
| **Raw research** | market/competitor/pain notes, evidence | `vault/ventures/<slug>/research/` | frozen once written; cited or deleted |
| **Lessons** | discrete records: tag, venture, evidence link, confidence, status(active/retired/superseded) | `vault/memory/lessons/<id>.md` | consolidated/retired/promoted |
| **Playbooks** | reusable patterns: channel/pricing/segment | `vault/memory/playbooks/` | versioned |
| **Doctrine** | crystallized truths (the one page + promoted laws) | `docs/00_DOCTRINE.md` | rare, founder-only |
| **Projections** | board, metrics, briefs, lesson index | `vault/PIPELINE.md`, `data/metrics/`, indexes | disposable, regenerable |
| **Vector index** | embeddings for retrieval | `K:\Data\charter_house\vectors\` (see Package B) | rebuildable; **embedding model frozen** |

### 5.3 What gets stored / summarized / archived / promoted
- **Stored verbatim:** events (ledger), raw research, experiment outcomes, customer quotes (PII stays local; see governance). Truth is never summarized away.
- **Summarized:** lessons are *distilled* from raw outcomes into one transferable sentence + metadata. Briefs and readouts summarize research for human reading. Summaries always link back to verbatim source.
- **Archived:** killed ventures → `vault/archive/` after salvage; stale backlog parked/archived monthly. Archived is **never deleted**.
- **Promoted:** a lesson independently re-derived across ≥N ventures → Playbook; a load-bearing universal playbook → *proposed* to Doctrine (founder enacts).

### 5.4 Retrieval architecture (`32_RETRIEVAL_SPEC.md`)
- **Assembly:** the Conductor builds per-task working memory = Doctrine (always, it's tiny) + top-K retrieved {lessons, playbooks, segment insights} relevant to the task.
- **Ranking signals (weighted):** semantic similarity + tag match + recency + confidence + (for cross-venture) segment match. Retired/superseded lessons are excluded.
- **Local-first:** embeddings computed locally (frozen model), vectors in a local store on `K:\` (Package B). No external dependency for memory.
- **FREEZE RULE (critical):** the embedding model is chosen now and frozen. Changing it later forces a **full re-index** because vectors from different models are incompatible. Any future change is a deliberate, scheduled re-index migration, never casual.

### 5.5 Ledger schema (`31_LEDGER_SCHEMA.md`) — specification
Each event records, at minimum: `event_id`, `timestamp`, `venture_id`, `actor` (capability/conductor/founder), `type` (capture, frame, score, admit, validate, spend, send, gate-decision, deploy, launch, kill, salvage, graduate, consolidate, …), `from_state`/`to_state` (if a transition), `payload` (artifact links, numbers, rationale), and `authorization` (token id for RED/gate events). The ledger is the legal record for governance audits and calibration.

### 5.6 Long-term growth — why it improves with age
More ventures → broader evidence and better retrieval coverage. Consolidation continuously raises signal-to-noise. Contradicted lessons retire instead of misleading. Recurring truths climb into small, always-on doctrine that is cheap to apply. The store grows on disk (cheap, on `K:\`), but the *cost and quality of each call* improve or hold flat. The Forge's curve was cost-up/quality-down; this is cost-flat/quality-up.

---

*Continued in Design Package B — Infrastructure & Build (Parts 6–11) + the five final summary lists.*
