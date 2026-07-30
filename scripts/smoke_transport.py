"""Live transport smoke — the free profile, REAL network. NON-GATING (scripts/ is outside
pytest's testpaths, so this never runs in CI). Reports OK/FAIL per role only; never prints
keys or raw responses.

Checks (each role's expected provider is READ FROM THE RESOLVED ROUTE, never hardcoded — a
config reroute must not turn a healthy run into a false FAIL):
  reasoning         — one live call; the answering model MUST be the route's provider (so a
                      Groq outage that silently fails over elsewhere reads FAIL, not OK).
  critic            — same, following wherever the critic route resolves (currently the
                      local qwen3:8b, so this reports `critic(qwen3)`).
  embed (Ollama)    — one local embed returns a full-width vector.
  pii-block         — a contains_pii reasoning call makes ZERO cloud-transport sends.

Requires OLLAMA_HOST + Ollama running with the routed chat/embed models pulled, plus an API
key for whichever CLOUD providers the active profile's routes resolve to (a local role needs
no key). An unset key / unreachable endpoint is an ENV failure, not a code defect — reported
as such.

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


def expected_provider(config: Config, role: str) -> str:
    """The provider the role SHOULD answer on — derived from the resolved route's primary,
    never hardcoded. Rerouting a role in config (e.g. the critic from Gemini to local
    qwen3:8b) therefore moves the expectation with it instead of reporting a false FAIL."""
    return _provider_of(config, config.get_route(role).primary)


def role_label(config: Config, role: str) -> str:
    """The report label, naming the interesting fact: for a CLOUD role which vendor answered
    (`reasoning(Groq)`), for a LOCAL role which model (`critic(qwen3)`) — the provider is
    always ollama locally, so the model id is what distinguishes."""
    model_id = config.get_route(role).primary
    provider_id = _provider_of(config, model_id)
    if config.get_provider(provider_id).kind == "local":
        short = model_id.split(":", 1)[0]  # tag-stripped model id, e.g. qwen3:8b -> qwen3
    else:
        short = provider_id.title()  # groq -> Groq
    return f"{role}({short})"


def cloud_provider_ids(config: Config, transports) -> tuple[str, ...]:  # noqa: ANN001
    """Every wired provider whose kind is NOT local, sorted — the transports the pii-block
    check must watch. Derived from Config so a newly added cloud provider is covered by
    construction instead of being forgotten in a hardcoded list."""
    return tuple(sorted(pid for pid in transports
                        if config.get_provider(pid).kind != "local"))


def _role_check(router, config, key_lookup, role):  # noqa: ANN001
    """One live call for a role, pinning the answering provider to the route's resolution.
    Distinguishes an ENV failure (a cloud key unset) from a transport/network failure so the
    report reads honestly. A LOCAL role needs no key, so no key pre-check runs for it."""
    want_provider = expected_provider(config, role)
    label = role_label(config, role)
    provider = config.get_provider(want_provider)
    if provider.kind != "local":
        try:
            key_lookup(provider.key_env)  # env pre-check; the value is never printed
        except Exception:  # noqa: BLE001
            return (label, False, f"{provider.key_env} unset (env)")
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
        # Spy EVERY cloud transport (derived, not a hardcoded pair) so the pii-block check
        # proves zero egress across all of them — a new cloud provider can't slip past it.
        cloud_spies = {}
        for pid in cloud_provider_ids(config, transports):
            transports[pid] = cloud_spies[pid] = Spy(transports[pid])
        router = Router(config, ledger, transports=transports)

        # 1+2 — reasoning and critic, each pinned to WHEREVER ITS ROUTE RESOLVES.
        for role in ("reasoning", "critic"):
            results.append(_role_check(router, config, key_lookup, role))

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
