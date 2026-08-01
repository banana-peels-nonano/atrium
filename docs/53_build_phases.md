# 53 — BUILD PHASES
## Milestones from empty repo to production-ready, with exit criteria
**Owner:** Program · **Source of truth:** `52`, frozen Implementation Roadmap · **Status:** authoritative

> Governing principle (frozen): **safe before smart.** The deterministic spine (state, governance, PII, ledger) exists and is proven before any capability is intelligent. A phase does not begin until the prior phase's **exit criteria** are met.

> **Outcome (added 2026-08-01; the plan below is unchanged).** The build ran to completion and is closed —
> every subsystem S2–S15 is real on an always-green `main`. The phases did not run one-per-label: Phases 0–5 ran
> as written; **Phase 6 (governance integration end-to-end) was satisfied inside Phase 7** by the A10 Conductor
> dry-run (Capture→GRADUATED with every RED point halting at the authorization boundary, INV-TEST-SAFE proven as
> a code fact) rather than as a separate phase; **Phase 7 exited 2026-07-22** (tag `phase-7`, all 10 `63` gates
> mechanically live); **Phase 8's systemic verification is continuous** — the suite plus the invariant/anti-coupling/
> determinism/ownership gates run on every merge, and the Stress Test A/B/C scenarios are reproduced by the
> lifecycle simulator; **Phase 9 (production readiness) was reached only in part** — the founder CLI, real
> transports, and `QUICKSTART.md` shipped, but v1 deliberately has no real deploy/billing/send effect and the
> factory clock does not advance itself. See `BUILD_TRACKER.md` (Final state) and the top-level `README.md`.

---

## Phase 0 — Repository Foundation
- **Objectives:** buildable empty repo; ownership + CI enforceable.
- **Agents:** A0, A11 (harness), Program.
- **Required docs:** `30`,`31`,`56`,`60`,`61`,`62`,`63`.
- **Outputs:** module tree (`31`); `.gitignore`; `.env.example`; empty contract docs per subsystem; CI running the (empty) test harness; merge gates wired.
- **Acceptance:** structure test passes; CI green; every subsystem folder has its four empty contract docs.
- **Exit criteria:** any agent can create its files without touching another's; merge gates in `63` are active.

## Phase 1 — Environment & Configuration
- **Objectives:** the code runs only in a validated environment; all config typed + reproducible.
- **Agents:** A1, A2.
- **Required docs:** `20`–`25`.
- **Outputs:** `env/preflight`, `EnvContext`, `Config` loader + schemas.
- **Acceptance:** preflight passes on a prepared machine and fails closed with one precise error per missing prerequisite; malformed config is rejected with a located error; profile switch changes routes with no code change.
- **Exit criteria:** `INV-CFG` enforced; no subsystem reads env/config except through A1/A2 APIs.

## Phase 2 — Core Infrastructure (Ledger, Lifecycle, Governance, Security)
- **Objectives:** the deterministic spine — truth, state, rules, PII safety — with **no LLM anywhere**.
- **Agents:** A3, A4, A5.
- **Required docs:** `10`(deterministic parts),`14`,`15`,`24`,`32`,`41`,`42`.
- **Outputs:** ledger+registry with replay; state machine with guards/WIP/clocks; governance classify+tokens+envelope+send-budget; redaction+scan+pii-tag.
- **Acceptance:** state == replay(events); every illegal transition + WIP breach blocked; every RED action without a token refused; deterministic scanner catches a PII corpus; PII tag set correctly.
- **Exit criteria:** all `INV-LEDGER`, `INV-SM-*`, `INV-GOV-*`, `INV-PII-*` verified; a fake venture can be walked through every legal transition by hand with correct rejections.

## Phase 3 — Model Router & Substrate
- **Objectives:** model/provider independence + failover + budget guard + PII-safe routing.
- **Agents:** A6.
- **Required docs:** `11`,`22`,`40`(LLMClient),`43`.
- **Outputs:** `LLMClient.call`, adapters (OpenAI-compatible + shims), failover, telemetry.
- **Acceptance:** profile switch reroutes with no code change; primary failure fails over silently; PII-tagged context is refused by every cloud adapter; budget breach degrades tier.
- **Exit criteria:** `INV-ROUTE-*` verified; live-optional smoke against one free provider + local embedding passes; provider fakes cover failover tests.

