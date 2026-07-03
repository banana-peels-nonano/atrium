# 03 — ARCHITECTURE (the five primitives + two seams as build targets)
**Owner:** Program · **Source of truth:** Operating Model (frozen) · **Status:** authoritative

> The runtime architecture, expressed as what the code must instantiate. Maps 1:1 to subsystems (`50`).

## The five primitives (code must realize exactly these)
| Primitive | Definition | Subsystem | Never does |
|---|---|---|---|
| **Venture** | the entity: one registry record + event stream | S4 | hold logic |
| **Board / State Machine** | the lifecycle law: states + legal transitions + guards | S5 | know models/money/memory |
| **Workflow** | bounded procedure per state (5-beat) | S10 | cross a gate itself |
| **Capability** | stateless LLM executor: artifact + recommendation | S11 | hold authority/durable state |
| **Ledger** | append-only truth + compounding memory substrate | S4/S9 | be edited |

Plus two non-capability actors:
- **Conductor** (S12) — deterministic engine; the only chokepoint for state changes + external effects.
- **Founder** (human) — the only authority over gates and RED actions; surfaced via S13 briefs.

## The two seams (must remain separable — integrity)
- **Model-provider seam** = the Router (S8) + Config (S3). Capabilities call `role`, never a model. Swap = config.
- **Agent-runtime seam** = neutral capability specs (S11) + harness adapter (S10). Swap harness = regenerate adapter.

## Data-flow spine (what moves where)
```
inbox → Scout → brief → [gate] → Analyst/Growth → experiment(drafts) → [RED: spend/send] → market signal
     → [weekly gate] → Builder(spec→MVP) → [RED: deploy/billing] → launch → earning → [gate] → graduate
Every step → Ledger. Ledger → Librarian → lessons → playbooks → doctrine (retrieved top-K).
Every external effect → Conductor → Governance classify → (token) → act.
```

## Control principle (single chokepoint)
All state mutations and all external effects pass through the **Conductor**, which enforces state machine (S5), governance (S6), and PII (S7) by *calling* them. There is no path around the Conductor. This is the structural guarantee behind the doctrine invariants (`02`).

## Build implication
Because the Conductor is the integrator (S12, built last) and everything it enforces lives in owned subsystems (S5/S6/S7…), the deterministic spine can be built and proven **before** any capability is intelligent (`53` "safe before smart").
