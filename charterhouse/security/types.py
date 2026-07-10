"""Public value types + error taxonomy for S7 Security (security/API.md).

Declarations only. ``Finding.masked`` NEVER carries the raw matched value (INV-PII-4:
findings must be loggable).

Determinism (docs/61 §INV-DET): stdlib only; no LLM anywhere in S7.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One scanner hit: the rule kind, a masked excerpt (first/last char + ``…``), and the
    span in the scanned text. Loggable by construction — the raw value is never stored."""

    kind: str
    masked: str
    start: int
    end: int


Findings = tuple[Finding, ...]


@dataclass(frozen=True)
class Context:
    """A retrieval/prompt context as seen by the router seam (docs/40 §5 ``Require``):
    the assembled text, the source refs it was built from, and the ``contains_pii`` tag that
    excludes every cloud adapter (INV-PII-3)."""

    text: str
    sources: tuple[str, ...] = ()
    contains_pii: bool = False


@dataclass(frozen=True)
class CheckpointResult:
    """The only S7 output eligible for the shared tier (INV-PII-1): redacted text, the
    local-only sidecar ref (``None`` when nothing was redacted), and the resulting tag."""

    clean: str
    sidecar_ref: str | None
    contains_pii: bool


class SecurityError(Exception):
    """Base class for every S7 failure."""


class CheckpointError(SecurityError):
    """Residual PII/secret survived redaction — CHECKPOINT fails closed (INV-PII-2). The
    message names finding *kinds*, never values; the venture stays put."""


class PIIRouteBlocked(SecurityError):
    """A ``contains_pii`` context was presented to a cloud route (INV-PII-3)."""
