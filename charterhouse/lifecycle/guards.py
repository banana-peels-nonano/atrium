"""S5 guard functions — one pure function per named docs/42 §3 guard (IMPLEMENTATION §3).

Each guard is ``(facts: Facts) -> str | None``: ``None`` = holds, a string = the refusal
reason. Objective guards read only the ledger fact events (lifecycle/API.md §Guard
facts), the projection, and the clock; judgment guards check the founder's non-empty
``reason`` (IMPLEMENTATION §6.2).

Determinism (docs/61 §INV-DET): stdlib + contracts only; no LLM.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import Venture

from charterhouse.lifecycle.types import LifecycleLimits, SlotState

# BUILDING's exit bar: "5 design partners complete loop unassisted" (docs/42 §3;
# recruitment is the deterministic proxy — completion is the founder's gate judgment).
DESIGN_PARTNERS_REQUIRED = 5


@dataclass(frozen=True)
class Facts:
    """Everything a guard may consult — assembled once per check by the facade."""

    venture: Venture
    events: tuple[Event, ...]  # the venture's ledger stream, in total order
    slots: SlotState
    now_active: int
    limits: LifecycleLimits
    payload: dict = field(default_factory=dict)
    reason: str | None = None


def _latest(events: tuple[Event, ...], et: EventType,
            metrics: frozenset[str] | None = None) -> Event | None:
    for e in reversed(events):
        if e.type is et and (metrics is None or e.payload.get("metric") in metrics):
            return e
    return None


def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


# --- the named guards (docs/42 §3 guard column) ----------------------------------------------


def frame_payload(f: Facts) -> str | None:
    """CAPTURED→FRAMED: Scout brief exists, ≥2 primary quotes cited, integer score."""
    brief = f.payload.get("brief_ref")
    quotes = f.payload.get("quotes")
    score = f.payload.get("score")
    if not isinstance(brief, str) or not brief.strip():
        return "framing requires a brief_ref (the Scout brief)"
    if not _is_int(quotes) or quotes < 2:
        return "framing requires >=2 cited primary quotes"
    if not _is_int(score):
        return "framing requires an integer Factory Score"
    return None


def founder_reason(f: Facts) -> str | None:
    """Judgment rows (kills, archive hygiene, exits): a non-empty founder reason."""
    if not f.reason or not f.reason.strip():
        return "a founder-judgment row requires a non-empty reason"
    return None


def score_bar_or_override(f: Facts) -> str | None:
    """FRAMED→VALIDATING: score ≥18, or a logged admission override (R-OVERRIDE-LOG)."""
    if _is_int(f.venture.score) and f.venture.score >= 18:
        return None
    for e in reversed(f.events):
        if e.type is EventType.OVERRIDE and e.payload.get("decision") == "admit":
            return None
    return "score below 18 and no logged admission override"


def score_bar(f: Facts) -> str | None:
    """FRAMED→PARKED: score ≥18 (the park row is for slot overflow, not weak ideas)."""
    if _is_int(f.venture.score) and f.venture.score >= 18:
        return None
    return "score below 18 — the backlog park row is for slot overflow only"


def validating_full(f: Facts) -> str | None:
    """FRAMED→PARKED overflow condition: only when no validating slot is free."""
    if f.slots.free("validating"):
        return "a validating slot is free — admit at the gate, do not park"
    return None


def shaping_occupied(f: Facts) -> str | None:
    """VALIDATING→PARKED_SHOVEL_READY overflow condition: only when SHAPING is taken."""
    if f.slots.free("shaping"):
        return "SHAPING is free — advance at the gate, do not overflow"
    return None


def sub_gates(f: Facts) -> str | None:
    """VALIDATING exits (R-EVIDENCE-GATE): Evidence sub-gate PASS AND Experiment
    sub-gate PASS — a venture can die at either, so both must currently stand PASSed."""
    ev = _latest(f.events, EventType.EVIDENCE_GATE)
    if ev is None or ev.payload.get("verdict") != "PASS":
        return "Evidence sub-gate has not PASSed"
    ex = _latest(f.events, EventType.EXPERIMENT_RESULT)
    if ex is None or ex.payload.get("verdict") != "PASS":
        return "Experiment sub-gate has not PASSed"
    return None


def evidence_fresh(f: Facts) -> str | None:
    """PARKED_SHOVEL_READY→SHAPING (INV-SM-6): evidence age ≤ TTL, or a re-confirmation
    signal (a fresh evidence_gate PASS within TTL of now)."""
    ttl_at = f.venture.evidence_ttl_at
    if ttl_at is not None and f.now_active <= ttl_at:
        return None
    ev = _latest(f.events, EventType.EVIDENCE_GATE)
    if (ev is not None and ev.payload.get("verdict") == "PASS"
            and ev.active_time is not None
            and ev.active_time + f.limits.evidence_ttl_days >= f.now_active):
        return None
    return "shovel-ready evidence past TTL; re-confirmation required before BUILDING path"


def evidence_stale(f: Facts) -> str | None:
    """PARKED_SHOVEL_READY→VALIDATING: the mini re-validation row is the *stale* path."""
    ttl_at = f.venture.evidence_ttl_at
    if ttl_at is not None and f.now_active > ttl_at:
        return None
    return "evidence still within TTL — advance to SHAPING instead of re-validating"


def spec_approved(f: Facts) -> str | None:
    """SHAPING→BUILDING: an approved spec exists (`spec_approved` event)."""
    if _latest(f.events, EventType.SPEC_APPROVED) is None:
        return "no approved spec on the ledger"
    return None


def shaping_window(f: Facts) -> str | None:
    """SHAPING→BUILDING: ≤10 active-days in SHAPING (INV-SM-3 state window)."""
    entered = f.venture.state_entered_at
    if entered is None:
        return "SHAPING entry time unknown — cannot verify the 10-active-day window"
    if f.now_active - entered > f.limits.shaping_max_days:
        return (f"{f.now_active - entered} active-days in SHAPING exceeds the "
                f"{f.limits.shaping_max_days}-day window")
    return None


def partners_recruited(f: Facts) -> str | None:
    """BUILDING→LAUNCHED (R-PARTNERS): ≥5 design partners recruited (cumulative)."""
    total = sum(e.payload.get("recruited_count", 0)
                for e in f.events if e.type is EventType.PARTNERS)
    if total < DESIGN_PARTNERS_REQUIRED:
        return (f"{total} design partners recruited; "
                f"{DESIGN_PARTNERS_REQUIRED} must complete the loop")
    return None


def activation_pass(f: Facts) -> str | None:
    """LAUNCHED→EARNING: the activation bar (≥10 activated + payment-intent) PASSed."""
    e = _latest(f.events, EventType.EXPERIMENT_RESULT, frozenset({"activation"}))
    if e is None or e.payload.get("verdict") != "PASS":
        return "activation bar not PASSed (>=10 activated + payment-intent in window)"
    return None


def traction_in_window(f: Facts) -> str | None:
    """EARNING→GRADUATED: $1k MRR or 10 payers PASSed within 60 active-days of EARNING
    entry."""
    e = _latest(f.events, EventType.EXPERIMENT_RESULT, frozenset({"mrr", "payers"}))
    if e is None or e.payload.get("verdict") != "PASS":
        return "graduation traction bar not PASSed (mrr or payers)"
    entered = f.venture.state_entered_at
    if entered is None or e.active_time is None:
        return "EARNING entry / traction timing unknown — cannot verify the 60-day window"
    if e.active_time > entered + f.limits.graduation_window_days:
        return "traction PASS fell outside the 60-active-day graduation window"
    return None


def salvage_banked(f: Facts) -> str | None:
    """KILLED→ARCHIVED (R-SALVAGE-TYPES): ≥1 salvage asset banked (anti-patterns count)."""
    for e in reversed(f.events):
        if e.type is EventType.SALVAGE and e.payload.get("asset_types"):
            return None
    return "no salvage asset banked — every kill must bank at least one asset"


GUARDS: dict[str, Callable[[Facts], str | None]] = {
    fn.__name__: fn
    for fn in (
        frame_payload, founder_reason, score_bar_or_override, score_bar,
        validating_full, shaping_occupied, sub_gates, evidence_fresh, evidence_stale,
        spec_approved, shaping_window, partners_recruited, activation_pass,
        traction_in_window, salvage_banked,
    )
}


def evaluate(guard_names: tuple[str, ...], facts: Facts) -> dict[str, str]:
    """Run the named guards; return ``{guard_name: refusal_reason}`` for every failure
    (empty = all hold). An unknown guard name is a table bug → fail closed loudly."""
    failures: dict[str, str] = {}
    for name in guard_names:
        reason = GUARDS[name](facts)
        if reason is not None:
            failures[name] = reason
    return failures
