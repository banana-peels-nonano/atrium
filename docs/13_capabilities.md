# 13 — CAPABILITY FRAMEWORK & CONTRACTS (build contract)
**Owner:** Capability-Framework Agent (A8) + Content Agent (A9) · **Subsystems:** S10 (framework), S11 (content) · **Source of truth:** Capability Contracts (frozen) · **Consumes:** Lifecycle (S5), Router (S8), Memory (S9), Security (S7), Ledger (S4)

## Charter (framework, S10)
The 5-beat workflow runner + Critic ladder + neutral-spec loader + OpenCode harness adapter. It orchestrates capabilities but grants them no authority and lets no gate advance itself.

### 5 beats (frozen)
PREPARE (det: assemble top-K memory) → PRODUCE (capability, idempotent/retryable) → CRITIQUE (different model family; degrade ladder → deterministic tier-3 always available) → CHECKPOINT (det: redact+scan, write vault, append event) → GATE (human).

### MUST (framework)
- `INV-WF-1` CHECKPOINT is the only state-mutating beat; PRODUCE/CRITIQUE are idempotent + retryable (failure → retry, never state change).
- `INV-WF-2` CRITIQUE runs on a different model family than PRODUCE; ladder: diff-family → diff-model-same-family → deterministic checklist (tier-3); tier recorded.
- `INV-WF-3` no gate presentable without an attached Critic take.

## Charter (content, S11) — the six capabilities as neutral specs
These are **contracts, not prompts**. Each: mission, scope, inputs, outputs, memory scope (READ/WRITE), escalation, no authority, stateless.

| Capability | Produces | Memory scope | Special rules (v1.1) |
|---|---|---|---|
| **Scout** | brief + score | R: anti-patterns/segments; W: briefs | reachability = hypothesis (R-REACH-HYP); cold-start KPI grace |
| **Analyst** | research pack + validation plan | R: teardowns/segments; W: research | two-sub-gate: evidence bar before spend (R-EVIDENCE-GATE); PII → `.private.md` |
| **Builder** | spec + staging MVP + templates | R/W: build lessons + templates | prod deploy + billing = two-key RED (R-CHARGE); staging autonomous |
| **Growth** | copy + outreach drafts + launch kit + partners outreach | R: channel playbooks; W: channel findings | drafts only; design-partner recruitment starts in SHAPING (R-PARTNERS); send budget (R-SEND-BUDGET) |
| **Librarian** | lessons, playbooks, index, calibration | R: all; W: lessons+playbooks; PROPOSE doctrine | salvage types incl. anti-patterns (R-SALVAGE-TYPES); consolidation reversible |
| **Critic** (mode) | adversarial critique | R: lessons; no write | cross-family + degrade ladder (R-CRITIC-DEGRADE) |

### MUST (content)
- Each capability's declared memory scope matches this table + the frozen contract; the framework enforces write-scope (out-of-scope write refused).
- No capability holds authority (cannot send/spend/deploy/cross a gate). The framework refuses such attempts.

## Interfaces
Exposes `Workflow.run(state, venture)`, `Capability.produce`, `Critic.critique` (`40` §7). Consumes Lifecycle, Router, Memory, Security, Ledger.

## Deliverables
`capabilities/framework/*`, `adapters/harness/opencode/*` (A8); `agents/*.agent.md` neutral specs (A9).

## Acceptance / DoD
`54` S10/S11 + `55`: beat isolation, retry/escalation, critic degrade to tier-3, scope enforcement, dry-run of each capability's beat.

## Build order
Wave 4–5 (Phase 5). Depends on Lifecycle+Router+Memory+Security interface-freezes.
