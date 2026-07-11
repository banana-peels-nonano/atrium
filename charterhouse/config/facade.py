"""``Config`` — the immutable S3 facade (docs/40 §1 frozen surface; config/API.md).

A pure loader over files: ``Config.load(config_dir, profile)`` returns the same frozen
``Config`` every time. Exposes ``get_route/get_model/get_provider/profile/budgets``.
Holds no secret *values* (``Provider.key_env`` is the env-var name; the Router reads the
secret at call time, docs/24) and reads no environment variables (docs/20 — A1's job).

Determinism (docs/61 §INV-DET): stdlib + contracts + pinned pyyaml only; no LLM.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from charterhouse.contracts.config_types import Budgets, Model, Provider, Route

from charterhouse.config.loader import resolve
from charterhouse.config.types import (
    UnknownModel,
    UnknownProvider,
    UnknownRole,
)


class Config:
    """An immutable, validated view of the committed config (config/API.md). Construct
    only via ``Config.load`` — the constructor takes already-resolved, frozen tables."""

    def __init__(
        self,
        *,
        providers: Mapping[str, Provider],
        models: Mapping[str, Model],
        routes: Mapping[str, Route],
        budgets: Budgets,
        profile: str,
    ) -> None:
        # Read-only views; the frozen dataclass values are already immutable.
        self._providers = MappingProxyType(dict(providers))
        self._models = MappingProxyType(dict(models))
        self._routes = MappingProxyType(dict(routes))
        self._budgets = budgets
        self._profile = profile

    @classmethod
    def load(cls, config_dir: str | Path, profile: str | None = None,
             overrides: Mapping | None = None) -> "Config":
        """Parse + validate + cross-ref (INV-CFG) + apply precedence + freeze. Located
        error on any malformed/dangling/unknown input; never a partial Config."""
        providers, models, routes, budgets, active = resolve(
            Path(config_dir), profile, overrides)
        return cls(providers=providers, models=models, routes=routes,
                   budgets=budgets, profile=active)

    def get_route(self, role: str) -> Route:
        """Resolved route for ``role`` under the active profile. ``UnknownRole`` if absent."""
        try:
            return self._routes[role]
        except KeyError:
            raise UnknownRole(
                f"no route for role {role!r}; known roles: {sorted(self._routes)}") from None

    def get_model(self, id: str) -> Model:
        """Catalog entry for ``id``. ``UnknownModel`` if absent (no guessed default)."""
        try:
            return self._models[id]
        except KeyError:
            raise UnknownModel(f"no model {id!r} in models.yaml") from None

    def get_provider(self, id: str) -> Provider:
        """Endpoint for ``id``; ``key_env`` is a name, never a secret. ``UnknownProvider``."""
        try:
            return self._providers[id]
        except KeyError:
            raise UnknownProvider(f"no provider {id!r} in providers.yaml") from None

    @property
    def profile(self) -> str:
        """The active profile name."""
        return self._profile

    @property
    def budgets(self) -> Budgets:
        """Budgets resolved under the active profile."""
        return self._budgets
