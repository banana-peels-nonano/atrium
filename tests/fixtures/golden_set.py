"""``golden_set`` — saved real tasks for capability/model drift detection (docs/55 §2).

Frozen future-proofing: a small, stable set of representative task descriptors (5 scout
briefs, 2 analyst packs, 1 builder task — docs/55 §2). SHAPE + a minimal seed now; the
capability agents (S11) extend the payloads with real golden outputs when they land. The
harness contract is the descriptor shape, not the (future) captured completions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenTask:
    """One saved task: a role + input, and (later) the captured golden output to diff."""

    id: str
    role: str
    prompt: str
    golden_output: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


_SEED: tuple[GoldenTask, ...] = (
    GoldenTask("scout-01", "scout", "Draft a one-line venture brief for a B2B pain.",
               tags=("scout", "brief")),
    GoldenTask("scout-02", "scout", "Score reachability for an offline HVAC segment.",
               tags=("scout", "score")),
    GoldenTask("scout-03", "scout", "Summarize 3 primary pain quotes into a framing.",
               tags=("scout", "framing")),
    GoldenTask("scout-04", "scout", "Flag a known dead-pattern from a captured idea.",
               tags=("scout", "kill")),
    GoldenTask("scout-05", "scout", "Propose a validation plan first checkpoint.",
               tags=("scout", "plan")),
    GoldenTask("analyst-01", "analyst", "Bottom-up market ceiling for a $30/mo tool.",
               tags=("analyst", "market")),
    GoldenTask("analyst-02", "analyst", "Competitor teardown from 20 pain quotes.",
               tags=("analyst", "teardown")),
    GoldenTask("builder-01", "builder", "Cut a SPEC to one loop, three screens.",
               tags=("builder", "spec")),
)


def golden_set() -> tuple[GoldenTask, ...]:
    """Return the frozen golden task set (docs/55 §2)."""
    return _SEED
