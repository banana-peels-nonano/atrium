"""Shared pytest harness wiring (A11).

This holds the repo-root fixture used by the structure test and anchors the shared fakes
(FakeProvider, FakeEmbedder, Clock, pii_corpus, golden_set) that A11 delivered per
docs/55_testing_strategy.md §2. No production logic lives here.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root (the folder containing this `tests/` dir)."""
    return Path(__file__).resolve().parent.parent
