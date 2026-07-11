"""Logging & Telemetry (S14) — the observability spine (docs/40 §10, docs/41 §2).

``Log`` writes structured operational lines to ``logs_dir`` (files); ``Telemetry`` records
``llm_call`` events to the ledger (auditable, replayable). Distinct sinks by design. Both
redact secret/PII-shaped fields first (docs/24), reusing the merged S7 scanner.
"""

from charterhouse.logging.log import Log
from charterhouse.logging.telemetry import Telemetry
from charterhouse.logging.types import Level, filter_fields

__all__ = ["Log", "Telemetry", "Level", "filter_fields"]
