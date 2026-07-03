# 10 — CONDUCTOR (build contract)
**Owner:** Conductor Agent (A10) · **Subsystem:** S12 (+S13 projections) · **Source of truth:** Conductor Specification (frozen) · **Consumes:** all subsystem APIs (`40`)

## Charter
The deterministic integrator and single chokepoint. Runs workflows, enforces the state machine (S5), governance (S6) and PII (S7) **by calling them**, records events (S4), and regenerates projections (S13). Holds no rule owned by another subsystem and no durable state between commands.

## MUST
- `INV-COND-1` re-implement no rule owned by S5/S6/S7 — call through (verified by import + call-path tests).
- `INV-COND-2` every Gate Brief conforms to the fixed schema and includes the Critic field.
- `INV-COND-3` crash mid-command → replay reconstructs state, zero loss (no durable in-memory state).
- Every command: classify (S6) → enforce guards (S5/S6/S7) → act via owning subsystem → append event (S4) → regenerate projections (S13). Fail closed on any failure.
- No external effect executes without a valid authorization token of the correct class.

## Command surface
Exactly the set in `40` §8 / Conductor Spec §3. Each command's guard path is unit-tested (`54` S12).

## Interfaces
- Exposes: `Conductor.command`, `Conductor.gate_brief`, projection functions (`40` §8–§9).
- Consumes: Config, Ledger, Registry, Lifecycle, Gov, Sec, Router, Memory, Workflow.

## Deliverables
`conductor/` (command dispatch + enforcement orchestration), `projections/` (board/metrics/briefs/calibration — all pure functions of the ledger).

## Acceptance / DoD
See `54` S12/S13. Integration: full venture dry-run Capture→Graduate, zero real spend/send/deploy; every RED point halts for a token; briefs schema-valid.

## Build order
Built LAST (Wave 6, Phase 7) — it integrates finished subsystems. May be stubbed earlier for the lifecycle simulator, but its real build waits on A2–A9 interface-freezes (`52`).
