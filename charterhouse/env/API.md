# Environment (S2) — API
Owner: A1 Environment Agent   ·   `EnvContext` per docs/20 (the frozen S2 surface)

## Exposed surface

### `preflight() -> EnvContext`
- **Preconditions:** the machine is intended to be "Claude Code Ready" (docs/21).
- **Postconditions:** on success returns an immutable `EnvContext`; every prerequisite in docs/20 §Preflight
  has passed, including ≥1 resolvable route per role under the active profile (checked via `Config`).
- **Errors (fail closed):** the **first** failing check raises with exactly one precise, actionable message
  (item + remediation). No partial `EnvContext` is returned.
- **Side effects:** may create runtime subdirs it owns (under an existing writable K: parent) and may perform
  one explicit, logged embedding pull (docs/21); no other installs. **Determinism:** deterministic (I/O on local FS + a local health ping). **Auth:** n/a.

### `EnvContext` (immutable value; shared type in `charterhouse/contracts/`)
```
repo_root, data_dir, ledger_dir, vault_dir, vectors_dir, backups_dir, logs_dir,
config_dir, models_dir, profile, ollama_host, embed_model
```
- All paths absolute and K:-rooted where docs/23 requires. Read-only (mutation raises).

### `resolve(kind: PathKind) -> Path`
- Returns the K:-disciplined path for a category (`ledger`/`vectors`/`cache`/`logs`/`weights`/`backups`/…).
- **Errors:** an off-K: target for a growing category → refuse (fail closed). **Determinism:** pure. **Side effects:** none.

## Consumed surface
- `Config.load(config_dir: Path, profile: str | None) -> Config` and `Config.get_route(role) -> Route`
  (A2, docs/40 §1) — used by preflight check #5. **Failure handling:** a Config located error is surfaced as
  the preflight error for that role/profile (fail closed).

## Interface stability
- **Frozen:** `preflight() -> EnvContext`, the `EnvContext` shape, and `resolve(kind)`. Every subsystem receives
  paths/profile/endpoints through `EnvContext` and never reads env. Change = ICR (docs/43 §4).
- Internal/free to change: the check implementations, health-ping details, error wording.
