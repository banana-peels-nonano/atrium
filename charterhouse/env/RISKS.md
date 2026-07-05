# Environment (S2) — RISKS
Owner: A1 Environment Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced in |
|---|---|---|---|---|---|---|
| R1 | A subsystem reads env directly, bypassing `EnvContext` and the K:/profile discipline | High | High | architectural-integrity | env access funnels through `EnvContext`; static usage check fails the merge gate | `test_no_direct_env_read_outside_env` + merge gate |
| R2 | A hardcoded absolute path (or off-K: growing write) fills C: | Med | High | reliability/storage | all paths from `EnvContext`; growing-category guard refuses off-K: targets | `test_offK_growing_write_refused` |
| R3 | Partial boot: preflight proceeds with a missing prerequisite | Med | High | correctness | fail closed on first failure; no `EnvContext` returned | `test_no_partial_boot` |
| R4 | Compound/vague errors make setup un-actionable | Med | Med | usability | one precise error per item, with remediation referencing the Env Spec step | all `*_one_error` tests |
| R5 | A1↔A2 dependency cycle (Config reads env; A1 needs Config) | Med | Med | architectural-integrity | A1 reads env and injects `(config_dir, profile)` into `Config.load`; Config reads no env | Config `test_no_env_read` + this IMPLEMENTATION §6 |
| R6 | Silent auto-install/auto-pull masks a broken environment | Low | Med | reliability | no auto-install; only an explicit, logged embedding pull (docs/21) | IMPLEMENTATION §6 + review |
| R7 | `free` profile secretly requires a paid dependency | Low | High | cost/architecture | zero-paid-on-free asserted; embeddings local + free tiers only | `test_free_profile_zero_paid` |

## Refactor-avoidance notes
- The frozen seam is `preflight() -> EnvContext` + the `EnvContext` shape + `resolve(kind)`. Because every
  subsystem takes paths/profile/endpoints from `EnvContext`, changing where data lives on K: (or adding a
  path category) is a single-point change here — no consumer edits. This is the whole point of centralizing env.
- Making the env-boundary a *static test* (not a convention) means the discipline can't erode silently.

## Assumptions
- The machine follows the K:-only dependency/cache policy (tools→`K:\Tools`, caches→`K:\Data\charter_house\cache`,
  models→`K:\Models`) and the `setx` redirections in docs/25 §1 are set (verified by preflight check #1).
- A2 Config's `load(config_dir, profile)` and `get_route(role)` behave per its frozen `API.md` and read no env.
- Ollama exposes an OpenAI-compatible `/v1` with `nomic-embed-text` pulled to `K:\Models\ollama` (docs/20).
