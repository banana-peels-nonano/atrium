"""Config (S3) — typed, validated, immutable behavioral configuration (docs/25, docs/40 §1).

Public surface: ``Config`` (``load`` + ``get_route/get_model/get_provider/profile/
budgets``) and the S3 error taxonomy. Shared value types ``Route/Model/Provider/Budgets``
come from ``charterhouse.contracts`` (frozen IF-2 Config half).
"""

from charterhouse.config.facade import Config
from charterhouse.config.types import (
    Budgets,
    ConfigError,
    LocatedError,
    Model,
    Provider,
    Route,
    UnknownModel,
    UnknownProfile,
    UnknownProvider,
    UnknownRole,
)

__all__ = [
    "Config",
    "Budgets",
    "ConfigError",
    "LocatedError",
    "Model",
    "Provider",
    "Route",
    "UnknownModel",
    "UnknownProfile",
    "UnknownProvider",
    "UnknownRole",
]
