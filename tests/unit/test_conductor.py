"""S12 Conductor unit suite (conductor/TESTPLAN.md) — INV-COND-1..3.

Fully live stack behind the chokepoint (no stubs); founder tokens minted only at the
Gov boundary; refusal reasons are the owners'. No network (INV-TEST-SAFE).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.conductor import CommandRefused, NoCriticForGate
from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State

from tests.unit import _a10_support as a10

VID = "v-choke"


def _events(ledger):
    return list(ledger.read())


def _force_state(f, vid: str, state: State, codename: str = "pods") -> None:
    """Fixture history (the _a4 convention): place a venture at ``state`` by raw
    appends — used only to CONSTRUCT scenarios, never to test transitions."""
    f.ledger.append(Event(type=EventType.CAPTURE, actor="test",
                          payload={"codename": codename}, venture_id=vid,
                          to_state=State.CAPTURED.value, active_time=0))
    if state is not State.CAPTURED:
        f.ledger.append(Event(type=EventType.TRANSITION, actor="test",
                              payload={"reason": "fixture", "gate_type": "internal"},
                              venture_id=vid, from_state=State.CAPTURED.value,
                              to_state=state.value, active_time=0))


# --- the pipeline + INV-COND-1 -------------------------------------------------------------


def test_pipeline_classify_guard_act_append(tmp_path):
    """docs/10: one command walks classify (S6 spy) → guard → act → ONE append →
    projections reflect it on the next (re-derived) read."""
    f = a10.make_factory(tmp_path)
    result = f.conductor.command("capture", {"venture_id": VID, "codename": "pods"})
    assert result.ok and result.color == "GREEN" and result.event_id
    assert "capture" in f.gov.classified  # classification transited S6
    events = _events(f.ledger)
    assert [e.type for e in events] == [EventType.CAPTURE]
    assert f.registry.get(VID).state is State.CAPTURED
    board = f.conductor.command("pipeline", {}).data
    assert [row.venture_id for row in board.rows] == [VID]  # regenerated on read


def test_call_through_no_local_rules():
    """INV-COND-1 (static): no classify matrix, no transition-legality table, no
    AuthClass construction, no PII regex lives under conductor/."""
    root = Path(__file__).resolve().parents[2] / "charterhouse" / "conductor"
    offenders = []
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for needle in ("AuthClass(", "MATRIX", "TRANSITIONS", "re.compile(",
                       "lifecycle.table", "governance.classify", "security.scan"):
            if needle in text:
                offenders.append(f"{py.name}: {needle}")
    assert not offenders, f"owner-rule re-implementation in S12: {offenders}"


def test_call_path_transits_owners(tmp_path):
    """INV-COND-1 (call-path): admit's decision transits S5 (transition spy) and S6
    (authorize spy, exactly ONCE — single consumption at the owner)."""
    f = a10.make_factory(tmp_path)
    f.conductor.command("capture", {"venture_id": VID})
    f.conductor.command("frame", {"venture_id": VID, "brief_ref": "brief-001",
                                  "score": 20, "quotes": 3})
    before = list(f.gov.authorized)
    f.conductor.command("admit", {"venture_id": VID}, token=a10.tok(f, "admit", VID))
    assert f.lifecycle.transitions[-1] == (VID, "VALIDATING")  # act transited S5
    assert f.gov.authorized[len(before):] == ["admit"]  # ONE S6 authorization
    assert f.registry.get(VID).state is State.VALIDATING


def test_red_without_token_refused_by_owner(tmp_path):
    """RED commands without a token are refused with the OWNER's reason; the ledger
    stays untouched by the refusal."""
    f = a10.make_factory(tmp_path)
    f.conductor.command("capture", {"venture_id": VID})
    f.conductor.command("frame", {"venture_id": VID, "brief_ref": "brief-001",
                                  "score": 20, "quotes": 3})
    n = len(_events(f.ledger))
    with pytest.raises(CommandRefused):
        f.conductor.command("admit", {"venture_id": VID})  # no token
    # The refusal audit (S5's error event) may append; no STATE event may:
    assert f.registry.get(VID).state is State.FRAMED
    assert all(e.to_state is None for e in _events(f.ledger)[n:])


def test_unknown_command_refused(tmp_path):
    """An unknown name classifies RED (S6, fail closed) and is denied — nothing acts."""
    f = a10.make_factory(tmp_path)
    with pytest.raises(CommandRefused):
        f.conductor.command("made.up", {"venture_id": VID})
    assert _events(f.ledger) == []


def test_single_use_token_consumed_once(tmp_path):
    """A consumed admit token cannot admit a second venture — exactly-once consumption
    happens at the owner (S6 inside S5), never twice via the conductor."""
    f = a10.make_factory(tmp_path)
    for vid in ("v-one", "v-two"):
        f.conductor.command("capture", {"venture_id": vid})
        f.conductor.command("frame", {"venture_id": vid, "brief_ref": "brief-001",
                                      "score": 20, "quotes": 3})
    t = a10.tok(f, "admit", "v-one")
    assert f.conductor.command("admit", {"venture_id": "v-one"}, token=t).ok
    with pytest.raises(CommandRefused):
        # Same token object presented again (wrong venture AND already consumed).
        f.conductor.command("admit", {"venture_id": "v-two"}, token=t)
    assert f.registry.get("v-two").state is State.FRAMED


def test_two_key_commands_demand_check(tmp_path):
    """deploy.prod / billing.enable: token alone is refused (INV-GOV-2 needs the
    passing automated check); token+check appends the event with the token id — and
    NOTHING else happens (INV-TEST-SAFE: v1 has no real pipeline)."""
    f = a10.make_factory(tmp_path)
    _force_state(f, VID, State.BUILDING)
    for name, params in (("deploy.prod", {"tag": "v0.1.0"}),
                         ("billing.enable", {})):
        t = a10.tok(f, name, VID)
        with pytest.raises(CommandRefused):
            f.conductor.command(name, {"venture_id": VID, **params}, token=t)
        t2 = a10.tok(f, name, VID)
        result = f.conductor.command(
            name, {"venture_id": VID, **params, "check": a10.check_pass()}, token=t2)
        assert result.ok
        evt = _events(f.ledger)[-1]
        assert evt.type.value == name.replace(".", "_")
        assert evt.authorization == t2.id
        assert evt.to_state is None  # no state smuggling (RISKS R3)


def test_send_stage_records_batch_under_budget(tmp_path):
    """send.stage: authorized batches append send_batch with the token id; an
    over-budget batch is refused with S6's budget reason."""
    f = a10.make_factory(tmp_path)
    _force_state(f, VID, State.LAUNCHED)
    t = a10.tok(f, "send.stage", VID)
    result = f.conductor.command("send.stage", {"venture_id": VID, "count": 10,
                                                "audience_tz": "UTC"}, token=t)
    assert result.ok
    evt = _events(f.ledger)[-1]
    assert evt.type is EventType.SEND_BATCH and evt.authorization == t.id
    t2 = a10.tok(f, "send.stage", VID)
    with pytest.raises(CommandRefused, match="budget"):
        f.conductor.command("send.stage",
                            {"venture_id": VID, "count": 41,
                             "check": a10.check_pass("deliverability")}, token=t2)


