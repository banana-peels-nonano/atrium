"""Real HTTP transports (charterhouse/conductor/transport.py) — request build, response
parse, key handling, and the INV-PII-3 boundary, all with a fake ``send`` (zero network,
INV-TEST-SAFE). Fake key values are < 12 chars so the secret-scan gate stays quiet; they
are test tokens, never real credentials.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.conductor.transport import (
    HttpGeminiTransport,
    HttpOllamaTransport,
    HttpOpenAITransport,
    TransportError,
    build_transports,
)
from charterhouse.config import Config
from charterhouse.contracts.config_types import Provider
from charterhouse.env import env_key_lookup
from charterhouse.env.types import MissingEnvVar
from charterhouse.router.adapters.gemini import GeminiAdapter
from charterhouse.router.adapters.openai_compat import OpenAICompatibleAdapter
from charterhouse.security.types import Context, PIIRouteBlocked

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"
GROQ = "grq99999"   # < 12 chars — a test token, not a credential
GEMINI = "gmi88888"

OPENAI_RESP = {"choices": [{"message": {"content": "hello there"}}],
               "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
GEMINI_RESP = {"candidates": [{"content": {"parts": [{"text": "hi back"}]}}],
               "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 3}}
# Ollama's NATIVE /api/chat response (not the OpenAI-compat shape).
OLLAMA_RESP = {"model": "llama3.1:8b", "done": True,
               "message": {"role": "assistant", "content": "hello there"},
               "prompt_eval_count": 5, "eval_count": 2}


class FakeSend:
    """Records each (url, headers, body) and returns a canned provider payload — or raises
    a programmed error. The stand-in for the real urllib POST; counts sends."""

    def __init__(self, response: dict, *, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict] = []

    def __call__(self, url, headers, body, timeout):  # noqa: ANN001
        self.calls.append({"url": url, "headers": dict(headers), "body": body})
        if self._error is not None:
            raise self._error
        return self._response

    @property
    def count(self) -> int:
        return len(self.calls)


# --- OpenAI-compatible transport (Groq / OpenRouter / local Ollama) -----------------------


def test_openai_builds_request_and_parses_rawresult():
    fake = FakeSend(OPENAI_RESP)
    t = HttpOpenAITransport("https://api.groq.com/openai/v1",
                            env_key_lookup({"GROQ_API_KEY": GROQ}), "GROQ_API_KEY",
                            send=fake)
    raw = t.complete("llama-3.3-70b-versatile", [{"role": "user", "content": "hi"}], None, 128)
    call = fake.calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer " + GROQ
    assert call["body"]["model"] == "llama-3.3-70b-versatile"
    assert call["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert call["body"]["max_tokens"] == 128
    assert raw["text"] == "hello there"
    assert raw["tokens"] == {"in": 5, "out": 2}
    assert isinstance(raw["latency_ms"], int)
    assert raw["tool_calls"] == ()


def test_openai_local_provider_sends_no_auth_header():
    fake = FakeSend(OPENAI_RESP)
    t = HttpOpenAITransport("http://localhost:11434/v1", None, None, send=fake)
    t.complete("llama3.1:8b", [{"role": "user", "content": "hi"}])
    assert "Authorization" not in fake.calls[0]["headers"]


def test_openai_missing_key_refuses_before_any_send():
    fake = FakeSend(OPENAI_RESP)
    t = HttpOpenAITransport("https://api.groq.com/openai/v1",
                            env_key_lookup({}), "GROQ_API_KEY", send=fake)
    with pytest.raises(MissingEnvVar):
        t.complete("llama-3.3-70b-versatile", [{"role": "user", "content": "hi"}])
    assert fake.count == 0  # no key => nothing leaves the process


def test_openai_send_failure_omits_key_and_url():
    fake = FakeSend(OPENAI_RESP, error=RuntimeError(f"network detail {GROQ} api.groq.com"))
    t = HttpOpenAITransport("https://api.groq.com/openai/v1",
                            env_key_lookup({"GROQ_API_KEY": GROQ}), "GROQ_API_KEY",
                            send=fake)
    with pytest.raises(TransportError) as exc:
        t.complete("llama-3.3-70b-versatile", [{"role": "user", "content": "x"}])
    msg = str(exc.value)
    assert GROQ not in msg and "api.groq.com" not in msg
    assert "llama-3.3-70b-versatile" in msg  # the model is named; the detail is not


def test_openai_through_adapter_normalizes():
    provider = Provider(base_url="https://api.groq.com/openai/v1",
                        key_env="GROQ_API_KEY", kind="cloud")
    t = HttpOpenAITransport(provider.base_url, env_key_lookup({"GROQ_API_KEY": GROQ}),
                            "GROQ_API_KEY", send=FakeSend(OPENAI_RESP))
    out = OpenAICompatibleAdapter(provider, t).complete(
        "llama-3.3-70b-versatile", [{"role": "user", "content": "hi"}], context=Context(text=""))
    assert out["text"] == "hello there" and out["tokens"] == {"in": 5, "out": 2}


# --- Local Ollama transport (NATIVE /api/chat — the keep_alive path) ----------------------


def test_ollama_native_transport_builds_request_and_parses_rawresult():
    """The local transport speaks Ollama's NATIVE /api/chat (the OpenAI-compat endpoint
    does not accept keep_alive), parsing message/eval counts into the RawResult shape."""
    fake = FakeSend(OLLAMA_RESP)
    t = HttpOllamaTransport("http://localhost:11434/v1", send=fake)
    raw = t.complete("llama3.1:8b", [{"role": "user", "content": "hi"}], None, 128)
    call = fake.calls[0]
    assert call["url"] == "http://localhost:11434/api/chat"  # /v1 stripped
    assert call["body"]["model"] == "llama3.1:8b"
    assert call["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert call["body"]["stream"] is False  # native default is NDJSON streaming
    assert call["body"]["options"] == {"num_predict": 128}  # max_tokens' native name
    assert "Authorization" not in call["headers"]  # loopback, keyless
    assert raw["text"] == "hello there"
    assert raw["tokens"] == {"in": 5, "out": 2}
    assert isinstance(raw["latency_ms"], int)
    assert raw["tool_calls"] == ()


def test_ollama_transport_requests_immediate_unload():
    """VRAM discipline: every local call carries keep_alive=0, so Ollama unloads the model
    the moment the response completes — zero VRAM held while the factory is idle."""
    fake = FakeSend(OLLAMA_RESP)
    t = HttpOllamaTransport("http://localhost:11434/v1", send=fake)
    t.complete("llama3.1:8b", [{"role": "user", "content": "hi"}])
    assert fake.calls[0]["body"]["keep_alive"] == 0
    assert "options" not in fake.calls[0]["body"]  # no max_tokens => no options block
    t.complete("llama3.1:8b", [{"role": "user", "content": "again"}], None, 64)
    assert fake.calls[1]["body"]["keep_alive"] == 0  # every call, not just the first


def test_ollama_transport_tolerates_absent_token_counts():
    """A cached prompt omits prompt_eval_count — parse defensively, never KeyError."""
    fake = FakeSend({"message": {"content": "ok"}, "done": True})
    raw = HttpOllamaTransport("http://localhost:11434/v1", send=fake).complete("m", [])
    assert raw["text"] == "ok" and raw["tokens"] == {"in": 0, "out": 0}


def test_ollama_transport_send_failure_names_model_only():
    fake = FakeSend(OLLAMA_RESP, error=RuntimeError("connection refused 127.0.0.1:11434"))
    with pytest.raises(TransportError) as exc:
        HttpOllamaTransport("http://localhost:11434/v1", send=fake).complete(
            "llama3.1:8b", [{"role": "user", "content": "x"}])
    msg = str(exc.value)
    assert "llama3.1:8b" in msg and "127.0.0.1" not in msg


def test_ollama_transport_through_adapter_normalizes():
    """The local provider's OpenAI-compat adapter wraps this transport unchanged — the
    RawResult contract (docs/40 §5) is what the adapter normalizes."""
    provider = Provider(base_url="http://localhost:11434/v1", key_env="", kind="local")
    t = HttpOllamaTransport(provider.base_url, send=FakeSend(OLLAMA_RESP))
    out = OpenAICompatibleAdapter(provider, t).complete(
        "llama3.1:8b", [{"role": "user", "content": "hi"}], context=Context(text=""))
    assert out["text"] == "hello there" and out["tokens"] == {"in": 5, "out": 2}
    assert out["tool_calls"] == ()


def test_cloud_requests_carry_no_keep_alive():
    """keep_alive is an Ollama-only field: it must never appear in a cloud request body
    (Groq/Gemini reject unknown fields — a leak would 400 the whole free profile)."""
    groq = FakeSend(OPENAI_RESP)
    HttpOpenAITransport("https://api.groq.com/openai/v1",
                        env_key_lookup({"GROQ_API_KEY": GROQ}), "GROQ_API_KEY",
                        send=groq).complete("m", [{"role": "user", "content": "hi"}], None, 64)
    assert "keep_alive" not in groq.calls[0]["body"]
    gem = FakeSend(GEMINI_RESP)
    HttpGeminiTransport("https://generativelanguage.googleapis.com/v1beta",
                        env_key_lookup({"GEMINI_API_KEY": GEMINI}), "GEMINI_API_KEY",
                        send=gem).complete("m", [{"role": "user", "parts": [{"text": "hi"}]}])
    assert "keep_alive" not in gem.calls[0]["body"]


# --- Gemini native transport (the shim path) ----------------------------------------------


def test_gemini_uses_native_endpoint_and_returns_raw():
    fake = FakeSend(GEMINI_RESP)
    t = HttpGeminiTransport("https://generativelanguage.googleapis.com/v1beta/openai",
                            env_key_lookup({"GEMINI_API_KEY": GEMINI}), "GEMINI_API_KEY",
                            send=fake)
    contents = [{"role": "user", "parts": [{"text": "hi"}]}]
    raw = t.complete("gemini-2.0-flash", contents)
    call = fake.calls[0]
    # /openai stripped — the shim hits the native generateContent endpoint.
    assert call["url"] == ("https://generativelanguage.googleapis.com/v1beta/"
                           "models/gemini-2.0-flash:generateContent")
    assert call["headers"]["x-goog-api-key"] == GEMINI
    assert "Authorization" not in call["headers"]
    assert call["body"]["contents"] == contents
    assert "candidates" in raw  # returned raw for the adapter to normalize
    assert isinstance(raw["latency_ms"], int)


def test_gemini_through_adapter_normalizes():
    provider = Provider(base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                        key_env="GEMINI_API_KEY", kind="cloud")
    t = HttpGeminiTransport(provider.base_url, env_key_lookup({"GEMINI_API_KEY": GEMINI}),
                            "GEMINI_API_KEY", send=FakeSend(GEMINI_RESP))
    out = GeminiAdapter(provider, t).complete(
        "gemini-2.0-flash", [{"role": "user", "content": "hi"}], context=Context(text=""))
    assert out["text"] == "hi back" and out["tokens"] == {"in": 4, "out": 3}
    assert out["tool_calls"] == ()


# --- INV-PII-3: a PII context never reaches the transport ---------------------------------


@pytest.mark.parametrize("kind", ["openai", "gemini"])
def test_pii_context_never_reaches_cloud_transport(kind):
    """The cloud adapter's guard hard-stops a ``contains_pii`` context BEFORE any send —
    the transport (the only thing that egresses) is never invoked."""
    provider = Provider(base_url="https://api.example/v1", key_env="X_KEY", kind="cloud")
    lookup = env_key_lookup({"X_KEY": "xk777"})
    if kind == "openai":
        fake = FakeSend(OPENAI_RESP)
        adapter = OpenAICompatibleAdapter(provider, HttpOpenAITransport(
            provider.base_url, lookup, "X_KEY", send=fake))
    else:
        fake = FakeSend(GEMINI_RESP)
        adapter = GeminiAdapter(provider, HttpGeminiTransport(
            provider.base_url, lookup, "X_KEY", send=fake))
    with pytest.raises(PIIRouteBlocked):
        adapter.complete("m", [{"role": "user", "content": "x"}],
                         context=Context(text="pii here", contains_pii=True))
    assert fake.count == 0  # zero egress — the guard fired first


@pytest.mark.parametrize("cls,resp", [(HttpOllamaTransport, OLLAMA_RESP),
                                      (HttpOpenAITransport, OPENAI_RESP)])
def test_local_adapter_has_no_guard_and_sends(cls, resp):
    """Local execution is the PII-legal path: a local adapter carries no guard, so even a
    tagged context reaches the local transport (INV-ROUTE-3 = PII to LOCAL only). Covers
    BOTH local shapes — the native Ollama transport production wires, and the OpenAI-compat
    one any other local server (LM Studio / vLLM) uses."""
    provider = Provider(base_url="http://localhost:11434/v1", key_env="", kind="local")
    fake = FakeSend(resp)
    transport = (cls(provider.base_url, send=fake) if cls is HttpOllamaTransport
                 else cls(provider.base_url, None, None, send=fake))
    OpenAICompatibleAdapter(provider, transport).complete(
        "llama3.1:8b", [{"role": "user", "content": "x"}],
        context=Context(text="pii here", contains_pii=True))
    assert fake.count == 1


# --- wiring ---------------------------------------------------------------------------------


def test_requests_carry_a_user_agent():
    """Every request sends an explicit User-Agent (charterhouse/1.0) — urllib's default UA
    is edge-blocked by some cloud providers (Groq via Cloudflare 1010)."""
    fake = FakeSend(OPENAI_RESP)
    HttpOpenAITransport("https://api.groq.com/openai/v1",
                        env_key_lookup({"GROQ_API_KEY": GROQ}), "GROQ_API_KEY",
                        send=fake).complete("m", [{"role": "user", "content": "hi"}])
    assert fake.calls[0]["headers"]["User-Agent"] == "charterhouse/1.0"
    fake2 = FakeSend(GEMINI_RESP)
    HttpGeminiTransport("https://generativelanguage.googleapis.com/v1beta",
                        env_key_lookup({"GEMINI_API_KEY": GEMINI}), "GEMINI_API_KEY",
                        send=fake2).complete("m", [{"role": "user", "parts": [{"text": "hi"}]}])
    assert fake2.calls[0]["headers"]["User-Agent"] == "charterhouse/1.0"
    fake3 = FakeSend(OLLAMA_RESP)
    HttpOllamaTransport("http://localhost:11434/v1", send=fake3).complete("m", [])
    assert fake3.calls[0]["headers"]["User-Agent"] == "charterhouse/1.0"


def test_build_transports_wires_the_committed_providers():
    config = Config.load(REPO_CONFIG, "free")
    transports = build_transports(config, env_key_lookup(
        {"GROQ_API_KEY": GROQ, "GEMINI_API_KEY": GEMINI, "OPENROUTER_API_KEY": "or55555"}))
    assert isinstance(transports["groq"], HttpOpenAITransport)
    assert isinstance(transports["gemini"], HttpGeminiTransport)
    # ollama gets the NATIVE transport (keep_alive); a non-Ollama local server would still
    # get the OpenAI-compat one — the branch is keyed on the provider id, not on kind.
    assert isinstance(transports["ollama"], HttpOllamaTransport)
    assert not isinstance(transports["ollama"], HttpOpenAITransport)


def test_pii_reasoning_degrades_to_the_native_local_transport(tmp_path):
    """The PII path end-to-end through the REAL Router over the REAL built transports: a
    ``contains_pii`` reasoning call on the free profile is filtered off cloud (INV-PII-3),
    degrades to the catalog's local `llama3.1:8b`, and lands on Ollama's native endpoint
    with keep_alive=0 — the one live exercise the smoke's pii-block check gives this path."""
    from charterhouse.ledger import Ledger
    from charterhouse.router import Router
    from charterhouse.router.types import Require

    config = Config.load(REPO_CONFIG, "free")
    fake = FakeSend(OLLAMA_RESP)
    ts = build_transports(config, env_key_lookup(
        {"GROQ_API_KEY": GROQ, "GEMINI_API_KEY": GEMINI, "OPENROUTER_API_KEY": "or55555"}),
        send=fake)
    resp = Router(config, Ledger(tmp_path / "ledger"), transports=ts).call(
        "reasoning", [{"role": "user", "content": "hi"}], require=Require(contains_pii=True))
    assert resp.model == "llama3.1:8b"  # answered locally, never on Groq/Gemini
    assert [c["url"] for c in fake.calls] == ["http://localhost:11434/api/chat"]
    assert fake.calls[0]["body"]["keep_alive"] == 0


