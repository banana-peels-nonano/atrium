# Security (S7) — API
Owner: A5 Governance/Security Agent   ·   Matches docs/40 §4 exactly (frozen seam)   ·   Part of **interface-freeze IF-3** (with Governance S6, docs/52 §12 / docs/43 §3) — frozen so S8 Router can enforce the PII block

## Exposed surface

### `Sec.redact(text: str, doc_id: str | None = None) -> (clean: str, sidecar_ref: str | None)`
- **Preconditions:** none. `doc_id` (additive keyword; default = content hash) names the sidecar.
- **Postconditions:** every detected PII/secret span is replaced by a **stable token**
  `⟨PII:kind:h8⟩` (same raw value → same token across runs/documents); the raw original + token
  map is written to `<vault>/<doc_id>.private.md` (local-only tier); returns the cleaned text and
  the sidecar path — `(text, None)` when nothing was found (`INV-PII-1`).
- **Errors (fail closed):** sidecar I/O failure → raises; cleaned text is never returned without
  its sidecar persisted.
- **Side effects:** one local sidecar write (never shared tier, never ledger, never network).
- **Determinism:** deterministic. **Auth class:** GREEN (local, reversible via the sidecar).

### `Sec.scan(text: str) -> Findings`
- **Preconditions:** none (total).
- **Postconditions:** returns every rule hit as `Finding{kind, masked, start, end}` — kinds:
  `email, phone, ssn, credit_card, secret, high_entropy, name, financial`. Empty tuple = clean.
  `masked` never contains the raw match (`INV-PII-4`).
- **Errors:** none raised. **Side effects:** none.
- **Determinism:** **pure — rule-based only, never an LLM** (`INV-PII-2`). **Auth class:** n/a.

### `Sec.tag(ctx: Context) -> Context`
- **Preconditions:** `ctx.text` populated; `ctx.sources` lists the refs the context was built from.
- **Postconditions:** returns a copy with `contains_pii=True` iff the scan hits on `ctx.text` or
  any source ends `.private.md`; never clears an already-True flag (`INV-PII-3` input).
- **Errors:** none. **Side effects:** none. **Determinism:** pure. **Auth class:** n/a.

### `Sec.checkpoint(text: str, doc_id: str | None = None) -> CheckpointResult`  *(the docs/24 pipeline, composed)*
- **Preconditions:** called at every CHECKPOINT beat before any shared-tier write, embed, or cloud route.
- **Postconditions:** runs `redact` → independent `scan` of the redacted output; on zero residual
  findings returns `CheckpointResult{clean, sidecar_ref, contains_pii}` — the only S7 output
  eligible for the shared tier (`INV-PII-1`).
- **Errors (fail closed):** any residual finding → `CheckpointError` naming the finding *kinds*
  (never values); no clean text is returned; the caller must leave the venture put (`INV-PII-2`).
- **Side effects:** the `redact` sidecar write. **Determinism:** deterministic. **Auth class:** GREEN.

### `cloud_route_allowed(ctx: Context) -> bool`  ·  `require_cloud_allowed(ctx) -> None`
- **Postconditions:** `False` / raises `PIIRouteBlocked` iff `ctx.contains_pii` — the guard
  predicate **every cloud adapter must consult before sending** (`INV-PII-3`; enforcement lives in
  S8, the predicate is frozen here so S8 has one source of truth).
- **Determinism:** pure. **Auth class:** n/a.

## Public value types
`Finding{kind, masked, start, end}` · `Findings` · `Context{text, sources, contains_pii}` ·
`CheckpointResult{clean, sidecar_ref, contains_pii}` · errors `SecurityError` /
`CheckpointError` / `PIIRouteBlocked`.

## Consumed surface
- **None** (docs/43 §5: Security exposes redact/scan/tag; it never calls an action, a model, or
  another subsystem). Vault dir is injected (A1 `EnvContext` when S2 lands; `tmp_path` in tests).

## Interface stability
- **Frozen (IF-3):** `redact/scan/tag` signatures per docs/40 §4, the `Context.contains_pii`
  field, the `cloud_route_allowed`/`PIIRouteBlocked` guard contract, and the fail-closed
  CHECKPOINT semantics. Breaking change = ICR + consumer (S8/S9/S12) sign-off (docs/43 §4).
- **Additive v1 notes (docs/43 §7, no-bump):** the optional `doc_id` keyword on `redact`;
  `checkpoint` as the composed pipeline entry (docs/24 defines the pipeline; the composition
  point is declared here); the guard-predicate pair. No frozen signature altered.
- **Internal/free to change:** the rule table (patterns/thresholds may tighten any time — new
  detectors are additive), token format details, sidecar file layout, module split.
