"""Environment (S2) error taxonomy + the injectable seams (env/API.md; env/IMPLEMENTATION §3).

Every preflight failure is a typed ``EnvError`` carrying **exactly one precise, actionable
message** (item + remediation, docs/20/21). ``ConfigPort`` is the slice of A2's frozen
``Config`` that preflight check #5 consumes — stubbed until A2 merges (docs/43 §2).

Determinism (docs/61 §INV-DET): stdlib + contracts only; no LLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from charterhouse.contracts.config_types import Route

__all__ = [
    "EnvError",
    "MissingEnvVar",
    "PathNotWritable",
    "KDisciplineError",
    "InsufficientHeadroom",
    "EndpointUnreachable",
    "VectorStoreError",
    "EmbedModelMismatch",
    "RouteUnresolvable",
    "ConfigPort",
    "HealthProbe",
]


class EnvError(Exception):
    """Base class for every S2 preflight/resolve failure. A raised preflight returns no
    ``EnvContext`` — never a partial boot (docs/20 fail-closed)."""


class MissingEnvVar(EnvError):
    """A required environment variable is unset (docs/25 §1). Names the var + `setx` remedy."""


class PathNotWritable(EnvError):
    """A required K: path is missing or not writable. Names the path."""


class KDisciplineError(EnvError):
    """A growing-data category resolved to an off-K: target (docs/23 storage law)."""


class InsufficientHeadroom(EnvError):
    """C: free space is below the safety threshold. Names shortfall + threshold."""


class EndpointUnreachable(EnvError):
    """The local embedding endpoint (Ollama) is down or the model is not pulled (docs/21)."""


class VectorStoreError(EnvError):
    """The vector store path is uninitialized. Names the vectors path."""


class EmbedModelMismatch(EnvError):
    """``CHARTERHOUSE_EMBED_MODEL`` differs from the model the vector index was built with —
    a silent embed-model change would corrupt retrieval; refuse to start (docs/25 §4,
    guarded re-index required). A1 owns this check (env + vector-store access; see
    config/IMPLEMENTATION §6)."""


class RouteUnresolvable(EnvError):
    """No model route resolves for some role under the active profile — surfaces Config's
    located error (docs/20 preflight check #5)."""


class ConfigPort(Protocol):
    """The slice of A2's frozen ``Config`` (docs/40 §1) preflight consumes. The real
    ``Config.load`` classmethod satisfies this; tests inject a stub (docs/43 §2)."""

    def get_route(self, role: str) -> Route: ...


class HealthProbe(Protocol):
    """Injectable local-endpoint health check (env/IMPLEMENTATION §3): returns True iff
    Ollama is up and ``embed_model`` is pulled. Faked in tests (no network in CI)."""

    def __call__(self, ollama_host: str, embed_model: str) -> bool: ...
