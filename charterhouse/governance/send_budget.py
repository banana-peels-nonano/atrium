"""S6 founder-wide daily send budget — a pure fold over ``send_batch`` events (INV-GOV-5,
R-SEND-BUDGET).

The budget is a single cap across ALL ventures (never per-venture-unbounded): units sent on a
day = Σ ``send_batch.payload.count`` whose envelope ``timestamp`` date is that day.
"""

from __future__ import annotations

from charterhouse.contracts.events import Event, EventType


def sent_on(events: list[Event], day: str) -> int:
    """Total units sent on ``day`` (``YYYY-MM-DD``) across all ventures. Pure."""
    total = 0
    for event in events:
        if (
            event.type is EventType.SEND_BATCH
            and event.timestamp is not None
            and event.timestamp[:10] == day
        ):
            total += int(event.payload.get("count", 0))
    return total
