# CHARTER HOUSE — ENVIRONMENT SPECIFICATION
## From Fresh Windows 11 → "Claude Code Ready"
### Infrastructure Architect deliverable · design-frozen architecture · v1.0

> Scope: the complete implementation environment that must exist **before** Claude Code writes a single file. No code, no repo files, no prompts. The Charter House architecture is frozen; this document does not touch it.
> Hard constraints honored throughout: **Windows 11**; repo root `K:\the_charter_house`; **`K:` abundant**; **`C:` has ~25 GB free → treat as nearly full**, redirect everything possible to `K:`; open-source preferred; minimal recurring cost; model-provider independence; local / remote / hybrid all supported.
> The governing infrastructure principle that follows from the 25 GB `C:` limit: **REMOTE-FIRST by default, local-where-it-pays.** Big model weights and Docker are not safe on a 25 GB `C:` drive; we therefore default to free/cheap cloud inference for heavy roles and keep only small, high-value workloads (embeddings, optionally a mid-size local model whose weights live on `K:`) on the machine. Local stays a **config switch**, never a requirement (consistent with the frozen routing layer).

---

# PART 1 — Hardware Assessment

### 1.1 First: measure the actual machine (do this before choosing a stack)
Run these read-only commands (PowerShell) and record the answers — they decide which stack in Part 4 is *your* default:
- CPU/RAM: `systeminfo | findstr /C:"Total Physical Memory"` and `wmic cpu get name,NumberOfCores`
- GPU/VRAM: `nvidia-smi` (NVIDIA) — note the GB; if it errors, you have no usable CUDA GPU → remote-first is mandatory for LLMs.
- Free space: confirm `C:` (~25 GB) and `K:` (record free GB).

### 1.2 Hardware tiers
| Tier | CPU | RAM | GPU / VRAM | K: free | C: free | Posture |
|---|---|---|---|---|---|---|
| **Minimum viable** | 4-core x86-64 | 16 GB | none (CPU only) | ≥40 GB | ~25 GB ok | **Remote-first.** Only local embeddings run on-device. |
| **Recommended** | 8-core | 32 GB | NVIDIA 12–16 GB (e.g. 4060 Ti 16GB / 4070) | ≥200 GB | ~25 GB ok | **Hybrid.** Embeddings + one mid local model local; hard roles remote. |
| **Ideal (power user)** | 12+ core | 64–128 GB | 24–48 GB (4090 / 5090 / dual) or 64–128 GB unified | ≥400 GB | ~25 GB ok | **Local-heavy.** Most roles local; remote break-glass only. |

### 1.3 What runs where (the realistic split)
- **Always LOCAL (any tier):** the **embedding model** (small; required local so PII never reaches the cloud during indexing — see frozen Memory Architecture R-REDACT) and the **vector store** (LanceDB, embedded). The **Conductor** itself is deterministic local code — no GPU.
- **LOCAL if GPU allows (Recommended+):** a mid-size reasoning/critic model (e.g., Qwen3-30B-A3B Q4 on 24 GB, or Qwen3-14B Q5 on 12–16 GB).
- **REMOTE (Minimum/Recommended), optional local (Ideal):** frontier coding + deep reasoning + 1M-context research. These need either a big GPU or the cloud; on a 25 GB-`C:` machine without a large GPU, they are **remote**.
- **Crucial point:** the `C:` 25 GB limit does **not** block local models — model weights live on `K:`. The gate for local LLMs is **VRAM**, not `C:`. The `C:` limit blocks *Docker images and tool caches*, which is why those are redirected (Part 9) and Docker is discouraged (Part 3).

---

# PART 2 — Canonical K:\ Layout

Top-level folders and their roles. "Backup importance" drives Part 6/10 backup strategy.

