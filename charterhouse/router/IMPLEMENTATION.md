# Router (S8) — IMPLEMENTATION
Owner: A6 Router Agent   Subsystem: S8   Source of truth: docs/11_router.md, docs/22_models.md + docs/40 §5, docs/24 (PII), docs/54 §S8

## 1. Responsibility (one paragraph)
S8 makes every model/provider swappable via config: it resolves `role → model` from S3
Config data, calls the right adapter, normalizes the response, fails over deterministically,
degrades tier on budget, and **never routes PII-tagged context to a cloud adapter** — the
enforcement half of INV-PII-3 that S7 defined (the guard) and S8 makes real (the boundary).
It **MUST NOT**: hold any role-assignment logic (roles arrive from S10/S12; INV-ROUTE-1),
read environment variables (docs/20 — secrets reach the real transport via an injected
`key_lookup` at wiring time), leak provider differences to callers, re-implement any S7
rule (it *calls* the frozen `require_cloud_allowed` guard), perform real network I/O in
tests (INV-TEST-SAFE — A11's `FakeProvider` is the transport), or swallow a failure into a
partial/guessed response (fail closed).

## 2. Invariants enforced (docs/11 MUST, verbatim; docs/54 §S8)
- **INV-ROUTE-1** — "role→model resolved from Config only; no role-assignment logic in the
  router." *Guaranteed by:* the only role lookup is `Config.get_route(role)`; an unknown
  role propagates Config's `UnknownRole` untouched; profile switch reroutes with zero S8
  code change (asserted with two profiles over the same call).
- **INV-ROUTE-2** — "primary failure → deterministic failover chain; exhaustion → degrade
  to free/local → else signal `pause`." *Guaranteed by:* the candidate list is
  `[primary, *fallback]` in config order (never reordered); on adapter error the next
  candidate is tried; after the configured chain, a deterministic **degrade extension**
  (catalog models with `tier == "free"` and a local provider, sorted by id, minus already
  tried) is tried; if that too is empty/fails → `ProvidersExhausted` (the pause signal) +
  an `error` event. Seeded failure-mask tests assert chosen == first healthy candidate.
- **INV-ROUTE-3** — "`require.contains_pii` ⇒ cloud adapters excluded from the chain
  (local only)." *Guaranteed by* **two independent layers**: (1) the chain filter drops
  every model whose `Provider.kind != "local"` and appends a `pii_block` event naming the
  excluded route; (2) every cloud adapter calls the **merged S7 guard**
  (`require_cloud_allowed`) before any send and raises `PIIRouteBlocked` — so a chain-
  filter bug still cannot leak (defense in depth, docs/24). No local candidate anywhere →
  `PIIRouteBlocked`, nothing sent.
- **INV-ROUTE-4** — "every call emits an `llm_call` telemetry event (tokens/$/latency;
  critic_tier if applicable)." *Guaranteed by:* the success path returns only after
  `Telemetry.record` (S14) appends the event; `cost_usd` is computed from the catalog
  `Model.price_in/price_out` (USD per million tokens, docs/22).
- **Budget guard (docs/14 auto-degrade, docs/40 §5 "degrade on budget"):** month-to-date
  spend ≥ 80% of `budgets.monthly_usd` ⇒ paid-tier models are dropped from every chain
  (free/local only; `on_exceeded: degrade`). Spend is a ledger fold over `llm_call`
  events (injectable `spent_usd` seam for tests).
- **`INV-DET` boundary:** the routing *decision* is deterministic; the adapter call is the
  system's one LLM path. `router/` imports none of `memory`/`capabilities`/`conductor`.

## 3. Internal design
- `types.py` — `Require`, `LLMResponse`, `RawResult` conventions, error taxonomy
  (`RouterError`/`NoEligibleModel`/`ProvidersExhausted`); `PIIRouteBlocked` imported from
  S7 (one refusal type across the seam).
- `chain.py` — pure candidate builder: `[primary, *fallback]` → merge route ∪ require
  constraints (`min_ctx` vs `Model.ctx`; `needs_tools`/`needs_web` vs `Model.good_at`) →
  PII locality filter → budget tier filter → degrade extension. Returns the ordered
  eligible list + the list of PII-excluded cloud candidates (for the `pii_block` event).
- `budget.py` — the spend fold: Σ `payload.cost_usd` over `llm_call` events for the
  current month (events without a `timestamp` count — conservative/fail-closed; see §6)
  vs `budgets.monthly_usd`; returns the tier ceiling ("paid" allowed / "free" only).
