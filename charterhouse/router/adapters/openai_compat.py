"""``OpenAICompatibleAdapter`` — the one adapter covering ~all providers (docs/11):
OpenRouter, DeepInfra, Groq, Together, Fireworks, vLLM, Ollama, LM Studio. ``GrokAdapter``
is a named subclass (xAI's API is OpenAI-shaped; router/IMPLEMENTATION §6.4).

Messages pass through unchanged (the caller speaks OpenAI shape, docs/40 §5); the transport
result is already the normalized RawResult.
"""

from __future__ import annotations

from charterhouse.router.adapters.base import BaseAdapter


class OpenAICompatibleAdapter(BaseAdapter):
    """Pass-through adapter for OpenAI-shaped providers (base_url/key from Config)."""

    def complete(self, model, messages, tools=None, max_tokens=None, *, context=None) -> dict:
        self._guard(context)  # INV-PII-3 hard guard — before ANY send
        raw = self._transport.complete(model, messages, tools, max_tokens)
        return self._normalize(raw)


class GrokAdapter(OpenAICompatibleAdapter):
    """xAI Grok — OpenAI-compatible; a named adapter so provider registries read honestly."""
