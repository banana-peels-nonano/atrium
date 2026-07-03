# 22 — MODELS (role catalog + routing profiles as data)
**Owner:** Router Agent (A6) · **Source of truth:** Environment Specification (Model Strategy), frozen future-proofing

## Principle
Model names are **data, not code**. This doc defines the role catalog and the profile data the Router consumes; changing a model is a config edit, never a code change (except the embedding model — a guarded re-index).

## Roles (frozen)
`reasoning`, `coding`, `research` (long-context), `critic` (must differ in family from producer), `retrieval` (embedding, LOCAL + frozen).

## Config data shape (see `25` for schemas)
- `models.yaml`: id → {provider, ctx, price_in, price_out, tier, good_at[]}.
- `routes.yaml`: role → {primary, fallback[], min_ctx?, needs_tools?, needs_web?}.
- `profiles/*.yaml`: named stacks the founder switches between (`free`, `cheap-cloud`, `local-first`).

## Initial fill (this machine: RTX 5060 8GB, 32GB RAM, $0 preference → default `free`)
| Role | Default (`free` profile) | Run |
|---|---|---|
| reasoning | DeepSeek V4 / GLM-5.1 (OpenRouter/DeepInfra free) | remote |
| coding | Qwen3.5-Coder / GLM-5.1 (free) | remote |
| research | Gemini 2.5 Flash (free, 1M ctx) | remote |
| critic | a different free family (Llama/Qwen) → tier-3 deterministic if rate-limited | remote/local |
| retrieval | `nomic-embed-text` | **local (Ollama), frozen** |
Optional local helper (8GB VRAM): a 7–8B model for trivial offline tasks; not required.

## MUST
- The retrieval (embedding) model id is pinned; a change is a guarded re-index (`INV-MEM-2`).
- Every route's models exist in `models.yaml` (`INV-CFG`).
- Profiles are swappable with zero code change (`INV-ROUTE-1`).
- `critic` route MUST resolve to a different family than the paired producer, or degrade to tier-3 (`INV-WF-2`).

## Acceptance
`54` S8: switching profile reroutes; free profile runs with no paid dependency; critic family differs or degrades.
