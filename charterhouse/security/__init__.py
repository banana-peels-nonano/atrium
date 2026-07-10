"""S7 Security — the PII pipeline: redact / scan / tag / checkpoint + the cloud-route guard
(docs/24, docs/40 §4). Public surface per security/API.md."""

from __future__ import annotations

from charterhouse.security.checkpoint import run_checkpoint
from charterhouse.security.facade import Security
from charterhouse.security.redact import Redactor
from charterhouse.security.scan import Scanner
from charterhouse.security.tag import cloud_route_allowed, require_cloud_allowed, tag
from charterhouse.security.types import (
    CheckpointError,
    CheckpointResult,
    Context,
    Finding,
    Findings,
    PIIRouteBlocked,
    SecurityError,
)

__all__ = [
    "run_checkpoint",
    "Security",
    "Redactor",
    "Scanner",
    "cloud_route_allowed",
    "require_cloud_allowed",
    "tag",
    "CheckpointError",
    "CheckpointResult",
    "Context",
    "Finding",
    "Findings",
    "PIIRouteBlocked",
    "SecurityError",
]
