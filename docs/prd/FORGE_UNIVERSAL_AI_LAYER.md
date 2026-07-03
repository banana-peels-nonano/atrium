# THE FORGE — Universal AI Layer
### A principal-architect design review and redesign

> Mandate: make Anthropic optional, the system model-agnostic, and the architecture survivable for years. Audited as if before a $10M investment. Opinionated by request — where the current design is wrong, I say so and replace it.

> Landscape grounding: facts on models, providers, and tooling reflect the June 2026 market. The whole point of this redesign is that those facts are *configuration*, not architecture — they will be stale in 90 days and the design must not care. Sources at the end.

---

## 0. The one-sentence verdict

**THE FORGE is an excellent *operating doctrine* welded onto a *fragile substrate*.** The factory laws, WIP limits, kill-day discipline, and "every dead idea leaves an asset" are genuinely good and should not change. But the spec hard-wires the *substrate* — Claude Code as the runtime, Anthropic as the brain, `.claude/` as the contract — into the doctrine. That coupling is invisible today because it all happens to be one vendor's stack. It becomes a single point of failure the day pricing, terms, or availability move. The fix is not to swap Anthropic for someone else. The fix is to **insert two seams** — an *agent-runtime seam* and a *model-provider seam* — so that the doctrine rides on top of interchangeable parts.

---

# 1. Current Architecture Analysis (the brutal audit)

I'll separate what's *good and load-bearing* from what's *coupled and dangerous*, because a careless rewrite would throw away the best parts.

### 1.1 What is genuinely good (keep, do not touch)
- **The factory doctrine is the moat, not the tooling.** Three laws, WIP limits (3 validating / 1 building), Friday kill-day, binary verdicts, append-only `LESSONS.md`, "signal is the bottleneck." None of this depends on which LLM runs it. This is the actual product. Protect it.
- **Vault-as-repo, frontmatter-as-database.** Markdown + YAML + git is the single best decision in the spec. It is model-agnostic, tool-agnostic, and human-readable by accident. It will outlive every model named in this document.
- **Five agents, not fifteen.** Correct instinct. Resisting agent sprawl is rare and right.
- **Merchant-of-record checkout, template-first building, costly-action validation.** All sound and orthogonal to the AI layer.

### 1.2 Tight coupling to Claude Code (the runtime trap)
This is the deeper of the two lock-ins, and the spec doesn't even notice it.

- **`.claude/agents/*.md` and `.claude/commands/*` are a proprietary contract.** The frontmatter schema (`name`, `description`, `tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch`) is Claude Code's format. Those tool names are Claude Code's tool names. Move to any other harness and every agent file must be rewritten.
- **The "operating system" in §5 is literally Claude Code.** Branching, task workflow, deploy, prompt management are all described *as Claude Code behaviors*. The spec conflates "the agent runtime" with "the methodology." They must be divorced.
- **Slash commands (`/intake`, `/kill-day`, `/pipeline`) are harness-specific.** They have no existence outside Claude Code. If the harness dies, the muscle-memory interface dies with it.
- **Real-world proof this matters:** in 2026 OpenCode dropped Claude Pro/Max login after a dispute with Anthropic, and Google retired the Gemini CLI on June 18, 2026 in favor of a closed successor. Harnesses are *not* stable substrate. Betting the factory on one harness's continued goodwill is the same mistake as betting on one model.

**Verdict:** Claude Code is doing two jobs — (a) a good agent runtime, (b) the *definition* of the factory. Job (b) must be extracted into vendor-neutral files. (See §7.)

### 1.3 Tight coupling to Anthropic (the model trap)
- **No provider indirection anywhere.** Every agent implicitly calls "the model the harness is configured with," which is an Anthropic model. There is no place in the architecture where you could say "use DeepSeek for this."
- **Cost model assumes frontier-Anthropic economics.** Running scout at "10+ briefs/week" with heavy `WebFetch`, plus analyst's "20+ primary quotes," plus builder on full MVPs, is *thousands* of large-context calls per month. On premium Anthropic pricing that is a real monthly bill for a "near-zero budget solo founder in India." The spec's own success metric ("verdicts on ≥4 ideas at <$200 each") is *inference-cost-blind* — the $200 is ad-spend, not tokens. Token cost is unaccounted for and will dominate at volume.
- **WebSearch/WebFetch are harness-provided.** They're listed as agent tools but they're Anthropic/Claude-Code capabilities. On a local Ollama setup they don't exist. The agents assume a capability that isn't portable.

### 1.4 Hidden assumptions (the ones that bite later)
1. **"The model is always strong enough."** Every agent prompt assumes frontier reasoning and long, reliable instruction-following. Point a 8B local model at the analyst prompt and it will hallucinate the "20 primary quotes" rather than report that it couldn't find them — which *inverts* the whole validation philosophy. **Agent prompts must be written to a capability floor, and routing must guarantee that floor.**
2. **"One model does everything."** Scout (cheap volume), analyst (reasoning), builder (coding), growth (creative), ops (mechanical parsing) have wildly different cost/quality needs. Paying frontier prices for ops's "regenerate PIPELINE.md from frontmatter" is pure waste — that's a 4B model job, or arguably not an LLM job at all.
3. **"Context is free and infinite."** `LESSONS.md` is append-only and "read by every agent at session start." Fine at week 1. At month 12 it's a giant file silently eating context budget and money on every single call, on every model, forever. No summarization, no retrieval, no rotation. This is a slow leak that gets worse precisely as the factory succeeds.
4. **"Tools mean the same thing everywhere."** `Bash` in Claude Code ≠ shell access in Aider ≠ a tool-call in a raw Ollama loop. The capability surface is assumed uniform; it isn't.
5. **"WebSearch exists."** Assumed; not true for local/offline or many open models.

