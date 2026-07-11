"""``FakeProvider`` — programmable LLM stand-in (docs/55 §2).

Deterministic canned outputs with programmable latency / errors / rate-limits, so
LLM-dependent code (S8 Router, S10/S11 capabilities) is testable at zero cost. The exact
call signature will be pinned to IF-2's ``Adapter.complete`` half when S8 lands; until then
this exposes a stable, documented ``complete`` shape (docs/40 §5).
"""

from __future__ import annotations

from collections.abc import Sequence


class ProviderError(Exception):
    """A programmed provider failure (e.g. primary down) — drives failover tests."""


class RateLimited(ProviderError):
    """A programmed free-tier rate-limit — drives degrade-ladder tests."""


class FakeProvider:
    """A deterministic provider double. Programmable via the constructor; ``complete``
    returns the same result for the same call, honoring the programmed fault (if any)."""

    def __init__(
        self,
        *,
        canned: str = "fake-completion",
        latency_ms: int = 0,
        error: Exception | None = None,
        rate_limited: bool = False,
        sequence: Sequence[str] | None = None,
    ) -> None:
        self._canned = canned
        self._latency_ms = latency_ms
        self._error = error
        self._rate_limited = rate_limited
        self._sequence = list(sequence) if sequence is not None else None
        self._calls = 0

    def complete(self, model: str, messages: list, tools: list | None = None,
                 max_tokens: int | None = None) -> dict:
        """Return a deterministic ``RawResult``-shaped dict, or raise the programmed fault.
        Deterministic: same call index → same output."""
        self._calls += 1
        if self._rate_limited:
            raise RateLimited(f"{model}: free-tier rate limit (programmed)")
        if self._error is not None:
            raise self._error
        if self._sequence is not None:
            text = self._sequence[(self._calls - 1) % len(self._sequence)]
        else:
            text = self._canned
        return {
            "text": text,
            "model": model,
            "tokens": {"in": len(str(messages)), "out": len(text)},
            "latency_ms": self._latency_ms,
        }

    @property
    def call_count(self) -> int:
        return self._calls
