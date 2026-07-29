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


def test_local_adapter_has_no_guard_and_sends():
    """Local execution is the PII-legal path: a local adapter carries no guard, so even a
    tagged context reaches the local transport (INV-ROUTE-3 = PII to LOCAL only)."""
    provider = Provider(base_url="http://localhost:11434/v1", key_env="", kind="local")
    fake = FakeSend(OPENAI_RESP)
    OpenAICompatibleAdapter(provider, HttpOpenAITransport(
        provider.base_url, None, None, send=fake)).complete(
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


def test_build_transports_wires_the_committed_providers():
    config = Config.load(REPO_CONFIG, "free")
    transports = build_transports(config, env_key_lookup(
        {"GROQ_API_KEY": GROQ, "GEMINI_API_KEY": GEMINI, "OPENROUTER_API_KEY": "or55555"}))
    assert isinstance(transports["groq"], HttpOpenAITransport)
    assert isinstance(transports["gemini"], HttpGeminiTransport)
    assert isinstance(transports["ollama"], HttpOpenAITransport)


def test_committed_free_profile_hits_real_provider_endpoints():
    """The free-profile model ids ARE each provider's real API model string, and the wired
    transports resolve to the providers' real endpoints (send a fake — zero network)."""
    config = Config.load(REPO_CONFIG, "free")
    # The model id sent to the provider is the real API string (not an internal alias).
    assert config.get_route("reasoning").primary == "llama-3.3-70b-versatile"  # Groq's real id
    assert config.get_model("llama-3.3-70b-versatile").provider == "groq"
    assert config.get_route("critic").primary == "gemini-2.0-flash"  # Gemini's real id
    assert config.get_model("gemini-2.0-flash").provider == "gemini"
    # The local roles carry Ollama's real model string (name:tag), not an internal alias.
    assert config.get_route("classify").primary == "llama3.1:8b"
    assert config.get_route("draft").primary == "llama3.1:8b"
    assert config.get_model("llama3.1:8b").provider == "ollama"

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
