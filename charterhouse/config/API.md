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
- Returns `{provider, ctx, price_in, price_out, tier, good_at[]}`. Typed lookup error for unknown id. Pure.

### `Config.get_provider(id: str) -> Provider`
- Returns `{base_url, key_env, kind}`. **`key_env` is the env-var name, never the secret value.** Typed lookup error for unknown id. Pure.

### `Config.profile -> str`
- The active profile name (property).

### `Config.budgets -> Budgets`
- Returns `{monthly_usd, on_exceeded, send_daily}` resolved under the active profile. Pure.

## Consumed surface
- **None.** Inputs (`config_dir`, `profile`, `overrides`) are supplied by the caller (A1's `EnvContext`).
  Config does not call any subsystem API and does not read environment variables.

## Interface stability
- **Frozen (docs/40 §1):** `get_route`, `get_model`, `get_provider`, `profile`, `budgets`, and the
  four shared types `Route/Model/Provider/Budgets`. Breaking change = coordinated interface bump (docs/43 §4).
- **This is the Config half of interface-freeze IF-2 (docs/52 §12)** — recorded as frozen in the
  Build Tracker **only on founder clearance**, not on authoring.
- Internal/free to change: file-parsing internals, error-message wording, the `schema`/`loader` split.
