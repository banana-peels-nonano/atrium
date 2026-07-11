# Config (S3) — IMPLEMENTATION
Owner: A2 Config Agent   Subsystem: S3   Source of truth: docs/25_configuration.md, docs/22_models.md + docs/40 §1, docs/43, docs/54 §S3

## 1. Responsibility (one paragraph)
S3 loads, schema-validates, and exposes all Charter House **behavioral configuration** —
`providers.yaml`, `models.yaml`, `routes.yaml`, and `profiles/*.yaml` — as an **immutable,
typed `Config` object**, applying profile precedence and enforcing `INV-CFG` at load time.
It is a **pure loader over files**: given a config directory and a profile name, it returns
the same `Config` every time. It **MUST NOT** read environment variables (that is A1's sole
job — docs/20), **MUST NOT** read or hold secret *values* (it exposes the env-var *name*
`key_env`; the Router reads the secret at call time — docs/24), **MUST NOT** call an LLM
(deterministic module, docs/61 §INV-DET), and **MUST NOT** perform any routing *decision*
about which role maps to which model beyond returning the config data (role→model *policy*
is data here; role *assignment* is S10/S12).

## 2. Invariants enforced
- **`INV-CFG` (docs/25 §4) — both clauses, enforced at load, fail closed:**
  1. every `routes.yaml` `primary` and every `fallback[]` entry names a model id present in
     `models.yaml`;
  2. every `models.yaml` model's `provider` names a provider id present in `providers.yaml`.
  A dangling reference → reject the whole load with a **located error** (file + key path).
  *Guaranteed by:* a post-parse cross-reference pass that runs before `Config` is constructed;
  no partial `Config` is ever returned.
- **Unknown-key rejection (docs/25 §4):** any key not in a file's schema → reject with a
  located error. *Guaranteed by:* strict schema validation (no silent drop, no extra-key pass-through).
- **Profile-switch = zero code change (docs/25 §3, docs/22, docs/54 §S3):** the active profile
  overlays route/budget overrides via documented precedence
  (CLI arg > profile > `routes.yaml` default > `models.yaml`/`providers.yaml` base).
  *Guaranteed by:* profile overrides are applied as data at load; the same call resolves a
  different model under a different profile with no code path change.
- **`INV-DET` (docs/61):** no model call; `config/` imports none of `router`/`memory`/`capabilities`.
- **`INV-FAILCLOSED` (docs/61):** malformed/ambiguous config → reject + structured log; never a silent default.

## 3. Internal design
- **Deterministic**, pure. No durable state (config is read-only; the ledger holds no config).
- Modules: `schema` (typed shapes + strict validators for the 4 file kinds), `loader`
  (parse YAML → validate → cross-ref `INV-CFG` → apply profile precedence → freeze),
  `model` (the immutable `Config` facade exposing docs/40 §1).
- Typed shapes (shared types live in `charterhouse/contracts/`, docs/43 §6):
  `Route{primary, fallback[], min_ctx?, needs_tools?, needs_web?}`,
  `Model{provider, ctx, price_in, price_out, tier, good_at[]}`,
  `Provider{base_url, key_env, kind}`, `Budgets{monthly_usd, on_exceeded, send_daily}`.
- **YAML parser:** one pinned, safe-load-only library (no arbitrary object construction). Pinned in `pyproject.toml`; noted in RISKS.
- Immutability: the returned `Config` is frozen (read-only dataclasses / mapping proxies); callers cannot mutate resolved routes.

## 4. Dependencies
- **Consumes:** none of the subsystem APIs. Inputs are a `config_dir: Path` and a `profile: str | None`
  **passed in by the caller** (A1's `EnvContext` supplies both). This breaks the A1↔A2 cycle
  cleanly: Config never reads env; A1 resolves env → paths+profile, then calls `Config.load(...)`.
- **Consumed by:** A1 Environment (preflight route-resolvability check), A6 Router (role→model resolution).
- Shared types imported from `charterhouse/contracts/` (owned by Interface Agent, docs/43 §6).

## 5. Failure behavior
| Failure mode | Fail-closed response |
|---|---|
| YAML syntax error | reject load; error names file + line |
| Unknown key | reject load; error names file + key path |
| Missing required key | reject load; error names file + key path |
| Route references absent model (`INV-CFG` clause 1) | reject load; error names route role + missing model id |
| Model references absent provider (`INV-CFG` clause 2) | reject load; error names model id + missing provider id |
| Unknown profile name requested | reject load; error names the profile + lists known profiles |
| `get_route/get_model/get_provider` for unknown id at query time | raise typed lookup error; never return a guessed default |
No path partial-loads or substitutes a default for a security/routing value.

## 6. Open questions → RESOLVED
- **Q: Does Config read `CHARTERHOUSE_PROFILE` / paths from env?** **RESOLVED — No.** docs/20 mandates
  env is read only via A1's `EnvContext`. `Config.load(config_dir, profile)` takes both as
  parameters; A1 reads env and injects them. This also removes a would-be A1↔A2 dependency cycle.
- **Q: Does Config hold secret values?** **RESOLVED — No.** `Provider.key_env` is the env-var *name*;
  the Router reads the secret at call time (docs/24). Config exposing a secret value would violate docs/24.
- **Q: CLI-arg precedence (docs/25 §3) — who supplies it?** **RESOLVED —** `Config.load` accepts an
  optional `overrides` mapping for the CLI-arg tier; the CLI/Conductor supplies it. Absent overrides, precedence starts at profile.
- **Q: Where does the default `Budgets` live, given docs/31 lists no `budgets.yaml`?** **RESOLVED —**
  `routes.yaml` carries two top-level keys: `budgets` (the default envelope) and `routes` (role→Route).
  docs/25 §2 describes profiles as overriding "routes/budgets", so both defaults sit in the one behavioral
  file and profiles overlay either. With no profile, `budgets` resolves to this default and `profile == "default"`.
- **Q: docs/54 §S3 lists "embed-model mismatch refused" — does S3 own it?** **RESOLVED — No; A1 owns it.**
  The check compares `CHARTERHOUSE_EMBED_MODEL` (an **env** value) against the marker the vector index was
  built with (a **filesystem** read). S3 reads neither env nor the vector store by contract (docs/20), so the
  refusal lives in A1 preflight (which owns env + vector-store access); Config only exposes config data. Flagged
  as a cross-subsystem consistency note in the A2 tracker row for founder confirmation.
