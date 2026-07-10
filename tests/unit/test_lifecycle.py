"""S5 Lifecycle unit suite — INV-SM-1..6 (docs/42, docs/54 §S5; lifecycle/TESTPLAN.md).

Conventions follow the A3/A5 suites: real tmp-path Ledger + Registry + merged Gov (no
fakes for merged subsystems), injected deterministic ``FactoryClock``, typed fail-closed
errors via ``pytest.raises``, INV mapping in docstrings, seeded parametrize property
tests against an independent oracle.
"""

from __future__ import annotations

import pytest

from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State
from charterhouse.ledger import EventFilter, Ledger
from charterhouse.lifecycle import (
    TRANSITIONS,
    AuthorizationDenied,
    ExpressRefused,
    ForkCapExceeded,
    GuardFailed,
    IllegalTransition,
    Lifecycle,
    LifecycleError,
    OmwExhausted,
    SlotLimitExceeded,
    StaleEvidence,
)
from charterhouse.registry.facade import Registry

from tests.unit import _a4_support as sup
from tests.unit._a4_support import EXPECTED_ROWS, FRAME_PAYLOAD, S


@pytest.fixture
def sim(tmp_path) -> sup.Sim:
    return sup.Sim(tmp_path)


def errors_for(sim: sup.Sim, vid: str) -> list:
    return list(sim.ledger.read(EventFilter(venture_id=vid, type=EventType.ERROR)))


# --- INV-SM-1: legality — the full matrix, verbatim ------------------------------------------


def test_table_matches_docs42_verbatim():
    """INV-SM-1 (table fidelity): the implemented TRANSITIONS row set equals docs/42 §3
    exactly — same (from,to) pairs, same auth scope, same slot kind, same express
    marking; no extra rows. EXPECTED_ROWS is an independent transcription of the doc."""
    assert set(TRANSITIONS.keys()) == set(EXPECTED_ROWS.keys())
    for pair, (scope, slot, express_ok) in EXPECTED_ROWS.items():
        rule = TRANSITIONS[pair]
        assert rule.auth_scope == scope, f"{pair}: auth scope"
        assert rule.slot == slot, f"{pair}: slot kind"
        assert rule.express_ok is express_ok, f"{pair}: express marking"


def test_full_matrix_legal_vs_illegal(sim):
    """INV-SM-1: every one of the 15x15 (from,to) pairs is checked. Pairs in docs/42 §3
    never raise IllegalTransition; every other pair is rejected (`can_transition` says
    no, `transition` raises IllegalTransition) AND logged (`error` event appended)."""
    n = 0
    for frm in State:
        for to in State:
            vid = f"m{n:03d}"
            n += 1
            sup.force_state(sim, vid, frm)
            v = sim.v(vid)
            legal = (frm, to) in EXPECTED_ROWS
            scope = EXPECTED_ROWS[(frm, to)][0] if legal else "gate"
            tok = sim.mint(scope, vid) if scope else None
            if legal:
                try:
                    sim.life.transition(v, to, tok, reason="matrix probe",
                                        payload=dict(FRAME_PAYLOAD))
                except IllegalTransition:  # pragma: no cover - failure path
                    pytest.fail(f"legal row {frm}->{to} raised IllegalTransition")
                except LifecycleError:
                    pass  # other guards may refuse; legality must not
            else:
                before = len(errors_for(sim, vid))
                assert not sim.life.can_transition(v, to).ok
                with pytest.raises(IllegalTransition):
                    sim.life.transition(v, to, tok, reason="matrix probe")
                errs = errors_for(sim, vid)
                assert len(errs) == before + 1
                assert errs[-1].payload.get("kind") == "illegal_transition"


