# Config (S3) — TESTPLAN
Owner: A2 Config Agent   (written BEFORE implementation)

## Unit tests
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_valid_config_loads_immutable` | a well-formed config dir loads; result is frozen (mutation raises) | fixture config dir | docs/54 §S3 row 1 |
| `test_unknown_key_rejected_located` | an extra/unknown key → load rejected; error names file + key path | fixture with stray key | `INV-CFG`/unknown-key |
| `test_missing_required_key_rejected_located` | a missing required key → rejected with location | fixture missing key | fail-closed |
| `test_yaml_syntax_error_located` | malformed YAML → rejected; error names file + line | broken fixture | fail-closed |
| `test_invcfg_route_references_absent_model` | route primary/fallback naming a missing model id → rejected; names role + model | dangling-route fixture | **`INV-CFG` clause 1** |
| `test_invcfg_model_references_absent_provider` | model naming a missing provider id → rejected; names model + provider | dangling-provider fixture | **`INV-CFG` clause 2** |
| `test_profile_switch_reroutes_no_code_change` | same `get_route(role)` under profile A vs B → different resolved model | two-profile fixture | docs/54 §S3 row 3 |
| `test_unknown_profile_rejected` | requesting an absent profile → rejected; lists known profiles | fixture | fail-closed |
| `test_get_provider_exposes_key_env_not_secret` | `get_provider(id).key_env` is a name; no secret value present | fixture | docs/24 secrets rule |
| `test_get_unknown_id_raises_typed` | `get_route/model/provider` unknown id → typed lookup error, no default | fixture | fail-closed |
| `test_no_env_read` | loading with a mutated `os.environ` yields identical `Config` (no env dependence) | monkeypatched env | docs/20 env-boundary |
| `test_precedence_order` | overrides > profile > routes-default resolves correctly | layered fixture | docs/25 §3 |

## Integration tests
| Test | Partner | Scenario | Expected |
|---|---|---|---|
| `it_router_resolves_role_via_config` | A6 Router (stub against docs/40 §5) | Router asks `get_route('reasoning')` under `free` | resolves the `free`-profile model; no code branch on profile |
| `it_env_preflight_uses_config` | A1 Environment | `EnvContext` calls `Config.load(env.config_dir, env.profile)` then checks ≥1 route/role resolvable | happy path passes; a dangling route fails preflight with the located Config error |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| `INV-CFG` clause 1 (route→model) | `test_invcfg_route_references_absent_model` | unit |
| `INV-CFG` clause 2 (model→provider) | `test_invcfg_model_references_absent_provider` | unit |
| Unknown-key rejection (docs/25 §4) | `test_unknown_key_rejected_located` | unit |
| Profile-switch zero-code (docs/54 §S3) | `test_profile_switch_reroutes_no_code_change` | unit + integration |
| Secrets-are-names-only (docs/24) | `test_get_provider_exposes_key_env_not_secret` | unit |
| Env-boundary (docs/20) | `test_no_env_read` | unit |
| `INV-FAILCLOSED` (docs/61) | all `*_rejected*` tests | unit |
| `INV-DET` (docs/61) | anti-coupling import check (harness, A11) | static |

## Fixtures/fakes needed (from A11 shared harness)
- Config fixture directories (valid, and one per failure mode). No FakeProvider/Embedder/Clock needed (S3 has no LLM/time/PII surface).

## Out of scope (test-safety)
No real spend/send/deploy/charge is exercised (`INV-TEST-SAFE`). S3 performs no actions and no network I/O.
