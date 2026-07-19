"""S3 Config unit suite — INV-CFG + fail-closed loading (docs/25, docs/54 §S3;
config/TESTPLAN.md).

Conventions follow the merged suites: fixture config dirs on tmp_path, typed fail-closed
errors via ``pytest.raises``, INV/MUST mapping in docstrings. S3 has no ledger/clock/LLM
surface, so no fakes beyond the fixture dirs.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from charterhouse.config import (
    Config,
    LocatedError,
    UnknownModel,
    UnknownProfile,
    UnknownProvider,
    UnknownRole,
)

from tests.unit import _a2_support as sup


def test_valid_config_loads_immutable(tmp_path):
    """docs/54 §S3 row 1: a well-formed dir loads; the resolved value types are frozen
    (mutation raises)."""
    cfg = Config.load(sup.write_config(tmp_path), profile="free")
    route = cfg.get_route("reasoning")
    assert route.primary == "free-cloud-big"
    assert cfg.get_model("local-small").tier == "free"
    assert cfg.budgets.send_daily == 40
    with pytest.raises(dataclasses.FrozenInstanceError):
        route.primary = "x"  # type: ignore[misc]


def test_unknown_key_rejected_located(tmp_path):
    """INV-CFG/unknown-key (docs/25 §4): a stray key → load rejected; error names the
    file + key path."""
    models = sup.clone(sup.MODELS)
    models["local-small"]["colour"] = "green"
    with pytest.raises(LocatedError) as exc:
        Config.load(sup.write_config(tmp_path, models=models))
    assert "models.yaml" in str(exc.value) and "colour" in str(exc.value)


def test_missing_required_key_rejected_located(tmp_path):
    """Fail-closed: a missing required key → rejected with location."""
    providers = sup.clone(sup.PROVIDERS)
    del providers["openrouter"]["base_url"]
    with pytest.raises(LocatedError) as exc:
        Config.load(sup.write_config(tmp_path, providers=providers))
    assert "providers.yaml" in str(exc.value) and "base_url" in str(exc.value)


def test_yaml_syntax_error_located(tmp_path):
    """Fail-closed: malformed YAML → rejected; error names the file."""
    cfg_dir = sup.write_raw(tmp_path, "routes.yaml", "routes: {this: [is: broken")
    with pytest.raises(LocatedError) as exc:
        Config.load(cfg_dir)
    assert "routes.yaml" in str(exc.value)


def test_invcfg_route_references_absent_model(tmp_path):
    """INV-CFG clause 1: a route primary/fallback naming a missing model → rejected,
    naming role + model id."""
    routes = sup.clone(sup.ROUTES)
    routes["reasoning"]["primary"] = "ghost-model"
    with pytest.raises(LocatedError) as exc:
        Config.load(sup.write_config(tmp_path, routes=routes))
    assert "ghost-model" in str(exc.value) and "reasoning" in str(exc.value)


def test_invcfg_route_fallback_references_absent_model(tmp_path):
    """INV-CFG clause 1: a dangling *fallback* ref is caught too (not only primary)."""
    routes = sup.clone(sup.ROUTES)
    routes["draft"]["fallback"] = ["free-cloud-big", "ghost-fallback"]
    with pytest.raises(LocatedError) as exc:
        Config.load(sup.write_config(tmp_path, routes=routes))
    assert "ghost-fallback" in str(exc.value)


def test_invcfg_model_references_absent_provider(tmp_path):
    """INV-CFG clause 2: a model naming a missing provider → rejected, naming model +
    provider id."""
    models = sup.clone(sup.MODELS)
    models["paid-cloud-big"]["provider"] = "ghost-provider"
    with pytest.raises(LocatedError) as exc:
        Config.load(sup.write_config(tmp_path, models=models))
    assert "ghost-provider" in str(exc.value) and "paid-cloud-big" in str(exc.value)


def test_profile_switch_reroutes_no_code_change(tmp_path):
    """docs/54 §S3 row 3: the same ``get_route('reasoning')`` under two profiles resolves
    a different model — one call site, zero code branch on profile."""
    cfg_dir = sup.write_config(tmp_path)
    free = Config.load(cfg_dir, profile="free")
    cheap = Config.load(cfg_dir, profile="cheap-cloud")
    assert free.get_route("reasoning").primary == "free-cloud-big"
    assert cheap.get_route("reasoning").primary == "paid-cloud-big"
    # Budgets follow the profile too.
    assert free.budgets.monthly_usd == 20.0
    assert cheap.budgets.monthly_usd == 100.0


def test_default_budgets_without_profile(tmp_path):
    """With no profile, budgets resolve to the routes.yaml default (docs/25 §3)."""
    cfg = Config.load(sup.write_config(tmp_path))
    assert cfg.budgets.send_daily == 40
    assert cfg.profile == "default"


def test_unknown_profile_rejected(tmp_path):
    """Fail-closed: an absent profile → rejected; the error lists known profiles."""
    with pytest.raises(UnknownProfile) as exc:
        Config.load(sup.write_config(tmp_path), profile="ghost-profile")
    assert "ghost-profile" in str(exc.value)


def test_get_provider_exposes_key_env_not_secret(tmp_path):
    """docs/24 secrets rule: ``get_provider(id).key_env`` is a var *name*; no secret value
    is present anywhere in the loaded Config."""
    cfg = Config.load(sup.write_config(tmp_path), profile="free")
    prov = cfg.get_provider("openrouter")
    assert prov.key_env == "OPENROUTER_API_KEY"
    assert prov.base_url.startswith("https://")


def test_get_unknown_id_raises_typed(tmp_path):
    """Fail-closed: unknown role/model/provider → typed lookup error, never a default."""
    cfg = Config.load(sup.write_config(tmp_path), profile="free")
    with pytest.raises(UnknownRole):
        cfg.get_route("nonexistent-role")
    with pytest.raises(UnknownModel):
        cfg.get_model("nonexistent-model")
    with pytest.raises(UnknownProvider):
        cfg.get_provider("nonexistent-provider")


def test_no_env_read(tmp_path, monkeypatch):
    """docs/20 env-boundary: loading is independent of ``os.environ`` — a mutated env
    yields an identical Config (S3 reads no environment)."""
    monkeypatch.setenv("CHARTERHOUSE_PROFILE", "cheap-cloud")
    monkeypatch.setenv("OPENROUTER_API_KEY", "ignored-by-config")
    cfg_dir = sup.write_config(tmp_path)
    a = Config.load(cfg_dir, profile="free")
    b = Config.load(cfg_dir, profile="free")
    assert a.get_route("reasoning").primary == b.get_route("reasoning").primary == "free-cloud-big"
    assert a.profile == "free"  # not "cheap-cloud" from the env var


def test_precedence_overrides_beat_profile(tmp_path):
    """docs/25 §3: an explicit ``overrides`` mapping (the CLI-arg tier) beats the profile,
    which beats the routes.yaml default."""
    cfg_dir = sup.write_config(tmp_path)
    overrides = {"routes": {"reasoning": {"primary": "local-small", "fallback": []}}}
    cfg = Config.load(cfg_dir, profile="cheap-cloud", overrides=overrides)
    assert cfg.get_route("reasoning").primary == "local-small"  # override wins over profile


REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


@pytest.mark.parametrize("profile", [None, "free", "cheap-cloud", "local-first"])
def test_committed_config_loads(profile):
    """The real committed ``config/`` (docs/25 §2) loads and passes INV-CFG under every
    shipped profile — a regression guard on the files themselves, not just fixtures."""
    cfg = Config.load(REPO_CONFIG, profile=profile)
    assert cfg.get_route("reasoning").primary
    assert cfg.budgets.send_daily > 0


def test_committed_free_profile_zero_paid():
    """docs/20 zero-paid-on-`free`: every model reachable from the committed `free`
    profile (and the default) is free-tier — no paid cloud dependency to boot the factory."""
    for profile in (None, "free"):
        cfg = Config.load(REPO_CONFIG, profile=profile)
        for role in ("reasoning", "classify", "draft", "critic", "web"):
            route = cfg.get_route(role)
            for model_id in (route.primary, *route.fallback):
                assert cfg.get_model(model_id).tier == "free", \
                    f"{profile}:{role}->{model_id} is not free-tier"


def test_free_profile_all_free_tier(tmp_path):
    """docs/20 zero-paid-on-free: every model reachable from the `free` profile's routes
    is a free-tier model (no paid cloud dependency)."""
    cfg = Config.load(sup.write_config(tmp_path), profile="free")
    for role in ("reasoning", "classify", "draft"):
        route = cfg.get_route(role)
        for model_id in (route.primary, *route.fallback):
            assert cfg.get_model(model_id).tier == "free", f"{role}->{model_id} not free"


# --- the three A2 cross-note accessors (docs/43 s7 additive; feat/a2-accessors) -----------


def test_models_listing_accessor(tmp_path):
    """Router RISKS R9: ``Config.models()`` lists every catalog id, sorted — the frozen
    listing seam replacing the router's interim internal-table read."""
    cfg = Config.load(sup.write_config(tmp_path), profile="free")
    assert cfg.models() == ("free-cloud-big", "local-small", "paid-cloud-big")
    assert isinstance(cfg.models(), tuple)  # immutable listing, ids only


