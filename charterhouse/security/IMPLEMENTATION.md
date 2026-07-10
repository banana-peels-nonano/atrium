# Security (S7) — IMPLEMENTATION
Owner: A5 Governance/Security Agent   Subsystem: S7   Source of truth: docs/24_security.md (frozen) + docs/40 §4, docs/43, docs/54 §S7, docs/55 (security tier), Revision Register (R-REDACT, R-PRECOMMIT-SCAN)

## 1. Responsibility (one paragraph)
S7 is the PII pipeline — **the single most important guarantee in the system**: PII must never
reach a cloud model, not via an action and not via memory retrieval. It redacts raw PII
(names, emails, phones, financials, secrets) into local-only `*.private.md` sidecars replacing it
with stable tokens, re-checks the redacted output with an independent **deterministic** (never an
LLM) scanner, tags PII-bearing context `contains_pii`, and composes these into the CHECKPOINT
pipeline that **fails closed** on any residual hit. It **MUST NOT**: perform or authorize actions
(S6's), route or call models (S8's — S7 only supplies the tag and the guard predicate S8
enforces), write to shared/embedded tiers itself (it returns cleaned text; the caller writes),
hold secrets (env-only, docs/24), or put an LLM anywhere in the PII path.

## 2. Invariants enforced
- **`INV-PII-1` — redaction + scan run before any embed or cloud route.** *Guaranteed by:*
  `checkpoint(text)` is the only S7 path that yields shared-tier-safe text, and it always runs
  `redact` then `scan` on the redacted output before returning; raw PII goes only to the
  `*.private.md` sidecar; replacements are stable tokens (same raw value → same token).
- **`INV-PII-2` — the scanner is deterministic (never an LLM in the PII path).** *Guaranteed by:*
  `scan` is pure rules — regex + Luhn + entropy + a configured known-identities list; stdlib only,
  no model import anywhere in `charterhouse/security/`; a residual hit at CHECKPOINT raises
  `CheckpointError` and nothing is returned for the shared tier (fail closed).
- **`INV-PII-3` — `contains_pii` ⇒ cloud adapters excluded.** *Guaranteed by:* `tag` sets
  `contains_pii` when the scan hits or any source is a `*.private.md`; S7 exports the guard
  predicate `cloud_route_allowed(ctx)` that every cloud adapter must consult — S8 enforces it at
  route time (joint S7×S8 test; the S7 side is tested against a stub adapter now).
- **`INV-PII-4` — `*.private.md` is gitignored, never embedded, never logged, never pushed.**
  *Guaranteed by:* the repo `.gitignore` rule (verified by test + CI secret/sidecar scan, gate
  6/7); sidecars are written only under the local vault dir; `Findings` carry masked excerpts,
  never raw values; `redact`/`checkpoint` return the sidecar *path*, never its content.

## 3. Internal design
**Deterministic throughout; no LLM anywhere.** Durable state: only the `*.private.md` sidecars
under the injected local vault dir (never the shared tier, never the ledger).

- `types.py` — `Finding{kind, masked, start, end}` (masked = first/last char + `…`, never the raw
  match), `Findings = tuple[Finding, ...]`, `Context{text, sources, contains_pii}` (frozen),
  `CheckpointResult{clean, sidecar_ref, contains_pii}`, error taxonomy
  (`SecurityError` → `CheckpointError`, `PIIRouteBlocked`).
- `scan.py` — `Scanner(known_identities: tuple[str, ...] = ())`, `scan(text) -> Findings`.
  Rule set (each rule = kind + detector, table-driven):
  `email` (RFC-lite regex) · `phone` (international/US formats, ≥7 digits with separators) ·
  `ssn` (`ddd-dd-dddd`) · `credit_card` (13–19 digits with separators **and** Luhn-valid) ·
  `secret` (provider key shapes: `AKIA…`, `sk-…`, `ghp_…`, `xoxb-…`, PEM `BEGIN … PRIVATE KEY`,
  and `key/token/secret/password ∶=` assignments) · `high_entropy` (mixed-case+digit tokens
  ≥ 24 chars with Shannon entropy above threshold; hex-only strings excluded so content hashes/
  ULIDs never false-positive) · `name` (configured known-identities, case-insensitive, plus
  honorific/`Name:` field patterns) · `financial` (currency amounts/account patterns within a
  window of confidential-context words: unreleased, confidential, private, payroll, salary, bank,
  routing — so public pricing like "$29/mo" never trips).
