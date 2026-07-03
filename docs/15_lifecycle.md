# 15 — LIFECYCLE ENGINE (build contract)
**Owner:** Lifecycle Agent (A4) · **Subsystem:** S5 · **Source of truth:** Lifecycle (frozen), Stress Test, Revision Register v1.1 · **Consumes:** Ledger + Registry (S4)

## Charter
Enforce the venture state machine and all slot/WIP/clock rules. Deterministic; knows nothing of models, memory content, or money — only states, transitions, and guards. The formal machine is `42`; this card is the build framing.

## MUST (all from `42`)
- `INV-SM-1` only legal transitions execute; all else rejected + logged.
- `INV-SM-2` WIP: validating ≤3, SHAPING =1, building ≤1, HARVEST alumni ≤3.
- `INV-SM-3` deadlines in factory-active time from `experiment_live_at`; `pause` freezes clocks.
- `INV-SM-4` express-advance only for non-slot-consuming transitions.
- `INV-SM-5` pivot = kill-and-fork; one fork/lineage (ledger-checked); fork re-enters at FRAMED.
- `INV-SM-6` shovel-ready evidence past TTL requires re-confirmation before BUILDING.

## Interfaces
Exposes `Lifecycle.can_transition/transition/slots/clock` (`40` §3). Consumes Ledger + Registry. Emits transition/park/omw/pivot events.

## Deliverables
`lifecycle/` — the state table (`42` §3), guard functions, slot manager, active-time clock, pivot orchestration.

## Acceptance / DoD
`54` S5 + `55`: full legal/illegal transition matrix; WIP/slot breach; TTL expiry; express restriction; pivot fork cap; and the three Stress-Test scenarios reproduce expected states via the simulator.

## Build order
Wave 1 (Phase 2), parallel with Governance. Interface frozen at IF-4 so the Capability Framework (S10) and Conductor (S12) can build against it. This is the spine — freeze it early and change it never without an ICR (`43`).