def test_salvage_requires_asset_types(tmp_path):
    """R-SALVAGE-TYPES (docs/41 shape): empty asset_types refused naming the field;
    a named salvage appends."""
    f = a10.make_factory(tmp_path)
    _force_state(f, VID, State.KILLED)
    with pytest.raises(CommandRefused, match="asset_types"):
        f.conductor.command("salvage", {"venture_id": VID, "asset_types": []})
    result = f.conductor.command("salvage", {"venture_id": VID,
                                             "asset_types": ["anti_pattern"]})
    assert result.ok
    assert _events(f.ledger)[-1].type is EventType.SALVAGE


def test_workflow_commands_run_s10(tmp_path):
    """shape/build run the real S10 workflow under the conductor's table: ONE
    state-neutral artifact_produced with critic_tier; artifact in the vault."""
    f = a10.make_factory(tmp_path)
    _force_state(f, VID, State.SHAPING)
    result = f.conductor.command("shape", {"venture_id": VID})
    assert result.ok
    evt = _events(f.ledger)[-1]
    assert evt.type is EventType.ARTIFACT_PRODUCED
    assert evt.to_state is None
    assert evt.payload["capability"] == "builder"
    assert evt.payload["critic_tier"] in (1, 2, 3)
    assert (f.vault_dir / evt.payload["artifact_ref"]).is_file()


