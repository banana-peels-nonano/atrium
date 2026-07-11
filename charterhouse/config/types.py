"""Config (S3) error taxonomy + re-export of the frozen IF-2 shared types (config/API.md).

The value shapes ``Route/Model/Provider/Budgets`` are the frozen IF-2 (Config half) types
and live once in ``charterhouse/contracts/config_types.py`` (docs/43 §6); they are
re-exported here for callers that import from the subsystem package.

Determinism (docs/61 §INV-DET): stdlib + contracts only; no ``router`` / ``memory`` /
``capabilities``; no LLM; no environment read (docs/20 — env is A1's alone).
"""

from __future__ import annotations

from charterhouse.contracts.config_types import Budgets, Model, Provider, Route

__all__ = [
    "Budgets",
    "Model",
    "Provider",
    "Route",
    "ConfigError",
    "LocatedError",
    "UnknownRole",
    "UnknownModel",
    "UnknownProvider",
    "UnknownProfile",
]


class ConfigError(Exception):
    """Base class for every S3 load/lookup failure (fail closed, docs/61)."""


class LocatedError(ConfigError):
    """A validation failure that names *where* it is — file + key path (+ line when the
    YAML parser gives one). Raised for syntax errors, unknown keys, missing required
    keys, and dangling ``INV-CFG`` references. No partial ``Config`` is ever returned."""

    def __init__(self, message: str, *, file: str, where: str | None = None,
                 line: int | None = None) -> None:
        self.file = file
        self.where = where
        self.line = line
        location = file if line is None else f"{file}:{line}"
        if where:
            location = f"{location} at {where}"
        super().__init__(f"{location}: {message}")


class UnknownRole(ConfigError):
    """``get_route`` for a role absent from the resolved routes (no guessed default)."""


class UnknownModel(ConfigError):
    """``get_model`` for a model id absent from ``models.yaml`` (no guessed default)."""


class UnknownProvider(ConfigError):
    """``get_provider`` for a provider id absent from ``providers.yaml``."""


class UnknownProfile(ConfigError):
    """``load`` requested a profile with no matching file under ``profiles/``."""