def test_illegal_reject_leaves_state_unchanged(sim):
    """INV-SM-1 fail-closed: a rejected transition changes nothing — same projected
    state, same slots, and exactly one new event (the `error` log)."""
    sim.new("v1")
    sim.frame("v1")
    before_slots = sim.life.slots()
    before_events = len(list(sim.ledger.read()))
    with pytest.raises(IllegalTransition):
        sim.life.transition(sim.v("v1"), S.BUILDING, sim.mint("gate", "v1"))
    assert sim.v("v1").state is S.FRAMED
    assert sim.life.slots() == before_slots
    assert len(list(sim.ledger.read())) == before_events + 1


# --- INV-SM-2: WIP / slot limits --------------------------------------------------------------


def test_validating_wip_le_3(sim):
    """INV-SM-2: validating ≤3 — the 4th admission is refused; the overflow path
    FRAMED→PARKED (score ≥18, no slot) works."""
    for vid in ("v1", "v2", "v3", "v4"):
        sim.new(vid)
        sim.frame(vid)
    for vid in ("v1", "v2", "v3"):
        sim.admit(vid)
    with pytest.raises(SlotLimitExceeded):
        sim.admit("v4")
    assert sim.v("v4").state is S.FRAMED
    sim.advance("v4", S.PARKED, None)  # overflow row, internal
    assert sim.v("v4").state is S.PARKED


def test_shaping_wip_eq_1(sim):
    """INV-SM-2 (R-SHAPING-WIP): SHAPING =1 — a second validation-passed venture is
    refused SHAPING and overflows to PARKED_SHOVEL_READY with the evidence TTL stamped."""
    for vid in ("v1", "v2"):
        sim.new(vid)
        sim.frame(vid)
        sim.admit(vid)
        sim.pass_validation(vid)
    sim.advance("v1", S.SHAPING, "gate")
    with pytest.raises(SlotLimitExceeded):
        sim.advance("v2", S.SHAPING, "gate")
    sim.advance("v2", S.PARKED_SHOVEL_READY, None)
    v2 = sim.v("v2")
    assert v2.state is S.PARKED_SHOVEL_READY
    assert v2.evidence_ttl_at == sim.clock.now_active + 60


def test_building_wip_le_1(sim):
    """INV-SM-2: building ≤1 — with the build slot held, a second SHAPING→BUILDING is
    refused."""
    sim.new("v1"); sim.frame("v1"); sim.admit("v1"); sim.pass_validation("v1")
    sim.advance("v1", S.SHAPING, "gate")
    sup.spec_approved(sim.ledger, sim.clock, "v1")
    sim.advance("v1", S.BUILDING, "gate")
    sim.new("v2"); sim.frame("v2"); sim.admit("v2"); sim.pass_validation("v2")
    sim.advance("v2", S.SHAPING, "gate")  # slot freed when v1 left for BUILDING
    sup.spec_approved(sim.ledger, sim.clock, "v2")
    with pytest.raises(SlotLimitExceeded):
        sim.advance("v2", S.BUILDING, "gate")
    assert sim.v("v2").state is S.SHAPING


def test_harvest_alumni_cap_le_3(sim):
    """INV-SM-2 (R-ALUMNI-CEILING): with 3 HARVEST alumni, both a 4th graduation
    (alumni-capacity gate) and a 4th SCALING→HARVEST are refused; an EXIT reopens
    capacity."""
    for vid in ("h1", "h2", "h3"):
        sup.force_state(sim, vid, S.HARVEST)
    sup.force_state(sim, "e1", S.EARNING)
    sup.force_state(sim, "s1", S.SCALING)
    sup.exp_result(sim.ledger, sim.clock, "e1", metric="payers", verdict="PASS")
    with pytest.raises(SlotLimitExceeded):
        sim.advance("e1", S.GRADUATED, "graduate")
    with pytest.raises(SlotLimitExceeded):
        sim.advance("s1", S.HARVEST, "gate")
    sim.advance("h1", S.EXITED, "gate", reason="sold to operator")
    sim.advance("e1", S.GRADUATED, "graduate")
    assert sim.v("e1").state is S.GRADUATED


