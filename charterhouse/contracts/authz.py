"""Frozen shared authorization types — action classes and founder tokens (docs/43 §6;
docs/14 action-class table; docs/40 §4).

``AuthClass`` and ``Token`` are in the docs/43 §6 shared-type list: Governance (S6) issues
and validates them, Lifecycle (S5) declares them in ``can_transition``/``transition``, the
Conductor (S12) carries them. Declarations only — issuing, scoping, single-use consumption,
and expiry *enforcement* live in ``charterhouse/governance`` (INV-GOV-1..3); no consumer
re-implements a rule.

Determinism (docs/61 §INV-DET): stdlib only; no ``router`` / ``memory`` / ``capabilities``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionColor(str, Enum):
    """The three frozen action classes (docs/14 table).

    GREEN  — reversible, no external effect, capped inference: autonomous, logged.
    YELLOW — metered/internal within budget: allowed within budget, logged,
             auto-degrade past 80%.
    RED    — money out / production / contact / lifecycle gate: hard token,
             never autonomous.
    """

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


@dataclass(frozen=True)
class AuthClass:
    """A classification result: ``RED(+two_key?)`` per docs/40 §4.

    ``two_key`` is only meaningful for RED (INV-GOV-2: token AND passing automated
    check); it is always False for GREEN/YELLOW.
    """

    color: ActionColor
    two_key: bool = False


@dataclass(frozen=True)
class Token:
    """A single-use, expiring, scoped founder authorization (INV-GOV-1/3).

    The token object is immutable; *consumption* state is tracked by the issuing
    Governance token store, never on the token itself (a copied dataclass must not be
    able to reset single-use).

    ``scope``      — the action name this token authorizes (e.g. ``"deploy.prod"``);
                     a token presented for any other action is refused (INV-GOV-1
                     "correctly-scoped").
    ``venture_id`` — the venture the token is bound to; ``None`` = factory-global.
    ``cap_usd``    — for ``spend.envelope`` tokens: the authorized envelope cap
                     (INV-GOV-4); ``None`` for non-envelope tokens.
    ``issued_at`` / ``expires_at`` — seconds on the injected governance clock
                     (deterministic in tests; INV-GOV-3 expiry).
    """

    id: str
    scope: str
    venture_id: str | None
    issued_at: float
    expires_at: float
    cap_usd: float | None = None
