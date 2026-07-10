"""S7 CHECKPOINT pipeline — redact → independent scan → fail closed on residual
(INV-PII-1/2; docs/24 §The pipeline; R-PRECOMMIT-SCAN).

The scan never trusts the redactor (defense in depth): a misbehaving redaction step is caught
here, and ``CheckpointError`` names finding *kinds* only — never values. No clean text is
returned on failure; the venture stays put (caller contract).
"""

from __future__ import annotations

from charterhouse.security.redact import Redactor
from charterhouse.security.scan import Scanner
from charterhouse.security.types import CheckpointError, CheckpointResult


def run_checkpoint(
    text: str,
    doc_id: str | None = None,
    *,
    redactor: Redactor,
    scanner: Scanner,
) -> CheckpointResult:
    """The composed docs/24 pipeline. Raises ``CheckpointError`` on any residual finding."""
    clean, sidecar_ref = redactor.redact(text, doc_id)
    residual = scanner.scan(clean)
    if residual:
        kinds = ", ".join(sorted({finding.kind for finding in residual}))
        raise CheckpointError(
            f"residual PII/secret survived redaction (kinds: {kinds}) — "
            "failing closed; nothing is eligible for the shared tier (INV-PII-2)"
        )
    return CheckpointResult(
        clean=clean, sidecar_ref=sidecar_ref, contains_pii=sidecar_ref is not None
    )
