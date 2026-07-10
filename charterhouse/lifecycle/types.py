"""Frozen IF-4 value shapes + the S5 error taxonomy (lifecycle/API.md; docs/40 §3).

Declarations only — every *rule* (legality, slots, clocks, caps) lives in the sibling
modules and is added in the implementation step (tests-first).

Determinism (docs/61 §INV-DET): stdlib + contracts only; no ``router`` / ``memory`` /
``capabilities``; no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from charterhouse.contracts.authz import AuthClass
from charterhouse.contracts.state import State


@dataclass(frozen=True)
class LifecycleLimits:
    """The frozen docs/42 §2 WIP limits + §4/Stress-Test windows, in active-days
    (IMPLEMENTATION §6.4). Constructor-injectable for tests; defaults are the contract."""

    validating_wip: int = 3
    shaping_wip: int = 1
    building_wip: int = 1
    harvest_cap: int = 3
    evidence_ttl_days: int = 60
    shaping_max_days: int = 10
    building_max_days: int = 15
    validating_window_days: int = 14
    graduation_window_days: int = 60


@dataclass(frozen=True)
class GuardResult:
    """``can_transition`` outcome (docs/40 §3): pure check, no side effects."""

    ok: bool
    reasons: tuple[str, ...] = ()
    needs_auth: AuthClass | None = None


@dataclass(frozen=True)
class Result:
    """``transition`` success value (docs/40 §3). Refusals raise — they never return."""

    ok: bool
    event_id: str
    from_state: State
    to_state: State


@dataclass(frozen=True)
class SlotState:
    """Current WIP counts vs frozen limits (INV-SM-2), recomputed from the Registry on
    every call — never cached. Each field is ``(count, limit)``."""

    validating: tuple[int, int]
    shaping: tuple[int, int]
    building: tuple[int, int]
    harvest: tuple[int, int]

    def free(self, kind: str) -> bool:
        count, limit = getattr(self, kind)
        return count < limit


@dataclass(frozen=True)
class ActiveTime:
    """``clock(v)`` answer (INV-SM-3): everything in factory-active days. Deadlines run
    from ``experiment_live_at`` (never wall-clock, never state entry); state windows run
    from ``state_entered_at`` in active days."""

    now_active: int
    experiment_live_at: int | None
    elapsed_experiment: int | None
    elapsed_in_state: int | None
    deadline_at: int | None
    remaining: int | None
    paused: bool


@dataclass(frozen=True)
class PivotResult:
    """``pivot`` outcome (docs/42 §5): the kill-and-fork event trail."""

    killed_id: str
    new_id: str
    events: tuple[str, ...] = field(default_factory=tuple)


# --- Error taxonomy (fail closed, docs/61 §INV-FAILCLOSED; lifecycle/API.md) -----------------


class LifecycleError(Exception):
    """Base class for every S5 refusal. A raised transition appended exactly one
    ``error`` event and changed no venture state."""


class IllegalTransition(LifecycleError):
    """The (from, to) pair is not in the docs/42 §3 table (INV-SM-1): rejected + logged."""


class SlotLimitExceeded(LifecycleError):
    """The transition would exceed a docs/42 §2 WIP limit (INV-SM-2)."""


class GuardFailed(LifecycleError):
    """A legal row whose guard column does not hold (incl. a judgment-guard row missing
    its non-empty founder ``reason``)."""


class ExpressRefused(LifecycleError):
    """``express=True`` on a row not marked Express=yes (INV-SM-4, R-SLOT-GATE)."""


class StaleEvidence(LifecycleError):
    """Shovel-ready evidence past its TTL without a re-confirmation signal (INV-SM-6)."""


class ForkCapExceeded(LifecycleError):
    """A second ``pivot_fork`` anywhere in the lineage (INV-SM-5): one fork per lineage."""


class OmwExhausted(LifecycleError):
    """A second ONE-MORE-WEEK grant in the lineage (R-OMW-LEDGER)."""


class AuthorizationDenied(LifecycleError):
    """Gov denied (or no token was presented for) a gate row; carries Gov's reason."""
