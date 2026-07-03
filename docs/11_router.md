# 11 — MODEL ROUTER (build contract)
**Owner:** Router Agent (A6) · **Subsystem:** S8 · **Source of truth:** Environment Spec (routing), Operating Model (model-provider seam) · **Consumes:** Config (S3), Security tag (S7), Ledger telemetry (S4)

## Charter
Make every model/provider swappable via config. Resolve `role → model` from Config, call the right adapter, normalize the response, fail over on error, degrade tier on budget, and NEVER route PII-tagged context to a cloud adapter.

## MUST
- `INV-ROUTE-1` role→model resolved from Config only; **no role-assignment logic in the router** (roles come from S10/S12).
- `INV-ROUTE-2` primary failure → deterministic failover chain; exhaustion → degrade to free/local → else signal `pause`.
- `INV-ROUTE-3` `require.contains_pii` ⇒ cloud adapters excluded from the chain (local only).
- `INV-ROUTE-4` every call emits an `llm_call` telemetry event (tokens/$/latency; critic_tier if applicable).

## Adapters
- One `OpenAICompatibleAdapter` covers ~all providers (base_url+key from Config): OpenRouter, DeepInfra, Groq, Together, Fireworks, vLLM, Ollama, LM Studio, Grok.
- Thin shims: `AnthropicAdapter`, `GeminiAdapter` (translate to/from the OpenAI-shaped request/response). Never leak provider differences to the caller.

## Interfaces
- Exposes: `LLMClient.call(role, messages, tools?, require?) -> LLMResponse` (`40` §5).
- Consumes: `Config.get_route/get_model/get_provider`, `Sec.tag`/`require.contains_pii`, `Ledger.append(llm_call)`.

## Deliverables
`router/` + `router/adapters/*`. Embeddings may be served here or via a thin local-only embedding client (Ollama) — but embeddings MUST be local (`INV-PII`, `INV-MEM-4`).

## Acceptance / DoD
`54` S8: profile switch reroutes with no code change; failover order asserted with FakeProvider; PII→local enforced; budget breach degrades tier. Live smoke optional, non-gating.

## Build order
Wave 2 (Phase 3). Interface (`LLMClient.call`) frozen at IF-2 so Memory (S9) and Framework (S10) can stub against it.
