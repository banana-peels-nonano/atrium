"""A2-local test support for the S3 (Config) suite — PROVISIONAL.

Builds config fixture directories on tmp_path. A well-formed dir plus mutators for each
failure mode (unknown key, missing key, dangling model/provider ref, unknown profile,
broken YAML). A11-owned harness absorbs the reusable pieces later; deleted then.

File layout (config/IMPLEMENTATION §6 resolution): ``routes.yaml`` carries two top-level
keys — ``budgets`` (the default Budgets) and ``routes`` (role→Route) — because docs/31
lists no separate budgets file and docs/25 §2 says profiles override "routes/budgets".
``profiles/<name>.yaml`` carries partial ``routes`` and/or ``budgets`` overrides.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

# A well-formed base config: two providers (one local/free, one cloud), three models,
# three roles, default budgets, and two profiles that reroute a role.
PROVIDERS: dict = {
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": "OLLAMA_HOST",
               "kind": "local"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                   "key_env": "OPENROUTER_API_KEY", "kind": "cloud"},
}
MODELS: dict = {
    "local-small": {"provider": "ollama", "ctx": 8192, "price_in": 0.0, "price_out": 0.0,
                    "tier": "free", "good_at": ["draft", "classify"]},
    "free-cloud-big": {"provider": "openrouter", "ctx": 131072, "price_in": 0.0,
                       "price_out": 0.0, "tier": "free", "good_at": ["reasoning"]},
    "paid-cloud-big": {"provider": "openrouter", "ctx": 200000, "price_in": 3.0,
                       "price_out": 15.0, "tier": "paid", "good_at": ["reasoning"]},
}
ROUTES: dict = {
    "reasoning": {"primary": "free-cloud-big", "fallback": ["local-small"],
                  "min_ctx": 32000, "needs_web": False},
    "classify": {"primary": "local-small", "fallback": []},
    "draft": {"primary": "local-small", "fallback": ["free-cloud-big"]},
}
BUDGETS: dict = {"monthly_usd": 20.0, "on_exceeded": "degrade", "send_daily": 40}

# `free` keeps everything on free/local tiers; `cheap-cloud` reroutes reasoning to a paid
# model and lifts the budget — the profile-switch-reroutes test uses both.
PROFILES: dict = {
    "free": {"routes": {"reasoning": {"primary": "free-cloud-big",
                                      "fallback": ["local-small"]}}},
    "cheap-cloud": {"routes": {"reasoning": {"primary": "paid-cloud-big",
                                             "fallback": ["free-cloud-big"]}},
                    "budgets": {"monthly_usd": 100.0, "on_exceeded": "degrade",
                                "send_daily": 60}},
}


def write_config(root: Path, *, providers: dict | None = None, models: dict | None = None,
                 routes: dict | None = None, budgets: dict | None = None,
                 profiles: dict | None = None) -> Path:
    """Write a full config dir under ``root`` and return it. Any table can be overridden
    to construct a failure fixture."""
    cfg = root / "config"
    (cfg / "profiles").mkdir(parents=True, exist_ok=True)
    _dump(cfg / "providers.yaml", providers if providers is not None else PROVIDERS)
    _dump(cfg / "models.yaml", models if models is not None else MODELS)
    _dump(cfg / "routes.yaml", {"budgets": budgets if budgets is not None else BUDGETS,
                                "routes": routes if routes is not None else ROUTES})
    for name, body in (profiles if profiles is not None else PROFILES).items():
        _dump(cfg / "profiles" / f"{name}.yaml", body)
    return cfg


def write_raw(root: Path, filename: str, text: str) -> Path:
    """Write a raw (possibly malformed) file into an otherwise-valid config dir."""
    cfg = write_config(root)
    (cfg / filename).write_text(text, encoding="utf-8")
    return cfg


def _dump(path: Path, obj: object) -> None:
    path.write_text(yaml.safe_dump(obj, sort_keys=True), encoding="utf-8")


def clone(table: dict) -> dict:
    return copy.deepcopy(table)