| Folder | Purpose | Expected contents | Est. growth | Backup importance |
|---|---|---|---|---|
| `K:\the_charter_house\` | **The repository** (git root) | docs, config, conductor, ai, agents, vault, data\ledger, templates | 0.1–2 GB (text) | **CRITICAL** (ledger + vault = the business) |
| `K:\Models\` | All model weights & caches | `ollama\`, `hf\`, `lmstudio\`, `vllm\` | 5–150 GB+ | Low (re-downloadable) |
| `K:\AI\` | AI runtime configs & UIs | `ollama\` runtime, `openwebui\` data, `vllm\` venv | 0.5–3 GB | Medium (configs) |
| `K:\Tools\` | Relocated dev tools | `Git\`, `Python\`, `nodejs\`, `VSCode\`, `Ollama\`, `opencode\`, `uv\` | 3–6 GB | Low (re-installable) |
| `K:\Data\` | Databases, vectors, caches | `charter_house\vectors\` (LanceDB), `cache\` (pip/npm/hf), `tmp\` | 1–20 GB | **High** (vectors; rebuildable but costly) |
| `K:\Logs\` | All runtime + install logs | install logs, conductor logs, model-server logs | 0.5–5 GB | Low |
| `K:\Downloads\` | Staging for installers/weights | `.exe`/`.zip` installers, raw model pulls before placement | transient | None (purge after) |
| `K:\Backups\` | Local backup target | dated ledger/vault snapshots, env exports | grows with snapshots | **CRITICAL** (it IS the backup) |

### 2.1 Complete directory tree
```
K:\
├── the_charter_house\              # REPO (git) — CRITICAL backup
│   ├── docs\                       # frozen design docs (the canonical specs)
│   ├── config\                     # providers/models/routes/profiles (.yaml)
│   ├── conductor\                  # engine (Phase 1)
│   ├── ai\                         # router + adapters (Phase 2)
│   ├── agents\                     # neutral capability specs (Phase 3)
│   ├── vault\                      # inbox, ventures\<slug>, memory\{lessons,playbooks}, archive
│   │   └── ventures\<slug>\        # brief.md, research\ (+ *.private.md sidecars), spec.md, partners.md, launch\
│   ├── data\
│   │   └── ledger\                 # append-only events (source of truth) — CRITICAL
│   ├── templates\                  # landing, saas-starter
│   ├── scripts\                    # built later, not now
│   ├── .env                        # secrets (gitignored)
│   └── .gitignore
├── Models\
│   ├── ollama\                     # OLLAMA_MODELS target (weights)
│   ├── hf\                         # HF_HOME (transformers/fastembed cache)
│   ├── lmstudio\                   # optional
│   └── vllm\                       # ideal tier only
├── AI\
│   ├── ollama\                     # ollama runtime/config
│   ├── openwebui\                  # optional chat UI data
│   └── vllm\                       # optional venv (WSL)
├── Tools\
│   ├── Git\  Python\  nodejs\  VSCode\  Ollama\  opencode\  uv\
├── Data\
│   └── charter_house\
│       ├── vectors\                # LanceDB files — HIGH backup
│       ├── cache\ {pip, npm, hf}   # redirected caches
│       └── tmp\
├── Logs\
├── Downloads\
└── Backups\
    └── YYYY-MM-DD\                 # ledger + vault + .env snapshots
