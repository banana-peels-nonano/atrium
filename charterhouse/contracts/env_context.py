"""Frozen S2 shared types — ``EnvContext`` + ``PathKind`` (docs/20; env/API.md).

The immutable value A1 preflight produces and every other subsystem receives paths/
profile/endpoints from — no subsystem reads environment variables directly (docs/20
env-boundary). Declarations only: the preflight checks and path discipline live in
``charterhouse/env`` and are added in the implementation step.

Determinism (docs/61 §INV-DET): stdlib only; no ``router`` / ``memory`` / ``capabilities``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PathKind(str, Enum):
    """A resolvable path category (env/API.md ``resolve``). The GROWING kinds accumulate
    data and MUST live on K: (docs/23 storage law); the rest are structural."""

    # Growing categories (K:-disciplined — a large/growing write off K: is refused).
    LEDGER = "ledger"
    VECTORS = "vectors"
    CACHE = "cache"
    LOGS = "logs"
    WEIGHTS = "weights"
    BACKUPS = "backups"
    # Structural categories.
    REPO_ROOT = "repo_root"
    DATA = "data"
    VAULT = "vault"
    CONFIG = "config"
    MODELS = "models"


GROWING_KINDS: frozenset[PathKind] = frozenset({
    PathKind.LEDGER, PathKind.VECTORS, PathKind.CACHE,
    PathKind.LOGS, PathKind.WEIGHTS, PathKind.BACKUPS,
})


@dataclass(frozen=True)
class EnvContext:
    """The immutable runtime context (docs/20 §Preflight). All paths absolute and
    K:-rooted where docs/23 requires; frozen (mutation raises — it is a
    ``frozen=True`` dataclass). Produced only by a passing ``preflight()``."""

    repo_root: Path
    data_dir: Path
    ledger_dir: Path
    vault_dir: Path
    vectors_dir: Path
    backups_dir: Path
    logs_dir: Path
    config_dir: Path
    models_dir: Path
    profile: str
    ollama_host: str
    embed_model: str

    def resolve(self, kind: PathKind) -> Path:
        """Return the K:-disciplined path for a category (env/API.md). Pure."""
        mapping = {
            PathKind.REPO_ROOT: self.repo_root,
            PathKind.DATA: self.data_dir,
            PathKind.LEDGER: self.ledger_dir,
            PathKind.VAULT: self.vault_dir,
            PathKind.VECTORS: self.vectors_dir,
            PathKind.BACKUPS: self.backups_dir,
            PathKind.LOGS: self.logs_dir,
            PathKind.CONFIG: self.config_dir,
            PathKind.MODELS: self.models_dir,
            PathKind.CACHE: self.data_dir / "cache",
            PathKind.WEIGHTS: self.models_dir,
        }
        return mapping[kind]
