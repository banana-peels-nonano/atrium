# 23 — STORAGE (on-disk layout + K: discipline for code)
**Owner:** Environment Agent (A1) · **Source of truth:** Environment Spec (Parts 2, 9), Repository Architecture

## Storage law (frozen, enforced by code)
All growing artifacts live on `K:`. `C:` (~25 GB) is treated as nearly full. The code MUST resolve every path from `EnvContext` (never hardcode), and MUST refuse to write large/growing data anywhere but `K:`.

## Path map the code uses (from env vars, `25`)
| Data | Path (K:) | Owner |
|---|---|---|
| Repo (code, docs, vault, ledger) | `K:\the_charter_house\` | all |
| Ledger events | `…\the_charter_house\data\ledger\` | S4 |
| Vault (ventures, memory, archive) | `…\the_charter_house\vault\` | S9/S12 |
| PII sidecars | `vault\…\*.private.md` (gitignored, local-only) | S7 |
| Vectors (LanceDB) | `K:\Data\charter_house\vectors\` | S9 |
| Caches (pip/npm/hf/uv) | `K:\Data\charter_house\cache\` | infra |
| Model weights | `K:\Models\ollama\` | infra |
| Logs | `K:\Logs\` | S14 |
| Backups | `K:\Backups\YYYY-MM-DD\` | S4/ops |

## MUST
- No absolute path is hardcoded; all come from `EnvContext`.
- Growing data (vectors, cache, logs, weights, ledger) is on `K:` — a write attempt outside `K:` for these categories fails closed.
- `*.private.md` is never embedded, logged, pushed, or copied off-machine (`INV-PII-4`).
- Backups include ledger + vault + vectors; ledger + vault are CRITICAL (also pushed to a private git remote if configured).

## Backup/restore contract (S4)
`snapshot()` copies ledger+vault(+vectors) to a dated `K:\Backups` folder; `restore(snapshot)` reproduces state; a restore-then-replay MUST reconstruct identical registry state (tested, `54` S4).

## Acceptance
Path resolution test (all via EnvContext); a large-write-to-C attempt is refused; restore reproduces state.
