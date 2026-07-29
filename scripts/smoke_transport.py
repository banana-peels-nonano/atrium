"""Live transport smoke — the free profile, REAL network. NON-GATING (scripts/ is outside
pytest's testpaths, so this never runs in CI). Reports OK/FAIL per role only; never prints
keys or raw responses.

Checks:
  reasoning (Groq)  — one live call; the answering model MUST be Groq (pins the provider,
                      so a Groq outage that fails over to Gemini reads as FAIL, not OK).
  critic (Gemini)   — one live call; the answering model MUST be Gemini.
  embed (Ollama)    — one local embed returns a full-width vector.
  pii-block         — a contains_pii reasoning call makes ZERO cloud-transport sends.

Requires GROQ_API_KEY, GEMINI_API_KEY, OLLAMA_HOST in the environment + Ollama running with
the chat/embed models pulled. An unset key / unreachable endpoint is an ENV failure, not a
code defect — reported as such.

  Run:          uv run python scripts/smoke_transport.py
  Diagnose:     uv run python scripts/smoke_transport.py --debug

``--debug`` surfaces, per provider attempt, the endpoint URL, the model id being sent, and
the HTTP status + response body (so a swallowed ProvidersExhausted shows its real cause) —
with the API key always REDACTED (it lives only in the auth header; the URL/body never carry
it, and provider error bodies never echo it).
"""

from __future__ import annotations

import tempfile
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

from charterhouse.conductor.transport import build_transports
from charterhouse.config import Config
from charterhouse.env import env_key_lookup, load_env_file
from charterhouse.ledger import Ledger
from charterhouse.memory import OllamaEmbedder
from charterhouse.router import Router
from charterhouse.router.types import Require

REPO = Path(__file__).resolve().parents[1]
PROMPT = [{"role": "user", "content": "Reply with the single word: ok"}]
EMBED_DIMS = {"nomic-embed-text": 768}

# The auth header names to REDACT in --debug output — the key value is never printed.
_AUTH_HEADERS = ("authorization", "x-goog-api-key")


def _sent_model(url: str, body: dict) -> str:
    if isinstance(body, dict) and "model" in body:
        return body["model"]  # OpenAI shape
    if "/models/" in url and ":generateContent" in url:  # Gemini native shape
        return url.split("/models/", 1)[1].split(":generateContent", 1)[0]
    return "?"


def _redacted_auth(headers) -> str:  # noqa: ANN001
    names = [k for k in headers if k.lower() in _AUTH_HEADERS]
    return ", ".join(f"{k}=****" for k in names) or "(none)"


def debug_send(url, headers, body, timeout):  # noqa: ANN001
    """A --debug HTTP sender: surfaces the endpoint URL, the model id sent, and the HTTP
    status + response body for each attempt (the real cause the router otherwise swallows
    into ProvidersExhausted). The API key lives only in the auth header and is REDACTED;
    the URL/body carry no key, and provider error bodies never echo the key."""
    print(f"[debug] POST {url}")
    print(f"[debug]   model={_sent_model(url, body)}  auth=[{_redacted_auth(headers)}]")
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", **dict(headers)})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        print(f"[debug]   -> HTTP {resp.status} OK")
        return payload
    except urllib.error.HTTPError as exc:
        print(f"[debug]   -> HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}")
        raise
    except Exception as exc:  # noqa: BLE001 — kind + message (URLError has no key)
        print(f"[debug]   -> {type(exc).__name__}: {exc}")
        raise


