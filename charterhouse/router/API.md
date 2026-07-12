# Router (S8) — API
Owner: A6 Router Agent   ·   Matches docs/40 §5 exactly (frozen seam)   ·   This doc completes **interface-freeze IF-2** (the `LLMClient` half; the Config half froze 2026-07-04) — frozen so S9 Memory and S10 Capability Framework can build against it

## Exposed surface

### `LLMClient.call(role: str, messages: list[Msg], tools: list[Tool] | None = None, require: Require | None = None) -> LLMResponse`
- **Preconditions:** `role` is a routing role (NEVER a model id — docs/40 §5); `messages`
  are OpenAI-shaped `{role, content}` mappings; `require` carries the call's constraints
  `{min_ctx, needs_tools, needs_web, contains_pii}`.
- **Postconditions:** resolves `role → Route` via `Config.get_route` **only** (INV-ROUTE-1
  — no role-assignment logic here; an unknown role surfaces Config's typed error
  unchanged), builds the deterministic candidate chain `[primary, *fallback]`, filters it
  by the merged constraints (route ∪ require; require wins), by **PII locality**
  (`contains_pii` ⇒ only `Provider.kind == "local"` models remain — INV-ROUTE-3/INV-PII-3),
  and by the **budget tier guard** (≥80% of `Config.budgets.monthly_usd` spent ⇒ paid-tier
  models dropped, docs/14 auto-degrade), then tries candidates **in order**, failing over
  on any adapter error (INV-ROUTE-2). On success returns the normalized
  `LLMResponse{text, tool_calls[], model, usage, cost_usd, latency_ms, critic_tier?}`
  (provider differences never leak) and appends exactly one `llm_call` telemetry event via
  S14 `Telemetry` (INV-ROUTE-4; `cost_usd` computed from the `Model` catalog prices).
- **Errors (fail closed):** unknown role → Config's `UnknownRole` (propagated);
  `contains_pii` with no local model available → `PIIRouteBlocked` (**nothing sent
  anywhere**, `pii_block` event appended); configured chain + the free/local degrade
  extension all failing → `ProvidersExhausted` (the docs/11 **`pause` signal** — the
  Conductor declares a factory pause; `error` event appended). No partial response is
  ever returned.
- **Side effects:** one `llm_call` append on success; one `pii_block` append when a PII
  tag excluded cloud candidates; one `error` append on exhaustion. **Determinism:** the
  *routing decision* is deterministic (config + ledger-derived spend + injected seams);
  the model call itself is the system's one LLM path. **Auth class:** GREEN (capped
  inference; spend accounted via telemetry).
- **Additive kwarg note (docs/43 §7):** `critic_tier: int | None = None` — stamped into
  the response + telemetry when the caller (S10 critic beat) supplies it.

### `Adapter.complete(model: str, messages: list, tools: list | None = None, max_tokens: int | None = None) -> RawResult`
- One adapter per provider *shape* (docs/40 §5). `RawResult = {text, tool_calls?,
  tokens{in,out}, latency_ms}`. Adapters normalize; they never decide routing.
- **`OpenAICompatibleAdapter(provider, transport)`** covers OpenRouter/DeepInfra/Groq/
  Together/Fireworks/vLLM/Ollama/LM Studio (base_url+key_env from Config's `Provider`).
- **`GrokAdapter`** = a named `OpenAICompatibleAdapter` subclass (xAI is OpenAI-shaped).
- **`AnthropicAdapter` / `GeminiAdapter`** = thin shims: pure translation functions
  `to_provider_request(...)` / `from_provider_response(...)` around the transport.
- **INV-PII-3 hard guard (the A5 seam, made real here):** every **cloud** adapter calls
  the merged `security.tag.require_cloud_allowed(context)` before ANY send; a
  `contains_pii` context raises `PIIRouteBlocked` **inside the adapter** even if a buggy
  chain let it through (defense in depth: chain filter upstream, adapter guard at the
  boundary). Local adapters carry no guard (local execution is the PII-legal path).
- **Additive kwarg (docs/43 §7):** `context: Context | None = None` — the S7 `Context`
  the guard consults; `LLMClient` always supplies it.
- **Errors:** transport/provider failures raise (feeding failover); cloud+PII raises
  `PIIRouteBlocked`. **Side effects:** the provider call via the injected transport only.

### `Router(config: Config, ledger: Ledger, *, adapter_factory=None, transports=None, spent_usd=None) -> LLMClient`
- The wiring constructor (internal, free to change): builds adapters per provider via an
  injectable factory/transport map (tests inject A11's `FakeProvider` as the transport;
  no real network exists in this subsystem — see §Consumed/secrets note), a `Telemetry`
  over the ledger, and the budget spend fold.

## Public value types
`Require{min_ctx?, needs_tools?, needs_web?, contains_pii}` ·
`LLMResponse{text, tool_calls: tuple, model, usage: {in, out}, cost_usd, latency_ms,
critic_tier?}` · `RawResult` (adapter-internal dict shape above) · errors `RouterError` /
`NoEligibleModel` / `ProvidersExhausted` (the pause signal); `PIIRouteBlocked` is
**reused from S7** (`charterhouse.security.types`) — one PII refusal type across the seam.

## Consumed surface
- **Config (S3, IF-2 Config half, real):** `get_route(role)` / `get_model(id)` /
  `get_provider(id)` / `budgets` — routing data only; located/typed errors propagate.
- **Security (S7, IF-3, real):** `tag.require_cloud_allowed(Context)` — the one frozen
  PII guard (S8 re-implements NO S7 rule; it enforces at the boundary). `Context` shape.
- **Ledger (S4, IF-1, real) via S14 `Telemetry.record`** — `llm_call` events
  (INV-ROUTE-4); `pii_block`/`error` events appended directly (docs/41 §2).
- **Secrets (docs/24 vs docs/20 env-boundary):** `Provider.key_env` names the variable;
  the **real** HTTP transport receives an injected `key_lookup: Callable[[str], str|None]`
  at wiring time (supplied by the Conductor from A1's env seam) — S8 itself never reads
  `os.environ` (the A1 static boundary test stays green). No real transport ships in A6;
  live smoke is optional and non-gating (docs/11 DoD).

## Interface stability
- **Frozen (IF-2 LLMClient half, this doc):** `LLMClient.call` + `Require`/`LLMResponse`
  shapes + `Adapter.complete` positional signature + the INV-ROUTE-1..4 semantics.
  Breaking change = ICR (docs/43 §4).
- **Additive v1 notes (docs/43 §7):** `critic_tier` kwarg; adapter `context` kwarg;
  `Router` wiring seams (`adapter_factory`/`transports`/`spent_usd`).
- **Internal/free to change:** adapter registry heuristics, budget fold implementation,
  degrade-extension ordering, module layout, transport construction.
