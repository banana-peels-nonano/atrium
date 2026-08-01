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

# Per-row producer route (INV-ROUTE-1: a ROLE, never a model id). The judgment rows — the
# ones whose artifact goes to a founder gate — produce on `reasoning` (the free profile's
# strongest free model); the making rows stay on `draft`. Per-row rather than a global flip
# so `shape`/`build` keep the route they were merged with.
STATE_ROLE: dict[State, str] = {
    State.CAPTURED: "reasoning",
    State.VALIDATING: "reasoning",
}
DEFAULT_ROLE = "draft"


def _payload_fn(artifact_name: str):
    """The CHECKPOINT payload builder for one row. Additive fields (docs/41 §2, IF-1's
    versioned-no-bump rule) carry the critic's take onto the ledger so the gate brief can
    replay a STEER — direction, not just kill-or-continue — with its provenance."""
    def build(artifact, critique) -> dict:  # noqa: ANN001 — Artifact/Critique (IF-5)
        return {
            "artifact_ref": f"ventures/{artifact.venture_id}/{artifact_name}.md",
            "capability": artifact.capability,
            "critic_tier": critique.tier,
            "critic_verdict": critique.verdict,
            "critic_model": critique.model,
            "steer": critique.steer,
        }
    return build


def build_registry(agents_dir: str | Path, *, role: str | None = None,
                   k: int = 5, retries: int = 2) -> WorkflowRegistry:
    """Load the six merged neutral specs and assemble the real table rows —
    ``artifact_produced`` checkpoints, per-state artifact names, per-state producer roles.
    An explicit ``role`` overrides the whole table (tests/simulator)."""
    specs = {spec.name: spec for spec in load_capability_specs(agents_dir)}
    rows = {}
    for state, capability in STATE_CAPABILITY.items():
        artifact_name = f"{capability}-{state.value.lower()}"
        rows[state] = WorkflowSpec(
            capability=specs[capability],
            role=role if role is not None else STATE_ROLE.get(state, DEFAULT_ROLE),
            event_type=EventType.ARTIFACT_PRODUCED,
            artifact_name=artifact_name,
            payload_fn=_payload_fn(artifact_name),
            k=k,
            retries=retries,
        )
    return WorkflowRegistry(rows)
