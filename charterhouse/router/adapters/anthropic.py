"""``AnthropicAdapter`` — thin shim translating OpenAI-shaped requests to/from the
Anthropic Messages shape (docs/11: "never leak provider differences to the caller").

The translation functions are pure and unit-tested without any transport:
- ``to_provider_request``: system messages lift to the top-level ``system`` string;
  user/assistant messages map through.
- ``from_provider_response``: an Anthropic-shaped response (``content`` blocks +
  ``usage.input_tokens/output_tokens``) normalizes to the RawResult dict; an
  already-normalized result passes through (the transport may be a fake).
"""

from __future__ import annotations

from charterhouse.router.adapters.base import BaseAdapter


def to_provider_request(messages: list, tools: list | None = None) -> dict:
    """OpenAI-shaped messages → ``{"system": str | None, "messages": [...]}``. Pure."""
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    turns = [{"role": m["role"], "content": m["content"]}
             for m in messages if m.get("role") in ("user", "assistant")]
    return {"system": "\n".join(system_parts) if system_parts else None,
            "messages": turns}


def from_provider_response(raw: dict) -> dict:
    """Anthropic-shaped (or already-normalized) response → RawResult. Pure."""
    if "content" in raw:  # Anthropic Messages shape
        text = "".join(block.get("text", "") for block in raw["content"]
                       if block.get("type") == "text")
        usage = raw.get("usage", {})
        return {"text": text,
                "tokens": {"in": int(usage.get("input_tokens", 0)),
                           "out": int(usage.get("output_tokens", 0))},
                "latency_ms": int(raw.get("latency_ms", 0)),
                "tool_calls": tuple(raw.get("tool_calls", ()))}
    return {"text": raw.get("text", ""),
            "tokens": dict(raw.get("tokens", {"in": 0, "out": 0})),
            "latency_ms": int(raw.get("latency_ms", 0)),
            "tool_calls": tuple(raw.get("tool_calls", ()))}


class AnthropicAdapter(BaseAdapter):
    def complete(self, model, messages, tools=None, max_tokens=None, *, context=None) -> dict:
        self._guard(context)  # INV-PII-3 hard guard — before ANY send
        request = to_provider_request(messages, tools)
        raw = self._transport.complete(model, request["messages"], tools, max_tokens)
        return from_provider_response(raw)
