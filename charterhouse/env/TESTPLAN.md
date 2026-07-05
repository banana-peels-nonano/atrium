# Environment (S2) — TESTPLAN
Owner: A1 Environment Agent   (written BEFORE implementation)

## Unit tests
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_preflight_passes_on_ready_machine` | with all prereqs satisfied → returns a valid immutable `EnvContext` | temp K:-like fs + fake Ollama ping | docs/54 §S2 happy path |
| `test_missing_env_var_one_error` | an unset required var → one precise error naming var + `setx` remedy | monkeypatched env | one-precise-error |
| `test_k_path_missing_or_readonly_one_error` | missing/non-writable K: path → one precise error naming the path | temp fs | K:-discipline |
| `test_c_headroom_below_threshold_one_error` | low C: headroom → one precise error naming shortfall | faked disk stat | docs/20 |
| `test_ollama_unreachable_one_error` | embedding endpoint down / model absent → one precise error + pull step | fake failing ping | docs/21 |
| `test_vectors_dir_uninitialized_one_error` | missing vectors dir → one precise error | temp fs | docs/20 |
| `test_no_route_for_role_surfaces_config_error` | a dangling route → preflight fails with Config's located error | Config fixture (dangling) | integration w/ A2 |
| `test_offK_growing_write_refused` | `resolve()`/guard refuses an off-K: target for a growing category | temp fs | **K:-discipline** (docs/23) |
| `test_envcontext_immutable` | mutating `EnvContext` raises | — | immutability |
| `test_no_partial_boot` | any single failure → no `EnvContext` returned (halt) | fault matrix | `INV-FAILCLOSED` |
| `test_free_profile_zero_paid` | on `free`, preflight passes with local embeddings + free tiers only | free-profile fixture | zero-paid-on-free (docs/20) |
| `test_no_direct_env_read_outside_env` (static) | `os.environ`/`getenv` occurs only under `charterhouse/env/` | repo AST/grep scan | **env-boundary MUST** (docs/20) |

## Integration tests
| Test | Partner | Scenario | Expected |
|---|---|---|---|
| `it_preflight_config_healthcheck_happy` | A2 Config + fake Ollama | full preflight → Config load → route check → health ping | passes; returns `EnvContext`; `Config.load` called with `(env.config_dir, env.profile)` |
| `it_subsystems_use_envcontext_paths` | A3 Ledger (stub) | Ledger receives `env.ledger_dir`; no direct env read | Ledger writes under K: ledger dir; static check green |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| Env-boundary (no env read outside `env/`) | `test_no_direct_env_read_outside_env` (static) | static/acceptance |
| K:-discipline (refuse off-K: growing write) | `test_offK_growing_write_refused` | unit |
| One-precise-error per missing prereq | all `*_one_error` tests | unit |
| No partial boot (`INV-FAILCLOSED`) | `test_no_partial_boot` | unit |
| Zero-paid on `free` | `test_free_profile_zero_paid` | unit |
| Route resolvability via Config | `test_no_route_for_role_surfaces_config_error`, `it_preflight_config_healthcheck_happy` | unit + integration |
| `INV-DET` | anti-coupling import check (A11) | static |

## Fixtures/fakes needed (from A11 shared harness)
- A temp K:-like filesystem fixture; a fake Ollama health endpoint (programmable up/down + model-present);
  Config fixtures (valid + dangling route). No FakeProvider (no LLM call here) beyond the health ping stub.

## Out of scope (test-safety)
No real spend/send/deploy/charge (`INV-TEST-SAFE`). The only outbound touch is a local Ollama health ping
(faked in tests); the optional embedding pull is not exercised against the network in CI.
