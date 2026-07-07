"""Registry (S4) — the projection half: "what ventures exist and in what state?" as a pure
view of the ledger (docs/40 §2, IF-1; INV-LEDGER: ``Registry == Ledger.replay()``).

Holds no source-of-truth state and applies no lifecycle *rules* (legality/WIP/clocks are S5) —
it only reflects the replayed result. The event→``Venture`` fold is owned by ``Ledger.replay``
(docs/40 §2); this facade builds a fresh index from ``replay()`` on each call, so it can never
serve stale or independently-mutated state (cache discipline, IMPLEMENTATION §3). A Ledger chain
break surfaces here as ``ChainBroken`` (fail closed) rather than returning guessed state.

Determinism (docs/61 §INV-DET): stdlib only; imports nothing from ``router`` / ``memory`` /
``capabilities``; no LLM.
"""

from __future__ import annotations

from charterhouse.contracts.state import State, Venture
from charterhouse.ledger.store import Ledger


class Registry:
    """A read-only projection over a ``Ledger``. Any derived index is byte-reproducible from
    ``replay()`` and is never persisted as truth."""

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger

    def get(self, venture_id: str) -> Venture | None:
        """Return the current projected venture record, or ``None`` if no such venture exists in
        the replayed history (a defined, non-guessing answer). Equals ``replay()`` for that id
        (INV-LEDGER). A Ledger chain break surfaces the error (fail closed)."""
        return self._ledger.replay().ventures.get(venture_id)

    def query(self, state: State | None = None) -> list[Venture]:
        """Return all ventures (optionally filtered to ``state``) as projected from the ledger —
        the portfolio-as-view. Deterministic order (by id). Chain break = fail closed."""
        ventures = self._ledger.replay().ventures.values()
        selected = [v for v in ventures if state is None or v.state == state]
        return sorted(selected, key=lambda v: v.id)
