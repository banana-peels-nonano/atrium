"""S13 briefs — Daily, Gate, Kill-Day (projections/API.md; docs/05 shapes).

The Gate Brief is THE fixed schema (INV-COND-2): assembly refuses (``NoCriticForGate``)
when the venture's history holds no critic take — a schema-broken brief cannot exist.
The mechanical recommendation is an advisory ledger-fact fold (ADVANCE/HOLD/KILL);
the founder's ``gate`` decision is the authority.

Determinism (docs/61 §INV-DET): pure functions of the ledger; time = event
``active_time``/recorded day strings; no wall clock, no writes, no LLM.
"""

from __future__ import annotations

from collections import Counter

from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State, Venture
from charterhouse.ledger import Ledger

from charterhouse.projections.types import (
    CriticTake,
    DailyBrief,
    GateBrief,
    KillDayBrief,
    NoCriticForGate,
    UnknownVenture,
)
from charterhouse.projections.board import pipeline

__all__ = ["daily_brief", "gate_brief", "killday_brief"]

# Terminal states: outside the kill-day walk (docs/05 — every ACTIVE venture).
_TERMINAL = frozenset({State.KILLED, State.ARCHIVED, State.EXITED})


def _venture_events(ledger: Ledger, venture_id: str) -> list[Event]:
    return [e for e in ledger.read() if e.venture_id == venture_id]


def _critic_take(events: list[Event], venture_id: str) -> CriticTake:
    """The latest artifact_produced critic tier, else the latest gate_decision's —
    none → NoCriticForGate (INV-COND-2 fail-closed)."""
    for e in reversed(events):
        if e.type is EventType.ARTIFACT_PRODUCED:
            return CriticTake(tier=int(e.payload["critic_tier"]),
                              artifact_ref=e.payload.get("artifact_ref"))
    for e in reversed(events):
        if e.type is EventType.GATE_DECISION and "critic_tier" in e.payload:
            return CriticTake(tier=int(e.payload["critic_tier"]), artifact_ref=None)
    raise NoCriticForGate(
        f"no critic take on record for venture {venture_id!r} — no gate is "
        "presentable without one (INV-COND-2)")


def _evidence_facts(events: list[Event]) -> tuple[str, ...]:
    facts = []
    for e in events:
        if e.type is EventType.EVIDENCE_GATE:
            facts.append(f"evidence:{e.payload.get('verdict')}"
                         f"({e.payload.get('quote_count')} quotes)")
        elif e.type is EventType.EXPERIMENT_RESULT:
            facts.append(f"experiment:{e.payload.get('metric')}:"
                         f"{e.payload.get('verdict')}")
    return tuple(facts)


def _recommendation(events: list[Event]) -> str:
    """Advisory fold (IMPLEMENTATION §6.2): any latest-per-kind FAIL → KILL; a PASS
    evidence bar (or a PASS experiment) with no FAIL → ADVANCE; no verdicts → HOLD."""
    latest_evidence: str | None = None
    latest_experiments: dict[str, str] = {}
    for e in events:
        if e.type is EventType.EVIDENCE_GATE:
            latest_evidence = str(e.payload.get("verdict"))
        elif e.type is EventType.EXPERIMENT_RESULT:
            latest_experiments[str(e.payload.get("metric"))] = \
                str(e.payload.get("verdict"))
    verdicts = ([latest_evidence] if latest_evidence else []) \
        + list(latest_experiments.values())
    if not verdicts:
        return "HOLD"
    if any(v == "FAIL" for v in verdicts):
        return "KILL"
    if any(v == "PASS" for v in verdicts):
        return "ADVANCE"
    return "HOLD"


def gate_brief(ledger: Ledger, venture_id: str) -> GateBrief:
    """The fixed schema for one venture — critic mandatory (INV-COND-2)."""
    world = ledger.replay()
    v: Venture | None = world.ventures.get(venture_id)
    if v is None:
        raise UnknownVenture(f"no ledger history for venture {venture_id!r}")
    events = _venture_events(ledger, venture_id)
    critic = _critic_take(events, venture_id)  # may raise NoCriticForGate
    artifacts = tuple(e.payload["artifact_ref"] for e in events
                      if e.type is EventType.ARTIFACT_PRODUCED
                      and e.payload.get("artifact_ref"))
    return GateBrief(
        venture_id=venture_id,
        codename=v.codename,
        state=v.state,
        score=v.score,
        active_in_state=v.state_entered_at,
        evidence=_evidence_facts(events),
        artifacts=artifacts,
        critic=critic,
        recommendation=_recommendation(events),
    )


def daily_brief(ledger: Ledger, day: str | None = None) -> DailyBrief:
    """The triaged docs/05 brief — ≤3 decisions (briefable ventures whose advisory is
    not HOLD), the RED queue, pending sends, board glance. Silence is valid."""
    board = pipeline(ledger)
    decisions: list[str] = []
    red_queue: list[str] = []
    for row in board.rows:
        if row.state in _TERMINAL:
            continue
        try:
            brief = gate_brief(ledger, row.venture_id)
        except NoCriticForGate:
            continue  # not gate-presentable yet — not a decision (INV-COND-2)
        if brief.recommendation == "KILL":
            red_queue.append(f"{row.venture_id}: KILL recommended at "
                             f"{row.state.value}")
        if brief.recommendation != "HOLD" and len(decisions) < 3:
            decisions.append(f"{row.venture_id}: {brief.recommendation} at the "
                             f"{row.state.value} gate")
    sends: Counter[str] = Counter()
    for e in ledger.read():
        if e.type is EventType.SEND_BATCH:
            batch_day = (e.timestamp or "unknown")[:10]
            if day is None or batch_day == day:
                sends[batch_day] += int(e.payload.get("count") or 0)
    return DailyBrief(decisions=tuple(decisions), red_queue=tuple(red_queue),
                      pending_sends=tuple(sorted(sends.items())), board=board)


def killday_brief(ledger: Ledger) -> KillDayBrief:
    """Every ACTIVE venture as (GateBrief, recommendation); unbriefable ventures
    named, never dropped (docs/05 kill-day)."""
    rows = []
    unbriefable = []
    for row in pipeline(ledger).rows:
        if row.state in _TERMINAL:
            continue
        try:
            brief = gate_brief(ledger, row.venture_id)
        except NoCriticForGate:
            unbriefable.append(row.venture_id)
            continue
        rows.append((brief, brief.recommendation))
    return KillDayBrief(rows=tuple(rows), unbriefable=tuple(unbriefable))
