"""``Clock`` — injectable factory-active-time double (docs/55 §2).

Supports ``pause``/``resume`` so TTL/deadline tests (INV-SM-3) can freeze accumulation.
``rate`` scales wall advance → active time. Distinct from S5's ``FactoryClock`` (which is
integer active-days); this harness clock is float-seconds and general-purpose.
"""

from __future__ import annotations


class Clock:
    """A deterministic, pausable clock. ``now()`` returns accumulated active time."""

    def __init__(self, start: float = 0.0, rate: float = 1.0) -> None:
        self._active = float(start)
        self._rate = float(rate)
        self._paused = False

    def now(self) -> float:
        return self._active

    def advance(self, wall_seconds: float) -> None:
        """Advance wall time; active time grows by ``wall_seconds * rate`` unless paused."""
        if not self._paused:
            self._active += float(wall_seconds) * self._rate

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused
