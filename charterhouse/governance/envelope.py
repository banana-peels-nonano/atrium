"""S6 spend envelope accounting — a pure fold over one venture's ledger events (INV-GOV-4).

``spend_envelope`` (re)sets the cap and zeroes the running total (the latest envelope is the
active one — a "re-RED" is a fresh envelope); ``spend_meter`` adds to it. Derived from the
ledger on every call: restart-safe, never cached (governance/RISKS R3).
"""

from __future__ import annotations

from dataclasses import dataclass

from charterhouse.contracts.events import Event, EventType


@dataclass(frozen=True)
class EnvelopeState:
    """The active envelope derived from a venture's event stream. ``open`` is False when no
    ``spend_envelope`` was ever appended for the venture."""

    open: bool
    cap_usd: float = 0.0
    running_total: float = 0.0


def envelope_state(events: list[Event]) -> EnvelopeState:
    """Fold a venture's events (ledger order) into its active ``EnvelopeState``. Pure."""
    open_ = False
    cap = 0.0
    total = 0.0
    for event in events:
        if event.type is EventType.SPEND_ENVELOPE:
            open_, cap, total = True, float(event.payload["cap_usd"]), 0.0
        elif event.type is EventType.SPEND_METER:
            total += float(event.payload["amount_usd"])
    return EnvelopeState(open=open_, cap_usd=cap, running_total=total)
