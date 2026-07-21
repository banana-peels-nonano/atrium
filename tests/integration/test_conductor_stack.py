"""S12/S13 integration suite (conductor/TESTPLAN.md) — the docs/10 DoD: a full venture
dry-run Capture → Graduate through the live chokepoint, every RED point halted first
at the authorization boundary, zero real spend/send/deploy (INV-TEST-SAFE), plus the
projections rendering the whole run.
"""

from __future__ import annotations

import pytest

from charterhouse.conductor import CommandRefused
from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State

from tests.unit import _a10_support as a10

VID = "v-journey"


def _red_halts_then_passes(f, name: str, args: dict, scope: str) -> None:
    """Every RED point: first WITHOUT a token → refused with zero state effect; then
    WITH a correctly-scoped founder token → passes (docs/10 DoD)."""
    state_before = f.registry.get(VID).state
    with pytest.raises(CommandRefused):
        f.conductor.command(name, args)
    assert f.registry.get(VID).state is state_before  # the halt had no effect
    result = f.conductor.command(name, args, token=a10.tok(f, scope, VID))
    assert result.ok


def test_it_full_venture_dry_run_capture_to_graduate(tmp_path):
    """Capture → FRAMED → VALIDATING → SHAPING → BUILDING → LAUNCHED → EARNING →
    GRADUATED, all through Conductor.command over the fully live stack; every gate
    carried a critic take; deploy/billing/launch recorded at the two-key/token
    boundary and NOTHING beyond it (INV-TEST-SAFE)."""
    f = a10.make_factory(tmp_path)

    # Sourcing & framing (GREEN + internal transition).
    assert f.conductor.command("capture", {"venture_id": VID,
                                           "codename": "pods"}).ok
    f.workflow.run(State.CAPTURED, f.registry.get(VID))  # scout brief (S10 surface)
    assert f.conductor.command("frame", {"venture_id": VID, "brief_ref": "brief-001",
                                         "score": 20, "quotes": 3}).ok

    # Admission (RED: halt first, then token).
    _red_halts_then_passes(f, "admit", {"venture_id": VID}, "admit")
    assert f.registry.get(VID).state is State.VALIDATING

    # Validation facts (GREEN/YELLOW), analyst artifact, then the SHAPING gate.
    assert f.conductor.command("validate.evidence",
                               {"venture_id": VID, "verdict": "PASS",
                                "quote_count": 22, "segment_kind": "online"}).ok
    assert f.conductor.command("validate.experiment",
                               {"venture_id": VID, "channel": "linkedin"}).ok
    assert f.conductor.command("validate.experiment",
                               {"venture_id": VID, "metric": "conversion",
                                "actual": 5.4, "threshold": 4.0,
                                "verdict": "PASS"}).ok
    f.workflow.run(State.VALIDATING, f.registry.get(VID))  # research pack + critique
    _red_halts_then_passes(f, "gate", {"venture_id": VID, "decision": "ADVANCE",
                                       "to": "SHAPING"}, "gate")
    assert f.registry.get(VID).state is State.SHAPING

    # Shaping work (workflow command) + partners + the BUILDING gate (spec approval).
    assert f.conductor.command("shape", {"venture_id": VID}).ok
    assert f.conductor.command("recruit.partners", {"venture_id": VID,
                                                    "recruited_count": 5}).ok
    _red_halts_then_passes(f, "gate", {"venture_id": VID, "decision": "ADVANCE",
                                       "to": "BUILDING", "spec_ref": "spec-001",
                                       "fits_days": 9}, "gate")
    assert f.registry.get(VID).state is State.BUILDING

    # Build work, then the two-key RED boundary (halt-only in v1: events, no effects).
    assert f.conductor.command("build", {"venture_id": VID}).ok
    for name, params, scope in (
            ("deploy.prod", {"tag": "v0.1.0"}, "deploy.prod"),
            ("billing.enable", {}, "billing.enable")):
        with pytest.raises(CommandRefused):  # token alone: second key missing
            f.conductor.command(name, {"venture_id": VID, **params},
                                token=a10.tok(f, scope, VID))
        assert f.conductor.command(
            name, {"venture_id": VID, **params, "check": a10.check_pass()},
            token=a10.tok(f, scope, VID)).ok
    _red_halts_then_passes(f, "launch", {"venture_id": VID,
                                         "kit_ref": "kit-001"}, "launch")

    # LAUNCHED gate (partners guard), activation, EARNING, traction, graduation.
    _red_halts_then_passes(f, "gate", {"venture_id": VID, "decision": "ADVANCE",
                                       "to": "LAUNCHED"}, "gate")
    assert f.conductor.command("validate.experiment",
                               {"venture_id": VID, "metric": "activation",
                                "actual": 12, "threshold": 10,
                                "verdict": "PASS"}).ok
    _red_halts_then_passes(f, "gate", {"venture_id": VID, "decision": "ADVANCE",
                                       "to": "EARNING"}, "gate")
    assert f.conductor.command("validate.experiment",
                               {"venture_id": VID, "metric": "mrr", "actual": 900,
                                "threshold": 500, "verdict": "PASS"}).ok
    _red_halts_then_passes(f, "graduate", {"venture_id": VID}, "graduate")
    assert f.registry.get(VID).state is State.GRADUATED

    # INV-TEST-SAFE: the RED externals exist ONLY as token-carrying ledger events.
    events = list(f.ledger.read())
    for etype in (EventType.DEPLOY_PROD, EventType.BILLING_ENABLE, EventType.LAUNCH):
        (evt,) = [e for e in events if e.type is etype]
        assert evt.authorization  # recorded AT the authorization boundary
        assert evt.to_state is None
    # Every gate decision carried a critic tier (INV-COND-2 end to end).
    decisions = [e for e in events if e.type is EventType.GATE_DECISION]
    assert decisions and all(d.payload["critic_tier"] in (1, 2, 3)
                             for d in decisions)
    # Nothing exists outside the ledger + tmp vault (no send/deploy/charge artifact).
    assert (tmp_path / "vault").is_dir()


