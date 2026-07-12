"""Adapter base (docs/40 §5) + the INV-PII-3 hard guard (router/IMPLEMENTATION §3).

Every adapter wraps an injected ``transport`` (A11's ``FakeProvider`` in tests; the real
HTTP client with its ``key_lookup`` seam at wiring time — never built here). **Cloud**
adapters call the merged S7 guard (``require_cloud_allowed``) before ANY send: a
``contains_pii`` context raises ``PIIRouteBlocked`` at the boundary even if a buggy chain
let it through. Local adapters carry no guard — local execution is the PII-legal path.

Determinism boundary: the adapter call is the system's one LLM path; everything around it
is deterministic normalization.
"""

from __future__ import annotations

from charterhouse.contracts.config_types import Provider
from charterhouse.security.tag import require_cloud_allowed
from charterhouse.security.types import Context

# The normalized transport result every adapter returns from ``complete``:
# {"text": str, "tokens": {"in": int, "out": int}, "latency_ms": int, "tool_calls": tuple}


class BaseAdapter:
    """One provider *shape*. ``complete`` keeps the frozen docs/40 §5 positional
    signature; ``context`` is the additive guard kwarg (API.md v1 note)."""

    def __init__(self, provider: Provider, transport) -> None:
        self._provider = provider
        self._transport = transport

    @property
    def kind(self) -> str:
        return self._provider.kind

    def _guard(self, context: Context | None) -> None:
        """The A5-defined, A6-enforced seam: cloud + ``contains_pii`` → refuse before any
        send (INV-PII-3). An absent context is an untagged (clean) context — tagging is
        the upstream CHECKPOINT's job (docs/24); the guard enforces the tag, never guesses."""
        if self._provider.kind != "local":
            require_cloud_allowed(context if context is not None else Context(text=""))

    def complete(self, model: str, messages: list, tools: list | None = None,
                 max_tokens: int | None = None, *, context: Context | None = None) -> dict:
        raise NotImplementedError("subclasses implement the provider shape")

    @staticmethod
    def _normalize(raw: dict) -> dict:
        """Any transport result → the one RawResult shape (docs/11 "never leak")."""
        return {
            "text": raw.get("text", ""),
            "tokens": dict(raw.get("tokens", {"in": 0, "out": 0})),
            "latency_ms": int(raw.get("latency_ms", 0)),
            "tool_calls": tuple(raw.get("tool_calls", ())),
        }
