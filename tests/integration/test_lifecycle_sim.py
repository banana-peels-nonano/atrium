"""S5 × S4 × S6 lifecycle simulation — the three Stress-Test scenarios (docs/prd/4,
docs/55 §3) driven end-to-end over the real Ledger + Registry + Gov + Lifecycle.

Each test walks a venture (or three) through the docs/42 machine exactly as the Conductor
will, asserting the expected end states, the key ledger events, and the v1.1 revision
behaviors the scenario was designed to expose (R-SLOT-GATE, R-CLOCK, R-OMW-LEDGER,
R-OVERRIDE-LOG, R-SALVAGE-TYPES, R-SHAPING-WIP, R-EVIDENCE-TTL, R-PIVOT).
"""

from __future__ import annotations

import pytest

from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State as S
from charterhouse.ledger import EventFilter
from charterhouse.lifecycle import (
    ExpressRefused,
    ForkCapExceeded,
    GuardFailed,
    OmwExhausted,
    SlotLimitExceeded,
    StaleEvidence,
)

from tests.unit import _a4_support as sup


@pytest.fixture
def sim(tmp_path) -> sup.Sim:
    return sup.Sim(tmp_path)


def test_sim_a_battlecard_happy_path(sim):
    """Stress-Test A (`battlecard`): the happy path Capture→HARVEST, with the v1.1 rules
    live — express is refused for the SHAPING slot-grab (R-SLOT-GATE / DEFECT A4) and
    permitted only for LAUNCHED→EARNING; graduation clears the alumni-capacity gate
    (R-ALUMNI-CEILING / DEFECT A8)."""
    sim.new("battlecard")
    sim.clock.advance(2)
    sim.frame("battlecard", score=20, quotes=3)   # Day 2: score 20/25, gut-yes
    sim.admit("battlecard")                        # validating slot free -> admitted
    sup.go_live(sim.ledger, sim.clock, "battlecard")
    sim.clock.advance(12)                          # Day 14: 5.4% > 4% threshold
    sim.pass_validation("battlecard")
    # DEFECT A4 / R-SLOT-GATE: a mid-week express grab of the on-deck slot is refused.
    with pytest.raises(ExpressRefused):
        sim.advance("battlecard", S.SHAPING, "advance.express", express=True)
    sim.advance("battlecard", S.SHAPING, "gate")   # deliberate gate instead
    sup.spec_approved(sim.ledger, sim.clock, "battlecard")
    sup.partners(sim.ledger, sim.clock, "battlecard", 5)  # R-PARTNERS: lined up in SHAPING
    sim.clock.advance(3)                           # Day 17: spec approved, <=10 days
    sim.advance("battlecard", S.BUILDING, "gate")
    sim.clock.advance(9)                           # Day 27: partners complete the loop
    sim.advance("battlecard", S.LAUNCHED, "gate")
    sim.clock.advance(13)                          # Day 41: 14 activated, payment-intent
    sup.exp_result(sim.ledger, sim.clock, "battlecard", "activation", "PASS")
    # The one legal express advance (non-slot-consuming).
    sim.advance("battlecard", S.EARNING, "advance.express", express=True)
    sim.clock.advance(46)                          # Day 88: 12 payers in 46 active days
    sup.exp_result(sim.ledger, sim.clock, "battlecard", "payers", "PASS")
    sim.advance("battlecard", S.GRADUATED, "graduate")  # alumni capacity 0/3 -> ok
    sim.advance("battlecard", S.SCALING, "gate")
    sim.advance("battlecard", S.HARVEST, "gate")
    assert sim.v("battlecard").state is S.HARVEST
    assert sim.life.slots().harvest == (1, 3)
    # Exactly one express transition happened, and it is EARNING entry.
    express = [e for e in sim.ledger.read()
               if e.payload.get("gate_type") == "express"]
    assert len(express) == 1 and express[0].to_state == S.EARNING.value


