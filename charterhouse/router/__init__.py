"""Router (S8) — the model-agnostic layer (docs/11; docs/40 §5; IF-2 LLMClient half).

Public surface: ``LLMClient``/``Router`` (``call(role, messages, tools?, require?)``),
the ``Require``/``LLMResponse`` shapes, the S8 error taxonomy, and the adapters. The PII
refusal type (``PIIRouteBlocked``) and ``Context`` are S7's, re-exported for seam callers.
"""

from charterhouse.router.facade import LLMClient, Router
from charterhouse.router.types import (
    Context,
    LLMResponse,
    NoEligibleModel,
    PIIRouteBlocked,
    ProvidersExhausted,
    Require,
    RouterError,
)

__all__ = [
    "LLMClient",
    "Router",
    "Context",
    "LLMResponse",
    "NoEligibleModel",
    "PIIRouteBlocked",
    "ProvidersExhausted",
    "Require",
    "RouterError",
]
