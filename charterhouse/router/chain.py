"""S8 candidate-chain builder (INV-ROUTE-1/2/3; router/IMPLEMENTATION §3) — pure.

``[primary, *fallback]`` in config order (never reordered) → constraint filters (route ∪
require; require wins) → PII locality filter (``contains_pii`` ⇒ ``Provider.kind ==
"local"`` only) → budget tier filter (ceiling "free" drops paid) → the deterministic
free/local degrade extension (catalog ∩ free-tier ∩ local provider − already listed,
sorted by id). Bodies land in the implementation step.

Determinism (docs/61 §INV-DET): pure functions over Config data; no LLM, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from charterhouse.config import Config

from charterhouse.router.types import NoEligibleModel, PIIRouteBlocked, Require


@dataclass(frozen=True)
class ChainPlan:
    """The routing decision: ordered candidate model ids (configured chain first, degrade
    extension after) + the cloud candidates a PII tag excluded (for the ``pii_block``
    audit event)."""

    candidates: tuple[str, ...]
    pii_excluded: tuple[str, ...]


def build_chain(config: Config, role: str, require: Require, tier_ceiling: str) -> ChainPlan:
    """Resolve + filter + extend. Raises ``PIIRouteBlocked`` (PII with no local candidate
    anywhere — nothing may be sent) or ``NoEligibleModel`` (a non-PII chain emptied by
    constraints, naming the constraint). An unknown role propagates Config's error."""
    route = config.get_route(role)  # INV-ROUTE-1: the only role lookup in S8
    configured = [route.primary, *route.fallback]

    # Merged constraints: route ∪ require, require wins where set. Under a PII tag the
    # ROUTE-level min_ctx (a quality preference) is relaxed so the security invariant
    # can be satisfied by a smaller local model (docs/24: PII work RUNS locally,
    # degraded, rather than failing); an EXPLICIT require.min_ctx is still enforced —
    # a genuine conflict with PII locality then fails closed (IMPLEMENTATION §6.6).
    if require.min_ctx is not None:
        min_ctx = require.min_ctx
    else:
        min_ctx = None if require.contains_pii else route.min_ctx
    needs_tools = require.needs_tools if require.needs_tools is not None else route.needs_tools
    needs_web = require.needs_web if require.needs_web is not None else route.needs_web

    def meets_constraints(model_id: str) -> bool:
        model = config.get_model(model_id)
        if min_ctx is not None and model.ctx < min_ctx:
            return False
        if needs_tools and "tools" not in model.good_at:
            return False
        if needs_web and "web" not in model.good_at:
            return False
        if tier_ceiling == "free" and model.tier != "free":
            return False  # budget degrade (docs/14): paid tier dropped
        return True

    def is_local(model_id: str) -> bool:
        model = config.get_model(model_id)
        return config.get_provider(model.provider).kind == "local"

    # The deterministic free/local degrade extension (INV-ROUTE-2): catalog models on a
    # free tier AND a local provider, sorted by id, minus what the route already lists.
    extension = sorted(
        mid for mid in _catalog_ids(config)
        if mid not in configured
        and config.get_model(mid).tier == "free" and is_local(mid)
        and meets_constraints(mid)
    )

    eligible = [mid for mid in configured if meets_constraints(mid)]
    pii_excluded: tuple[str, ...] = ()
    if require.contains_pii:
        # INV-ROUTE-3 / INV-PII-3 chain half: cloud candidates leave the chain entirely.
        pii_excluded = tuple(mid for mid in eligible if not is_local(mid))
        eligible = [mid for mid in eligible if is_local(mid)]

    candidates = tuple(dict.fromkeys([*eligible, *extension]))
    if not candidates:
        if require.contains_pii:
            raise PIIRouteBlocked(
                f"role {role!r}: context is tagged contains_pii and no local model is "
                "available — cloud routes are excluded, nothing was sent (INV-PII-3)")
        raise NoEligibleModel(
            f"role {role!r}: no candidate satisfies the merged constraints "
            f"(min_ctx={min_ctx}, needs_tools={needs_tools}, needs_web={needs_web}, "
            f"tier_ceiling={tier_ceiling!r})")
    return ChainPlan(candidates=candidates, pii_excluded=pii_excluded)


def _catalog_ids(config: Config) -> tuple[str, ...]:
    """All model ids in the catalog. Config's frozen surface has no listing seam yet, so
    this is the ONE sanctioned read of its internal table (RISKS R9; IMPLEMENTATION §6.7
    — replaced by A2's additive ``Config.models()`` when it lands)."""
    return tuple(sorted(config._models))  # noqa: SLF001 — see RISKS R9
