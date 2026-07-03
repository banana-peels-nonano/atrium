# 14 — GOVERNANCE ENGINE (build contract)
**Owner:** Governance Agent (A5) · **Subsystem:** S6 (+S7 security, same agent) · **Source of truth:** Governance Architecture (frozen) · **Consumes:** Ledger (S4), Config (S3)

## Charter
Classify every proposed action and let nothing cross a money/deploy/contact/gate boundary without a valid founder authorization. Perform no actions itself — only classify + authorize/deny + record.

## Action classes (frozen)
| Class | Meaning | Examples | Rule |
|---|---|---|---|
| GREEN | reversible, no external effect, capped inference | research, draft, score, write vault, regenerate views | autonomous, logged |
| YELLOW | metered/internal within budget | inference spend, within-envelope spend, staging deploy, schedule (not send) | allowed within budget; logged; auto-degrade past 80% |
| RED | money out / production / contact / lifecycle gate | pay, deploy prod, enable billing, send outreach, publish, charge, advance/kill, share data room | hard token; never autonomous |

## MUST
- `INV-GOV-1` every RED action requires a valid, correctly-scoped token.
- `INV-GOV-2` two-key set (prod payment-path deploy, `billing.enable`, scaled outreach) requires token AND passing automated check.
- `INV-GOV-3` tokens single-use + expiring; reuse refused.
- `INV-GOV-4` spend envelope: authorize cap once (RED); within-cap = YELLOW; breach → re-RED.
- `INV-GOV-5` send budget is founder-wide (≤ configured/day), Conductor-allocated by priority; never unbounded per venture.
- `INV-GOV-6` every founder override (admission/advance/kill) logged with reason.

## Interfaces
Exposes `Gov.classify/authorize/envelope_open/spend/send_budget_remaining` (`40` §4). Consumes Ledger, Config. Security (S7) surface (`redact/scan/tag`) documented in `24`.

## Deliverables
`governance/` (classify, tokens, envelope, send budget) + `security/` (see `24`).

## Acceptance / DoD
`54` S6: class matrix, token single-use/expiry, envelope breach re-RED, two-key, override logging.

## Build order
Wave 1 (Phase 2), parallel with Lifecycle. Interface frozen at IF-3 (with Security) so Router (S8) can enforce the PII block.
