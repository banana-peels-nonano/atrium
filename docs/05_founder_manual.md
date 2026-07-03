# 05 — FOUNDER TOUCHPOINTS (what the software must expose to the human)
**Owner:** Program · **Source of truth:** Founder Operating Manual (frozen) · **Status:** authoritative

> The Founder Manual is a human process doc. This card extracts the **software obligations** it implies — the surfaces the code MUST expose so the human process works. It is the acceptance spec for the human-facing layer (S12/S13).

## Required surfaces (the code MUST provide)
| Surface | What it is | Backed by | Phase |
|---|---|---|---|
| **Daily Brief** | triaged: the 2–3 decisions needing a human today + RED queue + send batch to approve + board glance | S13 | 7 |
| **Gate Brief** | fixed schema per gate; MUST include Critic field (`INV-COND-2`) | S13 | 7 |
| **Kill-Day Brief** | every active venture as a Gate Brief + mechanical recommendation | S13 | 7 |
| **Send batch approval** | founder-wide daily budget, audience-timezone scheduled, drafts from outbox | S6/S13 | 6 |
| **Spend envelope approval** | authorize a cap once (RED); within-cap spends auto (YELLOW) | S6 | 6 |
| **Five levers** | gut-yes (admit), cut-list (spec), verdict (gate), price (earning), send/publish | S12 | 7 |
| **Calibration report** | monthly; all overrides vs outcomes | S13/S9 | 8 |

## The five levers → commands (exact)
- gut-yes → `admit` (gate, slot). cut-list → `spec_approved` (gate). verdict → `gate` (ADVANCE/KILL/OMW). price → pricing action in EARNING (RED if it bills). send/publish → `send.stage` / `launch` / `billing.enable` (RED).

## Hard human-in-loop rules the code MUST enforce
1. No outreach send that the founder didn't authorize from an outbox draft (`INV-GOV-1`).
2. No Gate Brief presentable without a Critic section (`INV-COND-2`).
3. Kills only via the weekly gate; express is advance-only, non-slot (`INV-GATE-CADENCE`, `INV-SM-4`).
4. Pivot is kill-and-fork, never an in-place redirect (`INV-SM-5`).
5. Graduation refused if HARVEST alumni at cap (`INV-SM-2`).
6. Overrides allowed but logged with reason (`INV-GOV-6`).

## Time-budget obligation
The system MUST make the founder's daily interaction completable in a short morning block: the Daily Brief is triaged (`INV-TRIAGE`), sends are scheduled to the audience timezone (decoupled from the decision block), and silence (nothing to decide) is a valid, correct output.

## Acceptance for the human layer
Phase 9: a founder can run one full day-cycle and one kill-day cycle end-to-end in dry-run, issuing every lever, with every RED action correctly halting for authorization, and every brief conforming to schema.