### 1.5 Lock-in, cost, scalability, context, agent-design risks (scored)

| Risk | Severity | Why |
|---|---|---|
| **Model lock-in (Anthropic)** | High | No abstraction seam; pricing/terms/availability are existential single points of failure. |
| **Runtime lock-in (Claude Code)** | High | Factory *definition* lives in proprietary files; harness instability is already real in 2026. |
| **Cost blindness** | High | No token accounting; one-model-for-all; append-only context that grows unbounded. |
| **Context-window bloat** | Medium-High | `LESSONS.md`-on-every-call has no retrieval/rotation; degrades quality and cost over time. |
| **Capability-floor fragility** | Medium-High | Prompts assume frontier behavior; degrade silently on weaker models, corrupting verdicts. |
| **Scalability of human gate** | Medium | The *founder* is the bottleneck by design (good), but nothing protects the founder from agent volume scaling faster than they can review. Needs explicit human-gate budgeting. |
| **No failover** | Medium | Single provider = if it's down or rate-limited, the factory stops. No fallback chain. |
| **Tooling assumptions** | Medium | WebSearch/WebFetch/Bash assumed portable; they aren't. |

**Bottom line for the $10M investor:** the *business logic* is fundable. The *technical substrate* is a prototype that will not survive its first vendor shock. Fund it only with the two seams below as a condition.

---

# 2. Model-Agnostic AI Layer

The core idea: **agents never name a model. They name a *role*. A router maps role → provider/model at call time, from config.** One file changes when the world changes; zero agent files change.

### 2.1 The two seams