## Phase 4 — Memory Engine
- **Objectives:** the compounding substrate; retrieval top-K; consolidation reversible.
- **Agents:** A7.
- **Required docs:** `12`,`33`,`41`.
- **Outputs:** embeddings (local, frozen model), LanceDB schema, retrieval, consolidation/promotion/retirement, reindex.
- **Acceptance:** retrieval returns top-K only (never full dump); PII never embedded; consolidation never edits ledger; reindex reproduces retrievable state.
- **Exit criteria:** `INV-MEM-*` verified; embedding model id pinned; kill→salvage→lesson→retrievable-at-next-gate integration passes.

## Phase 5 — Capability Framework & Content
- **Objectives:** the 5-beat runner + Critic ladder + the six capabilities as neutral specs.
- **Agents:** A8, A9.
- **Required docs:** `13`, Capability Contracts, `43`.
- **Outputs:** `Workflow.run`, retry/escalation, Critic degrade ladder, harness (OpenCode) adapter, `agents/*.agent.md`.
- **Acceptance:** model failure at PRODUCE/CRITIQUE → retry not state-change; CHECKPOINT is the only mutating beat; no gate without a Critic take; each capability's memory scope matches its contract.
- **Exit criteria:** `INV-WF-*` verified; a dry-run of each state completes with a fake model.

## Phase 6 — Governance Integration (end-to-end enforcement)
- **Objectives:** prove the full governance chain across capabilities (not just unit level).
- **Agents:** A5 + A8 + A10 (integration).
- **Required docs:** `14`,`24`, Stress Test.
- **Outputs:** end-to-end RED-token gating, spend envelope, send budget, two-key, outbox (no auto-send), PII cloud-block across a running workflow.
- **Acceptance:** in a dry-run venture, every RED point halts for a token; envelope breach re-REDs; a PII-bearing artifact is provably never cloud-routed.
- **Exit criteria:** governance + PII invariants hold *in integration*, not only in isolation.

## Phase 7 — Conductor Integration
- **Objectives:** the thin integrator binds all subsystems; briefs + projections produced.
- **Agents:** A10.
- **Required docs:** `10`,`40`,`13`.
- **Outputs:** command surface; Gate/Daily/Kill-Day Briefs; PIPELINE/METRICS/Calibration; crash→replay.
- **Acceptance:** every command enforces guards via the owning subsystem (no duplicated rule); no Gate Brief lacks a Critic section; crash mid-command loses nothing on replay.
- **Exit criteria:** `INV-COND-*` verified; a full venture dry-run Capture→Graduate completes with zero real spend/send/deploy.

## Phase 8 — Testing & Verification (systemic)
- **Objectives:** the whole system verified against the Stress Test and all invariants.
- **Agents:** A11 + all.
- **Required docs:** `54`,`55`, Stress Test, Revision Register.
- **Outputs:** lifecycle simulations (Stress-Test A/B/C), regression suite, invariant harness, failover/rate-limit/perf benchmarks.
- **Acceptance:** Stress-Test scenarios A/B/C reproduce expected states + defects-fixed behavior; all `INV-*` green; failover + budget-degrade + pii-block verified under fault injection.
- **Exit criteria:** 100% of defined invariants covered by a passing test; no `MUST` unverified.

## Phase 9 — Production Readiness
- **Objectives:** operable by the founder; recoverable; observable; documented.
- **Agents:** A1, A11, A10, Program.
- **Required docs:** `05`,`21`,`23`,`24`,`62`.
- **Outputs:** backup/restore verified (ledger+vault+vectors); telemetry dashboards (tokens/$/latency); the founder-facing command flow matches `05`; docs synced (`62`).
- **Acceptance:** restore-from-backup reproduces state; founder can run a day/kill-day cycle end-to-end (dry-run); every IB doc matches the code.
- **Exit criteria:** the readiness checklist (Env Spec Part 10 + `54`) is fully green → **Charter House is operable.**

---

## Phase gating rule
Each phase's exit criteria are a **hard gate**. The build does not advance on optimism (mirrors the product's own doctrine). A phase may ship partially only if the unshipped part is *not* a dependency of the next phase (see `52`).
