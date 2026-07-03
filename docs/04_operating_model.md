# 04 — OPERATING MODEL (runtime interaction of the primitives)
**Owner:** Program · **Source of truth:** Operating Model (frozen) · **Status:** authoritative

> How the primitives interact tick-by-tick at runtime. Implementers use this to understand the *sequence*; the exact APIs are in `40`.

## The runtime loop (one command)
1. **Founder or schedule issues a command** to the Conductor (S12) — e.g. `gate`, `validate.experiment`, `spend.envelope`.
2. **Conductor classifies** the action via Governance (S6): GREEN / YELLOW / RED(+two-key).
3. If RED and no valid token → **assemble decision package** (Gate Brief, S13) and halt for the founder. Fail closed.
4. If authorized → **run the state's workflow** (S10) if a transition is implied, else perform the deterministic action.
5. **Workflow 5-beat:** PREPARE (Conductor assembles top-K memory, S9) → PRODUCE (Capability, S11, via Router S8) → CRITIQUE (different-family, S10 ladder) → CHECKPOINT (redact+scan S7, write vault, append event S4) → GATE (human).
6. **Conductor regenerates projections** (S13) from the ledger: board, metrics, briefs.

## Who holds what state (critical for correctness)
- Durable state lives **only** in the Ledger (S4). The Registry, board, and metrics are projections.
- Capabilities (S11) hold **no** state between calls (stateless).
- The Conductor holds **no** durable state between commands (crash → replay → zero loss, INV-COND-3).

## The determinism boundary at runtime
- Deterministic (no LLM): steps 2, 3, the CHECKPOINT beat, projections, all guards.
- LLM-path: PRODUCE and CRITIQUE beats only, always behind the Router, always after PREPARE has supplied redacted, PII-safe context.

## Concurrency model (solo operator)
Single-writer to the ledger (append is serialized). Workflows for different ventures are independent but the founder is the serialization point at gates. WIP limits (S5) bound concurrency structurally — at most 3 validating + 1 shaping + 1 building active at once. No distributed coordination is needed; the system is single-node by design (Env Spec).

## Escalation & failure at runtime
- Capability failure → retry → escalate one routing tier → queue + notify (never a state change).
- Provider failure → failover chain → degrade to free/local → `pause` (freezes clocks) → vault stays human-usable.
- Any ambiguity → reject + log. (INV-FAILCLOSED)
