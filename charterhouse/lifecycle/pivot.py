"""S5 pivot orchestration — kill-and-fork (INV-SM-5; docs/42 §5, R-PIVOT) + the lineage
walk shared with the OMW cap (R-OMW-LEDGER).

The lineage is the ``forked_from`` chain: two ventures share a lineage iff they walk up
to the same root. Caps are checked against the *ledger* (never memory): the fold here
asks "does any ``pivot_fork``/``omw_grant`` event belong to this lineage?". The S4
per-venture replay cap remains the backstop (IMPLEMENTATION §6.7).

Determinism (docs/61 §INV-DET): stdlib + contracts only; no LLM.
"""

from __future__ import annotations

from charterhouse.contracts.events import EventType
from charterhouse.ledger import EventFilter, Ledger
from charterhouse.registry.facade import Registry

_MAX_LINEAGE_DEPTH = 64  # defensive bound; a factory lineage is 1-2 links deep


def lineage_root(registry: Registry, venture_id: str) -> str:
    """Walk ``forked_from`` links up to the lineage root (cycle-bounded, fail closed)."""
    vid = venture_id
    for _ in range(_MAX_LINEAGE_DEPTH):
        v = registry.get(vid)
        if v is None or v.forked_from is None:
            return vid
        vid = v.forked_from
    raise ValueError(f"forked_from chain from {venture_id!r} exceeds "
                     f"{_MAX_LINEAGE_DEPTH} links — refusing to guess a lineage root")


def lineage_has(ledger: Ledger, registry: Registry, venture_id: str,
                event_type: EventType) -> bool:
    """True iff any ``event_type`` event in the ledger belongs to ``venture_id``'s
    lineage — the once-per-lineage cap check (INV-SM-5, R-OMW-LEDGER)."""
    root = lineage_root(registry, venture_id)
    for e in ledger.read(EventFilter(type=event_type)):
        if e.venture_id is not None and lineage_root(registry, e.venture_id) == root:
            return True
    return False
