"""``Simulator`` — the lifecycle-simulator harness surface (docs/55 §3; SHAPE frozen).

The crown-jewel test driver: instantiate ventures, issue Conductor commands with the fakes,
assert states/events/invariants, and reproduce Stress-Test A/B/C. Its **shape is frozen
now**; the executable body lands with S10 Capability Framework + S12 Conductor (the beats
`Simulator` drives do not exist yet). S5's own Stress-Test reproduction already runs against
the real stack in ``tests/integration/test_lifecycle_sim.py``; this class is the general,
Conductor-command-driven form that supersedes it once S12 exists.

Until then ``run`` raises with a precise "not yet executable" message (not a silent stub) —
``it_simulator_shape_available`` asserts the interface is present and documented.
"""

from __future__ import annotations

from collections.abc import Mapping


class Simulator:
    """Deterministic lifecycle driver over injected fakes. Shape-only (docs/55 §3)."""

    def __init__(self, *, ledger=None, clock=None, provider=None, embedder=None,
                 config=None) -> None:
        self.ledger = ledger
        self.clock = clock
        self.provider = provider
        self.embedder = embedder
        self.config = config
        self._commands: list[tuple[str, Mapping]] = []

    def command(self, name: str, args: Mapping | None = None) -> "Simulator":
        """Queue a Conductor command (the frozen shape). Recorded but not executed until the
        body lands with S12."""
        self._commands.append((name, dict(args or {})))
        return self

    def run(self):
        """Execute the queued scenario. **Not yet executable** — needs S10 + S12."""
        raise NotImplementedError(
            "Simulator.run needs S10 Capability Framework + S12 Conductor (docs/55 §3); "
            "the shape is frozen now, the body lands with those subsystems. For lifecycle "
            "(S5) scenarios today, see tests/integration/test_lifecycle_sim.py.")

    @property
    def queued(self) -> list[tuple[str, Mapping]]:
        return list(self._commands)
