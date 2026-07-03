# 25 — CONFIGURATION (schemas, precedence, reproducibility)
**Owner:** Config Agent (A2) · **Subsystem:** S3 · **Source of truth:** Environment Spec (Part 7)

## Principle
All configuration is explicit, typed, validated, and reproducible. **No hidden state.** Two homes: machine-level env (paths/caches/secrets) and repo config files (behavior).

## 1. Machine-level env vars (set via `setx`; documented, not committed)
Redirection: `OLLAMA_MODELS, HF_HOME, PIP_CACHE_DIR, UV_CACHE_DIR, UV_PYTHON_INSTALL_DIR, NPM_CONFIG_CACHE, NPM_CONFIG_PREFIX, TMP/TEMP`. Runtime: `CHARTERHOUSE_ROOT, CHARTERHOUSE_DATA_DIR, CHARTERHOUSE_VECTORS_DIR, CHARTERHOUSE_PROFILE, CHARTERHOUSE_EMBED_MODEL, OLLAMA_HOST`. Secrets (`.env`): `OPENROUTER_API_KEY, DEEPINFRA_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY?, OPENAI_API_KEY?`.

## 2. Repo config files (committed; secrets excluded)
- `config/providers.yaml` — provider → {base_url, key_env, kind}.
- `config/models.yaml` — model id → {provider, ctx, price_in, price_out, tier, good_at[]}.
- `config/routes.yaml` — role → {primary, fallback[], min_ctx?, needs_tools?, needs_web?}.
- `config/profiles/*.yaml` — named overrides of routes/budgets.
- `.env.example` — every variable with placeholder values (reproducibility).

## 3. Precedence (highest wins)
CLI arg > active profile (`CHARTERHOUSE_PROFILE`) > `routes.yaml` default > `models.yaml`/`providers.yaml` base. Secrets only from env, never from committed files.

## 4. Validation (MUST, fail closed)
- Schema-validate every file on load; unknown keys → reject with a located error.
- `INV-CFG`: every route model exists in `models.yaml`; every model's provider exists in `providers.yaml`.
- The embedding model id (`CHARTERHOUSE_EMBED_MODEL`) must match the value the vector index was built with; mismatch → refuse to start (guarded re-index required).

## 5. Reproducibility
A second machine is reproducible from: `.env.example` + the documented `setx` list + the committed config files. No behavior depends on undocumented state. The active profile + config hash is logged at startup for auditability.

## Acceptance
`54` S3: valid loads; malformed rejected with location; profile switch reroutes; embed-model mismatch refused.
