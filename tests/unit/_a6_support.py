"""A6-local test support for the S8 (Router) suite — PROVISIONAL.

Router-shaped config fixtures (paid + free cloud + local models across four providers,
two profiles) built on the A2 fixture writer, plus a stack factory wiring the real Config
+ real tmp-path Ledger + A11 ``FakeProvider`` transports (docs/55 §2 — **no network**).
"""

from __future__ import annotations

from types import SimpleNamespace

from charterhouse.config import Config
from charterhouse.ledger import Ledger
from charterhouse.router.facade import Router

from tests.fakes import FakeProvider
from tests.unit import _a2_support as a2
from tests.unit import _a3_support as a3

PROVIDERS: dict = {
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": "OLLAMA_HOST",
               "kind": "local"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                   "key_env": "OPENROUTER_API_KEY", "kind": "cloud"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1",
                  "key_env": "ANTHROPIC_API_KEY", "kind": "cloud"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "key_env": "GEMINI_API_KEY", "kind": "cloud"},
}

MODELS: dict = {
    "local-small": {"provider": "ollama", "ctx": 8192, "price_in": 0.0, "price_out": 0.0,
                    "tier": "free", "good_at": ["draft", "classify"]},
    "free-cloud-big": {"provider": "openrouter", "ctx": 131072, "price_in": 0.0,
                       "price_out": 0.0, "tier": "free",
                       "good_at": ["reasoning", "tools"]},
    "gemini-flash": {"provider": "gemini", "ctx": 1000000, "price_in": 0.0,
                     "price_out": 0.0, "tier": "free",
                     "good_at": ["reasoning", "web", "long-context"]},
    "claude-sonnet": {"provider": "anthropic", "ctx": 200000, "price_in": 3.0,
                      "price_out": 15.0, "tier": "paid",
                      "good_at": ["reasoning", "critique", "tools"]},
}

ROUTES: dict = {
    "reasoning": {"primary": "free-cloud-big", "fallback": ["gemini-flash", "local-small"]},
    "critic": {"primary": "gemini-flash", "fallback": ["free-cloud-big"]},
    "web": {"primary": "gemini-flash", "fallback": [], "needs_web": True},
    "draft": {"primary": "local-small", "fallback": ["free-cloud-big"]},
}

PROFILES: dict = {
    "free": {},
    "cheap-cloud": {"routes": {"reasoning": {"primary": "claude-sonnet",
                                             "fallback": ["free-cloud-big"]}}},
}

BUDGETS: dict = {"monthly_usd": 20.0, "on_exceeded": "degrade", "send_daily": 40}


def write_router_config(root, *, providers=None, models=None, routes=None,
                        profiles=None, budgets=None):
    return a2.write_config(
        root,
        providers=providers if providers is not None else PROVIDERS,
        models=models if models is not None else MODELS,
        routes=routes if routes is not None else ROUTES,
        profiles=profiles if profiles is not None else PROFILES,
        budgets=budgets if budgets is not None else BUDGETS,
    )


def make_stack(tmp_path, *, profile: str = "free", providers=None, models=None,
               routes=None, profiles=None, transports: dict | None = None,
               spent_usd=None) -> SimpleNamespace:
    """(router, config, ledger, transports) over the real Config + real Ledger + one
    FakeProvider transport per provider (overridable per test)."""
    cfg_dir = write_router_config(tmp_path, providers=providers, models=models,
                                  routes=routes, profiles=profiles)
    config = Config.load(cfg_dir, profile=profile)
    ledger = Ledger(tmp_path / "ledger", new_id=a3.deterministic_id_factory())
    prov_ids = (providers if providers is not None else PROVIDERS).keys()
    t = {pid: FakeProvider(canned=f"answer-from-{pid}") for pid in prov_ids}
    if transports:
        t.update(transports)
    router = Router(config, ledger, transports=t, spent_usd=spent_usd)
    return SimpleNamespace(router=router, config=config, ledger=ledger, transports=t)


USER_MSG = [{"role": "user", "content": "draft the weekly battlecard"}]
