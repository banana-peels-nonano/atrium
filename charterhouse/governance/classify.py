"""S6 action-class engine — the frozen GREEN/YELLOW/RED(+two-key) matrix (docs/14 table,
docs/40 §8 command names; governance/IMPLEMENTATION §3).

The matrix is data, not control flow: every docs/40 §8 command maps to its class; unknown
names classify RED (fail closed) and are additionally denied by ``Gov.authorize``.
"""

from __future__ import annotations

from charterhouse.contracts.authz import ActionColor, AuthClass

from charterhouse.governance.types import Action

# "Scaled outreach" bound (IMPLEMENTATION §6): a send.stage batch above one founder-day of
# manual sends (Stress Test §1) is two-key. Internal constant — tightening it is not an ICR.
SCALED_SEND_THRESHOLD = 25

_GREEN = (
    "capture", "frame", "validate.evidence", "shape", "recruit.partners", "salvage",
    "consolidate", "calibrate", "pause", "resume", "pipeline", "brief", "killday", "gatebrief",
)
_YELLOW = ("spend.meter", "validate.experiment", "build")
_RED = (
    "admit", "gate", "advance.express", "spend.envelope", "send.stage", "launch",
    "pivot", "graduate", "kill",
)
_RED_TWO_KEY = ("deploy.prod", "billing.enable")

MATRIX: dict[str, AuthClass] = {
    **{name: AuthClass(ActionColor.GREEN) for name in _GREEN},
    **{name: AuthClass(ActionColor.YELLOW) for name in _YELLOW},
    **{name: AuthClass(ActionColor.RED) for name in _RED},
    **{name: AuthClass(ActionColor.RED, two_key=True) for name in _RED_TWO_KEY},
}


def is_known(name: str) -> bool:
    """True iff ``name`` is a docs/40 §8 command in the frozen matrix."""
    return name in MATRIX


def batch_count(action: Action) -> int | None:
    """The send.stage batch size as a clean non-negative int, or ``None`` when the present
    ``count`` is malformed (non-numeric, bool, fractional, or negative — fail closed).
    A missing count is 0 (the bare command classifies plain RED per the frozen matrix)."""
    count = action.params.get("count", 0)
    if isinstance(count, bool) or not isinstance(count, (int, float)):
        return None
    if count != int(count) or count < 0:
        return None
    return int(count)


def classify(action: Action) -> AuthClass:
    """Return the frozen class for ``action`` (docs/40 §4). Pure; total (unknown → RED)."""
    base = MATRIX.get(action.name)
    if base is None:
        return AuthClass(ActionColor.RED)  # fail closed; authorize additionally denies
    if action.name == "send.stage":
        count = batch_count(action)
        # Scaled outreach is two-key (INV-GOV-2); a malformed count cannot dodge the gate.
        if count is None or count > SCALED_SEND_THRESHOLD:
            return AuthClass(ActionColor.RED, two_key=True)
    return base