def test_sim_b_hvac_route_messy_death(sim):
    """Stress-Test B (`hvac-route`): the messy validation death — admission override
    logged (R-OVERRIDE-LOG / B1), deadline from experiment-live not entry (R-CLOCK / B3),
    exactly one ONE-MORE-WEEK ever (R-OMW-LEDGER / B5), salvage required before ARCHIVED
    with the anti-pattern as a first-class asset (R-SALVAGE-TYPES / B6)."""
    sim.new("hvac-route")
    sim.clock.advance(3)
    sim.frame("hvac-route", score=17, quotes=2)    # 17 < 18: backlog, not auto-advance
    with pytest.raises(GuardFailed):
        sim.admit("hvac-route")                    # no override yet -> refused
    sim.gov.record_override("admission", "backlog", "admit",
                            "founder has a direct contact in the trade", "hvac-route")
    sim.admit("hvac-route")                        # B1: override logged, then admitted
    entry_day = sim.clock.now_active
    sim.clock.advance(5)                           # domain warming: setup latency
    sup.go_live(sim.ledger, sim.clock, "hvac-route")
    at = sim.life.clock(sim.v("hvac-route"))
    assert at.deadline_at == entry_day + 5 + 14    # B3/R-CLOCK: from live, not entry
    sim.clock.advance(14)
    sup.exp_result(sim.ledger, sim.clock, "hvac-route", "booked_calls", "FAIL",
                   actual=3, threshold=5)
    with pytest.raises(GuardFailed):               # failed experiment cannot advance
        sim.advance("hvac-route", S.SHAPING, "gate")
    sim.life.grant_omw(sim.v("hvac-route"), sim.mint("gate", "hvac-route"))  # B4: OMW
    sim.clock.advance(7)
    sup.exp_result(sim.ledger, sim.clock, "hvac-route", "booked_calls", "FAIL",
                   actual=4, threshold=5)
    with pytest.raises(OmwExhausted):              # B5/R-OMW-LEDGER: max one, ever
        sim.life.grant_omw(sim.v("hvac-route"), sim.mint("gate", "hvac-route"))
    sim.kill("hvac-route",
             reason="experiment threshold missed twice; offline trade unreachable by cold email")
    with pytest.raises(GuardFailed):               # B6: no salvage banked yet
        sim.advance("hvac-route", S.ARCHIVED, None)
    sup.salvage(sim.ledger, sim.clock, "hvac-route", ("anti_pattern", "audience"))
    sim.advance("hvac-route", S.ARCHIVED, None)
    assert sim.v("hvac-route").state is S.ARCHIVED
    omws = list(sim.ledger.read(EventFilter(type=EventType.OMW_GRANT)))
    assert len(omws) == 1
    overrides = list(sim.ledger.read(EventFilter(venture_id="hvac-route",
                                                 type=EventType.OVERRIDE)))
    assert len(overrides) == 1 and overrides[0].payload["reason"]