def test_slots_projection_matches_registry(sim):
    """INV-SM-2: `slots()` equals fresh Registry counts (never cached), limits frozen."""
    for vid, st in (("a", S.VALIDATING), ("b", S.VALIDATING), ("c", S.SHAPING),
                    ("d", S.BUILDING), ("e", S.HARVEST), ("f", S.FRAMED)):
        sup.force_state(sim, vid, st)
    slots = sim.life.slots()
    assert slots.validating == (len(sim.registry.query(S.VALIDATING)), 3)
    assert slots.shaping == (len(sim.registry.query(S.SHAPING)), 1)
    assert slots.building == (len(sim.registry.query(S.BUILDING)), 1)
    assert slots.harvest == (len(sim.registry.query(S.HARVEST)), 3)
    sim.kill("a", reason="hygiene")
    assert sim.life.slots().validating == (1, 3)


# --- INV-SM-3: factory-active-time clocks ------------------------------------------------------


def test_deadline_from_experiment_live_not_entry(sim):
    """INV-SM-3 (R-CLOCK): the experiment deadline runs from `experiment_live_at`, never
    from state entry — setup latency does not consume the window."""
    sim.new("v1"); sim.frame("v1")
    sim.clock.advance(3)
    sim.admit("v1")  # enters VALIDATING on day 3
    assert sim.life.clock(sim.v("v1")).deadline_at is None  # not live yet
    sim.clock.advance(5)  # domain warming etc.
    sup.go_live(sim.ledger, sim.clock, "v1")  # live on day 8
    at = sim.life.clock(sim.v("v1"))
    assert at.experiment_live_at == 8
    assert at.deadline_at == 8 + 14  # NOT 3 + 14
    assert at.elapsed_experiment == 0
    sim.clock.advance(4)
    assert sim.life.clock(sim.v("v1")).remaining == 10


def test_pause_freezes_active_time(sim):
    """INV-SM-3 (R-ACTIVE-TIME): `pause` freezes active-time accumulation — wall time
    passing during a pause moves no deadline; `pause`/`resume` are ledger events."""
    sim.new("v1"); sim.frame("v1"); sim.admit("v1")
    sup.go_live(sim.ledger, sim.clock, "v1")
    sim.clock.advance(2)
    before = sim.life.clock(sim.v("v1"))
    sim.life.pause("provider outage")
    sim.clock.advance(5)  # wall days pass; active time must not
    during = sim.life.clock(sim.v("v1"))
    assert during.now_active == before.now_active == 2
    assert during.remaining == before.remaining
    assert during.paused
    with pytest.raises(GuardFailed):
        sim.life.pause("already paused")
    sim.life.resume("outage over")
    sim.clock.advance(1)
    assert sim.life.clock(sim.v("v1")).now_active == 3
    types = [e.type for e in sim.ledger.read() if e.venture_id is None]
    assert EventType.PAUSE in types and EventType.RESUME in types


def test_state_windows_in_active_days(sim):
    """INV-SM-3: state windows (SHAPING ≤10) are measured in active days from state
    entry — a pause inside the window does not consume it; overrunning refuses BUILDING."""
    sim.new("v1"); sim.frame("v1"); sim.admit("v1"); sim.pass_validation("v1")
    sim.advance("v1", S.SHAPING, "gate")
    sup.spec_approved(sim.ledger, sim.clock, "v1")
    sim.clock.advance(11)
    with pytest.raises(GuardFailed):
        sim.advance("v1", S.BUILDING, "gate")
    sim.kill("v1", reason="spec rotted past the 10-day window")
    sim.new("v2"); sim.frame("v2"); sim.admit("v2"); sim.pass_validation("v2")
    sim.advance("v2", S.SHAPING, "gate")
    sup.spec_approved(sim.ledger, sim.clock, "v2")
    sim.clock.advance(4)
    sim.life.pause("founder vacation")
    sim.clock.advance(100)  # frozen
    sim.life.resume("back")
    sim.clock.advance(4)  # elapsed-in-state: 8 active days
    sim.advance("v2", S.BUILDING, "gate")
    assert sim.v("v2").state is S.BUILDING


