"""S13 calibration — overrides and evidence verdicts vs outcomes (projections/API.md;
docs/41 §3; the docs/05 monthly judgment audit).

Determinism (docs/61 §INV-DET): a pure fold of the ledger; no clock, no writes.
"""

from __future__ import annotations

from charterhouse.contracts.events import EventType
from charterhouse.ledger import Ledger

from charterhouse.projections.types import CalibrationReport

__all__ = ["calibration"]


def calibration(ledger: Ledger) -> CalibrationReport:
    """Every ``override``/``score_override`` paired with its venture's outcome so far;
    every ``evidence_gate`` verdict paired with the venture's current fate."""
    world = ledger.replay()

    def outcome(venture_id: str | None) -> str:
        if venture_id is None:
            return "FACTORY"
        v = world.ventures.get(venture_id)
        return v.state.value if v is not None else "UNKNOWN"

    overrides = []
    evidence = []
    for e in ledger.read():
        if e.type is EventType.OVERRIDE:
            overrides.append((e.venture_id or "", "override", outcome(e.venture_id)))
        elif e.type is EventType.SCORE_OVERRIDE:
            overrides.append((e.venture_id or "", "score_override",
                              outcome(e.venture_id)))
        elif e.type is EventType.EVIDENCE_GATE:
            evidence.append((e.venture_id or "", str(e.payload.get("verdict")),
                             outcome(e.venture_id)))
    return CalibrationReport(overrides=tuple(overrides),
                             evidence_vs_outcome=tuple(evidence))
