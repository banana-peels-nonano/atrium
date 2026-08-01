"""S5 factory-active-time clock (INV-SM-3; docs/42 §4, R-ACTIVE-TIME, R-CLOCK).

``FactoryClock`` is the injectable active-day accumulator (docs/55 §2 "Clock"): wall time
may pass, but active time advances only while the factory is un-paused.
``derive_active_time`` is the ``Lifecycle.clock(v)`` rule: the experiment deadline runs
from ``experiment_live_at`` (never wall-clock, never state entry); state windows
(SHAPING/BUILDING) run from ``state_entered_at`` — all in active days.

Determinism (docs/61 §INV-DET): stdlib only; no LLM.
"""

from __future__ import annotations

from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State, Venture

from charterhouse.lifecycle.types import ActiveTime, LifecycleLimits

__all__ = ["FactoryClock", "clock_from_ledger", "derive_active_time"]


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


def clock_from_ledger(ledger) -> FactoryClock:  # noqa: ANN001 — Ledger (IF-1)
    """Reconstruct the factory clock at boot from the ledger — the composition root's
    seed (INV-COND-3: the ledger is the only memory, so the clock is derived like every
    other piece of state, never carried in a process).

    Two facts are recovered by replay:

    - **the paused flag**, from the last ``pause``/``resume`` event. Without this a fresh
      process always booted un-paused, so ``resume`` refused ("factory is not paused")
      and a ``pause`` never survived the command that issued it.
    - **accumulated active time**, as the high-water mark of the ``active_time`` already
      stamped on the ledger. Without this every command restarted the counter at 0, so
      every event stamped 0 and no active-day guard could ever fire.

    Degrades to ``(0, un-paused)`` on an empty ledger or a history whose events carry no
    ``active_time`` — which is every event written before this seam existed, so booting
    against an existing ledger is safe.
    """
    paused = False
    high_water = 0
    for event in ledger.read():
        if event.type is EventType.PAUSE:
            paused = True
        elif event.type is EventType.RESUME:
            paused = False
        stamped = event.active_time
        if stamped is not None and int(stamped) > high_water:
            high_water = int(stamped)
    clock = FactoryClock(start=high_water)
    if paused:
        clock.pause()
    return clock


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