class Spy:
    """Delegating transport that counts sends — proves zero cloud egress under PII."""

    def __init__(self, inner) -> None:  # noqa: ANN001
        self._inner = inner
        self.count = 0

    def complete(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.count += 1
        return self._inner.complete(*args, **kwargs)


def _provider_of(config: Config, model_id: str) -> str:
    return config.get_model(model_id).provider


def _cloud_check(router, config, key_lookup, role, want_provider, label):  # noqa: ANN001
    """One live cloud call, pinning the answering provider. Distinguishes an ENV failure
    (key unset) from a transport/network failure so the report reads honestly."""
    key_env = config.get_provider(want_provider).key_env
    try:
        key_lookup(key_env)  # env pre-check; the value is never printed
    except Exception:  # noqa: BLE001
        return (label, False, f"{key_env} unset (env)")
    try:
        prov = _provider_of(config, router.call(role, PROMPT).model)
    except Exception as exc:  # noqa: BLE001 — kind only, never the detail
        return (label, False, f"{type(exc).__name__} (endpoint/env)")
    return (label, prov == want_provider,
            "" if prov == want_provider else f"answered on {prov}")


def main(debug: bool = False) -> int:
    loaded = load_env_file()  # populate the process environment from .env; names only, no values
    print(f".env: loaded {len(loaded)} var(s)" + ("  [debug on]" if debug else ""))
    key_lookup = env_key_lookup()
    config = Config.load(REPO / "config", "free")
    results: list[tuple[str, bool, str]] = []

    with tempfile.TemporaryDirectory() as tmp:
        ledger = Ledger(Path(tmp) / "ledger")
        transports = build_transports(config, key_lookup,
                                      send=debug_send if debug else None)
        cloud_spies = {}
        for pid in ("groq", "gemini"):
            if pid in transports:
                transports[pid] = cloud_spies[pid] = Spy(transports[pid])
        router = Router(config, ledger, transports=transports)

        # 1 — reasoning on Groq (pin the provider).
        results.append(_cloud_check(router, config, key_lookup,
                                    "reasoning", "groq", "reasoning(Groq)"))
        # 2 — critic on Gemini (pin the provider).
        results.append(_cloud_check(router, config, key_lookup,
                                    "critic", "gemini", "critic(Gemini)"))

        # 3 — local embed on Ollama.
        try:
            host = key_lookup("OLLAMA_HOST")
        except Exception:  # noqa: BLE001
            host = None
            results.append(("embed(Ollama)", False, "OLLAMA_HOST unset (env)"))
        if host is not None:
            try:
                model = _embed_model(key_lookup)
                dim = EMBED_DIMS.get(model, 768)
                vec = OllamaEmbedder(host, model, dim).embed("charter house smoke")
                results.append(("embed(Ollama)", len(vec) == dim,
                                "" if len(vec) == dim else f"dim {len(vec)}!={dim}"))
            except Exception as exc:  # noqa: BLE001
                results.append(("embed(Ollama)", False,
                                f"{type(exc).__name__} (endpoint/env)"))

        # 4 — PII-tagged context makes ZERO cloud sends (the guard hard-stops first).
        before = sum(s.count for s in cloud_spies.values())
        try:
            router.call("reasoning", PROMPT, require=Require(contains_pii=True))
        except Exception:  # noqa: BLE001, S110 — refusal or local-exhaustion both fine
            pass
        after = sum(s.count for s in cloud_spies.values())
        results.append(("pii-block(0 cloud)", after == before,
                        "" if after == before else f"{after - before} cloud send(s)!"))

    ok_all = all(ok for _, ok, _ in results)
    for name, ok, reason in results:
        print(f"{name:20} {'OK' if ok else 'FAIL'}" + (f"  [{reason}]" if reason else ""))
    print("---")
    print("SMOKE OK" if ok_all else "SMOKE FAIL")
    return 0 if ok_all else 1


def _embed_model(key_lookup) -> str:  # noqa: ANN001
    try:
        return key_lookup("CHARTERHOUSE_EMBED_MODEL")
    except Exception:  # noqa: BLE001 — default to the committed embed model
        return "nomic-embed-text"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live transport smoke (free profile).")
    parser.add_argument(
        "--debug", action="store_true",
        help="surface each provider attempt: endpoint URL, model id, HTTP status + "
             "response body (the API key is always redacted)")
    raise SystemExit(main(debug=parser.parse_args().debug))