# --- INV-SM-4: express restriction -------------------------------------------------------------


def test_express_only_launched_to_earning(sim):
    """INV-SM-4 (R-SLOT-GATE): express is permitted ONLY on LAUNCHED→EARNING; every
    slot-consuming row refuses it before any token is consumed."""
    refused = (
        ("f1", S.FRAMED, S.VALIDATING, "admit"),
        ("f2", S.VALIDATING, S.SHAPING, "gate"),
        ("f3", S.SHAPING, S.BUILDING, "gate"),
        ("f4", S.EARNING, S.GRADUATED, "graduate"),
    )
    for vid, frm, to, scope in refused:
        sup.force_state(sim, vid, frm)
        with pytest.raises(ExpressRefused):
            sim.advance(vid, to, scope, express=True, reason="mid-week grab")
        assert sim.v(vid).state is frm
    # The refusal happens before auth: the same (unconsumed) token still works normally.
    sup.exp_result(sim.ledger, sim.clock, "f4", metric="mrr", verdict="PASS")
    token = sim.mint("graduate", "f4")
    with pytest.raises(ExpressRefused):
        sim.life.transition(sim.v("f4"), S.GRADUATED, token, express=True)
    sim.life.transition(sim.v("f4"), S.GRADUATED, token)  # not consumed by the refusal
    assert sim.v("f4").state is S.GRADUATED
    # The one legal express advance (non-slot-consuming).
    sup.force_state(sim, "x1", S.LAUNCHED)
    sup.exp_result(sim.ledger, sim.clock, "x1", metric="activation", verdict="PASS")
    sim.advance("x1", S.EARNING, "advance.express", express=True)
    assert sim.v("x1").state is S.EARNING


# --- INV-SM-5: pivot = kill-and-fork; lineage caps ---------------------------------------------


def test_pivot_kill_and_fork(sim):
    """INV-SM-5 (R-PIVOT): pivot kills the venture, forks a new one at FRAMED with
    `forked_from` + inherited refs, frees the slots, and jumps no queue."""
    sup.force_state(sim, "clip", S.LAUNCHED)
    slots_before = sim.life.slots()
    res = sim.life.pivot(
        sim.v("clip"), sim.mint("pivot", "clip"), new_id="clip-fork",
        codename="showscribe", inherited={"audience": "aud-ref-01", "segment": "seg-ref-01"},
        reason="podcasters want show-notes, not clips")
    assert (res.killed_id, res.new_id) == ("clip", "clip-fork")
    assert sim.v("clip").state is S.KILLED
    fork = sim.v("clip-fork")
    assert fork.state is S.FRAMED and fork.forked_from == "clip"
    assert sim.life.slots() == slots_before  # no slot consumed, none was held
    types = [e.type for e in sim.ledger.read(EventFilter(venture_id="clip"))]
    assert EventType.KILL in types and EventType.PIVOT_FORK in types
    forks = list(sim.ledger.read(EventFilter(type=EventType.PIVOT_FORK)))
    assert len(forks) == 1 and forks[0].payload["new_id"] == "clip-fork"


