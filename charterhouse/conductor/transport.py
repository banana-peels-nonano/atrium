"""Real HTTP model transports — the wiring-layer HTTP client the Router's adapters wrap
(router IMPLEMENTATION §6.1: composed at wiring time, never inside S8). Two shapes matching
the two adapter families:

- ``HttpOpenAITransport`` — Groq / OpenRouter / any OpenAI-shaped local server, e.g. LM
  Studio / vLLM (OpenAI ``/chat/completions``). The OpenAI-compatible adapter is a
  pass-through, so THIS parses ``choices``/``usage`` into the RawResult shape
  ``{text, tokens:{in,out}, latency_ms, tool_calls}``.
- ``HttpOllamaTransport`` — the local Ollama chat path, on Ollama's **native**
  ``/api/chat``. Native (not the OpenAI-compat endpoint) because ``keep_alive`` is not an
  accepted field there, and ``keep_alive: 0`` is what makes Ollama unload the model the
  moment the response completes — zero VRAM held while the factory is idle. Same
  ``complete`` signature + RawResult contract as the OpenAI transport, so the local
  provider's OpenAI-compat adapter wraps it unchanged.
- ``HttpGeminiTransport`` — the Gemini shim's native ``generateContent``. Returns the raw
  Gemini JSON (``candidates``/``usageMetadata``) with ``latency_ms`` injected, for the
  adapter's ``from_provider_response`` to normalize (do NOT parse it here).

Keys: read via the injected ``key_lookup(name)`` (A1 env seam) at call time; placed only in
the auth header; NEVER logged, NEVER in an exception message or event payload. No environment
read here (docs/20). Cloud PII enforcement is the adapter's ``_guard``, which runs BEFORE
``complete`` — a ``contains_pii`` context never reaches this layer.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

from charterhouse.contracts.config_types import Provider

__all__ = ["HttpOpenAITransport", "HttpOllamaTransport", "HttpGeminiTransport",
           "TransportError", "build_transports"]

_TIMEOUT_S = 60.0
# Ollama duration semantics: 0 = unload the model as soon as the response completes
# (-1 would pin it in memory forever, the default is 5 minutes). Local calls therefore
# pay a reload from disk each time — the deliberate trade for zero idle VRAM.
_UNLOAD_IMMEDIATELY = 0
# An explicit User-Agent on every request — urllib's default ("Python-urllib/x.y") is
# edge-blocked by some cloud providers (Groq via Cloudflare 1010). Not a secret.
USER_AGENT = "charterhouse/1.0"


class TransportError(Exception):
    """An HTTP/transport failure. The message names the model + error KIND only — never the
    key, never the URL (which could echo a key), never the response body (fail closed)."""


def _http_post(url: str, headers: Mapping[str, str], body: dict,
               timeout: float) -> dict:  # pragma: no cover — real network, live smoke only
    """The default real sender: POST JSON, return parsed JSON. Injectable seam (tests pass
    a fake) so the transport logic is exercised with zero network (INV-TEST-SAFE)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", **dict(headers)})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — HTTPS only
        return json.loads(resp.read().decode("utf-8"))