- `facade.py` — `Router`/`LLMClient`: resolve → chain → try-in-order (each attempt via
  the provider's adapter; any exception advances the chain) → normalize → telemetry.
  Emits `pii_block` (when clouds were excluded) and `error` (on exhaustion) directly.
- `adapters/base.py` — the `Adapter` contract + `CloudGuardMixin` (the INV-PII-3 hard
  guard around `require_cloud_allowed`); `adapters/openai_compat.py` (+ `GrokAdapter`);
  `adapters/anthropic.py`, `adapters/gemini.py` — **pure translation functions**
  (`to_provider_request`/`from_provider_response`) around the injected transport, unit-
  tested without any network. Adapter choice per provider: registry keyed on provider id
  ("anthropic"→shim, "gemini"→shim, "grok"/"xai"→Grok, else OpenAI-compatible), override
  via `adapter_factory`.
- **State ownership: none.** Spend is a ledger fold; routing tables live in Config; no
  cache survives a call (recomputed per call).

## 4. Dependencies (docs/43)
- **IF-2 Config half (frozen, real):** `get_route/get_model/get_provider/budgets`.
- **IF-3 (frozen, real):** `security.tag.require_cloud_allowed` + `security.types.Context`
  / `PIIRouteBlocked`.
- **IF-1 via S14 (real):** `Telemetry.record` (llm_call), direct `Ledger.append` for
  `pii_block`/`error` (docs/41 §2 vocabulary).
- **A11 harness:** `FakeProvider` as the injected transport in every test (docs/55 §2).

## 5. Failure behavior (fail closed; no guess/continue)
| Failure mode | Response |
|---|---|
| Unknown role | Config's `UnknownRole` propagates (no default route, ever) |
| Constraint filter empties the chain (ctx/tools/web) | `NoEligibleModel` naming the constraint |
| PII tag with no local candidate | `PIIRouteBlocked`; nothing sent; `pii_block` appended |
| PII context reaches a cloud adapter (chain bug) | adapter guard raises `PIIRouteBlocked` before send |
| Adapter/provider error mid-chain | advance to next candidate (deterministic order) |
| Configured chain + degrade extension exhausted | `ProvidersExhausted` (pause signal) + `error` event |
| Budget ≥80% | paid tier dropped; free/local only (degrade, never silent overspend) |
| Telemetry append fails | error propagates (a call without its audit event does not "succeed") |

## 6. Open questions → RESOLVED
1. *docs/24 says the Router reads secrets from env at call time, but the A1 env-boundary
   test forbids `os.environ` outside `charterhouse/env/`.* → **RESOLVED:** the *real*
   transport takes an injected `key_lookup(name)` callable, wired by the Conductor from
   A1's env seam at composition time. S8 never touches env; `Provider.key_env` stays a
   name. No real transport ships in A6 (live smoke is optional/non-gating, docs/11 DoD).
   → **REALIZED (feat/ops-transport, 2026-07-29):** the real HTTP transports live at the
   wiring layer in `charterhouse/conductor/transport.py` (`HttpOpenAITransport` for Groq/
   OpenRouter/local Ollama, `HttpGeminiTransport` for the Gemini shim), composed by
   `build_transports(config, key_lookup)`; `key_lookup` is A1's `env.env_key_lookup`.
   `router/` is unchanged — the adapters wrap the injected transport exactly as designed;
   the cloud `_guard` still hard-stops PII before any transport send (proven CI-safe with a
   fake sender; a `scripts/smoke_transport.py` runner does the non-gating live check).
2. *Where do embeddings live (docs/11 "may be served here")?* → **RESOLVED — deferred to
   A7 Memory** as a thin local-only Ollama client (`Embeddings.embed`, docs/40 §6); S8
   ships chat-completion routing only. Embeddings MUST remain local (INV-MEM-4) — noted
   for A7.
3. *Month scoping for the budget fold when `llm_call` events carry no `timestamp`
   (A11's `Telemetry` doesn't stamp one).* → **RESOLVED — conservative:** un-timestamped
   events count toward the current month (degrade earlier, never overspend). Cross-
   subsystem note for A11: stamp `timestamp` in `Telemetry.record` (additive) so the fold
   tightens; recorded in RISKS.
4. *Grok: docs/11 lists it under OpenAI-compatible, the build order asks for a shim.* →
   **RESOLVED:** `GrokAdapter` is a named subclass of `OpenAICompatibleAdapter` (xAI's API
   is OpenAI-shaped) — the named adapter exists, no fake translation layer is invented.
5. *`critic_tier` (docs/40 §5 response field) — who supplies it?* → **RESOLVED:** the
   caller (S10 critic beat) via an additive kwarg; S8 stamps it through to the response
   and telemetry. S8 does not compute critic tiers (INV-WF-2 is S10's).
6. *A PII tag + a route-level `min_ctx` can exclude every local model (the committed
   `reasoning` route wants ≥32k ctx; the local model has 8k).* → **RESOLVED — security
   outranks a route quality preference:** under `contains_pii`, the ROUTE-level `min_ctx`
   is relaxed so the work runs on a smaller local model (docs/24 R-REDACT: PII work "may
   only run on local models" — the intent is it *runs*, degraded, not that it fails and
   pressures the operator to untag). An EXPLICIT `require.min_ctx` from the caller is
   still enforced; a genuine conflict with PII locality then fails closed
   (`PIIRouteBlocked`). Capability requirements (`needs_tools`/`needs_web`) are
   functional, not quality, and stay enforced under PII.
7. *The degrade extension needs the catalog's model ids, but Config's frozen surface has
   no listing method.* → **RESOLVED (final, 2026-07-19):** A2's additive
   `Config.models() -> tuple[str, ...]` seam landed (feat/a2-accessors); the interim
   `chain._catalog_ids` internal-table read is deleted and a static test keeps
   `router/` free of private Config reach. RISKS R9 retired.
