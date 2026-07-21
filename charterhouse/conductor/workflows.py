"""S12's REAL state→workflow table (conductor/API.md; the docs/13 rows S12 owns).

CAPTURED→scout · VALIDATING→analyst · SHAPING→builder · BUILDING→builder ·
LAUNCHED→growth — every row checkpoints the additive, state-neutral
``artifact_produced{artifact_ref, capability, critic_tier}`` event (docs/41 §2).
Built on A8's ``WorkflowRegistry``, which re-validates no-authority at construction
(a gate/RED event type can never enter this table).

Determinism (docs/61 §INV-DET): pure data assembly; the loader parses the six merged
neutral specs from ``agents/`` (A9, live data).
"""

from __future__ import annotations

from pathlib import Path

from charterhouse.capabilities.framework import (
    WorkflowRegistry,
    WorkflowSpec,
    load_capability_specs,
)
from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State

__all__ = ["build_registry", "STATE_CAPABILITY"]

# The docs/13 mapping S12 owns (IMPLEMENTATION §3).
STATE_CAPABILITY: dict[State, str] = {
    State.CAPTURED: "scout",
    State.VALIDATING: "analyst",
    State.SHAPING: "builder",
    State.BUILDING: "builder",
    State.LAUNCHED: "growth",
}


def build_registry(agents_dir: str | Path, *, role: str = "draft",
                   k: int = 5, retries: int = 2) -> WorkflowRegistry:
    """Load the six merged neutral specs and assemble the real table rows —
    ``artifact_produced`` checkpoints, per-state artifact names."""
    specs = {spec.name: spec for spec in load_capability_specs(agents_dir)}
    rows = {
        state: WorkflowSpec(
            capability=specs[capability],
            role=role,
            event_type=EventType.ARTIFACT_PRODUCED,
            artifact_name=f"{capability}-{state.value.lower()}",
            k=k,
            retries=retries,
        )
        for state, capability in STATE_CAPABILITY.items()
    }
    return WorkflowRegistry(rows)