```
┌─────────────────────────────────────────────────────────────┐
│  DOCTRINE (never changes): laws, WIP, gates, scoring, kill   │
│  Lives in: CLAUDE.md → renamed AGENTS.md + vault/            │
└───────────────┬─────────────────────────────────────────────┘
                │  Seam 1: AGENT-RUNTIME seam (harness-neutral agent specs)
┌───────────────▼─────────────────────────────────────────────┐
│  AGENT SPECS (portable): role, system prompt, tool needs,    │
│  capability floor, output contract — in neutral YAML/MD      │
└───────────────┬─────────────────────────────────────────────┘
                │  Seam 2: MODEL-PROVIDER seam (the universal AI layer)
┌───────────────▼─────────────────────────────────────────────┐
│  ROUTER → ADAPTERS → PROVIDERS                                │
│  Anthropic · OpenAI · Gemini · Grok · OpenRouter · HF ·      │
│  Ollama · LM Studio · vLLM · any OpenAI-compatible endpoint  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 The cheat code: standardize on the OpenAI Chat Completions schema
Do **not** hand-write a bespoke adapter per provider. In 2026 the `/v1/chat/completions` (and increasingly `/v1/responses`) schema is the lingua franca: OpenAI, Together, Fireworks, DeepInfra, Groq, OpenRouter, vLLM, Ollama (`/v1`), and LM Studio all speak it. Gemini, Anthropic, and Grok need thin translation shims; everything else is one base URL + key.

This collapses "support 12 providers" into "support 1 protocol + 3 shims." That is the difference between a maintainable layer and a museum of adapters.

### 2.3 Folder structure

```
factory/
├── AGENTS.md                       # vendor-neutral constitution (was CLAUDE.md)
├── ai/                             # ← THE UNIVERSAL AI LAYER (new)
│   ├── router.py                   # role → model resolution, failover, budget guard
│   ├── client.py                   # one call(): messages, tools → normalized response
│   ├── adapters/
│   │   ├── openai_compatible.py    # covers ~80% of providers (base_url + key)
│   │   ├── anthropic.py            # shim: messages API ↔ openai schema
│   │   ├── gemini.py               # shim: generateContent ↔ openai schema
│   │   └── grok.py                 # xAI is openai-compatible; thin wrapper
│   ├── capabilities.py             # tool/websearch availability per provider
│   └── telemetry.py                # token + $ accounting per call/agent/idea
├── config/
│   ├── providers.yaml              # endpoints, keys (env refs), limits, prices
│   ├── models.yaml                 # model catalog: id, ctx, $/Mtok, tier, strengths
│   ├── routes.yaml                 # role → model + fallback chain  ← edit this monthly
│   └── profiles/                   # named stacks the founder switches between
│       ├── free.yaml
│       ├── cheap-cloud.yaml
│       ├── local-first.yaml
│       └── max-quality.yaml
├── agents/                         # ← neutral specs (moved out of .claude/)
│   ├── scout.agent.md
│   ├── analyst.agent.md
│   ├── builder.agent.md
│   ├── growth.agent.md
│   └── ops.agent.md
├── adapters/harness/               # map neutral specs → whatever harness runs them
│   ├── claude-code/                # generates .claude/agents/* from agents/*
│   ├── opencode/                   # generates opencode config from agents/*
│   └── aider/                      # generates .aider.conf + conventions
└── vault/ ...                      # unchanged
```

The key move: `.claude/` becomes a **build artifact**, generated from `agents/*.agent.md`. You author once in neutral form; a tiny generator emits harness-specific files. Switching harness = re-run the generator, not rewrite five agents.

### 2.4 The interface (this is the whole contract)

```python
# ai/client.py — the only thing agents/harness code is allowed to call
from dataclasses import dataclass

@dataclass
class LLMResponse:
    text: str
    tool_calls: list          # normalized [{name, args}]
    model: str                # what actually answered (post-failover)
    usage: dict               # {input, output, cached} tokens
    cost_usd: float
    latency_ms: int

class LLMClient:
    def call(
        self,
        role: str,                 # "scout" | "analyst" | ... NEVER a model id
        messages: list[dict],      # openai schema
        tools: list[dict] | None = None,
        *,
        max_tokens: int = 4096,
        require: dict | None = None # {min_ctx, needs_tools, needs_web, json}
    ) -> LLMResponse:
        ...
```

Every adapter implements one method:

```python
# ai/adapters/openai_compatible.py
class OpenAICompatibleAdapter:
    def __init__(self, base_url, api_key_env, default_model):
        self.base_url = base_url
        self.key = os.environ[api_key_env]
        self.default_model = default_model

    def complete(self, model, messages, tools, max_tokens) -> RawResult:
        # one POST to {base_url}/chat/completions. Works for OpenRouter,
        # DeepInfra, Together, Fireworks, Groq, vLLM, Ollama, LM Studio, Grok.
        ...
```

Anthropic/Gemini get a `complete()` that internally translates request+response to/from this shape. **No caller ever sees the difference.**

### 2.5 Configuration structure

```yaml
# config/models.yaml  — the catalog (facts that go stale; that's fine, it's data)
deepseek-v4:        { provider: deepinfra,  ctx: 164000, in: 1.30, out: 2.60, tier: strong,   good_at: [reason, code] }
deepseek-v4-flash:  { provider: deepinfra,  ctx: 164000, in: 0.10, out: 0.20, tier: cheap,    good_at: [bulk, scan] }
glm-5.1:            { provider: deepinfra,  ctx: 200000, in: 1.05, out: 3.50, tier: strong,   good_at: [code, agentic] }
kimi-k2.6:          { provider: deepinfra,  ctx: 256000, in: 0.75, out: 3.50, tier: strong,   good_at: [code, reason] }
qwen3.5-coder:      { provider: openrouter, ctx: 262000, in: 0.30, out: 1.20, tier: strong,   good_at: [code, agentic] }
qwen3-235b:         { provider: deepinfra,  ctx: 131000, in: 0.09, out: 0.10, tier: cheap,    good_at: [bulk, reason] }
gemini-2.5-flash:   { provider: gemini,     ctx: 1000000,in: 0.00, out: 0.00, tier: free,     good_at: [bulk, web, long] }  # free tier
claude-sonnet:      { provider: anthropic,  ctx: 200000, in: 3.00, out: 15.0, tier: frontier, good_at: [code, reason, agentic] }
local-qwen3-30b:    { provider: ollama,     ctx: 64000,  in: 0.00, out: 0.00, tier: local,    good_at: [code, bulk] }
```

```yaml
# config/routes.yaml — THE FILE YOU EDIT WHEN THE WORLD CHANGES
defaults:
  budget_usd_month: 20
  on_budget_exceeded: degrade   # degrade | block | warn

roles:
  scout:    { primary: gemini-2.5-flash, fallback: [qwen3-235b, deepseek-v4-flash] }
  analyst:  { primary: deepseek-v4,      fallback: [glm-5.1, claude-sonnet], min_ctx: 128000 }
  builder:  { primary: glm-5.1,          fallback: [qwen3.5-coder, claude-sonnet], needs_tools: true }
  growth:   { primary: deepseek-v4-flash,fallback: [gemini-2.5-flash] }
  ops:      { primary: qwen3-235b,       fallback: [local-qwen3-30b, deepseek-v4-flash] }
```

### 2.6 Routing logic + failover (the actual algorithm)

```
call(role, messages, require):
  route = routes.yaml[role]
  chain = [route.primary] + route.fallback
  apply require{min_ctx, needs_tools, needs_web}: drop models in chain that can't satisfy
  if budget_guard.month_spend > budget and on_exceeded == degrade:
        chain = chain filtered to tier in {cheap, free, local}   # graceful degradation
  for model in chain:
      if rate_limiter.blocked(model.provider):   continue
      try:
          r = adapters[model.provider].complete(model, messages, tools, max_tokens)
          telemetry.record(role, model, r.usage, r.cost)
          return normalize(r)
      except (RateLimit, ServerError, Timeout):   mark provider cooling; continue
  raise NoHealthyProvider(role)   # last resort: queue for human or retry later
```

Failover is **automatic and silent** for transient errors, **budget-aware** (degrades tier instead of failing), and **observable** (telemetry says which model actually answered). Anthropic disappearing tomorrow = one line in `routes.yaml`, or nothing at all if it was a fallback.

### 2.7 Why this is maintainable for years
- New provider = add a row to `providers.yaml` (if OpenAI-compatible) or one ~40-line shim.
- New model = one row in `models.yaml`.
- New strategy = edit `routes.yaml` or switch profile.
- **Agent prompts, vault, doctrine: never touched.** The blast radius of any model-world change is one or two YAML files.

---

# 3. Local-First Strategy

**Can THE FORGE run entirely local? Mostly yes — with one honest exception.** Scout, ops, growth, and most of analyst run fine on local models in 2026. The one place local struggles is *frontier-grade agentic building of real MVPs* and *deep multi-step reasoning with large context* — and even there, MoE models on unified-memory machines have closed most of the gap.

### 3.1 Model evaluation (June 2026, open weights)

| Model | Params (active) | Reasoning | Coding | Agent fit | Context | Realistic HW (quantized) | Practical limitation |
|---|---|---|---|---|---|---|---|
| **Qwen3.5 / Qwen3-Coder-Next** | 80B MoE (~3B act) | High | **Top open** | **Excellent** | up to 1M | ~46GB unified/VRAM | Tooling lag (GGUF/vision quirks); best needs 48GB+ |
| **GLM-5 / 5.1** | ~358B MoE | **Top open** | **Top open** (77.8% SWE-bench Verified) | **Excellent** | 200K | server-class (multi-GPU) or hosted | Too big for consumer; shines hosted |
| **DeepSeek V4 / Flash** | 671B MoE (~37B act) | **Top open** | High | Strong | 164K | not consumer-local (~700GB FP8) | Local only on serious servers; use hosted |
| **Kimi K2.6 Thinking** | large MoE | High | High | Strong | 256K | server-class or hosted | Hosted-only in practice |
| **Mistral (latest)** | ~24–123B dense/MoE | Good | Good | Good | 128K+ | 24–80GB | Solid generalist, no longer top of any category |
| **Gemma (latest)** | 27B-class dense | Good | Moderate | Moderate | 128K | 24GB | Great cheap generalist; weaker at agentic coding |
| **Llama (3.3/4 latest)** | 70B / MoE | Good | Moderate | Moderate | 128K | 48GB+ | Fell behind Chinese labs on code; fine as utility |
| **gpt-oss-120B** | 120B MoE | Good | Good | Good | 128K | ~60–80GB | Honest open option; mid-pack vs GLM/Qwen |

**Headline:** the open frontier for *agentic coding* in 2026 is **GLM-5.x and Qwen3.5-Coder**, with **DeepSeek V4** the best capability-per-dollar when hosted. For *local consumer hardware*, **Qwen3 30B-A3B (MoE)** and **Qwen3-Coder-Next 80B MoE** are the sweet spot because MoE keeps active params (and thus speed) low while fitting in unified memory.

### 3.2 Recommended local stacks

| Tier | Hardware | Serving | Models | What runs locally | What still goes cloud |
|---|---|---|---|---|---|
| **A. Consumer laptop** | 16–32GB RAM, no/iGPU or M-series 16–24GB | **LM Studio** or Ollama | Qwen3 8B / 14B Q4, Gemma 27B Q4 (Mac) | scout, ops, growth drafts | analyst depth, builder MVPs |
| **B. High-end desktop** | RTX 4090 24GB (or 5090) | **Ollama** + llama.cpp | Qwen3 30B-A3B Q4, Qwen3-14B Q6 | scout, ops, growth, light analyst, landing-page builder | hard reasoning, full MVP build |
| **C. Small home server** | 64–128GB unified (Mac Studio / Strix Halo) | **Ollama / llama.cpp** | Qwen3-Coder-Next 80B MoE, GLM-air-class | + most analyst, most builder | only the hardest agentic build steps |
| **D. Serious founder** | 1× workstation GPU 48–80GB (or 2×24GB) | **vLLM** | GLM-air / Qwen3.5-Coder FP8, DeepSeek-Flash | nearly everything incl. real MVP coding | rare frontier "make-or-break" calls |
| **E. Max performance** | 4–8× H200 / rented cluster | **vLLM** | DeepSeek V4, GLM-5.1, Kimi K2.6 full | everything, frontier-grade | nothing (you *are* the frontier-open) |

**Serving-tool guidance:**
- **Ollama** — default for A/B/C. One-command pulls, auto CUDA/ROCm, OpenAI-compatible `/v1`. Best ergonomics.
- **LM Studio** — best for non-technical/laptop users; GUI, model browser, also serves `/v1`.
- **vLLM** — for D/E. Far higher throughput, batching, FP8; the right choice once you're serving real load or want production latency.

**Honest local limitation:** even C/D can run the *MVP builder* role, but expect more ret/review loops than a hosted GLM-5.1. The factory's human-gate absorbs this — the founder reviews builder output anyway. Local is *good enough* for the factory's actual cadence; it is not magically equal to the hosted frontier on the hardest tasks. That's exactly what the hybrid layer (§6) is for.

---

# 4. Cloud Inference Strategy (assuming no Anthropic spend)

You can run the entire factory on open models via aggregators and serverless inference — cheaper, and with no single-vendor dependency. Ranked recommendation:

| Rank | Provider | Cost | Reliability | Speed | Rate limits | Context | OSS catalog | Verdict |
|---|---|---|---|---|---|---|---|---|
| **1** | **OpenRouter** | Pass-through + 5.5% credit fee | High (multi-backend failover built in) | Varies by route | Generous; 28+ free models | Up to provider max | **Widest** | **Default control plane.** One key, one bill, automatic provider failover, BYOK. The abstraction you want even if you go direct later. |
| **2** | **DeepInfra** | **Cheapest** (DeepSeek V4 $1.30/$2.60; Flash $0.10/$0.20; Qwen3-235B $0.09/$0.10) | High | Good | High | 164K+ | Widest direct | **Cost floor.** Route price-sensitive bulk here directly to skip the 5.5%. |
| **3** | **Groq** | Low-mid | High | **Fastest** (300+ tok/s; LPU) | Free tier cut to ~1k rpd in 2026; paid generous | Model-limited | Curated (Llama, etc.) | **Latency role.** Ops/scout where speed matters; great free tier to start. |
| **4** | **Together AI** | Mid | High | Good | High | Large | Wide + **fine-tuning** | If you ever fine-tune a factory-specific model, do it here or Fireworks. |
| **5** | **Fireworks** | Mid (50% cached discount) | High | Good (fast serving) | High | Large | Wide + fine-tuning | Strong serving + caching; good for repeat-context agents. |
| **6** | **Cerebras** | Low | Med | **Extreme** (~2000 tok/s) | Free 1M tok/day but catalog shrank in 2026 | Model-limited | Narrow (shrinking) | Use for speed bursts; don't depend on its free catalog. |
| **7** | **HF Inference / Nebius / Hyperbolic** | Varies | Med | Varies | Varies | Varies | Broad (HF) / OSS-focused | Useful breadth and occasional unique models; keep as fallbacks, not primaries. |
| **8** | **Gemini API (free tier)** | **Free** (1,500 req/day, 1M ctx) | High | Fast | 1,500 rpd free | **1M** | n/a (closed) | Not open, but the free 1M-context workhorse is too good to ignore for scout/bulk. |

**Recommended cloud posture:** **OpenRouter as the control plane** (unified billing + failover + breadth), **DeepInfra as the direct cost route** for high-volume cheap roles, **Groq/Gemini-free** for latency and zero-cost bulk. This trio gives you frontier-open quality, the cheapest per-token in the market, and a free tier — with no Anthropic and no single point of failure.

---

# 5. Intelligent Model Routing

Different agents have different jobs; pay accordingly. The routing below is the *default* in `routes.yaml`; the founder overrides per profile.

| Agent | Job character | Recommended model (cloud) | Why | Quality tradeoff |
|---|---|---|---|---|
| **scout** | High-volume, shallow, web-heavy, "many briefs cheaply" | **Gemini 2.5 Flash (free)** → Qwen3-235B → DeepSeek-Flash | Volume role; free 1M context eats web pages; honesty enforced by prompt + cite-or-delete rule | Slightly more shallow synthesis; acceptable — analyst re-scores anyway |
| **analyst** | Deep reasoning, evidence weighing, kill design | **DeepSeek V4** → GLM-5.1 → (Claude Sonnet only as last resort) | This is where reasoning quality protects you from false positives; spend here | Minimal; this is the role worth its tokens |
| **builder** | Agentic coding, tool use, multi-file | **GLM-5.1** → Qwen3.5-Coder → Claude Sonnet | Top open coding + agentic scores; tool-calling reliable | Some extra review loops vs frontier-closed; human gate covers it |
| **growth** | Creative copy, outreach, persuasive | **DeepSeek-Flash** → Gemini Flash | Cheap + creative-sufficient; voice quality is "good enough," founder edits anyway | Marginal; copy is A/B tested in market, not in the model |
| **ops** | Mechanical: parse frontmatter, regen PIPELINE.md | **Qwen3-235B (cheap)** → local 30B; *or no LLM at all* | Most of ops is deterministic text munging — script it; LLM only for lesson-extraction prose | None — much of this shouldn't be an LLM call |

**Expected cost impact vs "frontier-Anthropic-for-everything":** routing scout/growth/ops to cheap/free tiers and reserving strong models for analyst/builder cuts blended token cost by roughly **85–95%** at the same factory throughput, because the high-volume roles (scout's 10+ briefs/week, ops daily) are exactly the ones that don't need frontier models. The expensive roles are also the *low-volume* ones (1 build at a time, ≤3 analyses), so the budget concentrates where quality matters.

**Dynamic routing rules (beyond static role mapping):**
1. **Escalation on uncertainty.** If analyst/builder self-reports low confidence or fails a self-check, auto-retry one tier up the fallback chain (cheap→strong→frontier) — capped at one escalation to bound cost.
2. **Context-size routing.** If a request's `min_ctx` exceeds the primary's window, skip to a long-context model (Gemini 1M, Qwen 1M, Kimi 256K) automatically.
3. **Budget-aware degradation.** Past 80% of monthly budget, drop primaries to cheap/local tier for everything except builder's make-or-break and analyst's kill decisions (the two roles where a wrong answer costs more than tokens).
4. **Free-tier-first.** For idempotent/retryable calls (scout sweeps, ops regen), try free tiers first; fall to paid only on rate-limit.

---

# 6. Hybrid Architecture

The production-grade target: **local does routine + private work; cloud does hard work; the founder gates anything expensive or irreversible.**

```
            ┌──────────────── ROUTINE (local first) ────────────────┐
 inbox ──►  scout (local Qwen3-30B)  ──►  ops (local/script)         │
            growth drafts (local)         pipeline regen (script)    │
            └───────────────────────────────────┬───────────────────┘
                       escalate when hard / low-confidence
            ┌──────────────────────────────────▼────────────────────┐
 HARD ───►  analyst (cloud DeepSeek V4)  ──►  builder (cloud GLM-5.1) │
            long-context research            real MVP coding         │
            └───────────────────────────────────┬───────────────────┘
                       gate before money / irreversible
            ┌──────────────────────────────────▼────────────────────┐
 GATE ───►  FOUNDER approves: spend >$X, deploy, send outreach,      │
            graduate venture, any payment-path code merge            │
            └────────────────────────────────────────────────────────┘
```

**Routine→local, hard→cloud decision rule (in router):** route to local if `tier==local satisfies require AND role in {scout, ops, growth-draft, light-analyst}`; else cloud. Privacy flag forces local regardless (founder's raw inbox/customer quotes never leave the machine unless flagged shareable).

**Cost estimates (illustrative, monthly, steady-state factory at spec throughput):**

| Posture | Local share | Cloud spend/mo | Notes |
|---|---|---|---|
| All-local (Tier C/D HW) | ~100% | **~$0** | electricity only; slower builder loops |
| Hybrid (laptop + cloud) | ~60% | **~$8–25** | cheap cloud for analyst/builder only |
| Hybrid (free-tier-max) | ~50% | **~$0–5** | Gemini/Groq/OpenRouter free + occasional paid |
| Cloud-only open | 0% | **~$15–60** | DeepInfra/OpenRouter, no Anthropic |
| Frontier-closed everything | 0% | **$300–1500+** | the spec's implicit default — rejected |

**Latency estimates:** local 30B on a 4090 ≈ 20–60 tok/s (fine for async factory work, not chat); Groq/Cerebras cloud ≈ 300–2000 tok/s; DeepInfra/OpenRouter ≈ 30–120 tok/s. The factory is *batch/async by nature* (sweeps, research packs, builds), so throughput matters more than first-token latency — local is perfectly acceptable.

**Failure modes + fallback chains:**
- *Local GPU OOM / model unloaded* → fall to cheap cloud automatically (router catches it).
- *Cloud provider down / rate-limited* → next in fallback chain; if all paid exhausted, drop to free tier; if those exhausted, queue and notify founder.
- *Budget exhausted* → degrade to local/free; builder + analyst kill-decisions protected.
- *Local quality too low (self-check fails)* → single escalation to cloud strong tier.
- *Total outage of all providers* → factory keeps running on local; if no local, vault is still fully usable by the human (the doctrine never required AI to function — that's the point).

---

# 7. Claude Code Replacement Analysis

**Is Claude Code *required*? No.** It's a good harness, but the spec wrongly made it the operating system. The OS should be the **neutral agent specs + the AI layer**; the harness is a swappable executor. That said, you still want *a* harness, and you should pick a **model-agnostic, open, actively-maintained** one as primary.

| Tool | License/Open | Model-agnostic | Maintenance (2026) | Strength | FORGE fit |
|---|---|---|---|---|---|
| **OpenCode** | Open | **Yes** (75+ providers, local via Ollama/LM Studio) | **Very active** | Provider-agnostic by design, LSP, privacy-first, parallel agents | **Primary.** Lowest-risk default; embodies the no-lock-in goal |
| **OpenHands** | MIT (68k★) | Yes | Active | Sandboxed, unattended, CI-friendly autonomous runs | **Optional/CI.** Use for hands-off builder runs in a sandbox |
| **Aider** | Apache (41k★) | Yes | Active | Disciplined git-native edits, surgical diffs | **Optional.** Best for tight builder commits; pairs with OpenCode |
| **Goose** | Apache (32k★, Linux Foundation) | Yes | Active (neutral governance) | General agent beyond code; foundation-backed longevity | **Optional.** Good for non-code ops automation |
| **Continue** | Apache (31k★) | Yes | Active | IDE-embedded autocomplete/chat | **Optional.** If founder lives in an IDE |
| **Cline** | Apache (58k★) | Yes | Active | Popular VS Code agent | Optional; overlaps OpenCode |
| **Cursor** | Closed | Partial | Active | Polished IDE | **Remove.** Closed + subscription = the lock-in you're fleeing |
| **Roo Code** | Apache (was 22–24k★) | Yes | **Archived May 2026** | — | **Remove.** Don't adopt stalled tools |
| **Gemini CLI** | Was open | Google-only | **Retired Jun 18 2026 → closed successor** | — | **Remove.** Textbook harness-lock-in casualty |
| **Claude Code** | Closed | Anthropic-first | Active | Excellent ergonomics, skills, MCP | **Demote to optional.** Keep as *one* executor via the harness adapter; never the definition |

**Ranking (primary → remove):**
1. **OpenCode** — primary OS of THE FORGE.
2. **OpenHands** — sandboxed/autonomous builder + CI.
3. **Aider** — surgical git-native coding.
4. **Goose / Continue** — optional, role-dependent.
5. **Claude Code / Cline** — optional executors via adapter (keep if the founder likes them, never depend).
6. **Remove:** Cursor (closed), Roo Code (archived), Gemini CLI (retired/closed).

**The crucial reframing:** because agents are authored in neutral `agents/*.agent.md` and a generator emits harness configs, *the harness choice becomes reversible*. You can run OpenCode today, test Claude Code tomorrow, and CI on OpenHands — all from the same source of truth. Claude Code goes from "the OS" to "one of several interchangeable hands."

---

# 8. Future-Proof Architecture

Design assumption: **a new frontier model every ~90 days; today's best is obsolete within a year.** The system must absorb this by editing *config*, never *logic*.

### 8.1 Dependency boundaries (what's allowed to change, and what isn't)

```
NEVER changes:  doctrine (AGENTS.md, laws, gates, scoring), vault format, agent ROLES
RARELY changes: agent system prompts (only on capability-floor shifts), AI-layer interface
OFTEN changes:  config/models.yaml, config/routes.yaml, config/profiles/*  ← the churn lives here
ISOLATED:       adapters/* (one file per provider protocol; new providers added, old untouched)
```

The architectural law: **model knowledge flows in one direction — into config files only.** No model name, price, or provider string may appear in any agent prompt, vault note, or business-logic file. A grep for `claude`/`gpt`/`deepseek` outside `config/` and `ai/adapters/` should return nothing. Enforce it with a CI check.

### 8.2 Configuration design (already shown in §2.5) — the upgrade unit is a YAML row.

### 8.3 Upgrade workflow (new model drops Friday)

```
1. Add row to config/models.yaml (id, ctx, price, tier, good_at).
2. Bench it: scripts/eval-model.sh <id> runs the factory's golden set
   (5 saved scout briefs, 2 analyst packs, 1 builder task) and prints
   quality + cost vs current primary.
3. If better $/quality for a role → change that role's primary in routes.yaml.
   Keep the old model as fallback for one cycle.
4. Commit "config: route builder → glm-5.2". Done. Zero agent edits.
```

### 8.4 Migration process (provider dies / gets expensive)
- **Provider deprecation:** remove its rows from `models.yaml`; router's failover already routes around it. No outage because every role has a fallback chain on a *different* provider.
- **Protocol change:** isolated to one adapter file. Since 80% of providers share the OpenAI-compatible adapter, a schema shift touches one file, not twelve.
- **Harness death (the OpenCode/Gemini-CLI scenario):** swap the harness adapter; re-generate configs from `agents/*.agent.md`. Doctrine and prompts untouched.
- **Golden-set regression guard:** the eval set (§8.3) is the safety net — any model/route change is validated against saved real factory tasks before it ships, so "newer" never silently means "worse for our workload."

**Net:** the only thing that should ever change in response to the AI world is files under `config/`. That is the definition of future-proof here.

---

# 9. Final Recommendation

For each budget, the *doctrine and vault are identical* — only the AI layer config differs. That's the payoff of the design.

### 9.1 Solo founder, near-zero budget ($0)
- **Harness:** OpenCode.
- **Models:** Gemini 2.5 Flash (free, 1,500 rpd, 1M ctx) for scout/growth/bulk; OpenRouter free models (DeepSeek/Qwen/Llama) for analyst/builder; Groq free for latency.
- **Profile:** `free.yaml`. Failover across free tiers when rate-limited; queue-and-wait when all exhausted.
- **Why:** zero dollars, no Anthropic, real frontier-open quality. Rate limits are the cost, and the factory's async cadence tolerates them. **This is viable from day one.**

### 9.2 Under $20/month
- **Harness:** OpenCode.
- **Models:** free tiers for scout/ops/growth; **DeepInfra DeepSeek V4 ($1.30/$2.60) for analyst**, **GLM-5.1 ($1.05/$3.50) for builder**, billed direct.
- **Profile:** `cheap-cloud.yaml`, budget guard at $20 with degrade-to-free past 80%.
- **Why:** spends real money only on the two roles where reasoning/coding quality protects you from false-positive ventures. Comfortably under $20 at spec throughput. **Best value tier — recommended starting point for most founders.**

### 9.3 Under $100/month
- **Harness:** OpenCode primary + OpenHands for sandboxed autonomous builds.
- **Models:** add **Kimi K2.6 / Qwen3.5-Coder** as builder primaries via DeepInfra/OpenRouter; analyst on DeepSeek V4 with **GLM-5.1 escalation**; keep Claude Sonnet as a *break-glass* fallback for the single hardest call per venture.
- **Profile:** `hybrid-100.yaml`; escalation-on-uncertainty enabled; OpenRouter as control plane for unified billing + failover.
- **Why:** near-frontier quality on every role, automatic escalation when needed, still multi-vendor. $100 buys generous headroom at this throughput.

### 9.4 Unlimited budget
- **Harness:** OpenCode + OpenHands + Aider, all from neutral specs.
- **Models:** best-in-class per role regardless of price — GLM-5.1/Kimi K2.6/DeepSeek V4 full for open frontier, **plus Claude Sonnet and the strongest closed frontier as routed escalation** for builder/analyst make-or-break. Self-hosted vLLM cluster (Tier E) for privacy-sensitive + zero-marginal-cost bulk.
- **Profile:** `max-quality.yaml`; aggressive escalation; redundant providers.
- **Why:** here Anthropic is *welcome again — as one option among many, never a dependency.* That's the whole philosophy: not "no Anthropic," but "Anthropic optional."

### 9.5 My overall recommendation

**Build the two seams, ship the `<$20/month` hybrid as the default, and treat Anthropic as a break-glass escalation rather than the engine.**

Concretely:
1. **Extract the doctrine from Claude Code.** Rename `CLAUDE.md`→`AGENTS.md`, move agents to neutral `agents/*.agent.md`, make `.claude/` a generated artifact. This single move kills the runtime lock-in.
2. **Insert the AI layer** (`ai/` + `config/`). Standardize on the OpenAI-compatible protocol + 3 shims. Every agent calls `LLMClient.call(role=...)`, never a model.
3. **Adopt OpenCode as primary harness**, keep Claude Code/OpenHands/Aider as interchangeable executors via adapters.
4. **Default routing:** free/cheap models for scout/ops/growth, DeepSeek V4 + GLM-5.1 for analyst/builder, frontier-closed only as escalation. ~85–95% cheaper than the spec's implicit Anthropic-for-everything, with strictly *more* resto vendor shocks.
5. **Fix the three latent bugs** the original spec hides: (a) token-cost accounting via `ai/telemetry.py` and a budget guard; (b) `LESSONS.md` bloat — add retrieval/summarization so it doesn't tax every call forever; (c) capability-floor — write prompts to a defined floor and let routing guarantee it, so weak models can't silently corrupt verdicts.

**Why this and not "just switch to OpenRouter":** swapping one vendor for another aggregator solves today's bill and none of tomorrow's structural risk. The seams solve the *category* of problem — any model, any provider, any harness, for years — by ensuring the only thing that ever changes when the AI world moves is a YAML file. The factory's real asset was never the model. It was the doctrine and the vault. This design finally makes that literally true in the architecture.

---

### What I deliberately deleted or replaced
- **Deleted:** Claude Code as "the operating system" (§5) → replaced with neutral specs + swappable harness.
- **Deleted:** `.claude/` as source of truth → demoted to generated artifact.
- **Replaced:** one-model-for-everything → role-based routing with failover and budget guard.
- **Replaced:** Anthropic-as-engine → Anthropic-as-optional-escalation.
- **Flagged for fix (not in original):** token accounting, `LESSONS.md` context bloat, capability-floor enforcement.
- **Kept untouched (correctly):** three laws, WIP limits, kill-day, vault-as-repo, frontmatter-as-DB, five-agent roster, MoR checkout, template-first building.

---

### Sources
- [Best Open-Source LLMs 2026 — BuildFastWithAI](https://www.buildfastwithai.com/blogs/collection/open-source-llms) · [Best Open Source LLM 2026 — BenchLM](https://benchlm.ai/blog/posts/best-open-source-llm) · [Open Source LLM Comparison — ComputingForGeeks](https://computingforgeeks.com/open-source-llm-comparison/) · [Agentic Coding Models — MindStudio](https://www.mindstudio.ai/blog/best-open-source-llms-agentic-coding-2026)
- [AI Inference API Providers Compared — Infrabase](https://infrabase.ai/blog/ai-inference-api-providers-compared) · [OpenRouter Alternatives 2026 — Morph](https://www.morphllm.com/openrouter-alternative) · [DeepInfra vs OpenRouter — PricePerToken](https://pricepertoken.com/endpoints/compare/deepinfra-vs-openrouter) · [OpenRouter Free Tier 2026 — Klymentiev](https://klymentiev.com/blog/openrouter-free-tier)
- [Best Open Source CLI Coding Agents 2026 — Pinggy](https://pinggy.io/blog/best_open_source_cli_coding_agents/) · [Open-Source AI Coding Tools 2026 — Frontman](https://frontman.sh/blog/best-open-source-ai-coding-tools-2026/) · [awesome-cli-coding-agents — GitHub](https://github.com/bradAGI/awesome-cli-coding-agents) · [Coding Agents — Artificial Analysis](https://artificialanalysis.ai/agents/coding)
- [GPU Requirements Cheat Sheet 2026 — Spheron](https://www.spheron.network/blog/gpu-requirements-cheat-sheet-2026/) · [Run Qwen3-Coder & DeepSeek Locally — TheAITechPulse](https://www.theaitechpulse.com/running-qwen3-coder-deepseek-locally-vram-guide) · [Local LLMs by VRAM Tier — PromptQuorum](https://www.promptquorum.com/local-llms) · [Qwen3.5 Run Locally — Unsloth](https://unsloth.ai/docs/models/qwen3.5)
- [Free LLM API Tiers 2026 — WeTheFlywheel](https://wetheflywheel.com/en/ai-model-access/free-llm-api-tiers-2026/) · [Free LLM APIs Compared — OpenRouter](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/) · [Free LLM API 2026 — Klymentiev](https://klymentiev.com/blog/free-llm-api)