class HttpOpenAITransport:
    """OpenAI-shaped ``/chat/completions`` transport (Groq, OpenRouter, local Ollama)."""

    def __init__(self, base_url: str, key_lookup: Callable[[str], str] | None = None,
                 key_env: str | None = None, *, send: Callable | None = None,
                 timeout: float = _TIMEOUT_S) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key_lookup = key_lookup
        self._key_env = key_env
        self._send = send if send is not None else _http_post
        self._timeout = timeout

    def _auth_headers(self) -> dict:
        """The auth header, or none for a keyless local endpoint. The secret is read by
        name at call time and never logged."""
        if not self._key_env or self._key_lookup is None:
            return {}
        key = self._key_lookup(self._key_env)  # MissingEnvVar propagates BEFORE any send
        return {"Authorization": "Bearer " + key}

    def complete(self, model: str, messages: list, tools: list | None = None,
                 max_tokens: int | None = None) -> dict:
        headers = {"User-Agent": USER_AGENT, **self._auth_headers()}  # UA before send
        body: dict = {"model": model, "messages": messages}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        start = time.monotonic()
        try:
            raw = self._send(self._url, headers, body, self._timeout)
        except Exception as exc:  # names the model + error KIND only — never key/url/body
            raise TransportError(f"{model}: {type(exc).__name__}") from None
        latency_ms = int((time.monotonic() - start) * 1000)
        choice = (raw.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        usage = raw.get("usage") or {}
        return {"text": text,
                "tokens": {"in": int(usage.get("prompt_tokens", 0)),
                           "out": int(usage.get("completion_tokens", 0))},
                "latency_ms": latency_ms,
                "tool_calls": ()}


class HttpOllamaTransport:
    """Local Ollama chat transport on the NATIVE ``/api/chat`` endpoint.

    Why native rather than Ollama's OpenAI-compatible ``/chat/completions``: that endpoint's
    accepted-field list has no ``keep_alive``, so the field would be silently dropped and the
    model would sit in VRAM for the default 5 minutes after every call. The native endpoint
    honours it, so each call carries ``keep_alive: 0`` and the model unloads immediately.

    Keyless by construction (loopback); returns the same RawResult shape as
    ``HttpOpenAITransport`` so the local provider's adapter needs no change.
    """

    def __init__(self, base_url: str, *, send: Callable | None = None,
                 timeout: float = _TIMEOUT_S) -> None:
        # providers.yaml carries the OpenAI-compat base (…:11434/v1); the native API lives
        # one level up at …:11434/api/chat. str.removesuffix, never regex — conductor/ is
        # scanned for re.compile by the INV-COND-1 static test.
        self._url = base_url.rstrip("/").removesuffix("/v1") + "/api/chat"
        self._send = send if send is not None else _http_post
        self._timeout = timeout

    def complete(self, model: str, messages: list, tools: list | None = None,
                 max_tokens: int | None = None) -> dict:
        headers = {"User-Agent": USER_AGENT}  # no auth header: loopback, keyless
        body: dict = {"model": model, "messages": messages,
                      # native /api/chat streams NDJSON unless told otherwise — the sender
                      # parses one JSON object, so streaming must be off.
                      "stream": False,
                      "keep_alive": _UNLOAD_IMMEDIATELY}
        if max_tokens is not None:
            body["options"] = {"num_predict": max_tokens}  # native name for max_tokens
        start = time.monotonic()
        try:
            raw = self._send(self._url, headers, body, self._timeout)
        except Exception as exc:  # names the model + error KIND only — never url/body
            raise TransportError(f"{model}: {type(exc).__name__}") from None
        latency_ms = int((time.monotonic() - start) * 1000)
        # Native counts; either may be absent (a fully cached prompt omits prompt_eval_count).
        return {"text": (raw.get("message") or {}).get("content") or "",
                "tokens": {"in": int(raw.get("prompt_eval_count", 0)),
                           "out": int(raw.get("eval_count", 0))},
                "latency_ms": latency_ms,
                "tool_calls": ()}


class HttpGeminiTransport:
    """Gemini native ``generateContent`` transport (the shim path)."""

    def __init__(self, base_url: str, key_lookup: Callable[[str], str],
                 key_env: str, *, send: Callable | None = None,
                 timeout: float = _TIMEOUT_S) -> None:
        # providers.yaml carries the native Gemini base (.../v1beta); the shim hits
        # .../v1beta/models/{model}:generateContent. A trailing /openai (Google's OpenAI-
        # compat base) is also tolerated via removesuffix (str, never regex — conductor/
        # is scanned for re.compile by the INV-COND-1 static test).
        self._base = base_url.rstrip("/").removesuffix("/openai")
        self._key_lookup = key_lookup
        self._key_env = key_env
        self._send = send if send is not None else _http_post
        self._timeout = timeout

    def complete(self, model: str, contents: list, tools: list | None = None,
                 max_tokens: int | None = None) -> dict:
        key = self._key_lookup(self._key_env)  # by name; never logged
        headers = {"User-Agent": USER_AGENT, "x-goog-api-key": key}
        body: dict = {"contents": contents}
        if max_tokens is not None:
            body["generationConfig"] = {"maxOutputTokens": max_tokens}
        url = f"{self._base}/models/{model}:generateContent"
        start = time.monotonic()
        try:
            raw = self._send(url, headers, body, self._timeout)
        except Exception as exc:
            raise TransportError(f"{model}: {type(exc).__name__}") from None
        raw = dict(raw)  # raw Gemini JSON (candidates/usageMetadata) for the adapter
        raw["latency_ms"] = int((time.monotonic() - start) * 1000)
        return raw


# provider ids that use a non-OpenAI transport shape (mirrors the router's shim registry).
_SHIM_TRANSPORTS = {"gemini": HttpGeminiTransport}


def build_transports(config, key_lookup: Callable[[str], str],  # noqa: ANN001
                     provider_ids=None, *, send: Callable | None = None) -> dict:
    """Compose the router's real transports dict ``{provider_id: transport}`` from Config
    (base_url/key_env NAMES only) + the injected ``key_lookup`` for secrets. ``gemini`` gets
    the native shim transport; ``ollama`` gets the native keep_alive transport; any OTHER
    local provider (``kind == "local"`` — LM Studio, vLLM) gets the OpenAI-compat transport
    without an auth header. Keyed on the provider id, not on ``kind``: "local" does not imply
    "speaks Ollama's native API". ``send`` is the injectable HTTP sender (tests pass a fake; the smoke's ``--debug`` passes
    a logging wrapper) — ``None`` uses each transport's real ``urllib`` default."""
    ids = (provider_ids if provider_ids is not None
           else {config.get_model(mid).provider for mid in config.models()})
    transports: dict = {}
    for pid in ids:
        provider: Provider = config.get_provider(pid)
        shim = _SHIM_TRANSPORTS.get(pid)
        if pid == "ollama":
            transports[pid] = HttpOllamaTransport(provider.base_url, send=send)  # keyless
        elif shim is not None:
            transports[pid] = shim(provider.base_url, key_lookup, provider.key_env,
                                   send=send)
        elif provider.kind == "local":
            transports[pid] = HttpOpenAITransport(provider.base_url, send=send)  # keyless
        else:
            transports[pid] = HttpOpenAITransport(
                provider.base_url, key_lookup, provider.key_env, send=send)
    return transports
