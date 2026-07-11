"""Invariant harness (S15, docs/55 §4): the INV-* → test map + completeness checker.

An ``INV-*``/``MUST`` with no mapped, collectable test blocks the phase-exit gate. Wired
into CI gate 2 (docs/63) for the INV-SM lifecycle family via ``scripts/invariant_check.py``.
"""

from tests.invariants.manifest import (
    INVARIANT_MANIFEST,
    REQUIRED_INVARIANTS,
    family,
    invariant_manifest,
    unmapped,
)

__all__ = [
    "INVARIANT_MANIFEST",
    "REQUIRED_INVARIANTS",
    "family",
    "invariant_manifest",
    "unmapped",
]
