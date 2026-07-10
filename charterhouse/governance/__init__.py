"""S6 Governance — classify / authorize / envelope / send budget (docs/14, docs/40 §4).

Public surface per governance/API.md. Shared types (``AuthClass``, ``ActionColor``,
``Token``) come from ``charterhouse.contracts``.
"""

from __future__ import annotations

from charterhouse.governance.classify import SCALED_SEND_THRESHOLD, classify
from charterhouse.governance.facade import Gov
from charterhouse.governance.types import (
    Action,
    CheckResult,
    ConfigPort,
    Decision,
    GovernanceError,
    MissingReason,
    SpendResult,
)

__all__ = [
    "SCALED_SEND_THRESHOLD",
    "classify",
    "Gov",
    "Action",
    "CheckResult",
    "ConfigPort",
    "Decision",
    "GovernanceError",
    "MissingReason",
    "SpendResult",
]
