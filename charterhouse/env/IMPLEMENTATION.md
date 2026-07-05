# Environment (S2) — IMPLEMENTATION
Owner: A1 Environment Agent   Subsystem: S2   Source of truth: docs/20_environment.md, docs/21_installation.md, docs/23_storage.md, docs/25_configuration.md + docs/43, docs/54 (Global/S2)

## 1. Responsibility (one paragraph)
S2 guarantees the code runs **only in a correctly-prepared environment**. It is the **sole reader of
environment variables** (docs/20): it resolves paths (K: discipline), the active profile, and service
endpoints into an immutable `EnvContext`, and runs a **deterministic preflight** that verifies every
prerequisite, failing closed with **exactly one precise, actionable error per missing item** (docs/21).
It **MUST NOT**: let any other subsystem read env directly (all go through `EnvContext`), hardcode any
absolute path (all come from env), auto-install/auto-download beyond an explicit logged embedding pull
(docs/21), call an LLM, or partial-boot (a missing prerequisite halts). It **owns no durable state** — the
`EnvContext` is a read-only value produced at startup.

## 2. Invariants enforced (no numbered INV owned; hard MUSTs from docs/20/23, testable)
- **Env-boundary MUST (docs/20, Phase-1 exit):** no module outside `charterhouse/env/` reads environment
  variables. *Guaranteed by:* a **static usage check** (A11 harness) asserting `os.environ`/`getenv` appears
  only in `env/`; violation fails the merge gate. All env access funnels through `EnvContext`.
- **K:-discipline MUST (docs/23):** growing data (ledger, vectors, cache, logs, weights, backups) resolves
  to K:; a large/growing write outside K: fails closed. *Guaranteed by:* the path resolver returns only
  K:-rooted paths for those categories + a guard that refuses off-K: targets for them.
- **One-precise-error MUST (docs/20, docs/21, docs/54):** each failure mode yields exactly one actionable
  message naming the item + remediation (referencing the Env Spec step). No compound/vague errors.
- **Zero-paid-on-`free` MUST (docs/20):** on the default `free` profile, preflight passes using local
  embeddings + free tiers only — no paid cloud dependency.
- **`INV-FAILCLOSED` / `INV-DET` (docs/61):** deterministic; no LLM; missing prerequisite → halt, never partial-boot.

## 3. Internal design
- **Deterministic**, no LLM. Modules: `paths` (env → resolved K: path map, docs/23), `context`
  (`EnvContext` immutable value: paths, profile, endpoints), `preflight` (the ordered checks), `healthcheck`
  (Ollama `/v1` reachability, embedding model present, LanceDB vectors dir).
- **`EnvContext` shape (docs/20):** `{ repo_root, data_dir, ledger_dir, vault_dir, vectors_dir, backups_dir,
  logs_dir, config_dir, models_dir, profile, ollama_host, embed_model }` — all absolute, all K:-rooted where
  docs/23 requires. Frozen/read-only.
- **Preflight checks (docs/20 §Preflight; ordered; each → one precise error):**
  1. required env vars present (docs/25 §1);
  2. K: paths exist + writable; C: headroom ≥ threshold;
  3. local embedding endpoint reachable (Ollama up, `nomic-embed-text` pulled);
  4. vector store path initialized;
  5. ≥1 model route resolvable for each role under the active profile — **via `Config.load(...)` (A2)**.
- **Config bootstrap (breaks the A1↔A2 cycle):** A1 reads env → derives `config_dir` + `profile`, then calls
  `Config.load(config_dir, profile)` (A2). Config reads no env; A1 injects. A1 depends on Config's frozen
  `API.md`; Config depends on nothing.

## 4. Dependencies
- **Consumes:** `Config.load(config_dir, profile)` + `Config.get_route(role)` (A2, docs/40 §1) for check #5.
- **Consumed by:** every subsystem that needs a path/profile/endpoint — they receive an `EnvContext`, never read env.
- Shared types (`EnvContext`) live in `charterhouse/contracts/` (docs/43 §6).

## 5. Failure behavior
| Failure mode | Fail-closed response (one precise error) |
|---|---|
| A required env var is unset | name the exact var + the `setx` remediation (docs/25 §1) |
| A K: path missing or not writable | name the path + that it must exist/writable on K: |
| C: headroom below threshold | name the shortfall + threshold |
| Ollama unreachable / embedding model not pulled | name the endpoint/model + the pull step (docs/21) |
| Vectors dir uninitialized | name the vectors path |
| No route resolvable for a role | surface Config's located error for that role/profile |
| A subsystem attempts an off-K: growing write | refuse + log (K:-discipline guard) |
Never partial-boot; never auto-install beyond an explicit, logged embedding pull.

## 6. Open questions → RESOLVED
- **Q: Does A1 or A2 own the profile source (`CHARTERHOUSE_PROFILE`)?** **RESOLVED —** A1 reads it (sole env
  reader) and passes the name to `Config.load`. Config never touches env. (Matches Config `IMPLEMENTATION §6`.)
- **Q: Is the "no direct env read" rule testable, not just documented?** **RESOLVED — Yes.** A11 provides a
  static usage check (grep/AST) asserting `os.environ`/`getenv` outside `env/` = 0; wired as an acceptance test + merge gate.
- **Q: May preflight auto-create missing K: dirs?** **RESOLVED —** it may create the *runtime* subdirs it owns
  the contract for (ledger/vectors/logs/backups roots) when their K: parent exists and is writable; it never
  creates drives, installs software, or pulls models silently (only an explicit, logged embedding pull, docs/21).