@pytest.mark.parametrize("role,model", [("classify", "llama3.1:8b"),
                                        ("draft", "llama3.1:8b"),
                                        ("critic", "qwen3:8b")])
def test_local_chat_goes_native_with_immediate_unload_end_to_end(role, model):
    """Every committed free-profile local role reaches Ollama's native endpoint with
    keep_alive=0 — wired, not just constructed."""
    config = Config.load(REPO_CONFIG, "free")
    fake = FakeSend(OLLAMA_RESP)
    ts = build_transports(config, env_key_lookup({}), send=fake)
    ts["ollama"].complete(config.get_route(role).primary,
                          [{"role": "user", "content": "hi"}])
    assert fake.calls[0]["url"] == "http://localhost:11434/api/chat"
    assert fake.calls[0]["body"]["model"] == model
    assert fake.calls[0]["body"]["keep_alive"] == 0


# --- free profile: zero Gemini dependency -------------------------------------------------

# The roles the v1 factory actually calls. `web` is configured but never invoked by any
# code path (nothing calls role "web") — see the web-role test below for its status.
LIVE_ROLES = ("reasoning", "classify", "draft", "critic")


def test_free_profile_live_roles_have_zero_gemini_dependency():
    """Gemini's free tier is provisioned at limit 0 for this account (a permanent 429), so
    no live free-profile role may depend on it — not as a primary, not as a fallback hop
    (a dead hop only burns a failover attempt before ProvidersExhausted)."""
    config = Config.load(REPO_CONFIG, "free")
    for role in LIVE_ROLES:
        route = config.get_route(role)
        for mid in (route.primary, *route.fallback):
            provider = config.get_model(mid).provider
            assert provider != "gemini", f"role {role!r} still depends on Gemini via {mid!r}"
            # Every candidate resolves to a provider proven working by the live smoke:
            # Groq (200 OK) or local Ollama.
            assert provider in ("groq", "ollama"), f"role {role!r}: {mid!r} on {provider!r}"


