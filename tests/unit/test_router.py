"""S8 Router unit suite — INV-ROUTE-1..4 + the INV-PII-3 S8-half (docs/11, docs/54 §S8;
router/TESTPLAN.md).

Conventions per the merged suites: real Config over fixture dirs, real tmp-path Ledger,
A11 ``FakeProvider`` as every transport (no network — INV-TEST-SAFE), typed fail-closed
errors via ``pytest.raises``, INV mapping in docstrings, seeded failure-mask property test.
"""

from __future__ import annotations

import random

import pytest

from charterhouse.config import UnknownRole
from charterhouse.contracts.config_types import Provider
from charterhouse.contracts.events import EventType
from charterhouse.ledger import EventFilter
from charterhouse.router import (
    Context,
    NoEligibleModel,
    PIIRouteBlocked,
    ProvidersExhausted,
    Require,
)
from charterhouse.router.adapters import (
    AnthropicAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
)
from charterhouse.router.adapters import anthropic as anthropic_shim
from charterhouse.router.adapters import gemini as gemini_shim

from tests.fakes import FakeProvider, ProviderError
from tests.unit import _a6_support as sup
from tests.unit._a6_support import USER_MSG


# --- INV-ROUTE-1: role→model from Config only --------------------------------------------------


def test_role_resolved_from_config_only(tmp_path):
    """INV-ROUTE-1 (docs/54 §S8): the same call under two profiles resolves different
    models — the routing decision is config data, zero S8 code change."""
    free = sup.make_stack(tmp_path / "f", profile="free")
    cheap = sup.make_stack(tmp_path / "c", profile="cheap-cloud")
    a = free.router.call("reasoning", USER_MSG)
    b = cheap.router.call("reasoning", USER_MSG)
    assert a.model == "free-cloud-big"
    assert b.model == "claude-sonnet"


def test_unknown_role_propagates_config_error(tmp_path):
    """INV-ROUTE-1 fail-closed: an unknown role surfaces Config's typed error unchanged —
    the router holds no default/fallback role logic."""
    stack = sup.make_stack(tmp_path)
    with pytest.raises(UnknownRole):
        stack.router.call("no-such-role", USER_MSG)


# --- INV-ROUTE-2: deterministic failover → degrade → pause ------------------------------------


def test_failover_primary_down_uses_first_fallback(tmp_path):
    """INV-ROUTE-2: primary transport fails → the FIRST fallback (config order) answers."""
    stack = sup.make_stack(tmp_path, transports={
        "openrouter": FakeProvider(error=ProviderError("primary down"))})
    resp = stack.router.call("reasoning", USER_MSG)
    assert resp.model == "gemini-flash"  # first fallback, not local-small
    assert stack.transports["openrouter"].call_count == 1  # tried once, no retry loop


@pytest.mark.parametrize("seed", range(20))
def test_failover_order_deterministic_property(tmp_path, seed):
    """INV-ROUTE-2 (property): for random failure masks, the answering model equals the
    first healthy candidate in [primary, *fallback] order — independently recomputed."""
    chain = [("free-cloud-big", "openrouter"), ("gemini-flash", "gemini"),
             ("local-small", "ollama")]
    rng = random.Random(seed)
    failed = {pid for _mid, pid in chain if rng.random() < 0.5}
    transports = {pid: FakeProvider(error=ProviderError(f"{pid} down"))
                  for pid in failed}
    stack = sup.make_stack(tmp_path, transports=transports)
    expected = next((mid for mid, pid in chain if pid not in failed), None)
    if expected is None:
        with pytest.raises(ProvidersExhausted):
            stack.router.call("reasoning", USER_MSG)
    else:
        assert stack.router.call("reasoning", USER_MSG).model == expected


def test_exhaustion_degrades_to_local_free(tmp_path):
    """INV-ROUTE-2 degrade: the configured chain (critic: gemini-flash, free-cloud-big)
    all failing → the free/local catalog extension answers (local-small)."""
    stack = sup.make_stack(tmp_path, transports={
        "gemini": FakeProvider(error=ProviderError("down")),
        "openrouter": FakeProvider(error=ProviderError("down"))})
    resp = stack.router.call("critic", USER_MSG)
    assert resp.model == "local-small"  # not in the critic route; the degrade extension


def test_exhaustion_signals_pause(tmp_path):
    """INV-ROUTE-2 pause: configured chain AND degrade extension all down →
    ProvidersExhausted (the Conductor's pause signal) + an `error` event; no partial
    response."""
    stack = sup.make_stack(tmp_path, transports={
        "gemini": FakeProvider(error=ProviderError("down")),
        "openrouter": FakeProvider(error=ProviderError("down")),
        "ollama": FakeProvider(error=ProviderError("down"))})
    with pytest.raises(ProvidersExhausted):
        stack.router.call("critic", USER_MSG)
    errors = list(stack.ledger.read(EventFilter(type=EventType.ERROR)))
    assert len(errors) == 1 and errors[0].payload["fail_closed"] is True


