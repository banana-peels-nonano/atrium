"""Logging (S14) value types + the deterministic field filter (logging/API.md,
logging/IMPLEMENTATION §3).

The field filter is defense-in-depth: it strips/redacts secret- and PII-shaped values
*before* a log line or telemetry payload is written (docs/24, never logs secrets/PII). It
reuses the merged S7 ``Scanner`` (INV-PII-2) so the log filter can never drift from the
authoritative PII detector — a redacted field becomes ``⟨REDACTED:kind,…⟩``.

Determinism (docs/61 §INV-DET): stdlib + security(S7) only; no LLM.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

from charterhouse.security.scan import Scanner

_SCANNER = Scanner()


class Level(str, Enum):
    """Structured log severity (logging/API.md)."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


def _redact_value(value: object) -> object:
    """Return ``value`` unchanged, or ``⟨REDACTED:kinds⟩`` if it (stringified) carries any
    secret/PII shape. Nested mappings/sequences are filtered element-wise."""
    if isinstance(value, Mapping):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(v) for v in value]
    if isinstance(value, (str, bytes)):
        text = value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
        findings = _SCANNER.scan(text)
        if findings:
            kinds = ",".join(sorted({f.kind for f in findings}))
            return f"⟨REDACTED:{kinds}⟩"
    return value


def filter_fields(fields: Mapping) -> dict:
    """Return a copy of ``fields`` with every secret/PII-shaped value redacted (docs/24).
    Never raises — a field that cannot be inspected is passed through only if it is a plain
    scalar with no secret shape."""
    return {str(k): _redact_value(v) for k, v in fields.items()}
