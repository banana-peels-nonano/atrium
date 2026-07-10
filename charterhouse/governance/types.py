"""Public value types + error taxonomy for S6 Governance (governance/API.md).

Declarations only. Shared authorization types (``AuthClass``, ``ActionColor``, ``Token``) live
in ``charterhouse/contracts/authz.py`` (docs/43 §6) — never redefined here.

Determinism (docs/61 §INV-DET): stdlib only; no ``router`` / ``memory`` / ``capabilities``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from charterhouse.contracts.authz import ActionColor
from charterhouse.contracts.config_types import Budgets


@dataclass(frozen=True)
class CheckResult:
    """The automated-check half of a two-key authorization (INV-GOV-2): the named check that
    ran (payment-path test, deliverability check, …) and whether it passed. S6 verifies
    presence + result; *running* the check belongs to the deploy pipeline (S8/S12)."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class Action:
    """A proposed action presented for classification/authorization (docs/40 §4).

    ``name`` is a docs/40 §8 command name (e.g. ``"deploy.prod"``); unknown names classify RED
    and are denied (fail closed). ``check`` carries the two-key automated-check result when the
    action is in the two-key set.
    """

    name: str
    venture_id: str | None = None
    params: Mapping[str, object] = field(default_factory=dict)
    check: CheckResult | None = None


@dataclass(frozen=True)
class Decision:
    """An authorize outcome: ``ok`` or denied-with-reason. Denial is a normal, logged outcome,
    never an exception (governance/API.md)."""

    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class SpendResult:
    """A ``Gov.spend`` outcome (INV-GOV-4). ``color`` is YELLOW for a within-envelope spend,
    ``None`` on refusal. ``degrade`` is the docs/14 auto-degrade signal (running total past 80%
    of cap). ``running_total`` reflects the state *after* an ok spend / *unchanged* on refusal."""

    ok: bool
    color: ActionColor | None
    amount: float
    running_total: float
    cap_usd: float | None
    degrade: bool = False
    reason: str = ""


class ConfigPort(Protocol):
    """The slice of S3 Config that S6 consumes (docs/40 §1, frozen IF-2 Config-half shape).
    Stubbed by a test double until A2 lands (docs/43 §2); the real Config satisfies it as-is."""

    @property
    def budgets(self) -> Budgets: ...


class GovernanceError(Exception):
    """Base class for every S6 misuse failure (refusals are ``Decision``/``SpendResult``
    values, not exceptions)."""


class MissingReason(GovernanceError):
    """A founder override was recorded without a non-empty reason (INV-GOV-6 fail-closed)."""
