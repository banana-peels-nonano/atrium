"""S14 telemetry — ``Telemetry.record`` → an ``llm_call`` ledger event (logging/API.md,
docs/40 §10, docs/41 §2).

Telemetry is the **auditable, replayable** sink (distinct from operational file logs): each
LLM call is one `llm_call` event appended via ``Ledger.append`` (INV-ROUTE-4). No secret/PII
in the payload — fields are filtered first (docs/24), and the Ledger's own structural
pre-check is the backstop. A ledger failure is surfaced (never silently dropped, RISKS R7).

Determinism (docs/61 §INV-DET): stdlib + S4 + S7 filter only; no LLM.
"""

from __future__ import annotations

from collections.abc import Mapping

from charterhouse.contracts.events import Event, EventType
from charterhouse.ledger import Ledger

from charterhouse.logging.types import filter_fields

# docs/41 §2 llm_call payload fields.
_LLM_CALL_FIELDS = ("role", "model", "provider", "tokens", "cost_usd", "latency_ms",
                    "critic_tier")


class Telemetry:
    """Records per-call telemetry as ledger ``llm_call`` events. Construct with the real
    (or in-memory) ``Ledger`` — the same append surface (IF-1)."""

    def __init__(self, ledger: Ledger, *, actor: str = "system") -> None:
        self._ledger = ledger
        self._actor = actor

    def record(self, llm_call_fields: Mapping) -> str:
        """Append one ``llm_call`` event (docs/41 §2) and return its ``event_id``. Payload
        is secret/PII-filtered first; a Ledger failure propagates (surfaced, not dropped)."""
        payload = filter_fields({k: llm_call_fields[k] for k in _LLM_CALL_FIELDS
                                 if k in llm_call_fields})
        venture_id = llm_call_fields.get("venture_id")
        event = Event(
            type=EventType.LLM_CALL,
            actor=self._actor,
            payload=payload,
            venture_id=venture_id,
        )
        return self._ledger.append(event)