def test_free_profile_chains_never_offer_a_gemini_candidate():
    """Chain-level confirmation, stronger than the config-level check above: the router's
    free/local degrade extension APPENDS catalog models the route never names, so the real
    question is what the chain offers. For every live role, under both a plain and a
    contains_pii require, no candidate the router would try resolves to Gemini."""
    from charterhouse.router.chain import build_chain
    from charterhouse.router.types import Require

    config = Config.load(REPO_CONFIG, "free")
    for role in LIVE_ROLES:
        for require in (Require(), Require(contains_pii=True)):
            plan = build_chain(config, role, require, tier_ceiling="free")
            assert plan.candidates, f"role {role!r} resolves to no candidate at all"
            for mid in plan.candidates:
                assert config.get_model(mid).provider != "gemini", (
                    f"role {role!r} would try {mid!r} on Gemini")
    # Stronger still for the critic: every candidate is LOCAL, so a critique never leaves
    # the machine — no key, no quota, and no cloud egress on the verification path.
    critic = build_chain(config, "critic", Require(), tier_ceiling="free")
    assert [m for m in critic.candidates] == ["qwen3:8b", "llama3.1:8b"]
    assert all(config.get_provider(config.get_model(m).provider).kind == "local"
               for m in critic.candidates)


def test_free_profile_critic_is_local_and_cross_family():
    """INV-WF-2 tier 1 needs a critic of a DIFFERENT family than the producer. With Gemini
    cut, the critic is local qwen3:8b — family "qwen" vs the Groq producer's "llama"."""
    config = Config.load(REPO_CONFIG, "free")
    critic, reasoning = config.get_route("critic"), config.get_route("reasoning")
    assert critic.primary == "qwen3:8b"
    critic_model = config.get_model(critic.primary)
    assert critic_model.provider == "ollama"  # local: no key, no quota, no cloud dependency
    assert critic_model.family == "qwen"
    assert config.get_model(reasoning.primary).family == "llama"
    assert critic_model.family != config.get_model(reasoning.primary).family  # tier 1 holds
    # A local fallback is kept. It shares the producer's family, so a qwen3 failure degrades
    # the ladder to tier 2 (same-family, different model) rather than losing the critic.
    assert critic.fallback == ("llama3.1:8b",)
    assert config.get_model(critic.fallback[0]).provider == "ollama"
    assert config.get_model(critic.fallback[0]).family == "llama"