# --- INV-ROUTE-3 / INV-PII-3: the S8 enforcement half ------------------------------------------


def test_pii_chain_excludes_cloud(tmp_path):
    """INV-ROUTE-3/INV-PII-3: a contains_pii call routes ONLY to local — the cloud
    transports are never called, and the exclusion is audited as a `pii_block` event."""
    stack = sup.make_stack(tmp_path)
    resp = stack.router.call("reasoning", USER_MSG,
                             require=Require(contains_pii=True))
    assert resp.model == "local-small"
    assert stack.transports["openrouter"].call_count == 0
    assert stack.transports["gemini"].call_count == 0
    assert stack.transports["anthropic"].call_count == 0
    blocks = list(stack.ledger.read(EventFilter(type=EventType.PII_BLOCK)))
    assert len(blocks) == 1
    assert "free-cloud-big" in blocks[0].payload["attempted_route"]


def test_pii_no_local_candidate_blocked(tmp_path):
    """INV-ROUTE-3 fail-closed: PII over an all-cloud catalog → PIIRouteBlocked with ZERO
    transport calls (nothing is ever sent), and the refusal is audited."""
    providers = {k: v for k, v in sup.PROVIDERS.items() if k != "ollama"}
    models = {k: v for k, v in sup.MODELS.items() if k != "local-small"}
    routes = {"reasoning": {"primary": "free-cloud-big", "fallback": ["gemini-flash"]}}
    stack = sup.make_stack(tmp_path, providers=providers, models=models, routes=routes)
    with pytest.raises(PIIRouteBlocked):
        stack.router.call("reasoning", USER_MSG, require=Require(contains_pii=True))
    assert all(t.call_count == 0 for t in stack.transports.values())
    blocks = list(stack.ledger.read(EventFilter(type=EventType.PII_BLOCK)))
    assert len(blocks) == 1


def test_cloud_adapter_hard_guard():
    """INV-PII-3 defense in depth: a CLOUD adapter called directly with a contains_pii
    Context refuses via the merged S7 guard BEFORE any transport call — independent of
    the chain filter."""
    transport = FakeProvider()
    adapter = OpenAICompatibleAdapter(
        Provider(base_url="https://api.example-cloud.test/v1",
                 key_env="EXAMPLE_KEY", kind="cloud"),
        transport)
    with pytest.raises(PIIRouteBlocked):
        adapter.complete("any-model", USER_MSG,
                         context=Context(text="tagged", contains_pii=True))
    assert transport.call_count == 0


def test_local_adapter_accepts_pii():
    """INV-ROUTE-3 complement: the local adapter completes a contains_pii context —
    local execution is the PII-legal path (docs/24)."""
    adapter = OpenAICompatibleAdapter(
        Provider(base_url="http://localhost:11434/v1", key_env="OLLAMA_HOST",
                 kind="local"),
        FakeProvider(canned="local answer"))
    raw = adapter.complete("local-small", USER_MSG,
                           context=Context(text="tagged", contains_pii=True))
    assert raw["text"] == "local answer"


# --- budget guard ------------------------------------------------------------------------------


def test_budget_80pct_drops_paid_tier(tmp_path):
    """docs/14 auto-degrade: at ≥80% of monthly_usd the paid primary is skipped (free
    fallback answers); under the threshold the paid primary is used."""
    over = sup.make_stack(tmp_path / "over", profile="cheap-cloud",
                          spent_usd=lambda: 16.0)  # 80% of 20.0
    assert over.router.call("reasoning", USER_MSG).model == "free-cloud-big"
    under = sup.make_stack(tmp_path / "under", profile="cheap-cloud",
                           spent_usd=lambda: 15.99)
    assert under.router.call("reasoning", USER_MSG).model == "claude-sonnet"


def test_budget_fold_from_ledger(tmp_path):
    """The default spend fold sums llm_call cost_usd from the ledger; un-timestamped
    events count (conservative — degrade early, never overspend)."""
    from charterhouse.logging import Telemetry
    from charterhouse.router.budget import month_spend

    stack = sup.make_stack(tmp_path)
    tele = Telemetry(stack.ledger)
    for cost in (1.5, 2.25, 0.25):
        tele.record({"role": "reasoning", "model": "m", "provider": "p",
                     "tokens": {"in": 10, "out": 10}, "cost_usd": cost,
                     "latency_ms": 1})
    assert month_spend(stack.ledger) == pytest.approx(4.0)


# --- INV-ROUTE-4: telemetry --------------------------------------------------------------------


