"""S5 slot accounting (INV-SM-2; docs/42 §2) — a pure Registry projection, never cached.

Determinism (docs/61 §INV-DET): stdlib + contracts only; no LLM.
"""

from __future__ import annotations

from charterhouse.contracts.state import State
from charterhouse.registry.facade import Registry

from charterhouse.lifecycle.types import LifecycleLimits, SlotState


def slot_state(registry: Registry, limits: LifecycleLimits) -> SlotState:
    """Current WIP counts vs limits from ``Registry.query`` (docs/40 §3 ``slots()``).
    Recomputed on every call so it can never serve stale counts (INV-SM-2)."""
    return SlotState(
        validating=(len(registry.query(State.VALIDATING)), limits.validating_wip),
        shaping=(len(registry.query(State.SHAPING)), limits.shaping_wip),
        building=(len(registry.query(State.BUILDING)), limits.building_wip),
        harvest=(len(registry.query(State.HARVEST)), limits.harvest_cap),
    )
