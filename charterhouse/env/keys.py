"""Provider secret lookup — the A1 env seam for keys (docs/24; router IMPLEMENTATION §6.1).

The real model transport reads no environment (docs/20 env-boundary); it takes an injected
``key_lookup(name)`` callable. THIS module builds that callable — under ``charterhouse/env/``,
the sole place permitted to read ``os.environ`` (the env-boundary scan exempts it). The
secret is returned by name and NEVER logged; ``Provider.key_env`` stays a name everywhere
else. The Conductor wires this into the transport at composition time (the §6.1 resolution).

Determinism (docs/61 §INV-DET): stdlib + env-package types only; no LLM, no router import.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from charterhouse.env.types import MissingEnvVar

__all__ = ["env_key_lookup"]


def env_key_lookup(env: Mapping[str, str] | None = None) -> Callable[[str], str]:
    """Return a ``key_lookup(name) -> secret`` bound to ``env`` (the real ``os.environ``
    when ``None``; tests inject a mapping). A missing/empty var raises ``MissingEnvVar``
    naming ONLY the variable, never the value; the returned callable performs no logging."""
    source: Mapping[str, str] = os.environ if env is None else env

    def lookup(name: str) -> str:
        value = source.get(name)
        if not value:  # unset or empty — refuse the same way, naming only the var
            raise MissingEnvVar(
                f"required secret env var {name} is unset; set it in the environment "
                "(never commit it) and restart — the transport reads keys only by this "
                "name (docs/24)")
        return value

    return lookup