def test_second_fork_in_lineage_refused(sim):
    """INV-SM-5: one fork per lineage — pivoting the fork is refused with NOTHING
    appended, checked against the ledger by a fresh engine (never memory)."""
    sup.force_state(sim, "clip", S.LAUNCHED)
    sim.life.pivot(sim.v("clip"), sim.mint("pivot", "clip"), new_id="clip-fork",
                   codename="showscribe", inherited={"audience": "aud-ref-01"},
                   reason="pivot one")
    # Walk the fork forward (raw history), then try to pivot it on a FRESH engine.
    sim.ledger.append(sup.Event(
        type=EventType.TRANSITION, actor="test",
        payload={"reason": "fixture", "gate_type": "internal"}, venture_id="clip-fork",
        from_state=S.FRAMED.value, to_state=S.LAUNCHED.value,
        active_time=sim.clock.now_active))
    fresh = Lifecycle(sim.ledger, sim.registry, sim.gov, sim.clock)
    before = len(list(sim.ledger.read()))
    with pytest.raises(ForkCapExceeded):
        fresh.pivot(sim.v("clip-fork"), sim.mint("pivot", "clip-fork"),
                    new_id="clip-fork-2", codename="again",
                    inherited={"audience": "aud-ref-01"}, reason="pivot two")
    assert len(list(sim.ledger.read())) == before
    assert sim.v("clip-fork").state is S.LAUNCHED


def test_omw_once_per_lineage(sim):
    """R-OMW-LEDGER / INV-SM-5: ONE-MORE-WEEK is a ledger event, max one per lineage —
    a second grant is refused on the venture AND on its fork, across engine restarts."""
    sup.force_state(sim, "hvac", S.LAUNCHED)
    sim.life.grant_omw(sim.v("hvac"), sim.mint("gate", "hvac"))
    with pytest.raises(OmwExhausted):
        sim.life.grant_omw(sim.v("hvac"), sim.mint("gate", "hvac"))
    sim.life.pivot(sim.v("hvac"), sim.mint("pivot", "hvac"), new_id="hvac-fork",
                   codename="fork", inherited={"audience": "aud-ref-02"}, reason="pivot")
    fresh = Lifecycle(sim.ledger, sim.registry, sim.gov, sim.clock)
    with pytest.raises(OmwExhausted):
        fresh.grant_omw(sim.v("hvac-fork"), sim.mint("gate", "hvac-fork"))
    grants = list(sim.ledger.read(EventFilter(type=EventType.OMW_GRANT)))
    assert len(grants) == 1


# --- INV-SM-6: evidence TTL --------------------------------------------------------------------


def test_ttl_stale_shovel_ready_blocked(sim):
    """INV-SM-6 (R-EVIDENCE-TTL): shovel-ready evidence past TTL blocks SHAPING until a
    re-confirmation signal; the mini-re-validation row (→VALIDATING) stays open for the
    stale case."""
    for vid in ("v1", "v2"):
        sim.new(vid); sim.frame(vid); sim.admit(vid); sim.pass_validation(vid)
    sim.advance("v1", S.SHAPING, "gate")           # v1 occupies SHAPING
    sim.advance("v2", S.PARKED_SHOVEL_READY, None)  # v2 overflows, TTL stamped
    ttl_at = sim.v("v2").evidence_ttl_at
    sim.kill("v1", reason="clears the on-deck slot for the test")
    # Fresh (≤ TTL) would be fine — but wait past it:
    sim.clock.advance(61)
    assert sim.clock.now_active > ttl_at
    with pytest.raises(StaleEvidence):
        sim.advance("v2", S.SHAPING, "gate")
    assert sim.v("v2").state is S.PARKED_SHOVEL_READY
    # A fresh evidence PASS (the re-confirmation signal) reopens the row.
    sup.evidence(sim.ledger, sim.clock, "v2", "PASS")
    sim.advance("v2", S.SHAPING, "gate")
    assert sim.v("v2").state is S.SHAPING
    # Mini re-validation: a third stale shovel-ready venture may re-enter VALIDATING.
    sim.new("v3"); sim.frame("v3"); sim.admit("v3"); sim.pass_validation("v3")
    sim.advance("v3", S.PARKED_SHOVEL_READY, None)  # SHAPING occupied by v2
    with pytest.raises(GuardFailed):
        sim.advance("v3", S.VALIDATING, "admit")  # not stale yet: mini re-val is the stale path
    sim.clock.advance(61)
    sim.advance("v3", S.VALIDATING, "admit")
    assert sim.v("v3").state is S.VALIDATING