def test_local_first_profile_critic_is_cross_family_and_fully_local():
    """local-first is the max-privacy posture, so its critic must be local AND a different
    family from its local producers — with the dead OpenRouter fallback gone (that provider
    has no key and was dropped from the working set)."""
    config = Config.load(REPO_CONFIG, "local-first")
    critic = config.get_route("critic")
    producer_family = config.get_model(config.get_route("draft").primary).family
    assert config.get_model(critic.primary).family != producer_family  # tier 1 holds
    for mid in (critic.primary, *critic.fallback):
        model = config.get_model(mid)
        assert model.provider == "ollama", f"critic candidate {mid!r} is not local"
        assert model.provider != "openrouter"
    assert "deepseek-chat-free" not in (critic.primary, *critic.fallback)
    # Every role in this profile stays off the dead providers entirely.
    for role in ("reasoning", "classify", "draft", "critic"):
        route = config.get_route(role)
        for mid in (route.primary, *route.fallback):
            assert config.get_model(mid).provider in ("ollama", "groq")


def _load_smoke():
    """Load the non-gating smoke runner by path (scripts/ is not an importable package).
    Import-safe: the module body is imports + constants behind a __main__ guard."""
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts" / "smoke_transport.py"
    spec = importlib.util.spec_from_file_location("smoke_transport", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def test_smoke_derives_each_role_expectation_from_the_resolved_route():
    """The smoke pins the answering provider per role so a silent failover reads FAIL — but
    the expectation must come from the RESOLVED ROUTE, not a hardcoded provider, or a config
    reroute (Gemini critic → local qwen3:8b) turns a healthy run into a false FAIL."""
    smoke, path = _load_smoke()
    config = Config.load(REPO_CONFIG, "free")
    assert smoke.expected_provider(config, "reasoning") == "groq"
    assert smoke.expected_provider(config, "critic") == "ollama"  # follows the reroute
    assert smoke.expected_provider(config, "classify") == "ollama"
    # Labels name the interesting fact: WHICH VENDOR for a cloud role, WHICH MODEL for a
    # local one (the provider is always ollama, so the model id is what distinguishes).
    assert smoke.role_label(config, "reasoning") == "reasoning(Groq)"
    assert smoke.role_label(config, "critic") == "critic(qwen3)"
    assert smoke.role_label(config, "draft") == "draft(llama3.1)"
    # The old hardcoded expectation must be gone, not merely overridden.
    assert "critic(Gemini)" not in path.read_text(encoding="utf-8")


def test_smoke_pii_block_watches_every_cloud_transport():
    """The pii-block check's spy set is derived too: EVERY non-local wired transport is
    watched, so a newly added cloud provider cannot slip past the zero-egress proof."""
    smoke, _ = _load_smoke()
    config = Config.load(REPO_CONFIG, "free")
    transports = build_transports(config, env_key_lookup(
        {"GROQ_API_KEY": GROQ, "GEMINI_API_KEY": GEMINI, "OPENROUTER_API_KEY": "or55555"}))
    watched = smoke.cloud_provider_ids(config, transports)
    assert watched == ("gemini", "groq", "openrouter")  # every cloud provider, not a pair
    assert "ollama" not in watched  # local egress is legal under PII (INV-ROUTE-3)


def test_free_profile_web_role_is_the_last_gemini_dependency():
    """Honest limit: `web` still resolves to Gemini and CANNOT be de-Gemini'd in config —
    it is the only catalog model with web capability. Nothing calls role "web" in v1, so
    this is inert; it stays pinned here so adding a web-capable provider trips this test."""
    config = Config.load(REPO_CONFIG, "free")
    web = config.get_route("web")
    assert web.primary == "gemini-2.0-flash" and web.needs_web is True
    web_capable = [mid for mid in config.models() if "web" in config.get_model(mid).good_at]
    assert web_capable == ["gemini-2.0-flash"]  # no local/Groq alternative exists yet


def test_committed_free_profile_hits_real_provider_endpoints():
    """The free-profile model ids ARE each provider's real API model string, and the wired
    transports resolve to the providers' real endpoints (send a fake — zero network)."""
    config = Config.load(REPO_CONFIG, "free")
    # The model id sent to the provider is the real API string (not an internal alias).
    assert config.get_route("reasoning").primary == "llama-3.3-70b-versatile"  # Groq's real id
    assert config.get_model("llama-3.3-70b-versatile").provider == "groq"
    # The local roles carry Ollama's real model string (name:tag), not an internal alias.
    assert config.get_route("classify").primary == "llama3.1:8b"
    assert config.get_route("draft").primary == "llama3.1:8b"
    assert config.get_route("critic").primary == "qwen3:8b"  # local, cross-family
    assert config.get_model("llama3.1:8b").provider == "ollama"
    assert config.get_model("qwen3:8b").provider == "ollama"
    # Gemini's id/endpoint stay pinned: the model + transport remain wired for the other
    # profiles and for model portability, even though `free` no longer depends on them.
    assert config.get_model("gemini-2.0-flash").provider == "gemini"

    lookup = env_key_lookup({"GROQ_API_KEY": GROQ, "GEMINI_API_KEY": GEMINI,
                             "OPENROUTER_API_KEY": "or55555"})
    groq_send, gemini_send = FakeSend(OPENAI_RESP), FakeSend(GEMINI_RESP)

    def route(url, headers, body, timeout):  # dispatch by host — one fake per provider
        return (gemini_send if "generativelanguage" in url else groq_send)(
            url, headers, body, timeout)

    ts = build_transports(config, lookup, send=route)
    ts["groq"].complete("llama-3.3-70b-versatile", [{"role": "user", "content": "hi"}])
    ts["gemini"].complete("gemini-2.0-flash", [{"role": "user", "parts": [{"text": "hi"}]}])
    assert groq_send.calls[0]["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert gemini_send.calls[0]["url"] == ("https://generativelanguage.googleapis.com/"
                                           "v1beta/models/gemini-2.0-flash:generateContent")