def test_consolidate_calls_s9(tmp_path):
    """consolidate is S9's pass — its ONE consolidate event, nothing conductor-owned."""
    f = a10.make_factory(tmp_path)
    result = f.conductor.command("consolidate", {})
    assert result.ok
    assert _events(f.ledger)[-1].type is EventType.CONSOLIDATE


def test_gate_requires_critic_take(tmp_path):
    """INV-COND-2: a gate on a venture with no critic history refuses
    (NoCriticForGate); nothing appended, state unchanged."""
    f = a10.make_factory(tmp_path)
    _force_state(f, VID, State.VALIDATING)
    n = len(_events(f.ledger))
    with pytest.raises(NoCriticForGate):
        f.conductor.command("gate", {"venture_id": VID, "decision": "ADVANCE",
                                     "to": "SHAPING"},
                            token=a10.tok(f, "gate", VID))
    assert len(_events(f.ledger)) == n
    assert f.registry.get(VID).state is State.VALIDATING


def test_gate_appends_decision_with_critic_tier(tmp_path):
    """INV-COND-2 + docs/41: a briefed gate advances via S5 AND appends ONE
    gate_decision{brief_ref, recommendation, decision, critic_tier}."""
    f = a10.make_factory(tmp_path)
    _force_state(f, VID, State.VALIDATING)
    f.conductor.command("validate.evidence", {"venture_id": VID, "verdict": "PASS",
                                              "quote_count": 22,
                                              "segment_kind": "online"})
    f.conductor.command("validate.experiment", {"venture_id": VID,
                                                "channel": "linkedin"})
    f.conductor.command("validate.experiment", {"venture_id": VID,
                                                "metric": "conversion", "actual": 5.4,
                                                "threshold": 4.0, "verdict": "PASS"})
    a10.seed_artifact_produced(f.ledger, VID, tier=1)
    result = f.conductor.command("gate", {"venture_id": VID, "decision": "ADVANCE",
                                          "to": "SHAPING"},
                                 token=a10.tok(f, "gate", VID))
    assert result.ok
    assert f.registry.get(VID).state is State.SHAPING
    decision = _events(f.ledger)[-1]
    assert decision.type is EventType.GATE_DECISION
    assert set(decision.payload) >= {"brief_ref", "recommendation", "decision",
                                     "critic_tier"}
    assert decision.payload["critic_tier"] == 1
    assert decision.payload["decision"] == "ADVANCE"


def test_gate_spec_approval_path(tmp_path):
    """§6.2: gate(ADVANCE→BUILDING, spec_ref) appends spec_approved under the SAME
    token id then transitions; the token is consumed exactly once (one S6 authorize)."""
    f = a10.make_factory(tmp_path)
    _force_state(f, VID, State.SHAPING)
    a10.seed_artifact_produced(f.ledger, VID, tier=2)
    before = list(f.gov.authorized)
    t = a10.tok(f, "gate", VID)
    result = f.conductor.command("gate", {"venture_id": VID, "decision": "ADVANCE",
                                          "to": "BUILDING", "spec_ref": "spec-001",
                                          "fits_days": 9}, token=t)
    assert result.ok
    assert f.registry.get(VID).state is State.BUILDING
    types = [e.type for e in _events(f.ledger)]
    spec_evt = next(e for e in _events(f.ledger)
                    if e.type is EventType.SPEC_APPROVED)
    assert spec_evt.authorization == t.id
    last_transition = max(i for i, ty in enumerate(types)
                          if ty is EventType.TRANSITION)  # the gate's, not the fixture's
    assert types.index(EventType.SPEC_APPROVED) < last_transition
    assert f.gov.authorized[len(before):] == ["gate"]  # exactly one consumption


# --- INV-COND-3 ----------------------------------------------------------------------------


