# 24 — SECURITY & PII PIPELINE (engineering rules)
**Owner:** Governance Agent (A5) · **Subsystem:** S7 · **Source of truth:** Governance + Memory Architecture (frozen), Revision Register (R-REDACT, R-PRECOMMIT-SCAN)

## The single most important guarantee in the system
Governance gates *actions*; Security gates *retrieval*. **PII must never reach a cloud model — not via an action, and not via memory retrieval.** This is the highest-severity invariant class (`INV-PII-*`); it was the top defect found in the Stress Test.

## The pipeline (runs at every CHECKPOINT beat; deterministic)
1. **Redact** (`Sec.redact`): raw PII (names, emails, phone, financials, secrets) is moved to a **local-only `*.private.md` sidecar**; a redacted version (PII→stable tokens) is what gets written to shared/embedded tiers.
2. **Deterministic scan** (`Sec.scan`): an independent, rule-based scanner (regex/entropy/secret-patterns — **no LLM**) re-checks the redacted output. A residual hit → CHECKPOINT **fails closed**; the venture stays put until cleaned.
3. **Tag** (`Sec.tag`): any context that reads a `.private.md` (or is otherwise PII-bearing) is tagged `contains_pii`.
4. **Route enforcement** (S8): `contains_pii` context is refused by every cloud adapter; only local models may process it.

## MUST (`INV-PII-1..4`)
- Redaction + scan run before any embed or cloud route.
- The scanner is deterministic (never an LLM in the PII path).
- `contains_pii` ⇒ cloud adapters excluded (joint test S7×S8).
- `*.private.md` is gitignored, never embedded, never logged, never pushed.

## Secrets handling
- Secrets only from env (`.env`, gitignored); never in config files, ledger, logs, or code.
- A pre-commit + CI secret scan blocks any secret in a diff (`63`).
- No capability holds payment or provider credentials directly; the Router reads keys from env at call time.

## Defense in depth
The capability-driven redaction (step 1) is backed by the deterministic scan (step 2) so a misbehaving LLM cannot leak PII. Security depends on the deterministic layer, never on model good behavior.

## Acceptance
`54` S7 + `55` security tier: PII corpus scan precision; CHECKPOINT fail-closed on residual; PII→cloud refused; `.private.md` never in diff/logs. Fault injection: force a redaction miss → scan catches it → fail closed.