# --- gate auth (IF-3 delegation) + guard facts -------------------------------------------------


def test_gate_rows_require_valid_token(sim):
    """Gate rows delegate token validation to Gov (IF-3): missing / mis-scoped / reused
    tokens are denied (nothing state-changing appended); a valid grant is consumed and
    its id is stamped on the event."""
    sim.new("v1"); sim.frame("v1")
    with pytest.raises(AuthorizationDenied):
        sim.life.transition(sim.v("v1"), S.VALIDATING, None)
    with pytest.raises(AuthorizationDenied):
        sim.life.transition(sim.v("v1"), S.VALIDATING, sim.mint("gate", "v1"))  # wrong scope
    assert sim.v("v1").state is S.FRAMED
    token = sim.mint("admit", "v1")
    sim.life.transition(sim.v("v1"), S.VALIDATING, token)
    admits = list(sim.ledger.read(EventFilter(venture_id="v1", type=EventType.ADMIT)))
    assert len(admits) == 1 and admits[0].authorization == token.id
    # Single-use: the consumed token cannot admit another venture.
    sim.new("v2"); sim.frame("v2")
    with pytest.raises(AuthorizationDenied):
        sim.life.transition(sim.v("v2"), S.VALIDATING, token)
    assert sim.v("v2").state is S.FRAMED


def test_internal_rows_need_no_token(sim):
    """docs/42 §3 Auth-column fidelity: internal rows execute with token=None."""
    sim.new("v1")
    sim.frame("v1")  # CAPTURED→FRAMED, internal (exercised throughout)
    for vid in ("a", "b", "c"):
        sim.new(vid); sim.frame(vid); sim.admit(vid)
    sim.advance("v1", S.PARKED, None)  # FRAMED→PARKED (validating full)
    assert sim.v("v1").state is S.PARKED
    sim.advance("v1", S.ARCHIVED, None, reason="superseded by a sharper framing")
    assert sim.v("v1").state is S.ARCHIVED
    sim.kill("a", reason="unreachable segment")
    sup.salvage(sim.ledger, sim.clock, "a")
    sim.advance("a", S.ARCHIVED, None)  # KILLED→ARCHIVED
    assert sim.v("a").state is S.ARCHIVED


def test_guard_facts_from_ledger(sim):
    """Objective guards read ledger facts (R-EVIDENCE-GATE, R-SALVAGE-TYPES, R-PARTNERS):
    each advance is refused until the acting subsystem's event exists."""
    # CAPTURED→FRAMED payload guard: ≥2 primary quotes.
    sim.new("q1")
    with pytest.raises(GuardFailed):
        sim.life.transition(sim.v("q1"), S.FRAMED,
                            payload={**FRAME_PAYLOAD, "quotes": 1})
    # Score bar: 17 needs a logged admission override (INV-GOV-6 pairing).
    sim.new("v1"); sim.frame("v1", score=17)
    with pytest.raises(GuardFailed):
        sim.admit("v1")
    sim.gov.record_override("admission", "backlog", "admit",
                            "founder has a direct contact in the trade", "v1")
    sim.admit("v1")
    assert sim.v("v1").state is S.VALIDATING
    # Evidence + experiment sub-gates (both required).
    with pytest.raises(GuardFailed):
        sim.advance("v1", S.SHAPING, "gate")
    sup.evidence(sim.ledger, sim.clock, "v1", "PASS")
    with pytest.raises(GuardFailed):
        sim.advance("v1", S.SHAPING, "gate")
    sup.exp_result(sim.ledger, sim.clock, "v1", "conversion", "PASS")
    sim.advance("v1", S.SHAPING, "gate")
    # Spec gate.
    with pytest.raises(GuardFailed):
        sim.advance("v1", S.BUILDING, "gate")
    sup.spec_approved(sim.ledger, sim.clock, "v1")
    sim.advance("v1", S.BUILDING, "gate")
    # Partners ≥5 (cumulative).
    with pytest.raises(GuardFailed):
        sim.advance("v1", S.LAUNCHED, "gate")
    sup.partners(sim.ledger, sim.clock, "v1", 3)
    with pytest.raises(GuardFailed):
        sim.advance("v1", S.LAUNCHED, "gate")
    sup.partners(sim.ledger, sim.clock, "v1", 2)
    sim.advance("v1", S.LAUNCHED, "gate")
    # Salvage before ARCHIVED.
    sim.kill("v1", reason="flat retention after two fixes")
    with pytest.raises(GuardFailed):
        sim.advance("v1", S.ARCHIVED, None)
    sup.salvage(sim.ledger, sim.clock, "v1", ("anti_pattern", "audience"))
    sim.advance("v1", S.ARCHIVED, None)
    assert sim.v("v1").state is S.ARCHIVED