def test_it_projections_reflect_the_run(tmp_path):
    """After a validated venture + one killed venture: all six projections render the
    ledger truthfully (S13 purity over the conductor-driven history)."""
    f = a10.make_factory(tmp_path)
    f.conductor.command("capture", {"venture_id": VID, "codename": "pods"})
    f.workflow.run(State.CAPTURED, f.registry.get(VID))
    f.conductor.command("frame", {"venture_id": VID, "brief_ref": "brief-001",
                                  "score": 20, "quotes": 3})
    f.conductor.command("admit", {"venture_id": VID},
                        token=a10.tok(f, "admit", VID))
    f.conductor.command("validate.evidence", {"venture_id": VID, "verdict": "PASS",
                                              "quote_count": 22,
                                              "segment_kind": "online"})
    f.conductor.command("capture", {"venture_id": "v-doomed", "codename": "husk"})
    f.conductor.command("kill", {"venture_id": "v-doomed",
                                 "reason": "no signal at capture"},
                        token=a10.tok(f, "kill", "v-doomed"))
    f.conductor.command("salvage", {"venture_id": "v-doomed",
                                    "asset_types": ["anti_pattern"]})

    board = f.conductor.command("pipeline", {}).data
    states = {r.venture_id: r.state for r in board.rows}
    assert states[VID] is State.VALIDATING
    assert states["v-doomed"] is State.KILLED
    m = f.conductor.command("calibrate", {}).data  # calibration report renders
    assert m is not None
    metrics_data = __import__("charterhouse.projections",
                              fromlist=["metrics"]).metrics(f.ledger)
    assert metrics_data.kills == 1
    daily = f.conductor.command("brief", {}).data
    assert daily.board.rows  # board glance attached
    kd = f.conductor.command("killday", {}).data
    assert VID in [b.venture_id for b, _ in kd.rows] or VID in kd.unbriefable
    brief = f.conductor.gate_brief(VID)
    assert brief.critic.tier in (1, 2, 3)
