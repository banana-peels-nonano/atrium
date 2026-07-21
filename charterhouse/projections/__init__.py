"""S13 Projections — pure, regenerable renderings of the ledger (docs/40 §9,
docs/41 §3, docs/05). Never a source of truth (INV-COND-3)."""

from charterhouse.projections.board import metrics, pipeline
from charterhouse.projections.briefs import daily_brief, gate_brief, killday_brief
from charterhouse.projections.calibration import calibration
from charterhouse.projections.types import (
    Board,
    BoardRow,
    CalibrationReport,
    CriticTake,
    DailyBrief,
    GateBrief,
    KillDayBrief,
    Metrics,
    NoCriticForGate,
    ProjectionsError,
    UnknownVenture,
)

__all__ = [
    "Board",
    "BoardRow",
    "CalibrationReport",
    "CriticTake",
    "DailyBrief",
    "GateBrief",
    "KillDayBrief",
    "Metrics",
    "NoCriticForGate",
    "ProjectionsError",
    "UnknownVenture",
    "calibration",
    "daily_brief",
    "gate_brief",
    "killday_brief",
    "metrics",
    "pipeline",
]