def test_judgment_kill_requires_reason(sim):
    """Guard rules §4: judgment rows (kills) deterministically require the founder's
    non-empty reason; it lands in the `kill` event payload."""
    sim.new("v1"); sim.frame("v1")
    for bad in (None, "", "   "):
        with pytest.raises(GuardFailed):
            sim.advance("v1", S.KILLED, "kill", reason=bad)
    assert sim.v("v1").state is S.FRAMED
    sim.kill("v1", reason="known dead-pattern: unreachable buyers")
    kills = list(sim.ledger.read(EventFilter(venture_id="v1", type=EventType.KILL)))
    assert len(kills) == 1
    assert kills[0].payload["reason"] == "known dead-pattern: unreachable buyers"


# --- property tests: seeded random walks vs the independent oracle ----------------------------


def plant_facts(sim: sup.Sim, vid: str, to: State) -> None:
    """Plant exactly the facts the oracle assumes true before an advance attempt.
    NOTE: sub-gate facts are planted only while VALIDATING — never as an accidental
    TTL re-confirmation (the oracle models 'no re-confirmation ever')."""
    v = sim.v(vid)
    frm = v.state if v else None
    if to in (S.SHAPING, S.PARKED_SHOVEL_READY) and frm is S.VALIDATING:
        sim.pass_validation(vid)
    elif to is S.BUILDING:
        sup.spec_approved(sim.ledger, sim.clock, vid)
    elif to is S.LAUNCHED:
        sup.partners(sim.ledger, sim.clock, vid, 5)
    elif to is S.EARNING:
        sup.exp_result(sim.ledger, sim.clock, vid, "activation", "PASS")
    elif to is S.GRADUATED:
        sup.exp_result(sim.ledger, sim.clock, vid, "payers", "PASS")
    elif to is S.ARCHIVED and frm is S.KILLED:
        sup.salvage(sim.ledger, sim.clock, vid)


