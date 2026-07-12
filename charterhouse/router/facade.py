"""``Router``/``LLMClient`` — the S8 seam (docs/40 §5 frozen surface; router/API.md).

Resolve role → chain (Config only) → try candidates in order via the provider's adapter →
normalize → telemetry. Emits ``pii_block`` when a PII tag excluded cloud candidates and
``error`` on exhaustion. Owns no durable state; spend is a ledger fold.

Determinism boundary: routing decision deterministic; the adapter call is the LLM path.
No environment read (docs/20) — the real transport's ``key_lookup`` is injected at wiring
time, outside this subsystem.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from charterhouse.config import Config
from charterhouse.contracts.events import Event, EventType
from charterhouse.ledger import Ledger
from charterhouse.logging import Telemetry
from charterhouse.security.types import Context, PIIRouteBlocked

from charterhouse.router.adapters.anthropic import AnthropicAdapter
from charterhouse.router.adapters.gemini import GeminiAdapter
from charterhouse.router.adapters.openai_compat import GrokAdapter, OpenAICompatibleAdapter
from charterhouse.router.budget import month_spend, tier_ceiling
from charterhouse.router.chain import build_chain
from charterhouse.router.types import LLMResponse, ProvidersExhausted, Require

_ACTOR = "router"

# provider id → adapter class; anything unlisted is OpenAI-compatible (IMPLEMENTATION §3).
_SHIMS = {"anthropic": AnthropicAdapter, "gemini": GeminiAdapter,
          "grok": GrokAdapter, "xai": GrokAdapter}


def _default_adapter_factory(provider_id: str, provider, transport):
    return _SHIMS.get(provider_id, OpenAICompatibleAdapter)(provider, transport)


class Router:
    """S8 Router. See router/API.md for the full per-function contract."""

    def __init__(
        self,
        config: Config,
        ledger: Ledger,
        *,
        transports: Mapping[str, object] | None = None,
        adapter_factory: Callable | None = None,
        spent_usd: Callable[[], float] | None = None,
    ) -> None:
        self._config = config
        self._ledger = ledger
        self._telemetry = Telemetry(ledger, actor=_ACTOR)
        self._transports = dict(transports or {})
        self._adapter_factory = (adapter_factory if adapter_factory is not None
                                 else _default_adapter_factory)
        self._spent_usd = (spent_usd if spent_usd is not None
                           else lambda: month_spend(ledger))

    # --- internals --------------------------------------------------------------------

    def _adapter(self, provider_id: str):
        provider = self._config.get_provider(provider_id)
        transport = self._transports.get(provider_id)
        if transport is None:
            raise ProvidersExhausted(
                f"no transport wired for provider {provider_id!r} — the real HTTP "
                "transport (with its key_lookup seam) is composed at wiring time, "
                "never built inside S8 (router/IMPLEMENTATION §6.1)")
        return self._adapter_factory(provider_id, provider, transport)

    def _cost_usd(self, model_id: str, tokens: Mapping) -> float:
        model = self._config.get_model(model_id)
        return ((tokens.get("in", 0) / 1e6) * model.price_in
                + (tokens.get("out", 0) / 1e6) * model.price_out)

    def _audit_pii_block(self, role: str, excluded: tuple[str, ...]) -> None:
        self._ledger.append(Event(
            type=EventType.PII_BLOCK, actor=_ACTOR,
            payload={"context_ref": "require.contains_pii",
                     "attempted_route": f"{role}: " + ", ".join(excluded)}))

    def _audit_exhausted(self, role: str, tried: list[str], last_error: str) -> None:
        self._ledger.append(Event(
            type=EventType.ERROR, actor=_ACTOR,
            payload={"where": "router", "kind": "providers_exhausted",
                     "detail": f"role {role}: tried {', '.join(tried)}; last: {last_error}",
                     "fail_closed": True}))

    # --- the frozen IF-2 seam (docs/40 §5) ----------------------------------------------

    def call(
        self,
        role: str,
        messages: list,
        tools: list | None = None,
        require: Require | None = None,
        *,
        critic_tier: int | None = None,
    ) -> LLMResponse:
        """The frozen IF-2 LLMClient seam (docs/40 §5): resolve from Config only
        (INV-ROUTE-1), deterministic failover → degrade → pause (INV-ROUTE-2), PII ⇒
        local only (INV-ROUTE-3), one ``llm_call`` telemetry event per success
        (INV-ROUTE-4)."""
        require = require if require is not None else Require()
        ceiling = tier_ceiling(self._spent_usd(), self._config.budgets)
        try:
            plan = build_chain(self._config, role, require, ceiling)
        except PIIRouteBlocked:
            # Nothing may be sent; the refusal itself is audited (docs/41 pii_block).
            self._audit_pii_block(role, ("<no local candidate>",))
            raise
        if plan.pii_excluded:
            self._audit_pii_block(role, plan.pii_excluded)

        # The S7 Context the cloud adapters' hard guard consults (defense in depth).
        context = Context(text="", contains_pii=require.contains_pii)

        tried: list[str] = []
        last_error = "no candidate attempted"
        for model_id in plan.candidates:
            model = self._config.get_model(model_id)
            tried.append(model_id)
            try:
                adapter = self._adapter(model.provider)
                raw = adapter.complete(model_id, messages, tools, None, context=context)
            except PIIRouteBlocked:
                raise  # the guard is a hard stop, never a failover hop (safety > uptime)
            except Exception as exc:  # any provider fault advances the chain (INV-ROUTE-2)
                last_error = f"{model_id}: {type(exc).__name__}"
                continue
            cost = self._cost_usd(model_id, raw["tokens"])
            response = LLMResponse(
                text=raw["text"], model=model_id, usage=dict(raw["tokens"]),
                cost_usd=cost, latency_ms=raw["latency_ms"],
                tool_calls=tuple(raw["tool_calls"]), critic_tier=critic_tier)
            # INV-ROUTE-4: a call without its audit event does not "succeed".
            self._telemetry.record({
                "role": role, "model": model_id, "provider": model.provider,
                "tokens": dict(raw["tokens"]), "cost_usd": cost,
                "latency_ms": raw["latency_ms"],
                **({"critic_tier": critic_tier} if critic_tier is not None else {})})
            return response

        self._audit_exhausted(role, tried, last_error)
        raise ProvidersExhausted(
            f"role {role!r}: every candidate failed ({', '.join(tried)}) — the Conductor "
            "should declare a factory pause (docs/11, INV-ROUTE-2)")


# The docs/40 §5 name for the seam consumers import.
LLMClient = Router
