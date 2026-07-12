"""``GeminiAdapter`` — thin shim translating OpenAI-shaped requests to/from the Gemini
``generateContent`` shape (docs/11).

Pure translation functions (unit-tested without transport):
- ``to_provider_request``: system messages → ``systemInstruction``; user/assistant →
  ``contents`` with roles ``user``/``model`` and ``parts=[{"text": …}]``.
- ``from_provider_response``: a Gemini-shaped response (``candidates`` +
  ``usageMetadata``) normalizes to the RawResult dict; an already-normalized result
  passes through.
"""

from __future__ import annotations

from charterhouse.router.adapters.base import BaseAdapter


_ROLE_MAP = {"user": "user", "assistant": "model"}


def to_provider_request(messages: list, tools: list | None = None) -> dict:
    """OpenAI-shaped messages → ``{"systemInstruction": …, "contents": [...]}``. Pure."""
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    contents = [{"role": _ROLE_MAP[m["role"]], "parts": [{"text": m["content"]}]}
                for m in messages if m.get("role") in _ROLE_MAP]
    return {"systemInstruction": "\n".join(system_parts) if system_parts else None,
            "contents": contents}


def from_provider_response(raw: dict) -> dict:
    """Gemini-shaped (or already-normalized) response → RawResult. Pure."""
    if "candidates" in raw:  # Gemini generateContent shape
        parts = raw["candidates"][0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        usage = raw.get("usageMetadata", {})
        return {"text": text,
                "tokens": {"in": int(usage.get("promptTokenCount", 0)),
                           "out": int(usage.get("candidatesTokenCount", 0))},
                "latency_ms": int(raw.get("latency_ms", 0)),
                "tool_calls": tuple(raw.get("tool_calls", ()))}
    return {"text": raw.get("text", ""),
            "tokens": dict(raw.get("tokens", {"in": 0, "out": 0})),
            "latency_ms": int(raw.get("latency_ms", 0)),
            "tool_calls": tuple(raw.get("tool_calls", ()))}


class GeminiAdapter(BaseAdapter):
    def complete(self, model, messages, tools=None, max_tokens=None, *, context=None) -> dict:
        self._guard(context)  # INV-PII-3 hard guard — before ANY send
        request = to_provider_request(messages, tools)
        raw = self._transport.complete(model, request["contents"], tools, max_tokens)
        return from_provider_response(raw)