- `redact.py` — `Redactor(vault_dir, scanner)`, `redact(text, doc_id) -> (clean, sidecar_ref)`:
  scanner findings replaced span-by-span with **stable tokens** `⟨PII:kind:h8⟩` where
  `h8 = sha256(raw)[:8]` (same value → same token across documents/runs, so redacted text stays
  linkable without exposing the value). Raw original + token map written to
  `<vault_dir>/<doc_id>.private.md`; returns `(clean, path)`; `(text, None)` when nothing found.
- `tag.py` — `tag(ctx, scanner) -> Context`: `contains_pii=True` iff scanner hits on `ctx.text`
  or any `ctx.sources` entry ends `.private.md`. `cloud_route_allowed(ctx) -> bool` — the exported
  guard (False iff `contains_pii`); `require_cloud_allowed(ctx)` raises `PIIRouteBlocked` (what an
  adapter calls, INV-PII-3).
- `checkpoint.py` — `checkpoint(text, doc_id, redactor, scanner) -> CheckpointResult`: (1)
  `redact`; (2) `scan(clean)` with the **independent** scanner (defense in depth — the scan never
  trusts the redactor, docs/24 §Defense in depth); (3) any residual finding → `CheckpointError`
  naming the kinds (never the values), no clean text returned, the venture stays put (caller
  contract); else returns the shared-tier-safe result.
- `facade.py` — `Security(vault_dir, known_identities=())` wiring `redact/scan/tag/checkpoint`
  (the frozen `Sec.*` surface, docs/40 §4).

## 4. Dependencies
- **None of the subsystem APIs.** S7 consumes stdlib only (docs/43 §5: Security exposes
  redact/scan/tag and never calls an action). The vault dir path will come from A1's `EnvContext`
  when S2 lands; until then it is an injected constructor argument (tests: `tmp_path`).
- **Consumed by (IF-3 downstream):** S8 Router (tag + `cloud_route_allowed` at every cloud route),
  S9 Memory (redact+scan before any embed), S12 Conductor (checkpoint at every CHECKPOINT beat),
  S4 Ledger payload hygiene sits behind this as an independent backstop.

## 5. Failure behavior
| Failure mode | Fail-closed response |
|---|---|
| Residual PII/secret in redacted output (redactor bug/bypass) | `CheckpointError`; no clean text returned; nothing eligible for embed/cloud; venture stays put |
| A capability/LLM misbehaves and emits raw PII | irrelevant to the guarantee: the deterministic scan backstops every CHECKPOINT (R-PRECOMMIT-SCAN); security never depends on model good behavior |
| Context read a `.private.md` | tagged `contains_pii`; `cloud_route_allowed` False; `require_cloud_allowed` raises `PIIRouteBlocked` |
| Sidecar write fails (I/O) | exception propagates; no clean text is returned without a persisted sidecar (raw PII is never silently dropped) |
| Scanner uncertain (e.g. Luhn-valid number, high-entropy token) | flagged — over-blocking is the correct failure direction; founder can whitelist by cleaning the source |
| Unknown/new PII shape not in the rule set | out of detector reach by definition — mitigated by corpus-driven rules + known-identities registry + upstream capability redaction (three layers); documented in RISKS R2 |
No path returns unscanned text for the shared tier, and no error message ever embeds a raw match.

## 6. Open questions → RESOLVED
- **Q: how can a deterministic scanner catch *names* (docs/24 lists them as PII) without NER/an
  LLM?** **RESOLVED —** a configured **known-identities registry** (interview subjects, partner
  names — populated by the capability writing the doc; the corpus test uses it) + structural
  patterns (honorifics, `Name:` fields). Free-text celebrity-style name inference is explicitly
  out of scope for the deterministic layer; the redaction step (layer 1) owns semantic naming,
  the scanner (layer 2) owns structural + registered names. Recorded in RISKS R2.
- **Q: what precision/recall must the corpus test meet? (docs/55 names no number.)**
  **RESOLVED —** on the curated corpus: **100% recall** on positives (any miss is a test failure
  — fail-closed philosophy) and **0 false positives** on the negatives set (precision guards
  against CHECKPOINT dead-lock on clean text). The corpus is the bar; extending the corpus is how
  the bar tightens.
- **Q: `Sec.redact(text)` (docs/40 §4) has no doc-id — where does the sidecar name come from?**
  **RESOLVED —** `doc_id` is an optional keyword (default: content hash), an additive parameter
  that keeps the frozen positional signature intact.
- **Q: does CHECKPOINT failure emit a ledger event?** **RESOLVED —** not from S7 (it consumes no
  Ledger; docs/43 §5). The `pii_block` event is appended by the *route* enforcer (S8) /
  CHECKPOINT caller (S12) on refusal, matching docs/41 §2's `pii_block{context_ref,
  attempted_route}`. S7 raises typed errors those callers translate.