def test_model_family_defaults_from_id(tmp_path):
    """Capabilities RISKS R3 (founder follow-up): ``Model.family`` — an explicit
    ``family:`` key wins; absent, the loader derives ``default_family(id)`` (leading
    alphabetic token). The catalog, not consumers, owns family semantics."""
    models = sup.clone(sup.MODELS)
    models["grok-beta"] = {"provider": "openrouter", "ctx": 131072, "price_in": 0.0,
                           "price_out": 0.0, "tier": "free", "family": "xai"}
    cfg = Config.load(sup.write_config(tmp_path, models=models), profile="free")
    assert cfg.get_model("grok-beta").family == "xai"          # explicit key wins
    assert cfg.get_model("local-small").family == "local"      # derived default
    assert cfg.get_model("free-cloud-big").family == "free"    # derived default


def test_model_family_invalid_refused(tmp_path):
    """Fail closed: a non-string / empty explicit ``family`` is a located error."""
    for bad in (42, ""):
        models = sup.clone(sup.MODELS)
        models["local-small"]["family"] = bad
        with pytest.raises(LocatedError, match="family"):
            Config.load(sup.write_config(tmp_path / str(bad), models=models),
                        profile="free")


def test_memory_accessor_defaults(tmp_path):
    """Memory RISKS R9: no ``memory:`` block in routes.yaml -> ``Config.memory`` carries
    the docs/33 defaults (mirrors ``RetrievalWeights`` field-for-field)."""
    cfg = Config.load(sup.write_config(tmp_path), profile="free")
    mc = cfg.memory
    assert (mc.w_semantic, mc.w_tag, mc.w_recency, mc.w_confidence, mc.w_segment) == \
        (0.5, 0.2, 0.15, 0.15, 0.1)
    assert (mc.half_life_active, mc.dup_threshold, mc.retire_below) == (30.0, 0.995, 0.2)
    assert (mc.promote_min_ventures, mc.max_k) == (3, 16)


