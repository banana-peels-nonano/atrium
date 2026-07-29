"""Environment (S2) — the preflight + the immutable ``EnvContext`` (docs/20).

Public surface: ``preflight()`` (the sole environment reader) returning an ``EnvContext``
(shared type in ``charterhouse.contracts``), plus ``PathKind`` and the S2 error taxonomy.
No other subsystem reads environment variables — all receive an ``EnvContext``.
"""

from charterhouse.contracts.env_context import EnvContext, PathKind

from charterhouse.env.envfile import load_env_file
from charterhouse.env.keys import env_key_lookup
from charterhouse.env.preflight import REQUIRED_ROLES, REQUIRED_VARS, preflight
from charterhouse.env.types import (
    EmbedModelMismatch,
    EndpointUnreachable,
    EnvError,
    InsufficientHeadroom,
    KDisciplineError,
    MissingEnvVar,
    PathNotWritable,
    RouteUnresolvable,
    VectorStoreError,
)

__all__ = [
    "EnvContext",
    "PathKind",
    "env_key_lookup",
    "load_env_file",
    "preflight",
    "REQUIRED_ROLES",
    "REQUIRED_VARS",
    "EmbedModelMismatch",
    "EndpointUnreachable",
    "EnvError",
    "InsufficientHeadroom",
    "KDisciplineError",
    "MissingEnvVar",
    "PathNotWritable",
    "RouteUnresolvable",
    "VectorStoreError",
]