def test_sim_c_clipscribe_pivot_concurrency(sim):
    """Stress-Test C (`clipscribe`): slot contention (R-SHAPING-WIP / C1), evidence TTL
    (R-EVIDENCE-TTL / C2), and the pivot path (R-PIVOT / C4-C5) — kill-and-fork with
    inheritance, fork at FRAMED with no queue jump, hard cap one fork per lineage."""
    # battlecard occupies the single build slot.
    for vid in ("battlecard", "clipscribe", "notesly"):
        sim.new(vid)
        sim.frame(vid, score=19)
    sim.admit("battlecard"); sim.pass_validation("battlecard")
    sim.advance("battlecard", S.SHAPING, "gate")
    sup.spec_approved(sim.ledger, sim.clock, "battlecard")
    sup.partners(sim.ledger, sim.clock, "battlecard", 5)
    sim.advance("battlecard", S.BUILDING, "gate")
    # clipscribe passes validation and takes the on-deck slot.
    sim.admit("clipscribe"); sim.pass_validation("clipscribe")
    sim.advance("clipscribe", S.SHAPING, "gate")
    # C1/R-SHAPING-WIP: notesly passes too -> SHAPING refused, shovel-ready with TTL.
    sim.admit("notesly"); sim.pass_validation("notesly")
    with pytest.raises(SlotLimitExceeded):
        sim.advance("notesly", S.SHAPING, "gate")
    sim.advance("notesly", S.PARKED_SHOVEL_READY, None)
    ttl_at = sim.v("notesly").evidence_ttl_at
    assert ttl_at == sim.clock.now_active + 60     # C2/R-EVIDENCE-TTL stamped
    # Build slot contention: clipscribe must wait for battlecard.
    sup.spec_approved(sim.ledger, sim.clock, "clipscribe")
    with pytest.raises(SlotLimitExceeded):
        sim.advance("clipscribe", S.BUILDING, "gate")
    sim.clock.advance(9)
    sim.advance("battlecard", S.LAUNCHED, "gate")  # frees the build slot
    sim.advance("clipscribe", S.BUILDING, "gate")
    sup.partners(sim.ledger, sim.clock, "clipscribe", 5)
    sim.clock.advance(12)
    sim.advance("clipscribe", S.LAUNCHED, "gate")
    # Below the bar: 6 activated, 0 payment-intent -> cannot advance to EARNING.
    sup.exp_result(sim.ledger, sim.clock, "clipscribe", "activation", "FAIL",
                   actual=6, threshold=10)
    with pytest.raises(GuardFailed):
        sim.advance("clipscribe", S.EARNING, "gate")
    # C4/R-PIVOT: kill-and-fork instead of zombie-or-lose.
    slots_before = sim.life.slots()
    res = sim.life.pivot(
        sim.v("clipscribe"), sim.mint("pivot", "clipscribe"), new_id="showscribe",
        codename="showscribe",
        inherited={"audience": "podcaster-waitlist-ref", "segment": "podcasters-validated"},
        reason="podcasters want automated show-notes, not clips")
    assert sim.v("clipscribe").state is S.KILLED
    fork = sim.v("showscribe")
    assert fork.state is S.FRAMED and fork.forked_from == "clipscribe"
    assert sim.life.slots() == slots_before        # C5: no slot grabbed, no queue jump
    # The fork is re-scored and walks the pipeline like any venture...
    sim.gov.record_override("score", "n/a", "rescore", "fork re-scored on inherited audience",
                            "showscribe", old_score=None, new_score=19)
    sim.admit("showscribe"); sim.pass_validation("showscribe")
    sim.advance("showscribe", S.SHAPING, "gate")   # clipscribe freed the on-deck slot
    sup.spec_approved(sim.ledger, sim.clock, "showscribe")
    sim.advance("showscribe", S.BUILDING, "gate")
    sup.partners(sim.ledger, sim.clock, "showscribe", 5)
    sim.advance("showscribe", S.LAUNCHED, "gate")
    # ...but a second pivot of the lineage is refused (C4 hard cap, ledger-checked).
    with pytest.raises(ForkCapExceeded):
        sim.life.pivot(sim.v("showscribe"), sim.mint("pivot", "showscribe"),
                       new_id="showscribe-2", codename="again",
                       inherited={"audience": "podcaster-waitlist-ref"},
                       reason="second pivot must clear fresh validation")
    # C2 close-out: notesly waited past TTL -> stale until re-confirmed.
    sim.clock.advance(61)
    with pytest.raises(StaleEvidence):
        sim.advance("notesly", S.SHAPING, "gate")
    sup.evidence(sim.ledger, sim.clock, "notesly", "PASS")  # cheap re-confirmation
    sim.advance("notesly", S.SHAPING, "gate")
    # End states: the whole board is where the stress test says it should be.
    assert sim.v("battlecard").state is S.LAUNCHED
    assert sim.v("clipscribe").state is S.KILLED
    assert sim.v("showscribe").state is S.LAUNCHED
    assert sim.v("notesly").state is S.SHAPING
    forks = list(sim.ledger.read(EventFilter(type=EventType.PIVOT_FORK)))
    assert len(forks) == 1 and forks[0].payload["inherited"]["audience"]