def test_memory_block_overrides(tmp_path):
    """A partial ``memory:`` block overrides only the named keys; the rest keep the
    docs/33 defaults; the value is frozen."""
    cfg = Config.load(sup.write_config(tmp_path, memory={"w_semantic": 0.7, "max_k": 8}),
                      profile="free")
    assert cfg.memory.w_semantic == 0.7 and cfg.memory.max_k == 8
    assert cfg.memory.w_tag == 0.2  # untouched default
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.memory.max_k = 99  # type: ignore[misc]


def test_memory_unknown_key_refused(tmp_path):
    """Strict-key discipline extends to the new block: an unknown memory key is a
    located error (docs/25 s4 — no silent drop)."""
    with pytest.raises(LocatedError, match="w_bogus"):
        Config.load(sup.write_config(tmp_path, memory={"w_bogus": 1.0}), profile="free")


def test_committed_config_carries_accessors(repo_root):
    """The real committed config/ loads with the new seams live: models() lists the
    catalog; memory carries the committed (default) block."""
    cfg = Config.load(repo_root / "config", profile="free")
    ids = cfg.models()
    assert ids and ids == tuple(sorted(ids))
    for mid in ids:
        assert cfg.get_model(mid).family  # every committed model has a family
    assert cfg.memory.max_k >= 1
