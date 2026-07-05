# Config (S3) — RISKS
Owner: A2 Config Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced in |
|---|---|---|---|---|---|---|
| R1 | A silent-default path substitutes a value for a missing/invalid config key, masking misconfiguration | Med | High | security/architectural-integrity | fail-closed loader; no defaults for routing/security values | code + `test_missing_required_key_rejected_located` |
| R2 | A secret value leaks into `Config`/logs via a provider entry | Low | Critical | security | `key_env` is a name only; Router reads secret at call time (docs/24); secret scan gate (docs/63 #6) | code + `test_get_provider_exposes_key_env_not_secret` + CI secret scan |
| R3 | Config reads env directly, breaking the docs/20 env-boundary and creating an A1↔A2 cycle | Med | Med | architectural-integrity | `load(config_dir, profile)` takes inputs as params; no `os.environ` in `config/` | code + `test_no_env_read` + anti-coupling check |
| R4 | YAML parser executes arbitrary objects (unsafe load) | Low | High | security | safe-load-only, pinned parser; new-dep review (docs/61) | code + RISKS review |
| R5 | Unknown-key tolerance lets config drift from schema silently | Med | Med | ambiguity | strict validation rejects unknown keys | `test_unknown_key_rejected_located` |
| R6 | Profile precedence implemented as code branches (not data), reintroducing per-profile code paths | Low | Med | refactor | precedence applied as data overlay; single resolution path | `test_profile_switch_reroutes_no_code_change` |
| R7 | `INV-CFG` checked only partially (route→model but not model→provider) | Med | High | architectural-integrity | both clauses tested separately | `test_invcfg_*` (two tests) |

## Refactor-avoidance notes
- The frozen seam is the five `Config.*` methods + four shared types (docs/40 §1). Keeping the
  profile system **data-driven** (overlays, not code) means adding a profile or model is a config
  edit, never a code change — directly serving priority #4 (minimal refactoring) and docs/54 §S3.
- Shared types live once in `charterhouse/contracts/` (docs/43 §6); changing one is an ICR, not a local edit.

## Assumptions
- A1's `EnvContext` supplies a valid `config_dir` and resolves `CHARTERHOUSE_PROFILE` → `profile`
  (matches A1 `API.md`). Config assumes nothing else about the environment.
- The Router (A6) consumes `get_route/get_model/get_provider` exactly as in docs/40 §5 and performs
  role→model resolution using this data (no role policy lives in Config).
