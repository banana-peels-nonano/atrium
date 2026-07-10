"""Lifecycle (S5) — the venture state machine (docs/42; lifecycle/API.md, IF-4).

Public surface: the frozen docs/40 §3 four (``can_transition``/``transition``/``slots``/
``clock``) + documented additive seams (``pivot``/``grant_omw``/``pause``/``resume``),
the IF-4 value shapes, the typed fail-closed error taxonomy, and the verbatim docs/42 §3
table (``TRANSITIONS``).
"""

from charterhouse.lifecycle.clock import FactoryClock
from charterhouse.lifecycle.facade import GovPort, Lifecycle
from charterhouse.lifecycle.table import TRANSITIONS, Rule
from charterhouse.lifecycle.types import (
    ActiveTime,
    AuthorizationDenied,
    ExpressRefused,
    ForkCapExceeded,
    GuardFailed,
    GuardResult,
    IllegalTransition,
    LifecycleError,
    LifecycleLimits,
    OmwExhausted,
    PivotResult,
    Result,
    SlotLimitExceeded,
    SlotState,
    StaleEvidence,
)

__all__ = [
    "TRANSITIONS",
    "ActiveTime",
    "AuthorizationDenied",
    "ExpressRefused",
    "FactoryClock",
    "ForkCapExceeded",
    "GovPort",
    "GuardFailed",
    "GuardResult",
    "IllegalTransition",
    "Lifecycle",
    "LifecycleError",
    "LifecycleLimits",
    "OmwExhausted",
    "PivotResult",
    "Result",
    "Rule",
    "SlotLimitExceeded",
    "SlotState",
    "StaleEvidence",
]