def run_script(sim: sup.Sim, oracle: sup.LifecycleOracle, ops: list[tuple]) -> None:
    """Drive engine + oracle op by op, asserting they agree on every accept/reject and on
    every resulting state (INV-SM-1/2/4/5 property; TESTPLAN)."""
    fork_n = 0
    for op in ops:
        kind = op[0]
        if kind == "new":
            sup.capture(sim.ledger, sim.clock, op[1])
            oracle.new(op[1])
        elif kind == "tick":
            sim.clock.advance(op[1])
            oracle.tick(op[1])
        elif kind in ("pause", "resume"):
            expected = oracle.set_paused(kind == "pause")
            try:
                (sim.life.pause if kind == "pause" else sim.life.resume)("scripted")
                assert expected, f"{op}: engine accepted, oracle rejected"
            except GuardFailed:
                assert not expected, f"{op}: engine rejected, oracle accepted"
        elif kind in ("frame", "advance", "kill"):
            vid = op[1]
            if kind == "frame":
                to, express = S.FRAMED, False
            elif kind == "kill":
                to, express = S.KILLED, False
            else:
                to, express = op[2], op[3]
            plant_facts(sim, vid, to)
            expected = oracle.expect_advance(vid, to, express)
            frm = oracle.state.get(vid)
            scope = EXPECTED_ROWS.get((frm, to), ("gate",))[0] if frm else "gate"
            if express and (frm, to) == (S.LAUNCHED, S.EARNING):
                scope = "advance.express"  # the express gate's own RED scope
            tok = sim.mint(scope, vid) if scope else None
            try:
                sim.life.transition(sim.v(vid), to, tok, express=express,
                                    reason="seeded walk", payload=dict(FRAME_PAYLOAD))
                assert expected, f"{op}: engine accepted, oracle rejected"
                oracle.on_advanced(vid, to)
                assert sim.v(vid).state is to
            except LifecycleError as exc:
                assert not expected, f"{op}: engine rejected ({exc}), oracle accepted"
        elif kind == "pivot":
            vid = op[1]
            expected = oracle.expect_pivot(vid)
            fork_n += 1
            new_id = f"{vid}-f{fork_n}"
            try:
                sim.life.pivot(sim.v(vid), sim.mint("pivot", vid), new_id=new_id,
                               codename=new_id, inherited={"audience": "aud-ref"},
                               reason="seeded pivot")
                assert expected, f"{op}: engine accepted, oracle rejected"
                oracle.on_pivoted(vid, new_id)
                assert sim.v(vid).state is S.KILLED
                assert sim.v(new_id).state is S.FRAMED
            except LifecycleError as exc:
                assert not expected, f"{op}: engine rejected ({exc}), oracle accepted"
        elif kind == "omw":
            vid = op[1]
            expected = oracle.expect_omw(vid)
            try:
                sim.life.grant_omw(sim.v(vid), sim.mint("gate", vid))
                assert expected, f"{op}: engine accepted, oracle rejected"
                oracle.on_omw(vid)
            except LifecycleError as exc:
                assert not expected, f"{op}: engine rejected ({exc}), oracle accepted"
    # Closing sweep: states agree everywhere; WIP limits were never exceeded.
    for vid, expected_state in oracle.state.items():
        assert sim.v(vid).state is expected_state, f"{vid}: state diverged"
    slots = sim.life.slots()
    for kind_name in ("validating", "shaping", "building", "harvest"):
        count, limit = getattr(slots, kind_name)
        assert count <= limit, f"{kind_name} WIP exceeded"


@pytest.mark.parametrize("seed", range(30))
def test_property_random_walks_never_violate(tmp_path, seed):
    """INV-SM-1/2/4/5 (property): for seeded random op scripts, every engine
    accept/reject matches the independent oracle; states agree after every op; WIP
    limits and lineage caps hold at the end."""
    sim = sup.Sim(tmp_path)
    run_script(sim, sup.LifecycleOracle(), sup.lifecycle_script(seed))
    per_lineage: dict[str, int] = {}
    for e in sim.ledger.read(EventFilter(type=EventType.PIVOT_FORK)):
        per_lineage[e.venture_id] = per_lineage.get(e.venture_id, 0) + 1
    assert all(n <= 1 for n in per_lineage.values())


@pytest.mark.parametrize("seed", range(30))
def test_property_replay_equals_projection(tmp_path, seed):
    """Ledger-as-truth (INV-LEDGER inherited): a fresh engine + registry over the same
    ledger dir projects identical states and slots — S5 holds no hidden state."""
    sim = sup.Sim(tmp_path)
    run_script(sim, sup.LifecycleOracle(), sup.lifecycle_script(seed))
    ledger2 = Ledger(tmp_path / "ledger")
    registry2 = Registry(ledger2)
    life2 = Lifecycle(ledger2, registry2, sim.gov, sim.clock)
    old = {v.id: v.state for v in sim.registry.query()}
    new = {v.id: v.state for v in registry2.query()}
    assert old == new
    assert life2.slots() == sim.life.slots()