```

---

# PART 3 — Required Software

Classification reflects the **remote-first, 25 GB-`C:`** posture. "Reloc?" = can be moved off `C:`.

| Tool | Class | Purpose / why Charter House needs it | Install path | Disk | Reloc? |
|---|---|---|---|---|---|
| **Git + Git Bash** | **MANDATORY** | version control of repo/ledger/vault; Bash shell the harness expects on Windows | `K:\Tools\Git` (installer custom dir) | ~0.4 GB | ✅ yes |
| **Python 3.12+** (via **uv**) | **MANDATORY** | AI layer, embeddings client, LanceDB, redaction/scan tooling | `K:\Tools\Python` or uv-managed in `K:\Tools\uv` | ~0.4 GB + venvs on K: | ✅ yes (uv → K:) |
| **Node.js LTS** | **MANDATORY** | runs **OpenCode**; saas-starter template tooling | `K:\Tools\nodejs` (zip build) | ~0.2 GB | ✅ yes (zip) |
| **OpenCode** | **MANDATORY** | the frozen primary coding-agent harness (model-agnostic) | `K:\Tools\opencode` (npm prefix on K:) | ~0.3 GB | ✅ yes |
| **Ollama** | **MANDATORY** | local **embedding** server (PII-safe indexing) + optional local LLMs | `K:\Tools\Ollama` via `/DIR`; weights `K:\Models\ollama` | program ~1.5 GB; weights on K: | ✅ mostly (see Part 5/9) |
| **LanceDB** (pip) | **MANDATORY** | the frozen embedded vector store; no server, no Docker | pip into K: venv; data `K:\Data\charter_house\vectors` | grows on K: | ✅ yes |
| **VS Code (Portable)** | **RECOMMENDED** | human oversight/editing; **portable build keeps extensions off `C:`** | `K:\Tools\VSCode` (portable) | ~0.5 GB incl. extensions | ✅ yes (portable) |
| **fastembed** (pip) | **RECOMMENDED** | in-process ONNX embeddings; zero-`C:` fallback if Ollama pressure | pip into K: venv; cache `K:\Models\hf` | ~0.3 GB on K: | ✅ yes |
| **LM Studio** | **OPTIONAL** | GUI model browser if you prefer it over Ollama | per-user (small C:); models → `K:\Models\lmstudio` | weights on K: | partial |
| **Open WebUI** | **OPTIONAL** | local browser chat over your models | pip or via Ollama; data `K:\AI\openwebui` | <2 GB on K: | ✅ yes |
| **Docker Desktop** | **OPTIONAL — DISCOURAGED** | only if you later run Qdrant; **unsafe on 25 GB `C:`** (core + WSL data land on C:) | core forced `C:\Program Files`; data-root → K: | 1–2 GB **on C:** + images | ❌ core on C: |
| **WSL2** | **OPTIONAL** | only for vLLM (Ideal tier) or Linux parity | kernel on C: (small); distro → K: | distro on K: | partial |
| **Qdrant** | **OPTIONAL** | vector store only at large scale (needs Docker/WSL) | Docker volume on K: | on K: | via Docker |
| **vLLM** | **OPTIONAL (Ideal)** | high-throughput local serving on a big GPU | WSL venv `K:\AI\vllm`; weights `K:\Models\vllm` | weights on K: | ✅ (WSL on K:) |

**Base "Claude Code Ready" set = the 6 MANDATORY + VS Code Portable.** Everything else is opt-in. **Docker and WSL are deliberately excluded from the base** to protect the 25 GB `C:` budget; LanceDB makes Docker unnecessary for memory.

---

# PART 4 — Model Strategy

Roles (frozen): **reasoning, coding, research/long-context, critic, retrieval(embedding)**. Model *names* are config and rotate; the *roles* are fixed. June-2026 leaders fill the slots. **Embedding model is frozen across all stacks = `nomic-embed-text`** (smallest capable, so the vector index is identical on every stack; changing it = deliberate full re-index).

### Stack A — Zero-cost (Minimum-viable hardware; default for a 25 GB-`C:`, no-GPU machine)
| Role | Model | Size | Quant | RAM | VRAM | Run | Strength / weakness |
|---|---|---|---|---|---|---|---|
| Reasoning | DeepSeek V4 / GLM-5.1 | (MoE) | — | — | — | **REMOTE** (OpenRouter/DeepInfra free) | frontier-open reasoning at $0; rate-limited |
| Coding | Qwen3.5-Coder / GLM-5.1 | (MoE) | — | — | — | **REMOTE** (free) | top open coding; rate limits |
| Research | Gemini 2.5 Flash | — | — | — | — | **REMOTE** (Google free, 1M ctx, ~1500/day) | huge context for pain-mining; closed |
| Critic | a *different family* than producer (e.g., Llama/Qwen free) | — | — | — | — | **REMOTE** (Groq/OpenRouter free) | enforces cross-model check; falls to tier-3 deterministic if rate-limited |
| Retrieval | **nomic-embed-text** | ~140M | — | ~1 GB | 0 (CPU) | **LOCAL** | free, private, CPU-ok; required local |
- Cost ≈ **$0/mo**; rate limits are the price; the factory's async cadence absorbs them. K: footprint ~2 GB.

### Stack B — Consumer hybrid (Recommended hardware: 12–24 GB VRAM)
| Role | Model | Size | Quant | RAM | VRAM | Run |
|---|---|---|---|---|---|---|
| Reasoning (routine) | Qwen3-30B-A3B (MoE) | 30B/3B act | Q4_K_M | 32 GB | ~17 GB | **LOCAL** |
| Reasoning (hard) | DeepSeek V4 | MoE | — | — | — | **REMOTE** (DeepInfra) |
| Coding | GLM-5.1 (cloud) + Qwen3-Coder-14B local | 14B | Q5_K_M | 32 GB | ~11 GB | **HYBRID** |
| Research | Gemini 2.5 Flash | — | — | — | — | **REMOTE** (free) |
| Critic | local 14B *or* a remote different-family | — | — | — | — | **HYBRID** |
| Retrieval | nomic-embed-text | ~140M | — | ~1 GB | 0–1 GB | **LOCAL** |
- Cost ≈ **<$20/mo**. K: footprint ~30–60 GB (weights). Leave 20–40% VRAM headroom for context.

### Stack C — Power-user (Ideal hardware: 24–48 GB VRAM or 128 GB unified; vLLM)
| Role | Model | Size | Quant | RAM | VRAM | Run |
|---|---|---|---|---|---|---|
| Reasoning | GLM-air-class / Qwen3.5 | ~40–48 GB | FP8 | 64 GB | ~40–48 GB | **LOCAL** (vLLM) |
| Coding | Qwen3.5-Coder | ~48 GB | FP8 | 64 GB | ~48 GB | **LOCAL** |
| Research | Qwen long-context (1M) local *or* Gemini free | — | FP8 | 64–128 GB | varies | **HYBRID** |
| Critic | a second local family (e.g., GLM vs Qwen) | — | — | — | shared | **LOCAL** (true cross-family) |
| Retrieval | nomic-embed-text (or Qwen3-Embedding for max quality) | 140M–8B | Q4 | 1–6 GB | 0–6 GB | **LOCAL** |
- Cost ≈ **electricity + rare break-glass cloud**. K: footprint ~120–200 GB. Max privacy + independence.

> Migration between stacks is **config-only** (routes.yaml/profiles) — except the embedding model, which is a deliberate re-index. Default recommendation for the stated constraints (25 GB `C:`, minimal cost, unknown GPU): **start on Stack A**, graduate to B if a 12 GB+ NVIDIA GPU is present.

---

# PART 5 — Ollama Decision

**Decision: INSTALL Ollama (MANDATORY), relocated to `K:`.**
- **Why:** the frozen Memory Architecture requires embeddings to be computed **locally** so customer PII is never sent to the cloud during indexing (R-REDACT). Ollama is the simplest open-source local server that (a) serves the frozen `nomic-embed-text` embedding model and (b) optionally serves local LLMs on Stacks B/C — all via an OpenAI-compatible `/v1` endpoint the router already speaks.
- **Role it serves:** (1) **always** — local embedding endpoint for retrieval/indexing; (2) **on GPU machines** — local reasoning/critic/coding models.
- **Models that belong there:** `nomic-embed-text` (all stacks); plus, by tier, `qwen3-30b-a3b` (B, 24 GB), `qwen3-coder-14b` (B), `glm`/`qwen3.5` FP8 (C, often via vLLM instead).
- **Storage (exact):** install program to `K:\Tools\Ollama` using `OllamaSetup.exe /DIR="K:\Tools\Ollama"`; set system env `OLLAMA_MODELS=K:\Models\ollama` **before the first pull**. If your Ollama build ignores `/DIR`, the ~1.5 GB program lands in `%LOCALAPPDATA%` on `C:` — acceptable but see the fallback.
- **Zero-`C:` fallback (documented, not default):** if `C:` pressure is acute, replace Ollama with **fastembed** (pip, in-process ONNX, no service, cache → `K:\Models\hf`) for embeddings and run any local LLM via LM Studio (models on K:). The embedding *model* stays `nomic-embed-text`, so the index remains compatible — no re-index needed when switching server.

---

# PART 6 — Vector Memory Decision

**Decision: LanceDB (primary). Confirmed from the frozen design; re-validated against the `C:` constraint.**

| Option | Verdict | Reason |
|---|---|---|
| **LanceDB** | **CHOSEN** | Embedded, file-based, **no server, no Docker** → zero `C:` footprint; files live on `K:\Data\charter_house\vectors`; perfect for a single-operator local-first system; trivial backup (copy files). |
| Chroma | rejected (primary) | Capable, but heavier/server-ish; no advantage over LanceDB for one operator. |
| Qdrant | deferred | Production-grade, but needs Docker/WSL → unsafe on 25 GB `C:`. Documented upgrade path only if retrieval volume ever demands a real server. |
| SQLite (+ vec ext) | rejected (primary) | Fine for metadata; LanceDB already covers vectors+metadata embedded. Optionally SQLite for the registry index if desired — but the ledger (files) is source of truth regardless. |
| Hybrid (LanceDB now → Qdrant later) | **the roadmap** | Start LanceDB; only migrate to Qdrant at scale, as a deliberate move. |

- **Storage location:** `K:\Data\charter_house\vectors` (LanceDB tables as files).
- **Backup strategy:** included in the daily/weekly snapshot to `K:\Backups\YYYY-MM-DD\` (copy the vectors dir + the ledger + the vault). Vectors are *rebuildable* from the redacted lesson records via re-embedding, so they're "High" not "Critical" — but snapshotting avoids costly re-index time. The **ledger + vault are CRITICAL** and must be in every snapshot and, ideally, pushed to a private git remote.
- **Scaling limits:** LanceDB comfortably handles the hundreds-to-low-millions of vectors a solo portfolio generates (lessons, research chunks) for years. Trigger to consider Qdrant: sustained multi-million-vector search or multi-process concurrent writes — neither expected at solo scale.

---

# PART 7 — Environment Variables & Configuration

All configuration is explicit and reproducible. Two homes: **machine-level** redirections (set once with `setx`, for caches/paths) and a **repo `.env`** (gitignored, for secrets + profile). No hidden state — everything below is documented and version-noted (values, not secrets, in a committed `.env.example`).

### 7.1 Storage / cache redirection (machine-level, `setx`)
| Variable | Purpose | Default (bad) | Example (set to) |
|---|---|---|---|
| `OLLAMA_MODELS` | Ollama weights location | `%USERPROFILE%\.ollama` | `K:\Models\ollama` |
| `HF_HOME` | HuggingFace/fastembed cache | `%USERPROFILE%\.cache\huggingface` | `K:\Models\hf` |
| `PIP_CACHE_DIR` | pip download cache | `%LOCALAPPDATA%\pip\Cache` | `K:\Data\charter_house\cache\pip` |
| `UV_CACHE_DIR` | uv cache | `%LOCALAPPDATA%\uv` | `K:\Data\charter_house\cache\uv` |
| `UV_PYTHON_INSTALL_DIR` | uv-managed Python location | `%LOCALAPPDATA%` | `K:\Tools\Python` |
| `NPM_CONFIG_CACHE` | npm cache | `%LOCALAPPDATA%\npm-cache` | `K:\Data\charter_house\cache\npm` |
| `NPM_CONFIG_PREFIX` | npm global install prefix | `%APPDATA%\npm` | `K:\Tools\opencode` |
| `TMP` / `TEMP` (optional) | scratch | `%LOCALAPPDATA%\Temp` | `K:\Data\charter_house\tmp` |
| `GIT_LFS_*` (if LFS used) | LFS cache | C: | `K:\Data\charter_house\cache\gitlfs` |

### 7.2 Charter House runtime (repo `.env`)
| Variable | Purpose | Default | Example |
|---|---|---|---|
| `CHARTERHOUSE_ROOT` | repo root | — | `K:\the_charter_house` |
| `CHARTERHOUSE_DATA_DIR` | ledger/data | `<root>\data` | `K:\the_charter_house\data` |
| `CHARTERHOUSE_VECTORS_DIR` | LanceDB dir | `K:\Data\charter_house\vectors` | same |
| `CHARTERHOUSE_PROFILE` | routing profile | `free` | `free` \| `cheap-cloud` \| `local-first` |
| `CHARTERHOUSE_EMBED_MODEL` | frozen embed model | `nomic-embed-text` | same (change = re-index) |
| `OLLAMA_HOST` | local model endpoint | `http://127.0.0.1:11434` | same |

