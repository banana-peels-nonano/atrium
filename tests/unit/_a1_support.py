"""A1-local test support for the S2 (Environment) suite — PROVISIONAL.

Builds a temp "K:-like" filesystem + a matching env mapping, a fake Config (satisfying
``ConfigPort``), and programmable health/disk probes. A11-owned harness absorbs the
reusable pieces later; deleted then.
"""

from __future__ import annotations

from pathlib import Path

from charterhouse.contracts.config_types import Route
from charterhouse.env.preflight import C_HEADROOM_MIN_BYTES, EMBED_MARKER

EMBED_MODEL = "nomic-embed-text"


def ready_fs(root: Path, *, embed_model: str = EMBED_MODEL) -> dict[str, str]:
    """Create a prepared machine layout under ``root`` and return a matching env mapping.
    repo/, data/ (+ ledger/backups/logs), vectors/ (+ embed marker), config/ all exist."""
    repo = root / "repo"
    data = root / "data"
    vectors = data / "vectors"
    for d in (repo, repo / "config", data, data / "ledger", data / "backups",
              data / "logs", data / "models", repo / "vault", vectors):
        d.mkdir(parents=True, exist_ok=True)
    (vectors / EMBED_MARKER).write_text(embed_model, encoding="utf-8")
    return {
        "CHARTERHOUSE_ROOT": str(repo),
        "CHARTERHOUSE_DATA_DIR": str(data),
        "CHARTERHOUSE_VECTORS_DIR": str(vectors),
        "CHARTERHOUSE_PROFILE": "free",
        "CHARTERHOUSE_EMBED_MODEL": embed_model,
        "OLLAMA_HOST": "http://localhost:11434",
    }


class FakeConfig:
    """A ``ConfigPort`` double. ``dangling_roles`` name roles whose ``get_route`` raises,
    modelling A2's located error for an unresolvable role."""

    def __init__(self, dangling_roles: tuple[str, ...] = ()) -> None:
        self._dangling = set(dangling_roles)

    def get_route(self, role: str) -> Route:
        if role in self._dangling:
            raise KeyError(f"routes.yaml at {role}: route references absent model 'ghost'")
        return Route(primary="llama3.1-8b-local", fallback=("llama-3.3-70b-groq",))


def make_config_loader(dangling_roles: tuple[str, ...] = ()):
    """Factory matching ``preflight``'s ``config_loader`` seam signature."""
    def loader(config_dir: Path, profile: str | None) -> FakeConfig:
        return FakeConfig(dangling_roles)
    return loader


def health_up(ollama_host: str, embed_model: str) -> bool:
    return True


def health_down(ollama_host: str, embed_model: str) -> bool:
    return False


def disk_ok(path: Path) -> int:
    return C_HEADROOM_MIN_BYTES * 4


def disk_low(path: Path) -> int:
    return C_HEADROOM_MIN_BYTES // 2
