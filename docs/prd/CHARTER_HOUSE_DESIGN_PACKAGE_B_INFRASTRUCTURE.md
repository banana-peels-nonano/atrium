# CHARTER HOUSE — DESIGN PACKAGE B
## Infrastructure & Build (Parts 6–11) + Final Summary
### Design Freeze · v1.0 · source material for Claude Code implementation

> Companion to Package A (Operating Specs). Same freeze rules. Repository root: `K:\the_charter_house`.
> **Storage law (frozen):** everything lives on `K:\` unless Windows forces otherwise. Every forced-`C:\` case below is justified. Big artifacts (model weights, vector store, caches, logs, datasets) are **always** on `K:\` — these are the GB-scale items and there is no technical reason for them to touch `C:\`.
> Infrastructure facts reflect the June 2026 landscape; per the future-proofing doctrine, models and providers are configuration — the *shape* of this stack is what's frozen, not the specific model names.

---

# PART 6 — Repository Architecture
### (`docs/60_REPOSITORY_STRUCTURE.md`)

### 6.1 Top-level `K:\` layout (frozen)
The repository is one folder; the broader AI environment lives in sibling `K:\` folders so weights and caches are shared across projects and never bloat the repo.

```
K:\
├── the_charter_house\            # THE REPOSITORY (git root)
├── AI\                           # serving configs + Open WebUI data + runtime
│   ├── ollama\                   # ollama runtime config (models go to K:\Models)
│   ├── openwebui\                # Open WebUI data dir
│   └── vllm\                     # vLLM venv + serve configs (serious stack)
├── Models\                       # ALL model weights (the big storage)
│   ├── ollama\                   # OLLAMA_MODELS target
│   ├── lmstudio\                 # LM Studio models dir
│   └── vllm\                     # FP8/HF weights for vLLM
├── Tools\                        # relocatable dev tools
│   ├── Git\  Python\  nodejs\  VSCode\  opencode\
├── Data\                         # databases, vectors, caches, datasets
│   └── charter_house\
│       ├── vectors\              # local vector store (LanceDB files / Qdrant volume)
│       ├── cache\                # embedding + inference caches
│       └── backups\              # ledger backups
└── Logs\                         # all runtime + install logs
```

### 6.2 Inside `K:\the_charter_house\` (the repo)
```
the_charter_house\
├── README.md
├── AGENTS.md                     # harness-neutral constitution pointer (generated)
├── docs\                         # ALL design specs (this package, split into files)
│   ├── 00_DOCTRINE.md ... 02_GLOSSARY.md
│   ├── 10_VENTURE_LIFECYCLE.md  11_WORKFLOWS.md  12_GOVERNANCE.md
│   ├── 20_CONDUCTOR_SPEC.md
│   ├── 30_MEMORY_ARCHITECTURE.md  31_LEDGER_SCHEMA.md  32_RETRIEVAL_SPEC.md
│   ├── 40_PORTFOLIO.md  50_FOUNDER_MANUAL.md
│   ├── 60_REPOSITORY_STRUCTURE.md  61_LOCAL_AI_STACK.md  62_MODEL_STRATEGY.md
│   ├── 63_DEV_ENVIRONMENT.md  64_INSTALLATION_GUIDE.md  70_IMPLEMENTATION_ROADMAP.md
│   └── capabilities\ SCOUT.md ANALYST.md BUILDER.md GROWTH.md LIBRARIAN.md CRITIC.md
├── ai\                           # the universal AI layer (router, adapters) — built in Phase 2
├── config\                       # providers.yaml, models.yaml, routes.yaml, profiles\
├── conductor\                    # the engine — built in Phase 1
├── agents\                       # neutral capability specs (*.agent.md) — Phase 2/3
├── adapters\harness\             # opencode\ (primary), claude-code\, aider\ generators
├── vault\                        # the knowledge + venture store (Obsidian-openable)
│   ├── inbox\                    # raw signal captures
│   ├── ventures\<slug>\          # brief.md, research\, experiments\, spec.md, launch\
│   ├── memory\
│   │   ├── lessons\<id>.md       # discrete lesson records
│   │   └── playbooks\            # channel/pricing/segment
│   ├── archive\                  # killed ventures (post-salvage)
│   └── PIPELINE.md               # board projection (generated)
├── data\
│   ├── ledger\                   # append-only event records (source of truth)
│   └── metrics\METRICS.md        # projection
├── templates\ landing\ saas-starter\
└── scripts\                      # operational scripts — built in implementation, not now
```

**Rationale:** the repo holds *specs, config, engine, agents, vault, ledger* — all small, git-friendly, human-readable text. The GB-scale assets (`Models`, `vectors`, `cache`, `logs`) live **outside** the repo under `K:\`, so git stays light and weights are reused across projects. Venture *product* code lives in separate `venture-<slug>` repos after graduation, never inside this one.

---

# PART 7 — Local AI Infrastructure
### (`docs/61_LOCAL_AI_STACK.md`)

Goal: maximum capability, minimal recurring cost, model independence, future-proof. Decisions are frozen at the **component** level; specific models are config (Part 8).

| Component | Decision | Purpose | Install location | Storage | Pros | Cons |
|---|---|---|---|---|---|---|
| **Ollama** | **INSTALL (primary serving)** | One-command local LLM + embedding serving; OpenAI-compatible `/v1` | program: `C:\...\Programs\Ollama` (forced, small binary); **weights: `K:\Models\ollama`** via `OLLAMA_MODELS` | weights 1–60 GB+ on K: | trivial ergonomics, auto CUDA/ROCm, embeddings too | lower throughput than vLLM |
| **LM Studio** | **OPTIONAL (laptop/GUI)** | GUI model browser + server for non-technical operation | app per-user (C:, small); **models dir → `K:\Models\lmstudio`** | weights on K: | best UX, easy model discovery | GUI-centric; redundant if Ollama used |
| **Open WebUI** | **OPTIONAL (chat UI)** | Local browser chat over Ollama/any endpoint for manual use | Docker or pip; **data → `K:\AI\openwebui`** | <2 GB on K: | nice manual interface, RAG playground | extra moving part; not needed for the Conductor |
| **vLLM** | **INSTALL only on Serious stack** | High-throughput FP8 serving for 48GB+ GPUs | WSL2 venv at `K:\AI\vllm`; **weights `K:\Models\vllm`** | weights 30–80 GB on K: | far higher throughput, batching, FP8 | Linux/WSL only; heavier setup |
| **OpenRouter** | **CONFIGURE (cloud control plane)** | Unified billing + failover across cloud open models; free tier | none (API); key in env | none | breadth, failover, free models | cloud dependency (mitigated by local) |
| **Local embeddings** | **INSTALL (via Ollama)** | Compute vectors locally for retrieval; **frozen model** | served by Ollama; weights `K:\Models\ollama` | 0.3–5 GB on K: | free, private, no API | re-index if model changes |
| **Vector DB** | **LanceDB (primary), Qdrant (scale)** | Local semantic retrieval store | LanceDB = embedded files at `K:\Data\charter_house\vectors`; Qdrant = Docker volume on K: | grows with lessons, on K: | LanceDB: zero-server, file-based, perfect for solo local; Qdrant: production-grade | Chroma/pgvector viable but not chosen |

### 7.1 Frozen choices and why
- **Serving:** Ollama for all tiers (embeddings + small/mid LLMs); add vLLM only when a 48GB+ GPU justifies throughput. LM Studio and Open WebUI are *optional human conveniences*, not part of the Conductor's path.
- **Vector store:** **LanceDB** is the frozen default — embedded, file-based, lives as plain files on `K:\Data\charter_house\vectors`, no server to run or secure, ideal for a single-operator local-first system. **Qdrant** (Docker volume on K:) is the documented upgrade path if/when retrieval volume demands a real server.
- **Embeddings:** chosen and **frozen** now (Part 8) because changing the embedding model forces a full re-index.
- **Cloud:** OpenRouter as control plane + DeepInfra direct for cheap bulk + Groq/Gemini-free for speed/zero-cost — all behind the router. No single cloud dependency.

---

# PART 8 — Model Strategy
### (`docs/62_MODEL_STRATEGY.md`)

Roles (frozen): **primary-reasoning**, **coding**, **research/long-context**, **retrieval/embedding**, **fallback**. Model *names* are config and will rotate; the *role structure* is frozen. June-2026 leaders are used as the initial fill.

### 8.0 Embedding model — FROZEN for all stacks
| Choice | Why | Footprint |
|---|---|---|
| **`nomic-embed-text` (v2) via Ollama** as the default; **`bge-m3`** if heavy multilingual; **`Qwen3-Embedding` (Q4)** on the Serious stack for max quality | strong retrieval@10, long-doc friendly, free + local; consistent across stacks so the index is portable | nomic ~0.3 GB · bge-m3 ~1.2 GB · Qwen3-Embedding Q4 ~5 GB, all on `K:\Models\ollama` |
> **Pick one and freeze it before the first index is built.** Default recommendation: **nomic-embed-text** (smallest, runs even on the zero-cost/laptop stack, so the index is identical whether you're on Stack A, B, or C). Upgrade to Qwen3-Embedding only as a deliberate, scheduled re-index.

### 8.A Zero-cost stack (no GPU required)
| Role | Model | Source | Why | Local footprint |
|---|---|---|---|---|
| Reasoning | DeepSeek V4 / GLM-5.1 | OpenRouter **free** / DeepInfra | frontier-open reasoning at $0 on free tier | none |
| Coding | Qwen3.5-Coder / GLM-5.1 | OpenRouter free | top open coding | none |
| Research | Gemini 2.5 Flash | Google AI Studio **free** (1,500 rpd, 1M ctx) | huge context for web/pain mining, free | none |
| Retrieval | nomic-embed-text | **Ollama, local** | free, private, CPU-OK | ~0.3 GB on K: |
| Fallback | Llama / Qwen free | Groq free / OpenRouter free | speed + redundancy | none |
- **Hardware:** any machine; only embeddings run locally (CPU fine). **VRAM: 0 required. RAM: 8 GB+.**
- **Cost:** ~$0/mo; rate limits are the price; the factory's async cadence absorbs them.

### 8.B Consumer hardware stack (24 GB VRAM class, e.g. RTX 4090; 32–64 GB RAM)
| Role | Model | Source | Quant | VRAM | Why |
|---|---|---|---|---|---|
| Reasoning (routine) | **Qwen3-30B-A3B (MoE)** | Ollama local | Q4_K_M | ~17 GB | MoE keeps it fast; handles scout/ops/light-analyst locally for free |
| Reasoning (hard) | DeepSeek V4 | DeepInfra | — | cloud | escalation for kill-decisions (accepted routing) |
| Coding | **GLM-5.1** (cloud) + Qwen3-Coder-14B local | DeepInfra / Ollama | local Q5_K_M | ~11 GB | cloud for real MVP builds; local for light edits |
| Research | Gemini 2.5 Flash | free | — | cloud | 1M context, free |
| Retrieval | nomic-embed-text / bge-m3 | Ollama local | — | ~0.3–1.2 GB | frozen embeddings |
| Fallback | DeepSeek-Flash | DeepInfra | — | cloud | cheap, fast |
- **VRAM: 24 GB. RAM: 32–64 GB.** Leave 20–40% VRAM headroom for context.
- **Expected performance:** ~20–60 tok/s local (fine for async); cloud for the hard ~10% of calls. **Cost: <$20/mo** (matches accepted budget tier).

### 8.C Serious founder stack (48–80 GB VRAM, or 128 GB unified; vLLM)
| Role | Model | Source | Quant | VRAM | Why |
|---|---|---|---|---|---|
| Reasoning | **GLM-air-class / Qwen3.5** | vLLM local | FP8 | ~40–48 GB | near-frontier reasoning, local, zero marginal cost |
| Coding | **Qwen3.5-Coder** | vLLM local | FP8 | ~48 GB | top open agentic coding, local |
| Research | Qwen long-context (1M) local **or** Gemini free | vLLM / cloud | FP8 | varies | privacy-sensitive long-context stays local |
| Retrieval | **Qwen3-Embedding** | Ollama local | Q4 | ~5 GB | max retrieval quality |
| Fallback | DeepSeek V4 | DeepInfra | — | cloud | break-glass frontier only |
- **VRAM: 48–80 GB (or 128 GB unified Mac/Strix-class). RAM: 64–128 GB.**
- **Expected performance:** near-everything local at high throughput via vLLM; cloud is rare break-glass. **Cost: ~electricity + occasional cloud.** This is the privacy-max / independence-max tier.

**Migration between stacks is config-only** (routes.yaml), per the accepted future-proofing design — except the embedding model, which is a deliberate re-index.

---

# PART 9 — Development Environment
### (`docs/63_DEV_ENVIRONMENT.md`)

Everything relocatable goes to `K:\Tools\`. Forced-`C:\` cases are justified. Disk estimates are approximate.

| Software | Why required | Mandatory? | Install path | Disk | C:\ justification |
|---|---|---|---|---|---|
| **Git + Git Bash** | version control; Bash shell for scripts/harness on Windows | **Yes** | `K:\Tools\Git` (installer allows custom dir) | ~0.4 GB | none — fully relocatable |
| **Python (3.12+)** | AI layer, embeddings, vector store, tooling | **Yes** | `K:\Tools\Python` (custom install dir) + `uv` for envs | ~0.4 GB + venvs on K: | none |
| **Node.js (LTS)** | OpenCode + JS tooling + saas-starter template | **Yes** | `K:\Tools\nodejs` (zip/custom) | ~0.2 GB | none |
| **OpenCode** | primary coding-agent harness (accepted) | **Yes** | `K:\Tools\opencode` (npm prefix on K:) | ~0.3 GB | none |
| **Ollama** | local model + embedding serving | **Yes** (all stacks need local embeddings) | program forced `C:\...\Programs\Ollama`; **models `K:\Models\ollama`** | program ~1 GB on C:; weights on K: | **C: forced:** installer hardcodes program dir to user AppData; only the small binary lives there, all weights relocate via `OLLAMA_MODELS` |
| **VS Code** | editor / manual oversight | Recommended | **Portable build → `K:\Tools\VSCode`** (preferred); else system installer on C: | ~0.4 GB | **C: only if** system installer chosen; portable build avoids C: entirely — use portable |
| **Docker Desktop** | run Qdrant / Open WebUI / sandboxed builds | Optional (B/C) | program forced `C:\Program Files\Docker`; **data-root + WSL distro → K:** | program ~1–2 GB on C:; data on K: | **C: forced:** Docker Desktop core + WSL2 integration must sit on the system drive; the GB-scale *data-root and images* are relocated to K: via WSL export/import or settings |
| **WSL2** | Linux backend for vLLM / Docker / Bash parity | Optional (B/C) | kernel forced C:; **distro storage → K:** via `wsl --export/--import` | kernel small on C:; distro on K: | **C: forced:** WSL2 kernel is a Windows system component; the distro filesystem (the big part) is moved to K: |
| **uv** (Python pkg mgr) | fast, reproducible Python envs on K: | Recommended | `K:\Tools\uv` | <0.1 GB | none |
| **LanceDB** (pip) | local vector store (embedded) | **Yes** | pip into K: venv; **data `K:\Data\charter_house\vectors`** | grows on K: | none |

**Summary of unavoidable C:\ residue:** only three small *program cores* — Ollama binary, Docker Desktop core, WSL2 kernel — and optionally a VS Code system install (avoidable via portable). **Every GB-scale asset (all model weights, vectors, caches, images, logs, datasets) is on `K:\`.** Total forced C: footprint ≈ 3–5 GB of program files; everything that grows is on K:.

---

# PART 10 — Installation & Setup Guide
### (`docs/64_INSTALLATION_GUIDE.md`)

From fresh Windows to operational Charter House. **Order matters** — it prevents duplicate downloads (e.g., setting `OLLAMA_MODELS` *before* pulling any model) and validates each layer before building on it.

### Stage 0 — Prepare K:\ (10 min)
1. Create the `K:\` skeleton: `K:\the_charter_house`, `K:\AI`, `K:\Models\{ollama,lmstudio,vllm}`, `K:\Tools`, `K:\Data\charter_house\{vectors,cache,backups}`, `K:\Logs`.
2. ✅ **Checkpoint:** all folders exist; `K:` has ≥200 GB free (Serious stack ≥400 GB).

### Stage 1 — Core dev tools (30 min)
3. Install **Git** → `K:\Tools\Git` (enable Git Bash). ✅ `git --version` in Git Bash.
4. Install **Python 3.12+** → `K:\Tools\Python`; add to PATH; install **uv**. ✅ `python --version`, `uv --version`.
5. Install **Node LTS** → `K:\Tools\nodejs`; set npm global prefix to `K:\Tools\npm-global`. ✅ `node -v`, `npm -v`.
6. Install **VS Code portable** → `K:\Tools\VSCode` (avoids C:). ✅ launches.

### Stage 2 — Local AI serving (20 min + downloads)
7. Install **Ollama**. **Before pulling anything**, set system env var `OLLAMA_MODELS=K:\Models\ollama` and restart the Ollama service. ✅ `ollama list` runs and points at K: (verify a test pull lands in `K:\Models\ollama`).
8. **Pull models in size order** (smallest first validates the pipeline, avoids wasted large downloads if something's wrong):
   a. **Embedding model first** (frozen): `nomic-embed-text`. ✅ embed a test string; vector returned.
   b. Then the stack's reasoning model (e.g., `qwen3-30b-a3b` on Stack B). ✅ a chat test responds.
   c. (Serious) set up **vLLM** in a WSL2 venv at `K:\AI\vllm`, weights to `K:\Models\vllm`.
9. (Optional) Install **LM Studio** (models dir → `K:\Models\lmstudio`) and/or **Open WebUI** (data → `K:\AI\openwebui`) for manual chat. ✅ open a chat.

### Stage 3 — Vector store + Python env (15 min)
10. Create a project venv with uv inside `K:\the_charter_house`; `pip install lancedb` (embedded). Point its data dir to `K:\Data\charter_house\vectors`. ✅ write + read a test vector locally.
11. (Scale option) If using Qdrant instead: install Docker Desktop (relocate data-root to K:), run Qdrant with a volume on `K:\Data\charter_house\vectors`. ✅ healthcheck.

### Stage 4 — Harness + cloud routing (20 min)
12. Install **OpenCode** (npm global on K:). ✅ `opencode` launches.
13. Create cloud accounts/keys as desired (OpenRouter, DeepInfra, Gemini free, Groq free). Store keys in **environment variables**, never in the repo. ✅ a one-shot router test hits a cloud model and a local model.

### Stage 5 — Repository + design docs (15 min)
14. `git init` in `K:\the_charter_house`; create the folder skeleton from Part 6.
15. Place all design docs (this package, split into `docs/`). ✅ `README.md` links resolve.
16. ✅ **Final checkpoint:** local embed works, local chat works, cloud route works, vector store read/writes, OpenCode runs, repo + docs in place. **Environment is operational; implementation (Part 11) can begin.**

**Mistake-prevention rules baked into the order:** set `OLLAMA_MODELS` before any pull (no re-downloads to C:); embeddings before LLMs (validate cheaply); freeze the embedding model before the first index; keys in env before any capability runs; never let a default installer silently choose C: for weights or data.

---

# PART 11 — Implementation Roadmap
### (`docs/70_IMPLEMENTATION_ROADMAP.md`)

The order Claude Code should build, designed to **minimize rework** by building the deterministic spine first and adding intelligence/scale last.

### Phase 1 — The Deterministic Spine (no LLM yet)
- **Goals:** prove the engine and the discipline without any model in the loop.
- **Outputs:** repo skeleton; **Conductor** core (state machine, WIP enforcement, registry); **Ledger** (append-only events) + projections (board/PIPELINE/METRICS); governance action-class table + RED-token mechanism (stubbed approvals). Doctrine/Glossary/Lifecycle/Workflow/Governance docs placed.
- **Validation:** push a fake venture through every legal transition by hand; confirm illegal transitions and WIP violations are blocked; confirm state is fully reconstructable by replaying the ledger.
- **Risks:** over-building memory/AI now (defer it); ledger schema churn (lock `31_LEDGER_SCHEMA.md` first).
- **Dependencies:** Package A Parts 1,3,5 + Package B Part 6.

### Phase 2 — The Substrate (AI layer, no business logic yet)
- **Goals:** model independence proven before any capability exists.
- **Outputs:** `ai/` router + adapters (OpenAI-compatible + Anthropic/Gemini/Grok shims); `config/` (providers/models/routes/profiles); OpenCode harness adapter + generator from neutral specs; **embeddings + LanceDB + retrieval** wired; golden-set harness.
- **Validation:** route the same prompt to a local and a cloud model; trigger a failover; embed + retrieve top-K from a seeded lesson set; run the golden set and record a baseline.
- **Risks:** embedding-model drift (it's frozen — enforce); provider key leakage (env-only check).
- **Dependencies:** Phase 1; accepted routing/abstraction docs.

### Phase 3 — Capabilities + Workflows (intelligence in the loop)
- **Goals:** one full venture loop runs end-to-end on a dummy idea, with **no real spend/send/deploy**.
- **Outputs:** neutral specs for Scout/Analyst/Builder/Growth/Librarian + **Critic cross-model** wiring; the 5-beat workflow per state; governance enforcement live (RED actions require founder tokens; outbox holds outreach); landing + saas-starter templates.
- **Validation:** dry-run a venture CAPTURED→…→LAUNCHED against a sandbox; confirm every RED action halts for a token; confirm a model failure at PRODUCE/CRITIQUE causes retry, not state corruption; confirm critique attaches before every gate.
- **Risks:** capability scope creep (contracts in Package A Part 4 are the boundary); prompts under-specified (derive strictly from contracts).
- **Dependencies:** Phases 1–2.

### Phase 4 — Memory Compounding + Scale
- **Goals:** the machine improves with age and stays manageable at portfolio scale.
- **Outputs:** **Librarian** consolidation/promotion + retirement; calibration report; portfolio registry-as-view + backlog hygiene + alumni track; dashboards/projections; progressive-disclosure switches that turn on full memory machinery as volume grows.
- **Validation:** simulate 50 ventures (mostly archived); confirm active WIP and founder load stay flat (O(active)); confirm consolidation is reversible (ledger intact); confirm contradicted lessons retire and recurring ones promote.
- **Risks:** premature complexity (gate features behind portfolio-size thresholds); over-pruning (consolidation is a view, never a ledger edit).
- **Dependencies:** Phases 1–3; Package A Part 5, Package B Parts 7–8.

> **Sequencing logic:** deterministic spine → substrate → intelligence → compounding. Each phase is independently validatable and the discipline (gates, WIP, governance) exists from Phase 1 — so the system is *safe before it is smart*.

---

# FINAL SUMMARY (the five required lists)

### 1. Complete list of Markdown documents Claude Code will need
**Design specs (authored in this freeze — 26):**
`docs/00_DOCTRINE.md` · `01_OPERATING_MODEL.md` · `02_GLOSSARY.md` · `README.md` · `10_VENTURE_LIFECYCLE.md` · `11_WORKFLOWS.md` · `12_GOVERNANCE.md` · `20_CONDUCTOR_SPEC.md` · `capabilities/SCOUT.md` · `ANALYST.md` · `BUILDER.md` · `GROWTH.md` · `LIBRARIAN.md` · `CRITIC.md` · `30_MEMORY_ARCHITECTURE.md` · `31_LEDGER_SCHEMA.md` · `32_RETRIEVAL_SPEC.md` · `40_PORTFOLIO.md` · `50_FOUNDER_MANUAL.md` · `60_REPOSITORY_STRUCTURE.md` · `61_LOCAL_AI_STACK.md` · `62_MODEL_STRATEGY.md` · `63_DEV_ENVIRONMENT.md` · `64_INSTALLATION_GUIDE.md` · `70_IMPLEMENTATION_ROADMAP.md` · (+ `AGENTS.md` generated).
**Operational docs (generated during build):** `vault/PIPELINE.md`, `vault/memory/lessons/LESSONS_INDEX.md`, `data/metrics/METRICS.md`, `templates/*`.

### 2. Order the documents should be created
1. `00_DOCTRINE` → `02_GLOSSARY` → `01_OPERATING_MODEL` (vocabulary + supreme law first).
2. `10_VENTURE_LIFECYCLE` → `11_WORKFLOWS` → `12_GOVERNANCE` (the rules).
3. `31_LEDGER_SCHEMA` → `20_CONDUCTOR_SPEC` (lock the event shape before the engine).
4. `30_MEMORY_ARCHITECTURE` → `32_RETRIEVAL_SPEC` → `capabilities/*` (memory before the agents that use it).
5. `40_PORTFOLIO` → `50_FOUNDER_MANUAL` (human-facing).
6. `60_REPOSITORY_STRUCTURE` → `61_LOCAL_AI_STACK` → `62_MODEL_STRATEGY` → `63_DEV_ENVIRONMENT` → `64_INSTALLATION_GUIDE` (environment).
7. `70_IMPLEMENTATION_ROADMAP` last (it references everything).

### 3. Exact software stack
**Mandatory:** Git (+Git Bash), Python 3.12+ (+uv), Node LTS, OpenCode, Ollama (+ frozen embedding model `nomic-embed-text`), LanceDB.
**Recommended:** VS Code (portable).
**Optional (Consumer/Serious):** Docker Desktop, WSL2, vLLM, LM Studio, Open WebUI, Qdrant.
**Cloud (config, behind router):** OpenRouter (control plane), DeepInfra (cheap direct), Gemini free + Groq free (zero-cost/speed).

### 4. Exact installation sequence
`K:\ skeleton` → Git → Python+uv → Node → VS Code (portable) → **set `OLLAMA_MODELS=K:\Models\ollama`** → Ollama → pull **embedding model first**, then reasoning model → (Serious: WSL2 + vLLM) → Python venv + LanceDB → (scale: Docker + Qdrant) → OpenCode → cloud keys in env → `git init` repo + place design docs → final validation checkpoint. **Then begin Phase 1.**

### 5. Recommended K:\ directory structure
```
K:\the_charter_house\   (repo: docs, ai, config, conductor, agents, vault, data\ledger, templates)
K:\AI\                  (ollama config, openwebui data, vllm)
K:\Models\              (ollama, lmstudio, vllm  ← all weights)
K:\Tools\               (Git, Python, nodejs, VSCode, opencode, uv)
K:\Data\charter_house\  (vectors, cache, backups)
K:\Logs\
```
Forced-C: residue (small program cores only, justified in Part 9): Ollama binary, Docker Desktop core, WSL2 kernel, optional VS Code system install. All GB-scale assets are on `K:\`.

---

### Sources (infrastructure currency, June 2026)
- [Best Embedding Models for Local RAG 2026 — PromptQuorum](https://www.promptquorum.com/power-local-llm/best-embedding-models-local-rag-2026) · [Choose an Embedding Model for RAG 2026 — Milvus](https://milvus.io/blog/choose-embedding-model-rag-2026.md) · [Best Embedding Models 2026 — Mixpeek](https://mixpeek.com/curated-lists/best-embedding-models)
- [GPU Requirements Cheat Sheet 2026 — Spheron](https://www.spheron.network/blog/gpu-requirements-cheat-sheet-2026/) · [Run Qwen3-Coder & DeepSeek Locally — TheAITechPulse](https://www.theaitechpulse.com/running-qwen3-coder-deepseek-locally-vram-guide) · [Local LLMs by VRAM Tier — PromptQuorum](https://www.promptquorum.com/local-llms)
- [Inference API Providers Compared 2026 — Infrabase](https://infrabase.ai/blog/ai-inference-api-providers-compared) · [Free LLM API Tiers 2026 — WeTheFlywheel](https://wetheflywheel.com/en/ai-model-access/free-llm-api-tiers-2026/) · [Best Open Source CLI Coding Agents 2026 — Pinggy](https://pinggy.io/blog/best_open_source_cli_coding_agents/)
