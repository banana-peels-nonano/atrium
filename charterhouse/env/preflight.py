"""Deterministic preflight (docs/20 §Preflight) — the sole environment reader.

Ordered checks, each failing closed with exactly one precise, actionable error; on success
an immutable ``EnvContext``. Never partial-boots. Seams (``env`` mapping, health probe,
disk probe, ``Config`` loader) are injected so the whole flow is deterministic in tests;
``preflight()`` with no arguments wires the real ``os.environ`` + real probes.

Determinism (docs/61 §INV-DET): stdlib + contracts + injected Config only; no LLM. This is
the **only** module in the codebase permitted to read ``os.environ`` (docs/20 env-boundary,
enforced by ``test_no_direct_env_read_outside_env``).
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from charterhouse.contracts.env_context import EnvContext

from charterhouse.env.types import (
    ConfigPort,
    EmbedModelMismatch,
    EndpointUnreachable,
    HealthProbe,
    InsufficientHeadroom,
    MissingEnvVar,
    PathNotWritable,
    RouteUnresolvable,
    VectorStoreError,
)

# docs/25 §1 runtime vars that MUST be present (secrets are validated per-provider at call
# time by the Router, not here — preflight verifies environment *structure*).
REQUIRED_VARS: tuple[str, ...] = (
    "CHARTERHOUSE_ROOT",
    "CHARTERHOUSE_DATA_DIR",
    "CHARTERHOUSE_VECTORS_DIR",
    "CHARTERHOUSE_PROFILE",
    "CHARTERHOUSE_EMBED_MODEL",
    "OLLAMA_HOST",
)

# Roles that MUST each resolve to ≥1 route under the active profile (docs/20 check #5).
REQUIRED_ROLES: tuple[str, ...] = ("reasoning", "classify", "draft", "critic")

# C: free-space safety threshold (docs/20: C: ~25 GB, treat as nearly full).
C_HEADROOM_MIN_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

# Marker file recording the embed model the vector index was built with (docs/25 §4).
EMBED_MARKER = "EMBED_MODEL"


class DiskProbe:
    """Injectable free-space probe (bytes free on the drive holding a path)."""

    def __call__(self, path: Path) -> int:
        return shutil.disk_usage(path).free


def _default_health(ollama_host: str, embed_model: str) -> bool:  # pragma: no cover
    """Real Ollama health check — not exercised in CI (network). Overridden in tests."""
    raise NotImplementedError("wired to a real Ollama ping outside tests")


def _default_config_loader(config_dir: Path, profile: str | None) -> ConfigPort:  # pragma: no cover
    """Real check-#5 loader: A2's ``Config.load``. Imported lazily so S2 has no import-time
    dependency on S3 (they build on independent branches; A2 satisfies ``ConfigPort``)."""
    from charterhouse.config import Config

    return Config.load(config_dir, profile)


def _writable(path: Path) -> bool:
    """A directory exists and accepts a write (Windows-reliable: attempt a probe file
    rather than trusting ``os.access`` on a directory)."""
    if not path.is_dir():
        return False
    probe = path / ".preflight_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def preflight(
    *,
    env: Mapping[str, str] | None = None,
    config_loader: Callable[[Path, str | None], ConfigPort] | None = None,
    health: HealthProbe | None = None,
    disk: Callable[[Path], int] | None = None,
    c_drive: Path | None = None,
) -> EnvContext:
    """Run the ordered docs/20 preflight and return an immutable ``EnvContext``; the first
    failing check raises its one precise error (no partial boot). Keyword seams are
    additive (docs/43 §7): ``preflight()`` wires the real environment + probes."""
    env = os.environ if env is None else env
    config_loader = config_loader if config_loader is not None else _default_config_loader
    health = health if health is not None else _default_health
    disk = disk if disk is not None else DiskProbe()
    c_drive = c_drive if c_drive is not None else Path(os.environ.get("SystemDrive", "C:") + "\\")

    # Check 1 — required env vars present (docs/25 §1). One precise error per missing var.
    for var in REQUIRED_VARS:
        if not env.get(var):
            raise MissingEnvVar(
                f"required environment variable {var} is unset; set it with "
                f"`setx {var} <value>` (docs/25 §1) and restart the shell")

    repo_root = Path(env["CHARTERHOUSE_ROOT"])
    data_dir = Path(env["CHARTERHOUSE_DATA_DIR"])
    vectors_dir = Path(env["CHARTERHOUSE_VECTORS_DIR"])
    profile = env["CHARTERHOUSE_PROFILE"]
    embed_model = env["CHARTERHOUSE_EMBED_MODEL"]
    ollama_host = env["OLLAMA_HOST"]

    ledger_dir = data_dir / "ledger"
    backups_dir = data_dir / "backups"
    logs_dir = data_dir / "logs"
    models_dir = data_dir / "models"
    config_dir = repo_root / "config"
    vault_dir = repo_root / "vault"

    # Check 2 — required K: paths exist + writable; C: headroom ≥ threshold.
    for path in (repo_root, data_dir, vectors_dir):
        if not _writable(path):
            raise PathNotWritable(
                f"required path {path} is missing or not writable; it must exist and be "
                "writable on the K: drive (docs/23)")
    free = disk(c_drive)
    if free < C_HEADROOM_MIN_BYTES:
        raise InsufficientHeadroom(
            f"C: free-space headroom {free} bytes is below the {C_HEADROOM_MIN_BYTES}-byte "
            "threshold; free space or relocate caches to K: (docs/20)")

    # Check 3 — local embedding endpoint reachable (Ollama up + model pulled).
    if not health(ollama_host, embed_model):
        raise EndpointUnreachable(
            f"local embedding endpoint {ollama_host} is unreachable or model "
            f"{embed_model!r} is not pulled; start Ollama and run "
            f"`ollama pull {embed_model}` (docs/21)")

    # Check 4 — vector store initialized + embed-model marker matches (docs/25 §4).
    marker = vectors_dir / EMBED_MARKER
    if not vectors_dir.is_dir() or not marker.is_file():
        raise VectorStoreError(
            f"vector store at {vectors_dir} is uninitialized (no {EMBED_MARKER} marker); "
            "initialize the LanceDB store before first run (docs/20)")
    built_with = marker.read_text(encoding="utf-8").strip()
    if built_with != embed_model:
        raise EmbedModelMismatch(
            f"CHARTERHOUSE_EMBED_MODEL={embed_model!r} but the vector index was built with "
            f"{built_with!r}; a silent embed-model change corrupts retrieval — run a "
            "guarded re-index before starting (docs/25 §4)")

    # Check 5 — ≥1 route resolvable for each required role under the active profile (A2).
    config = config_loader(config_dir, profile)
    for role in REQUIRED_ROLES:
        try:
            config.get_route(role)
        except Exception as exc:  # surface Config's located error as the preflight error
            raise RouteUnresolvable(
                f"no model route resolves for role {role!r} under profile {profile!r}: "
                f"{exc}") from exc

    return EnvContext(
        repo_root=repo_root, data_dir=data_dir, ledger_dir=ledger_dir,
        vault_dir=vault_dir, vectors_dir=vectors_dir, backups_dir=backups_dir,
        logs_dir=logs_dir, config_dir=config_dir, models_dir=models_dir,
        profile=profile, ollama_host=ollama_host, embed_model=embed_model)
