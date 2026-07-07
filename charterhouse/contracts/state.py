"""Frozen IF-1 projection contract — venture states, the per-venture ``Venture`` record, and
``WorldState`` (docs/42 §1, §6; docs/40 §2).

Declarations only. The projection fold that produces these from the event stream lives in
``charterhouse/registry`` and is added in the implementation step.

Determinism (docs/61 §INV-DET): stdlib only; no ``router`` / ``memory`` / ``capabilities``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class State(str, Enum):
    """The complete venture state set (docs/42 §1). Anything not listed is illegal (INV-SM-1,
    enforced by S5 — the Registry only *reflects* the replayed result)."""

    # Factory loop
    CAPTURED = "CAPTURED"
    FRAMED = "FRAMED"
    PARKED = "PARKED"
    PARKED_SHOVEL_READY = "PARKED_SHOVEL_READY"
    VALIDATING = "VALIDATING"
    SHAPING = "SHAPING"
    BUILDING = "BUILDING"
    LAUNCHED = "LAUNCHED"
    EARNING = "EARNING"
    GRADUATED = "GRADUATED"
    # Terminal / holding
    KILLED = "KILLED"
    ARCHIVED = "ARCHIVED"
    # Alumni (out of factory WIP)
    SCALING = "SCALING"
    HARVEST = "HARVEST"
    EXITED = "EXITED"


@dataclass(frozen=True)
class Venture:
    """The per-venture registry record (docs/42 §6). "Current state" is a projection; the
    authoritative state is the replay of the ledger (INV-LEDGER)."""

    id: str
    codename: str
    state: State
    score: int | None = None
    forked_from: str | None = None
    state_entered_at: int | None = None
    experiment_live_at: int | None = None
    active_time_accum: int = 0
    omw_granted: bool = False
    evidence_ttl_at: int | None = None
    artifact_links: tuple[str, ...] = ()
    event_stream_ptr: str | None = None


@dataclass(frozen=True)
class WorldState:
    """The deterministic output of ``Ledger.replay`` feeding the Registry projection
    (IMPLEMENTATION §6): per-venture records keyed by id, in first-seen (event) order.

    Slot/lineage/clock accounting *inputs* are derived here; the *rules* (WIP, legality,
    clocks) live in S5 Lifecycle, never in replay."""

    ventures: dict[str, Venture] = field(default_factory=dict)
