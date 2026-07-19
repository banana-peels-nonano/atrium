"""Config load pipeline (config/IMPLEMENTATION §3): parse YAML → validate → cross-ref
INV-CFG → apply profile/override precedence → freeze.

YAML is read with PyYAML ``safe_load`` only (no arbitrary object construction, RISKS R4).
No partial ``Config`` is ever returned: any located error aborts the whole load.

Determinism (docs/61 §INV-DET): stdlib + contracts + pinned pyyaml only; no LLM; no env
read (docs/20 — the caller injects ``config_dir`` and ``profile``).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from charterhouse.contracts.config_types import (
    Budgets,
    MemoryConfig,
    Model,
    Provider,
    Route,
)

from charterhouse.config.schema import (
    parse_budgets,
    parse_memory,
    parse_model,
    parse_provider,
    parse_route,
)
from charterhouse.config.types import LocatedError, UnknownProfile

_DEFAULT_PROFILE = "default"


def load_yaml(path: Path) -> dict:
    """``safe_load`` a YAML file to a mapping; a syntax error or non-mapping top level is
    a ``LocatedError`` naming the file (+ line when available)."""
    name = path.name
    if not path.is_file():
        raise LocatedError("config file not found", file=name)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        line = None
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
        raise LocatedError(f"YAML syntax error: {getattr(exc, 'problem', exc)}",
                           file=name, line=line) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise LocatedError(f"top level must be a mapping, got {type(data).__name__}",
                           file=name)
    return data


def cross_reference(routes: Mapping[str, Route], models: Mapping[str, Model],
                    providers: Mapping[str, Provider]) -> None:
    """Enforce ``INV-CFG`` both clauses (docs/25 §4): every route primary/fallback names a
    known model; every model's provider names a known provider. Dangling ref →
    ``LocatedError`` naming the referent. Fail closed."""
    for role, route in routes.items():
        for model_id in (route.primary, *route.fallback):
            if model_id not in models:
                raise LocatedError(
                    f"route references absent model {model_id!r} (INV-CFG clause 1)",
                    file="routes.yaml", where=role)
    for mid, model in models.items():
        if model.provider not in providers:
            raise LocatedError(
                f"model references absent provider {model.provider!r} (INV-CFG clause 2)",
                file="models.yaml", where=mid)


def _apply_route_overlay(base: dict[str, Route], overlay: object, *, file: str
                         ) -> dict[str, Route]:
    if overlay is None:
        return base
    if not isinstance(overlay, dict):
        raise LocatedError("routes override must be a mapping", file=file, where="routes")
    merged = dict(base)
    for role, raw in overlay.items():
        merged[role] = parse_route(role, raw, file=file)
    return merged


def resolve(
    config_dir: Path,
    profile: str | None,
    overrides: Mapping | None,
) -> tuple[dict[str, Provider], dict[str, Model], dict[str, Route], Budgets,
           MemoryConfig, str]:
    """The full pipeline → ``(providers, models, routes, budgets, memory,
    active_profile)`` with precedence applied (docs/25 §3: overrides > profile >
    routes default > base). ``memory`` is the additive docs/33 tuning block — base
    routes.yaml only for now (profile overlay is a later additive step, documented)."""
    config_dir = Path(config_dir)

    providers = {pid: parse_provider(pid, raw, file="providers.yaml")
                 for pid, raw in load_yaml(config_dir / "providers.yaml").items()}
    models = {mid: parse_model(mid, raw, file="models.yaml")
              for mid, raw in load_yaml(config_dir / "models.yaml").items()}

    routes_doc = load_yaml(config_dir / "routes.yaml")
    base_routes = {role: parse_route(role, raw, file="routes.yaml")
                   for role, raw in routes_doc.get("routes", {}).items()}
    base_budgets = parse_budgets(routes_doc["budgets"], file="routes.yaml") \
        if "budgets" in routes_doc else None
    if base_budgets is None:
        raise LocatedError("missing required key 'budgets'", file="routes.yaml")
    memory = parse_memory(routes_doc["memory"], file="routes.yaml") \
        if "memory" in routes_doc else MemoryConfig()

    routes = base_routes
    budgets = base_budgets
    active_profile = _DEFAULT_PROFILE

    # Profile tier (docs/25 §3): overrides routes.yaml defaults.
    if profile is not None:
        profile_path = config_dir / "profiles" / f"{profile}.yaml"
        if not profile_path.is_file():
            known = sorted(p.stem for p in (config_dir / "profiles").glob("*.yaml"))
            raise UnknownProfile(
                f"unknown profile {profile!r}; known profiles: {known}")
        pdoc = load_yaml(profile_path)
        routes = _apply_route_overlay(routes, pdoc.get("routes"),
                                      file=f"profiles/{profile}.yaml")
        if "budgets" in pdoc:
            budgets = parse_budgets(pdoc["budgets"], file=f"profiles/{profile}.yaml")
        active_profile = profile

    # CLI-arg / override tier (docs/25 §3): highest precedence.
    if overrides is not None:
        routes = _apply_route_overlay(routes, overrides.get("routes"), file="<overrides>")
        if overrides.get("budgets") is not None:
            budgets = parse_budgets(overrides["budgets"], file="<overrides>")

    # INV-CFG is enforced on the fully-resolved tables (a profile/override cannot smuggle
    # in a dangling reference either).
    cross_reference(routes, models, providers)
    return providers, models, routes, budgets, memory, active_profile