def test_crash_mid_command_zero_loss(tmp_path):
    """INV-COND-3: a fresh Conductor over the same ledger dir sees identical truth;
    a probe killing the trailing gate_decision append after a successful transition
    loses nothing — the transition survives and replay stays clean."""
    from charterhouse.ledger import Ledger
    from charterhouse.projections import pipeline

    f = a10.make_factory(tmp_path / "one")
    f.conductor.command("capture", {"venture_id": VID, "codename": "pods"})
    f.conductor.command("frame", {"venture_id": VID, "brief_ref": "brief-001",
                                  "score": 20, "quotes": 3})
    # "Crash": a brand-new process = a fresh Ledger over the same dir, read-only.
    reopened = Ledger(tmp_path / "one" / "ledger")
    assert pipeline(reopened) == pipeline(f.ledger)
    assert reopened.replay().ventures[VID].state is State.FRAMED

    # Probe: the recorder append dies AFTER the owner's transition append.
    class DyingRecorder(a10.Ledger):
        def append(self, event):
            if event.type is EventType.GATE_DECISION:
                raise RuntimeError("crash probe: recorder append died")
            return super().append(event)

    dying = DyingRecorder(tmp_path / "two" / "ledger",
                          new_id=a10.a3.deterministic_id_factory())
    f2 = a10.make_factory(tmp_path / "two", ledger=dying)
    _force_state(f2, VID, State.VALIDATING)
    f2.conductor.command("validate.evidence", {"venture_id": VID, "verdict": "PASS",
                                               "quote_count": 22,
                                               "segment_kind": "online"})
    f2.conductor.command("validate.experiment", {"venture_id": VID,
                                                 "channel": "linkedin"})
    f2.conductor.command("validate.experiment", {"venture_id": VID,
                                                 "metric": "conversion",
                                                 "actual": 5.4, "threshold": 4.0,
                                                 "verdict": "PASS"})
    a10.seed_artifact_produced(dying, VID, tier=1)
    with pytest.raises(RuntimeError, match="crash probe"):
        f2.conductor.command("gate", {"venture_id": VID, "decision": "ADVANCE",
                                      "to": "SHAPING"},
                             token=a10.tok(f2, "gate", VID))
    # Zero loss: the owner's state event survived; replay is clean and definite.
    assert f2.registry.get(VID).state is State.SHAPING
    assert not any(e.type is EventType.GATE_DECISION for e in _events(dying))


def test_conductor_holds_no_durable_state(tmp_path):
    """INV-COND-3: dispatch is stateless — no conductor attribute is rebound by
    command handling; two conductors over one ledger see identical truth."""
    f = a10.make_factory(tmp_path)
    snapshot = {k: id(v) for k, v in vars(f.conductor).items()}
    f.conductor.command("capture", {"venture_id": VID})
    f.conductor.command("pipeline", {})
    assert {k: id(v) for k, v in vars(f.conductor).items()} == snapshot
    from charterhouse.conductor import Conductor
    twin = Conductor(ledger=f.ledger, registry=f.registry, lifecycle=f.lifecycle,
                     gov=f.gov, memory=f.memory, workflow=f.workflow, clock=f.clock)
    assert twin.command("pipeline", {}).data == f.conductor.command("pipeline", {}).data


def test_projection_commands_pure_reads(tmp_path):
    """pipeline/brief/killday/gatebrief/calibrate append NOTHING (pure reads)."""
    f = a10.make_factory(tmp_path)
    _force_state(f, VID, State.VALIDATING)
    a10.seed_artifact_produced(f.ledger, VID, tier=3)
    n = len(_events(f.ledger))
    for name, args in (("pipeline", {}), ("brief", {}), ("killday", {}),
                       ("gatebrief", {"venture_id": VID}), ("calibrate", {})):
        result = f.conductor.command(name, args)
        assert result.ok and result.data is not None
    assert len(_events(f.ledger)) == n


def test_pause_resume_pass_through(tmp_path):
    """pause/resume transit S5 (factory-global clock control) — call-through."""
    f = a10.make_factory(tmp_path)
    assert f.conductor.command("pause", {"reason": "provider outage"}).ok
    assert _events(f.ledger)[-1].type is EventType.PAUSE
    assert f.conductor.command("resume", {"reason": "providers back"}).ok
    assert _events(f.ledger)[-1].type is EventType.RESUME
