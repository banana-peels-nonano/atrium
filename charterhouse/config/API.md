# Config (S3) — API
Owner: A2 Config Agent   ·   Matches docs/40 §1 exactly (frozen seam)

## Exposed surface

### `Config.load(config_dir: Path, profile: str | None = None, overrides: Mapping | None = None) -> Config`
- **Preconditions:** `config_dir` contains `providers.yaml`, `models.yaml`, `routes.yaml`, and
  `profiles/`. `profile`, if given, names a file in `profiles/`.
- **Postconditions:** returns an immutable `Config` in which `INV-CFG` (both clauses) holds and
  the profile+overrides precedence (docs/25 §3) is applied. Never returns a partially-built `Config`.
- **Errors:** located validation error on syntax / unknown key / missing key / dangling
  model ref / dangling provider ref / unknown profile. Fail closed.
- **Side effects:** none (no ledger write, no env read, no network). **Determinism:** deterministic/pure.
- **Auth class:** n/a (no action).

### `Config.get_route(role: str) -> Route`
- Returns the resolved `{primary, fallback[], min_ctx?, needs_tools?, needs_web?}` for a role under the active profile.
- **Errors:** typed lookup error for an unknown role. **Determinism:** pure. **Side effects:** none.

### `Config.get_model(id: str) -> Model`
- Returns `{provider, ctx, price_in, price_out, tier, good_at[], family}`. Typed lookup error for unknown id. Pure.
- **`family` (additive, docs/43 §7 — feat/a2-accessors, founder follow-up at the A8 gate):**
  the model family the INV-WF-2 cross-family critic check compares. An explicit
  `family:` key in `models.yaml` wins; absent, the loader defaults it via the canonical
  `contracts.config_types.default_family(id)` (leading alphabetic token). Always
  non-empty after a load; an explicit empty/non-string value is a located error.

### `Config.get_provider(id: str) -> Provider`
- Returns `{base_url, key_env, kind}`. **`key_env` is the env-var name, never the secret value.** Typed lookup error for unknown id. Pure.

### `Config.profile -> str`
- The active profile name (property).

### `Config.budgets -> Budgets`
- Returns `{monthly_usd, on_exceeded, send_daily}` resolved under the active profile. Pure.

### `Config.models() -> tuple[str, ...]`  (additive, docs/43 §7)
- Every model id in the catalog, sorted — the frozen listing seam (router RISKS R9
  retired: the S8 degrade extension reads this instead of Config internals). Ids only;
  shapes via `get_model`. Pure; no consumer bump.

### `Config.memory -> MemoryConfig`  (additive, docs/43 §7)
- The S9 retrieval/consolidation tuning block (docs/33 "weights in config, tunable";
  memory RISKS R9 retired) from `routes.yaml`'s optional `memory:` key — strict-key
  validated, numeric-typed, docs/33 defaults for absent keys, frozen value. Feeds
  `RetrievalWeights.from_config` at wiring. **Base routes.yaml only for now** — profile
  overlay of `memory` is a later additive step (documented, not implied).

## Consumed surface
- **None.** Inputs (`config_dir`, `profile`, `overrides`) are supplied by the caller (A1's `EnvContext`).
  Config does not call any subsystem API and does not read environment variables.

## Interface stability
- **Frozen (docs/40 §1):** `get_route`, `get_model`, `get_provider`, `profile`, `budgets`, and the
  four shared types `Route/Model/Provider/Budgets`. Breaking change = coordinated interface bump (docs/43 §4).
- **Additive v1 notes (docs/43 §7, feat/a2-accessors):** `models()`, `memory` +
  `MemoryConfig`, `Model.family` (defaulted field) + `default_family` — no consumer
  bump; consumers updated in the same branch (router degrade extension, S9 wiring,
  S10 critic family lookup).
- **This is the Config half of interface-freeze IF-2 (docs/52 §12)** — recorded as frozen in the
  Build Tracker **only on founder clearance**, not on authoring.
- Internal/free to change: file-parsing internals, error-message wording, the `schema`/`loader` split.
