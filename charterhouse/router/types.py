"""Frozen IF-2 (LLMClient half) value shapes + the S8 error taxonomy (router/API.md;
docs/40 §5).

``PIIRouteBlocked`` and ``Context`` are deliberately NOT redefined here — S8 reuses S7's
(one PII vocabulary across the seam, RISKS note). Declarations only; routing rules live in
the sibling modules and are added in the implementation step.

Determinism (docs/61 §INV-DET): stdlib + contracts only at this layer; no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Re-exported for callers of the seam (S9/S10 import the refusal + context types from the
# router package without caring that S7 owns them).
from charterhouse.security.types import Context, PIIRouteBlocked  # noqa: F401


@dataclass(frozen=True)
class Require:
    """Per-call constraints (docs/40 §5): merged with the route's own flags (require
    wins). ``contains_pii`` is the INV-ROUTE-3/INV-PII-3 locality switch."""

    min_ctx: int | None = None
    needs_tools: bool | None = None
    needs_web: bool | None = None
    contains_pii: bool = False


@dataclass(frozen=True)
class LLMResponse:
    """The one normalized response shape (docs/40 §5) — provider differences never leak.
    ``usage`` is ``{"in": tokens_in, "out": tokens_out}``; ``cost_usd`` is computed from
    the catalog ``Model`` prices (USD per million tokens, docs/22)."""

    text: str
    model: str
    usage: dict
    cost_usd: float
    latency_ms: int
    tool_calls: tuple = field(default_factory=tuple)
    critic_tier: int | None = None


class RouterError(Exception):
    """Base class for every S8 routing failure (fail closed; no partial response)."""


class NoEligibleModel(RouterError):
    """The constraint filters (ctx/tools/web/budget) emptied a non-PII chain — names the
    constraint; never substitutes a guessed model."""


class ProvidersExhausted(RouterError):
    """The configured chain AND the free/local degrade extension all failed — the docs/11
    `pause` signal. The Conductor catches this and declares a factory pause (clocks
    freeze, INV-SM-3); the venture deadline never ticks against a dead provider pool."""
