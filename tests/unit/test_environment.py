"""S2 Environment unit suite — preflight + K:-discipline (docs/20, docs/54 §S2/Global;
env/TESTPLAN.md).

Conventions follow the merged suites: temp K:-like fs + injected seams (env mapping,
health/disk probes, Config loader), typed fail-closed errors via ``pytest.raises``,
MUST mapping in docstrings. Only outbound touch is a faked local health ping (INV-TEST-SAFE).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from charterhouse.contracts.env_context import EnvContext, PathKind
from charterhouse.env import (
    EmbedModelMismatch,
    EndpointUnreachable,
    InsufficientHeadroom,
    KDisciplineError,
    MissingEnvVar,
    PathNotWritable,
    RouteUnresolvable,
    VectorStoreError,
    preflight,
)
from charterhouse.env.paths import guard_growing, is_within

from tests.unit import _a1_support as sup


def run(env, root, **over):
    """Drive preflight with the ready fixture's fully-faked seams, overriding as needed."""
    kwargs = dict(
        env=env,
        config_loader=sup.make_config_loader(),
        health=sup.health_up,
        disk=sup.disk_ok,
        c_drive=root,
    )
    kwargs.update(over)
    return preflight(**kwargs)


def test_preflight_passes_on_ready_machine(tmp_path):
    """docs/54 §S2 happy path: all prereqs satisfied → a valid immutable EnvContext with
    K:-rooted paths derived from the env roots."""
    env = sup.ready_fs(tmp_path)
    ctx = run(env, tmp_path)
    assert isinstance(ctx, EnvContext)
    assert ctx.profile == "free"
    assert ctx.embed_model == sup.EMBED_MODEL
    assert ctx.resolve(PathKind.LEDGER) == ctx.data_dir / "ledger"
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.profile = "x"  # type: ignore[misc]


def test_missing_env_var_one_error(tmp_path):
    """One-precise-error: an unset required var → exactly one error naming the var +
    `setx` remedy; no EnvContext returned."""
    env = sup.ready_fs(tmp_path)
    del env["CHARTERHOUSE_VECTORS_DIR"]
    with pytest.raises(MissingEnvVar) as exc:
        run(env, tmp_path)
    assert "CHARTERHOUSE_VECTORS_DIR" in str(exc.value)
    assert "setx" in str(exc.value).lower()


def test_k_path_missing_or_readonly_one_error(tmp_path):
    """K:-discipline: a missing required K: path → one precise error naming the path."""
    env = sup.ready_fs(tmp_path)
    import shutil
    shutil.rmtree(env["CHARTERHOUSE_DATA_DIR"])
    with pytest.raises(PathNotWritable) as exc:
        run(env, tmp_path)
    assert env["CHARTERHOUSE_DATA_DIR"] in str(exc.value)


def test_c_headroom_below_threshold_one_error(tmp_path):
    """docs/20: low C: headroom → one precise error naming the shortfall/threshold."""
    env = sup.ready_fs(tmp_path)
    with pytest.raises(InsufficientHeadroom) as exc:
        run(env, tmp_path, disk=sup.disk_low)
    assert "headroom" in str(exc.value).lower() or "space" in str(exc.value).lower()


def test_ollama_unreachable_one_error(tmp_path):
    """docs/21: embedding endpoint down / model absent → one precise error + pull step."""
    env = sup.ready_fs(tmp_path)
    with pytest.raises(EndpointUnreachable) as exc:
        run(env, tmp_path, health=sup.health_down)
    assert env["OLLAMA_HOST"] in str(exc.value)


def test_vectors_dir_uninitialized_one_error(tmp_path):
    """docs/20: missing vector store → one precise error naming the vectors path."""
    env = sup.ready_fs(tmp_path)
    import shutil
    shutil.rmtree(env["CHARTERHOUSE_VECTORS_DIR"])
    (Path(env["CHARTERHOUSE_DATA_DIR"]) / "vectors").mkdir()  # exists but no marker
    with pytest.raises(VectorStoreError) as exc:
        run(env, tmp_path)
    assert env["CHARTERHOUSE_VECTORS_DIR"] in str(exc.value)


