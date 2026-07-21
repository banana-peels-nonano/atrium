"""S13 board + metrics — pure single-pass folds over the ledger (projections/API.md).

Determinism (docs/61 §INV-DET): pure functions of ``ledger.read()``/``replay()``; no
cache, no clock, no writes, no LLM. Calling twice yields the identical value.
"""

from __future__ import annotations

from collections import Counter

from charterhouse.contracts.events import EventType
from charterhouse.ledger import Ledger

from charterhouse.projections.types import Board, BoardRow, Metrics

__all__ = ["pipeline", "metrics"]


def pipeline(ledger: Ledger) -> Board:
    """The PIPELINE board (docs/41 §3): every venture from replay, rows sorted by
    venture id, deadline flags from ledger facts."""
    world = ledger.replay()
    rows = []
    for vid in sorted(world.ventures):
        v = world.ventures[vid]
        flags: list[str] = []
        if v.evidence_ttl_at is not None:
            flags.append("evidence_ttl")
        if v.experiment_live_at is not None:
            flags.append("experiment_clock")
        if v.omw_granted:
            flags.append("omw_used")
        rows.append(BoardRow(venture_id=vid, codename=v.codename, state=v.state,
                             score=v.score, state_entered_at=v.state_entered_at,
                             flags=tuple(flags)))
    return Board(rows=tuple(rows))


def metrics(ledger: Ledger) -> Metrics:
    """Counts/rates folded from the event stream (docs/41 §3)."""
    by_state = Counter(v.state.value for v in ledger.replay().ventures.values())
    frames = kills = graduations = xp_pass = xp_fail = 0
    llm_cost = spend = 0.0
    sends: Counter[str] = Counter()
    for e in ledger.read():
        if e.type is EventType.FRAME:
            frames += 1
        elif e.type is EventType.KILL:
            kills += 1
        elif e.type is EventType.GRADUATE:
            graduations += 1
        elif e.type is EventType.EXPERIMENT_RESULT:
            if e.payload.get("verdict") == "PASS":
                xp_pass += 1
            else:
                xp_fail += 1
        elif e.type is EventType.LLM_CALL:
            llm_cost += float(e.payload.get("cost_usd") or 0.0)
        elif e.type is EventType.SPEND_METER:
            spend += float(e.payload.get("amount_usd") or 0.0)
        elif e.type is EventType.SEND_BATCH:
            day = (e.timestamp or "unknown")[:10]
            sends[day] += int(e.payload.get("count") or 0)
    return Metrics(
        by_state=tuple(sorted(by_state.items())),
        frames=frames, kills=kills, graduations=graduations,
        experiments_pass=xp_pass, experiments_fail=xp_fail,
        llm_cost_usd=llm_cost, spend_usd=spend,
        sends_by_day=tuple(sorted(sends.items())),
    )
