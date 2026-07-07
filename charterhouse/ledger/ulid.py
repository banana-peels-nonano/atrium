"""Monotonic ULID id factory (stdlib only) — the default ``Ledger`` id source.

A ULID is a 128-bit, lexicographically-sortable id: 48-bit millisecond timestamp + 80-bit
randomness, Crockford base32 (26 chars). Sorting ids therefore sorts events chronologically,
which gives the Ledger a **total order independent of file segmentation** (docs/32, ledger
IMPLEMENTATION §3). Within a single millisecond the factory increments the random component so
strictly-increasing order holds under bursty single-writer appends.

Determinism note: id generation is a *side-effecting* concern (time + randomness), deliberately
isolated behind an injectable factory so ``Ledger.replay`` stays a pure fold. Tests inject a
deterministic counter factory instead (see ``tests/unit/_a3_support.py``).
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_RAND_MASK = (1 << 80) - 1


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(out))


def monotonic_ulid_factory() -> Callable[[], str]:
    """Return a thread-safe callable producing strictly-increasing ULIDs."""
    lock = threading.Lock()
    state = {"ms": -1, "rand": 0}

    def _next() -> str:
        with lock:
            ms = time.time_ns() // 1_000_000
            if ms <= state["ms"]:
                # Same or backward clock tick: keep the last ms and bump randomness so ids stay
                # strictly monotonic (never regress).
                ms = state["ms"]
                state["rand"] = (state["rand"] + 1) & _RAND_MASK
            else:
                state["ms"] = ms
                state["rand"] = int.from_bytes(os.urandom(10), "big") & _RAND_MASK
            return _encode(ms, 10) + _encode(state["rand"], 16)

    return _next
