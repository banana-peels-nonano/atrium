"""Shared test fixtures (A11-owned harness, docs/55 §2).

``pii_corpus()`` returns the scanner-bar corpus (defined in ``pii_corpus.py``);
``golden_set()`` returns the drift-detection task set.
"""

from tests.fixtures import pii_corpus as _pii
from tests.fixtures.golden_set import GoldenTask, golden_set


def pii_corpus() -> dict:
    """The PII corpus as ``{positives, negatives, known_identities}`` (docs/55 §2)."""
    return {
        "positives": _pii.POSITIVES,
        "negatives": _pii.NEGATIVES,
        "known_identities": _pii.KNOWN_IDENTITIES,
    }


__all__ = ["pii_corpus", "golden_set", "GoldenTask"]
