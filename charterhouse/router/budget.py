"""S8 budget guard (docs/14 auto-degrade; docs/40 §5 "degrade on budget") — a ledger fold.

Month-to-date spend = Σ ``payload.cost_usd`` over ``llm_call`` events. Events without a
``timestamp`` count toward the current month — **conservative/fail-closed**: the guard may
degrade early but can never silently overspend (IMPLEMENTATION §6.3; A11 cross-note to
stamp timestamps). Bodies land in the implementation step.

Determinism (docs/61 §INV-DET): pure fold over the ledger + injected today; no LLM.
"""

from __future__ import annotations

from collections.abc import Callable

from charterhouse.contracts.config_types import Budgets
from charterhouse.ledger import Ledger

# Paid-tier models are dropped from every chain past this fraction of the monthly budget
# (docs/14: "auto-degrade past 80%").
DEGRADE_FRACTION = 0.8


def month_spend(ledger: Ledger, *, today: Callable[[], str] | None = None) -> float:
    """Σ cost_usd of ``llm_call`` events in the current month (un-timestamped events
    included — conservative)."""
    from datetime import datetime, timezone

    from charterhouse.contracts.events import EventType
    from charterhouse.ledger import EventFilter

    month = (today() if today is not None
             else datetime.now(timezone.utc).strftime("%Y-%m-%d"))[:7]
    total = 0.0
    for event in ledger.read(EventFilter(type=EventType.LLM_CALL)):
        ts = event.timestamp
        if ts is None or str(ts)[:7] == month:  # None counts: conservative (§6.3)
            cost = event.payload.get("cost_usd")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                total += float(cost)
    return total


def tier_ceiling(spent_usd: float, budgets: Budgets) -> str:
    """``"paid"`` while spend < 80% of ``budgets.monthly_usd``; ``"free"`` at/after the
    degrade threshold (free/local models only)."""
    if spent_usd >= DEGRADE_FRACTION * budgets.monthly_usd:
        return "free"
    return "paid"
