# Security (S7) — RISKS
Owner: A5 Governance/Security Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced in |
|---|---|---|---|---|---|---|
| R1 | PII reaches a cloud model via the retrieval path (the Stress-Test C3 leak — the top defect in the whole design) | Med | Critical | security | three independent layers: capability redaction (upstream) → deterministic CHECKPOINT scan (S7, fail closed) → `contains_pii` cloud-block (S7 guard, S8 enforced) → S4 payload backstop | `test_checkpoint_fails_closed_on_residual`, `test_cloud_adapter_blocks_pii`, `it_redacted_payload_accepted_raw_rejected` |
| R2 | A PII shape outside the rule set (free-text name, novel secret format) passes the scanner | Med | High | security | corpus-driven rules (extending the corpus tightens the bar); known-identities registry for names; upstream capability redaction owns semantic naming; over-blocking preferred to under-blocking on ambiguity | IMPLEMENTATION §6, corpus tests; corpus grows at S9/S12 |
| R3 | Scanner false positives dead-lock CHECKPOINT on clean text (venture can never advance) | Med | Med | correctness | negatives corpus pins zero-FP on representative clean content (pricing, hashes, ULIDs); hex-only strings excluded from entropy rule; financial rule requires confidential-context words | `test_scan_negatives_no_false_positives` |
| R4 | A `*.private.md` sidecar leaks (committed, embedded, logged, or pushed) | Low | Critical | security | `.gitignore` rule verified by test; CI gates 6/7 scan every diff for sidecars/secrets; findings/errors carry masked kinds only; sidecars written only under the local vault | `test_private_sidecar_gitignored`, `test_findings_never_carry_raw_pii`, CI |
| R5 | Someone puts an LLM in the PII path "to improve recall", silently breaking the determinism guarantee | Low | Critical | architectural-integrity | INV-PII-2 is a named MUST with a determinism test; `security/` imports stdlib only (anti-coupling gate 5/10 when active); design doc states the layer rule: security depends on the deterministic layer, never on model behavior | `test_scan_deterministic`, import check |
| R6 | Stable tokens (`h8` of raw value) enable cross-document correlation, or brute-force of low-entropy values (a phone number's hash is guessable) | Med | Low | security | tokens are *local-tier* linkage identifiers by design (docs/24 wants stable tokens); the shared tier holds only tokens, raw values only in the local sidecar; an attacker who can brute-force the token space already has local disk access | IMPLEMENTATION §3; accepted by design |
| R7 | Redactor and scanner drift apart (redactor replaces less than the scanner detects → chronic CHECKPOINT failures; more → silent over-redaction) | Med | Med | correctness | both are driven by the **same rule table** (one source of truth), while `checkpoint` still runs them as independent steps so a redactor bug is caught, not trusted | `test_checkpoint_order_redact_then_scan`, `test_checkpoint_fails_closed_on_residual` |
| R8 | Vault dir mis-injection scatters sidecars outside the local tier | Low | High | security | constructor validates the vault dir exists/is writable at wiring; sidecar paths always resolve under it; A1 `EnvContext` becomes the single source when S2 lands | `test_vault_dir_validated_at_wiring`, `test_redact_moves_pii_to_sidecar` |
| R9 | DX noise: the "assigned secret" rules (CI gates 6/7 `scripts/secret_scan.py`; S7 assignment detector) flag legitimate source lines that assign to a variable named after a secret keyword (`token`, `secret`, …) | Med | Low | dx | **kept strict by policy** — over-eager secret detection is the safe failure direction; resolve hits by renaming the variable at the flagged site (precedent: `redact.py` uses `replacement`), never by weakening the pattern | CI gates 6/7; policy recorded here |

## Refactor-avoidance notes
- **The rule table is data**: new detectors (kinds) are additive rows with corpus entries — no
  pipeline change, no interface change, no consumer impact. Tightening a pattern never touches
  the frozen surface.
- **The guard predicate is the seam** (`cloud_route_allowed`): S8 enforces one frozen boolean,
  so the entire scanner can be rewritten without the Router changing a line (IF-3 purpose).
- `checkpoint` composes `redact`+`scan` rather than fusing them, so either half swaps
  independently (e.g., a future stronger redactor) while the fail-closed contract stays fixed.
- Sidecar layout (raw + token map in one file) keeps restore/audit trivial and is internal —
  free to change without ICR.

## Assumptions
- **Callers (S9 Memory, S12 Conductor):** nothing is embedded or written to a shared tier except
  a `checkpoint(...).clean` result; CHECKPOINT failure leaves the venture put. (S7 cannot enforce
  callers; the joint tests at S9/S12 will.)
- **S8 Router (per its future API.md):** every cloud adapter calls `require_cloud_allowed(ctx)`
  before sending and appends the `pii_block` event on refusal (docs/41 §2).
- **S4 Ledger (per its API.md):** structural PII pre-check on payloads stays active as the
  independent backstop; sidecar *refs* in payloads are fine, contents never.
- **A1 EnvContext (per docs/20, when S2 lands):** supplies a local vault dir on K:; until then the
  injected dir in tests/wiring is local by construction.
- **Repo hygiene:** `.gitignore` keeps the `*.private.md` rule (a test pins it) and CI gates 6/7
  stay in the merge path.
