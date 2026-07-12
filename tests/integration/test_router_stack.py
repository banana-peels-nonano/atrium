"""S8 × S3 × S7 × S4 integration — the router over the real stack (router/TESTPLAN.md).

The PII flow is the one that matters (Stress-Test C3): a context carrying real corpus PII
is tagged by the merged S7 scanner, and the tagged call routes ONLY to a local model —
even though the committed `free` profile's reasoning chain is all-cloud (the degrade
extension provides the local path). No network: FakeProvider transports throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.config import Config
from charterhouse.contracts.events import EventType
from charterhouse.ledger import EventFilter, Ledger
from charterhouse.router import Require
from charterhouse.router.facade import Router
from charterhouse.security.scan import Scanner
from charterhouse.security.tag import tag
from charterhouse.security.types import Context

from tests.fakes import FakeProvider
from tests.fixtures import pii_corpus
from tests.unit import _a6_support as sup
from tests.unit._a6_support import USER_MSG

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


def committed_stack(tmp_path):
    config = Config.load(REPO_CONFIG, profile="free")
    ledger = Ledger(tmp_path / "ledger")
    transports = {pid: FakeProvider(canned=f"answer-from-{pid}")
                  for pid in ("ollama", "openrouter", "groq", "gemini")}
    return Router(config, ledger, transports=transports), config, ledger, transports


def test_it_committed_config_free_profile_routes(tmp_path):
    """INV-ROUTE-1 over the real committed config/: the `free` profile's reasoning
    primary answers; telemetry lands on the real ledger."""
    router, config, ledger, _ = committed_stack(tmp_path)
    resp = router.call("reasoning", USER_MSG)
    assert resp.model == config.get_route("reasoning").primary
    (event,) = list(ledger.read(EventFilter(type=EventType.LLM_CALL)))
    assert event.payload["model"] == resp.model


def test_it_pii_flow_tag_to_local_route(tmp_path):
    """INV-PII-3 end-to-end (S7 tag → S8 enforcement): corpus PII tags the context via
    the real scanner; the tagged call skips the all-cloud committed chain and lands on
    the LOCAL model via the degrade extension; cloud transports untouched; the block and
    the call are both audited on the real ledger."""
    email = next(v for k, v in pii_corpus()["positives"] if k == "email")
    ctx = tag(Context(text=f"reach the founder at {email}"), Scanner())
    assert ctx.contains_pii  # the real S7 scanner tagged it
    router, config, ledger, transports = committed_stack(tmp_path)
    resp = router.call("reasoning", USER_MSG,
                       require=Require(contains_pii=ctx.contains_pii))
    assert config.get_model(resp.model).provider == "ollama"  # local-only
    for pid in ("openrouter", "groq", "gemini"):
        assert transports[pid].call_count == 0
    kinds = [e.type for e in ledger.read()]
    assert EventType.PII_BLOCK in kinds and EventType.LLM_CALL in kinds


def test_it_budget_degrade_over_committed_cheap_cloud(tmp_path):
    """Budget guard over the committed cheap-cloud profile: at 80% spend the paid
    primary (claude-sonnet) is skipped for the free fallback."""
    config = Config.load(REPO_CONFIG, profile="cheap-cloud")
    ledger = Ledger(tmp_path / "ledger")
    transports = {pid: FakeProvider() for pid in
                  ("ollama", "openrouter", "groq", "gemini")}
    router = Router(config, ledger, transports=transports,
                    spent_usd=lambda: 80.0)  # 80% of the cheap-cloud 100.0
    resp = router.call("reasoning", USER_MSG)
    assert config.get_model(resp.model).tier == "free"
