"""S5 factory-active-time clock (INV-SM-3; docs/42 §4, R-ACTIVE-TIME, R-CLOCK).

``FactoryClock`` is the injectable active-day accumulator (docs/55 §2 "Clock"): wall time
may pass, but active time advances only while the factory is un-paused.
``derive_active_time`` is the ``Lifecycle.clock(v)`` rule: the experiment deadline runs
from ``experiment_live_at`` (never wall-clock, never state entry); state windows
(SHAPING/BUILDING) run from ``state_entered_at`` — all in active days.

Determinism (docs/61 §INV-DET): stdlib only; no LLM.
"""

from __future__ import annotations

from charterhouse.contracts.state import State, Venture

from charterhouse.lifecycle.types import ActiveTime, LifecycleLimits


class FactoryClock:
    """Active-day counter with a pause flag. ``advance(days)`` models wall-time passing:
    it accumulates into active time only while un-paused (INV-SM-3)."""

    def __init__(self, start: int = 0) -> None:
        self._active = int(start)
        self._paused = False

    @property
    def now_active(self) -> int:
        return self._active

    @property
    def paused(self) -> bool:
        return self._paused

    def advance(self, days: int) -> None:
        if not self._paused:
            self._active += int(days)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False


def derive_active_time(
    v: Venture, clock: FactoryClock, limits: LifecycleLimits
) -> ActiveTime:
    """The ``Lifecycle.clock(v)`` derivation (lifecycle/API.md): deadlines from
    ``experiment_live_at``; state windows from ``state_entered_at``; all active-days."""
    now = clock.now_active
    live = v.experiment_live_at
    entered = v.state_entered_at
    deadline: int | None = None
    if v.state is State.VALIDATING and live is not None:
        deadline = live + limits.validating_window_days
    elif v.state is State.SHAPING and entered is not None:
        deadline = entered + limits.shaping_max_days
    elif v.state is State.BUILDING and entered is not None:
        deadline = entered + limits.building_max_days
    return ActiveTime(
        now_active=now,
        experiment_live_at=live,
        elapsed_experiment=(now - live) if live is not None else None,
        elapsed_in_state=(now - entered) if entered is not None else None,
        deadline_at=deadline,
        remaining=(deadline - now) if deadline is not None else None,
        paused=clock.paused,
    )