### 7.3 Provider keys (repo `.env`, secrets — never committed)
| Variable | Purpose | Default | Example |
|---|---|---|---|
| `OPENROUTER_API_KEY` | cloud control plane + free models | — | `sk-or-...` |
| `DEEPINFRA_API_KEY` | cheapest direct open-model route | — | `...` |
| `GEMINI_API_KEY` | free 1M-context research | — | `...` |
| `GROQ_API_KEY` | fast/free latency role | — | `gsk_...` |
| `ANTHROPIC_API_KEY` | optional break-glass | — | `sk-ant-...` |
| `OPENAI_API_KEY` | optional | — | `sk-...` |

> Reproducibility rule: commit a `.env.example` listing every variable with placeholder values; keep real secrets only in `.env` (gitignored) and a copy in `K:\Backups`. A second machine is reproducible from `.env.example` + the `setx` list above.

---

# PART 8 — Installation Order (fresh Windows 11 → ready)

Order chosen to prevent wasted downloads (set cache/redirection env **before** anything pulls), duplicate installs, and wrong paths.

| # | Action | Expected result | Validation | Common failure |
|---|---|---|---|---|
| 0 | Create `K:` skeleton (Part 2 tree) | folders exist | `dir K:\` shows all | creating under `C:` by habit |
| 1 | **Set machine-level env vars** (Part 7.1) via `setx`, then open a NEW shell | vars present | `echo %OLLAMA_MODELS%` etc. | setting *before* `K:` folders exist; not reopening shell |
| 2 | Install **Git** → `K:\Tools\Git` (enable Git Bash) | git + bash work | `git --version` in Git Bash | default `C:\Program Files` path |
| 3 | Install **uv**; let it manage **Python 3.12** → `K:\Tools\Python` | python via uv | `uv --version`, `uv python list` | py launcher writing to `C:\Windows` (harmless) |
| 4 | Install **Node LTS** (zip) → `K:\Tools\nodejs`; set `NPM_CONFIG_PREFIX`/`CACHE` | node+npm on K: | `node -v`, `npm config get cache` → K: | MSI installing to `C:`; nvm-windows (C:-bound) |
| 5 | Install **VS Code Portable** → `K:\Tools\VSCode` | launches; `data\` in folder | extensions install under K: | using system installer (lands on C:) |
| 6 | Install **Ollama** → `OllamaSetup.exe /DIR="K:\Tools\Ollama"` | service runs | `ollama --version` | `/DIR` ignored → program on C: (acceptable / fallback) |
| 7 | **Pull embedding model FIRST:** `ollama pull nomic-embed-text` | model in `K:\Models\ollama` | `ollama list`; embed a test string | pulling before `OLLAMA_MODELS` set → lands on C: |
| 8 | (Stack B/C only) pull local LLM (e.g. `qwen3-30b-a3b`) | model on K: | a chat test responds | insufficient VRAM → OOM (drop quant/size) |
| 9 | Create repo venv with uv; `pip install lancedb fastembed` (cache→K:) | libs installed | write+read a test vector to `K:\Data\...\vectors` | pip cache on C: (env not set) |
| 10 | Install **OpenCode** (npm global → K: prefix) | `opencode` runs | `opencode --version` | global prefix still on C: |
| 11 | Create cloud accounts; put keys in repo `.env` (+ `.env.example`) | keys load | one router test hits a cloud model AND the local embed | committing secrets; keys in shell history |
| 12 | `git init` `K:\the_charter_house`; create tree; add `.gitignore` (.env, caches) | repo initialized | `git status` clean of secrets | `.env` not ignored |
| 13 | Place the **frozen design docs** into `docs\` | docs present | README links resolve | — |
| 14 | **Final validation** (Part 10 checklist) | all green | see Part 10 | — |

---

# PART 9 — Storage Redirection (keep `C:\Users\<user>\AppData` clean)

The 25 GB `C:` budget makes this section non-optional. Per tool: can it move, how, and limits.

| Tool / artifact | Normally pollutes | Relocate? | Exact method | Limitation |
|---|---|---|---|---|
| **Ollama models** (biggest) | `%USERPROFILE%\.ollama` | ✅ fully | `setx OLLAMA_MODELS K:\Models\ollama` before first pull | must set before pulling or re-download |
| **Ollama program** | `%LOCALAPPDATA%\Programs\Ollama` | ✅ mostly | `OllamaSetup.exe /DIR="K:\Tools\Ollama"` | older builds ignore `/DIR` → ~1.5 GB stays on C: |
| **HF / fastembed cache** | `~\.cache\huggingface` | ✅ | `setx HF_HOME K:\Models\hf` | none |
| **pip cache** | `%LOCALAPPDATA%\pip` | ✅ | `setx PIP_CACHE_DIR K:\...\cache\pip` | none |
| **uv cache + Python** | `%LOCALAPPDATA%\uv` | ✅ | `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR` | none |
| **npm cache + globals** | `%APPDATA%\npm`, `%LOCALAPPDATA%\npm-cache` | ✅ | `NPM_CONFIG_CACHE`, `NPM_CONFIG_PREFIX` | PATH must include K: prefix |
| **VS Code extensions** | `%USERPROFILE%\.vscode\extensions` | ✅ | use **Portable** build (`K:\Tools\VSCode\data`) | non-portable installs are C:-bound |
| **Node (runtime)** | `C:\Program Files\nodejs` | ✅ | use the **zip** build at `K:\Tools\nodejs` | MSI/nvm-windows are C:-bound |
| **Git** | `C:\Program Files\Git` | ✅ | choose `K:\Tools\Git` in installer | none |
| **LanceDB / vectors** | (app default) | ✅ | point `CHARTERHOUSE_VECTORS_DIR` to K: | none |
| **Embeddings cache** | HF cache | ✅ | covered by `HF_HOME` | none |
| **TEMP/scratch** | `%LOCALAPPDATA%\Temp` | ✅ (optional) | `setx TMP/TEMP K:\...\tmp` | some installers force C: temp |
| **Docker images** | `%LOCALAPPDATA%\Docker`, WSL vhdx on C: | ⚠️ partial | move data-root / `wsl --export/import` distro to K: | Docker Desktop core stays on C: → **avoid Docker** |
| **WSL distro** | `%LOCALAPPDATA%\Packages` | ⚠️ partial | `wsl --export` then `--import` to `K:\...` | kernel stays on C: |

**Net forced-`C:` residue with the recommended base set:** Git/Node/VSCode avoided entirely (all on K:), Python via uv on K:, caches on K:. The single likely C: item is the Ollama program (~1.5 GB) if `/DIR` is unsupported — well within 25 GB. **Docker and WSL are excluded specifically because their cores cannot leave `C:`.**

---

# PART 10 — Claude Code Readiness Checklist

The environment is **"CLAUDE CODE READY"** when every box is checked.

### Software checklist
- [ ] Git + Git Bash on K:, `git --version` works
- [ ] Python 3.12 (uv-managed) on K:, `uv` works
- [ ] Node LTS + npm on K:, prefix/cache on K:
- [ ] OpenCode installed, `opencode --version` works
- [ ] Ollama running (program on K: or accepted on C:), service responds
- [ ] LanceDB + fastembed installed in repo venv
- [ ] VS Code Portable on K: (recommended)

### Model checklist
- [ ] `nomic-embed-text` pulled, lives in `K:\Models\ollama`, embeds a test string
- [ ] At least one **reasoning** route works (remote free tier on Stack A, or local model on B/C)
- [ ] At least one **coding** route works
- [ ] A **critic** route of a *different model family* resolves (or tier-3 deterministic fallback confirmed)
- [ ] Chosen **profile** set in `.env` (`free` default)

### Storage checklist
- [ ] All Part 7.1 env vars set and verified in a fresh shell
- [ ] `C:` free space still ≥ ~20 GB after install
- [ ] Vectors dir on `K:`, test vector written and read
- [ ] `K:\Backups` exists; first snapshot of empty ledger/vault taken
- [ ] `.gitignore` excludes `.env` and caches; `.env.example` committed

### Validation checklist (end-to-end smoke)
- [ ] Embed locally → write to LanceDB → retrieve top-K (local round trip)
- [ ] Router call to a **remote** model succeeds (cloud reachable)
- [ ] Router **failover** works (kill primary key → fallback answers)
- [ ] A `contains_pii`-tagged context is **refused** by cloud adapters (redaction guard live)
- [ ] OpenCode can read the repo and list the `docs\` specs
- [ ] No secret appears in `git status` / git history

---

# PART 11 — Implementation Preparation (handoff to Claude Code)

### 11.1 Markdown files that belong IN the repository (`K:\the_charter_house\docs\`)
The frozen canonical set: `00_DOCTRINE`, `01_OPERATING_MODEL`, `02_GLOSSARY`, `10_VENTURE_LIFECYCLE`, `11_WORKFLOWS`, `12_GOVERNANCE`, `20_CONDUCTOR_SPEC`, `capabilities/{SCOUT,ANALYST,BUILDER,GROWTH,LIBRARIAN,CRITIC}`, `30_MEMORY_ARCHITECTURE`, `31_LEDGER_SCHEMA`, `32_RETRIEVAL_SPEC`, `40_PORTFOLIO`, `50_FOUNDER_MANUAL`, `60_REPOSITORY_STRUCTURE`, `70_IMPLEMENTATION_ROADMAP`, plus the **Lifecycle Stress Test** and **Revision Register (v1.1)** as `90_STRESS_TEST` / `91_REVISION_REGISTER`, and root `README` + generated `AGENTS.md`. This **Environment Specification** also belongs in-repo as `62_ENVIRONMENT.md` so the setup is reproducible alongside the design.

### 11.2 Files that should remain EXTERNAL to the repository
- `K:\` env/cache redirections (machine state, not repo) — documented but not committed.
- Real secrets `.env` (gitignored) + the backup copy in `K:\Backups`.
- Model weights (`K:\Models`), vector store (`K:\Data`), logs (`K:\Logs`) — all external, never committed (in `.gitignore`).
- `*.private.md` PII sidecars — **local-only, gitignored, never embedded, never pushed** (per R-REDACT).

### 11.3 Implementation phases (frozen roadmap, restated for handoff)
- **Phase 1 — Deterministic spine (no LLM):** Conductor (state machine, WIP, registry), Ledger + projections, governance action-class table + RED-token mechanism. Validate by moving a fake venture through every legal transition.
- **Phase 2 — Substrate:** AI router + adapters + `config/`, OpenCode harness adapter, embeddings + LanceDB + retrieval, golden-set harness, **redaction + pre-commit PII scan**. Validate failover + the PII cloud-block.
- **Phase 3 — Capabilities + workflows:** neutral specs for Scout/Analyst/Builder/Growth/Librarian + Critic ladder; the 5-beat workflows; governance enforcement (RED tokens, outbox, spend envelopes, send budget); templates. Validate one full dry-run venture, no real spend/send/deploy.
- **Phase 4 — Memory compounding + scale:** Librarian consolidation/promotion, calibration report, portfolio registry-as-view, backlog hygiene, alumni track + ceiling. Validate a simulated 50-venture portfolio stays O(active).

### 11.4 Recommended build order (one line)
Skeleton + env (this spec) → **Phase 1 spine** → **Phase 2 substrate (incl. PII guards)** → **Phase 3 capabilities/workflows** → **Phase 4 compounding/scale**. Safe before smart: gates, WIP, governance, and PII protection all exist before any capability is intelligent.

---

## Final statement
When Parts 8 and 10 are complete, the machine is **CLAUDE CODE READY**: a fresh Windows 11 box transformed into a remote-first, K:-resident, provider-independent, PII-safe environment that respects the 25 GB `C:` ceiling, costs ~$0 to start, and can run local models the moment a capable GPU is present — all without touching the frozen Charter House design. Claude Code's first action is Phase 1; nothing in the design is blocked by this environment.
