"""Strict schema validators for the four config file kinds (config/IMPLEMENTATION §3).

Each validator turns a parsed mapping into the frozen typed shape, rejecting unknown keys
and missing required keys with a ``LocatedError`` (file + key path). No silent drop, no
extra-key pass-through (docs/25 §4, RISKS R5).

Determinism (docs/61 §INV-DET): stdlib + contracts only; no LLM; no env read.
"""

from __future__ import annotations

from charterhouse.contracts.config_types import Budgets, Model, Provider, Route

from charterhouse.config.types import LocatedError

# Allowed keys per file kind: (required, optional). Anything else → unknown-key reject.
_PROVIDER_KEYS = (("base_url", "key_env", "kind"), ())
_MODEL_KEYS = (("provider", "ctx", "price_in", "price_out", "tier"), ("good_at",))
_ROUTE_KEYS = (("primary",), ("fallback", "min_ctx", "needs_tools", "needs_web"))
_BUDGET_KEYS = (("monthly_usd", "on_exceeded", "send_daily"), ())


def _require_mapping(raw: object, *, file: str, where: str) -> dict:
    if not isinstance(raw, dict):
        raise LocatedError(f"expected a mapping, got {type(raw).__name__}",
                           file=file, where=where)
    return raw


def _check_keys(mapping: dict, required: tuple[str, ...], optional: tuple[str, ...],
                *, file: str, where: str) -> None:
    """Reject unknown and missing-required keys with a located error (fail closed)."""
    allowed = set(required) | set(optional)
    for key in mapping:
        if key not in allowed:
            raise LocatedError(f"unknown key {key!r} (allowed: {sorted(allowed)})",
                               file=file, where=f"{where}.{key}")
    for key in required:
        if key not in mapping:
            raise LocatedError(f"missing required key {key!r}",
                               file=file, where=where)


def parse_provider(pid: str, raw: object, *, file: str) -> Provider:
    where = pid
    m = _require_mapping(raw, file=file, where=where)
    _check_keys(m, *_PROVIDER_KEYS, file=file, where=where)
    return Provider(base_url=str(m["base_url"]), key_env=str(m["key_env"]),
                    kind=str(m["kind"]))


def parse_model(mid: str, raw: object, *, file: str) -> Model:
    where = mid
    m = _require_mapping(raw, file=file, where=where)
    _check_keys(m, *_MODEL_KEYS, file=file, where=where)
    good_at = m.get("good_at", [])
    if not isinstance(good_at, list):
        raise LocatedError("good_at must be a list", file=file, where=f"{where}.good_at")
    return Model(provider=str(m["provider"]), ctx=int(m["ctx"]),
                 price_in=float(m["price_in"]), price_out=float(m["price_out"]),
                 tier=str(m["tier"]), good_at=tuple(str(g) for g in good_at))


def parse_route(role: str, raw: object, *, file: str) -> Route:
    where = role
    m = _require_mapping(raw, file=file, where=where)
    _check_keys(m, *_ROUTE_KEYS, file=file, where=where)
    fallback = m.get("fallback", [])
    if not isinstance(fallback, list):
        raise LocatedError("fallback must be a list", file=file, where=f"{where}.fallback")
    return Route(
        primary=str(m["primary"]),
        fallback=tuple(str(f) for f in fallback),
        min_ctx=int(m["min_ctx"]) if m.get("min_ctx") is not None else None,
        needs_tools=bool(m["needs_tools"]) if m.get("needs_tools") is not None else None,
        needs_web=bool(m["needs_web"]) if m.get("needs_web") is not None else None,
    )


def parse_budgets(raw: object, *, file: str) -> Budgets:
    where = "budgets"
    m = _require_mapping(raw, file=file, where=where)
    _check_keys(m, *_BUDGET_KEYS, file=file, where=where)
    return Budgets(monthly_usd=float(m["monthly_usd"]), on_exceeded=str(m["on_exceeded"]),
                   send_daily=int(m["send_daily"]))
