"""S15 shared test doubles (docs/55 §2; logging/API.md — the frozen harness surface).

The fakes every agent's tests import. Each exposes the *same signature* as the subsystem
it doubles (fake↔real parity, RISKS R3); ``InMemoryLedger`` is the strongest form — it is
a ``Ledger`` subclass over an ephemeral temp dir, so it cannot drift from IF-1 in either
signature or semantics. ``Simulator`` is shape-only until S10/S12 (docs/55 §3).
"""

from tests.fakes.clock import Clock
from tests.fakes.embedder import FakeEmbedder
from tests.fakes.ledger import InMemoryLedger
from tests.fakes.provider import FakeProvider, ProviderError, RateLimited
from tests.fakes.safety import RealActionBlocked, guard_real_action
from tests.fakes.simulator import Simulator

__all__ = [
    "Clock",
    "FakeEmbedder",
    "InMemoryLedger",
    "FakeProvider",
    "ProviderError",
    "RateLimited",
    "RealActionBlocked",
    "guard_real_action",
    "Simulator",
]