def test_telemetry_llm_call_every_success(tmp_path):
    """INV-ROUTE-4: every successful call appends exactly one llm_call event carrying
    role/model/provider/tokens/cost/latency; cost_usd = tokens × catalog prices; the
    critic_tier kwarg is stamped through."""
    stack = sup.make_stack(tmp_path, profile="cheap-cloud")
    resp = stack.router.call("reasoning", USER_MSG, critic_tier=2)
    (event,) = list(stack.ledger.read(EventFilter(type=EventType.LLM_CALL)))
    p = event.payload
    assert p["role"] == "reasoning" and p["model"] == "claude-sonnet"
    assert p["provider"] == "anthropic" and p["critic_tier"] == 2
    expected_cost = (p["tokens"]["in"] / 1e6) * 3.0 + (p["tokens"]["out"] / 1e6) * 15.0
    assert p["cost_usd"] == pytest.approx(expected_cost)
    assert resp.cost_usd == pytest.approx(expected_cost)
    assert resp.critic_tier == 2
    # A second call → a second event (one per call, always).
    stack.router.call("draft", USER_MSG)
    assert len(list(stack.ledger.read(EventFilter(type=EventType.LLM_CALL)))) == 2


# --- constraint merging ------------------------------------------------------------------------


def test_min_ctx_and_capability_filters(tmp_path):
    """Require merging: min_ctx drops small-ctx candidates; needs_web keeps only
    web-capable models; an emptied non-PII chain raises NoEligibleModel."""
    stack = sup.make_stack(tmp_path)
    big = stack.router.call("reasoning", USER_MSG, require=Require(min_ctx=500_000))
    assert big.model == "gemini-flash"  # the only ≥500k-ctx candidate
    web = stack.router.call("reasoning", USER_MSG, require=Require(needs_web=True))
    assert web.model == "gemini-flash"  # the only web-capable candidate
    with pytest.raises(NoEligibleModel):
        stack.router.call("reasoning", USER_MSG, require=Require(min_ctx=5_000_000))


# --- adapter normalization ---------------------------------------------------------------------


def test_response_normalized_across_adapters():
    """docs/11 "never leak": the same transport result through OpenAI-compat, Anthropic,
    and Gemini adapters yields the identical RawResult shape."""
    results = []
    for cls, kind in ((OpenAICompatibleAdapter, "cloud"), (AnthropicAdapter, "cloud"),
                      (GeminiAdapter, "cloud")):
        adapter = cls(Provider(base_url="https://x.test", key_env="K", kind=kind),
                      FakeProvider(canned="same-answer"))
        results.append(adapter.complete("m", USER_MSG, context=Context(text="")))
    assert all(r["text"] == "same-answer" for r in results)
    assert all(set(r) == {"text", "tokens", "latency_ms", "tool_calls"} for r in results)
    # Shape parity, not count equality: token counts legitimately come from the provider
    # (the fake derives them from payload length, which differs after shim translation).
    assert all(set(r["tokens"]) == {"in", "out"} for r in results)
    assert all(isinstance(v, int) for r in results for v in r["tokens"].values())


def test_anthropic_gemini_translation_pure():
    """The shims' translation functions are pure and round-trip provider shapes."""
    messages = [{"role": "system", "content": "be brief"},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"}]
    a_req = anthropic_shim.to_provider_request(messages)
    assert a_req["system"] == "be brief"
    assert [m["role"] for m in a_req["messages"]] == ["user", "assistant"]
    a_raw = anthropic_shim.from_provider_response(
        {"content": [{"type": "text", "text": "claude says"}],
         "usage": {"input_tokens": 7, "output_tokens": 3}})
    assert a_raw["text"] == "claude says" and a_raw["tokens"] == {"in": 7, "out": 3}
    g_req = gemini_shim.to_provider_request(messages)
    assert g_req["systemInstruction"] == "be brief"
    assert [c["role"] for c in g_req["contents"]] == ["user", "model"]
    assert g_req["contents"][0]["parts"] == [{"text": "hi"}]
    g_raw = gemini_shim.from_provider_response(
        {"candidates": [{"content": {"parts": [{"text": "gemini says"}]}}],
         "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3}})
    assert g_raw["text"] == "gemini says" and g_raw["tokens"] == {"in": 7, "out": 3}


# --- RISKS R9 retirement (feat/a2-accessors) ----------------------------------------------


def test_degrade_uses_public_models_accessor():
    """Router RISKS R9 retired: the degrade extension reads the additive
    ``Config.models()`` seam — no module under router/ reaches into Config internals
    (``config._``) and the interim ``_catalog_ids`` shim is gone."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "charterhouse" / "router"
    offenders = []
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "config._" in text or "_catalog_ids" in text:
            offenders.append(py.name)
    assert not offenders, f"private Config reach still present in: {offenders}"