def test_embed_model_mismatch_refused(tmp_path):
    """docs/25 §4 (A1-owned per config/IMPLEMENTATION §6): the env embed model differing
    from the vector-index marker → refuse to start (guarded re-index required)."""
    env = sup.ready_fs(tmp_path, embed_model="nomic-embed-text")
    env["CHARTERHOUSE_EMBED_MODEL"] = "bge-small-en"  # index built with nomic
    with pytest.raises(EmbedModelMismatch) as exc:
        run(env, tmp_path)
    assert "bge-small-en" in str(exc.value) and "nomic-embed-text" in str(exc.value)


def test_no_route_for_role_surfaces_config_error(tmp_path):
    """docs/20 check #5: a dangling route → preflight fails, surfacing Config's located
    error for that role."""
    env = sup.ready_fs(tmp_path)
    loader = sup.make_config_loader(dangling_roles=("critic",))
    with pytest.raises(RouteUnresolvable) as exc:
        run(env, tmp_path, config_loader=loader)
    assert "critic" in str(exc.value)


def test_offk_growing_write_refused(tmp_path):
    """K:-discipline (docs/23): the guard refuses an off-root target for a growing
    category; a within-root target passes."""
    growing_root = tmp_path / "data"
    growing_root.mkdir()
    off = tmp_path / "elsewhere" / "vectors"
    with pytest.raises(KDisciplineError):
        guard_growing(PathKind.VECTORS, off, growing_root=growing_root)
    within = growing_root / "vectors"
    assert guard_growing(PathKind.VECTORS, within, growing_root=growing_root) == within
    # Structural categories are not K:-guarded.
    assert guard_growing(PathKind.CONFIG, off, growing_root=growing_root) == off


def test_is_within_helper(tmp_path):
    """The containment helper underpinning the discipline guard."""
    assert is_within(tmp_path / "a" / "b", tmp_path)
    assert is_within(tmp_path, tmp_path)
    assert not is_within(tmp_path.parent / "sibling", tmp_path)


def test_no_partial_boot(tmp_path):
    """INV-FAILCLOSED: every single failure mode returns NO EnvContext (halt), never a
    partial one."""
    good = sup.ready_fs(tmp_path)
    # A representative failure from each check must raise, not return.
    cases = [
        dict(env={k: v for k, v in good.items() if k != "OLLAMA_HOST"}),
        dict(health=sup.health_down),
        dict(disk=sup.disk_low),
        dict(config_loader=sup.make_config_loader(dangling_roles=("reasoning",))),
    ]
    for over in cases:
        with pytest.raises(Exception):
            run(good, tmp_path, **over)


def test_free_profile_zero_paid(tmp_path):
    """docs/20 zero-paid-on-`free`: preflight passes on the `free` profile with only a
    local embedder reachable and NO cloud secret keys set in the environment."""
    env = sup.ready_fs(tmp_path)  # note: no *_API_KEY vars present at all
    ctx = run(env, tmp_path)
    assert ctx.profile == "free"


def test_no_direct_env_read_outside_env():
    """Env-boundary MUST (docs/20): ``os.environ`` / ``getenv`` appears only under
    ``charterhouse/env/`` — every other subsystem receives an EnvContext."""
    root = Path(__file__).resolve().parents[2] / "charterhouse"
    offenders = []
    for py in root.rglob("*.py"):
        if "env" in py.relative_to(root).parts[:1]:
            continue  # charterhouse/env/ is the sole permitted reader
        text = py.read_text(encoding="utf-8")
        for needle in ("os.environ", "os.getenv", "getenv("):
            if needle in text:
                offenders.append(f"{py.relative_to(root)}: {needle}")
    assert not offenders, f"env read outside charterhouse/env/: {offenders}"
