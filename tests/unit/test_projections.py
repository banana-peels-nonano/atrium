"""S13 Projections unit suite (projections/TESTPLAN.md) — pure ledger folds.

Real tmp-path Ledger seeded by raw appends (the _a3/_a4 convention); no fakes, no
network. Purity is proven by recomputation and snapshot/restore identity.
"""

from __future__ import annotations

import pytest

from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State
from charterhouse.ledger import Ledger
from charterhouse.projections import (
    NoCriticForGate,
    UnknownVenture,
    calibration,
    daily_brief,
    gate_brief,
    killday_brief,
    metrics,
    pipeline,
)

from tests.unit import _a10_support as a10
from tests.unit import _a3_support as a3


def _ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ledger", new_id=a3.deterministic_id_factory())


def _capture(lg, vid, codename=None, state: State = State.CAPTURED):
    lg.append(Event(type=EventType.CAPTURE, actor="test",
                    payload={"codename": codename or vid}, venture_id=vid,
                    to_state=State.CAPTURED.value, active_time=0))
    if state is not State.CAPTURED:
        lg.append(Event(type=EventType.TRANSITION, actor="test",
                        payload={"reason": "fixture", "gate_type": "internal"},
                        venture_id=vid, from_state=State.CAPTURED.value,
                        to_state=state.value, active_time=0))


def _story(lg) -> None:
    """Two live ventures + one killed: the fixture history every fold reads."""
    _capture(lg, "v-alpha", "pods", State.VALIDATING)
    lg.append(Event(type=EventType.FRAME, actor="test",
                    payload={"brief_ref": "brief-001", "score": 20,
                             "reach_is_hypothesis": True},
                    venture_id="v-alpha", active_time=0))
    lg.append(Event(type=EventType.EVIDENCE_GATE, actor="test",
                    payload={"verdict": "PASS", "quote_count": 22,
                             "segment_kind": "online"},
                    venture_id="v-alpha", active_time=1))
    lg.append(Event(type=EventType.EXPERIMENT_RESULT, actor="test",
                    payload={"metric": "conversion", "actual": 5.4, "threshold": 4.0,
                             "verdict": "PASS"},
                    venture_id="v-alpha", active_time=2))
    a10.seed_artifact_produced(lg, "v-alpha", tier=1, active_time=2)
    _capture(lg, "v-beta", "beacon", State.VALIDATING)
    lg.append(Event(type=EventType.EVIDENCE_GATE, actor="test",
                    payload={"verdict": "FAIL", "quote_count": 3,
                             "segment_kind": "online"},
                    venture_id="v-beta", active_time=3))
    _capture(lg, "v-dead", "husk", State.KILLED)
    lg.append(Event(type=EventType.LLM_CALL, actor="system",
                    payload={"role": "draft", "model": "llama3-local",
                             "provider": "ollama", "tokens": {"in": 10, "out": 20},
                             "cost_usd": 0.0, "latency_ms": 5}, venture_id=None))
    lg.append(Event(type=EventType.SPEND_ENVELOPE, actor="founder",
                    payload={"cap_usd": 50.0}, venture_id="v-alpha",
                    authorization="tok-fixture", active_time=2))
    lg.append(Event(type=EventType.SPEND_METER, actor="system",
                    payload={"amount_usd": 12.5, "running_total": 12.5},
                    venture_id="v-alpha", active_time=2))
    lg.append(Event(type=EventType.SEND_BATCH, actor="founder",
                    payload={"count": 10, "audience_tz": "UTC",
                             "per_domain": {"example": 10}},
                    venture_id="v-alpha", authorization="tok-fixture",
                    timestamp="2026-07-19T09:00:00+00:00", active_time=2))


def test_pipeline_board_from_replay(tmp_path):
    """docs/41 §3: every venture rendered, rows sorted by id."""
    lg = _ledger(tmp_path)
    _story(lg)
    board = pipeline(lg)
    assert [r.venture_id for r in board.rows] == ["v-alpha", "v-beta", "v-dead"]
    rows = {r.venture_id: r for r in board.rows}
    assert rows["v-alpha"].state is State.VALIDATING
    assert rows["v-alpha"].codename == "pods"
    assert rows["v-alpha"].score == 20
    assert rows["v-dead"].state is State.KILLED


def test_metrics_single_pass_counts(tmp_path):
    """docs/41 §3: exact counts from the seeded stream."""
    lg = _ledger(tmp_path)
    _story(lg)
    m = metrics(lg)
    assert dict(m.by_state)["VALIDATING"] == 2 and dict(m.by_state)["KILLED"] == 1
    assert m.frames == 1
    assert m.experiments_pass == 1 and m.experiments_fail == 0
    assert m.llm_cost_usd == 0.0
    assert m.spend_usd == 12.5
    assert dict(m.sends_by_day) == {"2026-07-19": 10}


def test_purity_recompute_and_replay_identical(tmp_path):
    """INV-COND-3 (S13 half): every projection twice → identical; a snapshot restored
    into a fresh dir → identical again (pure functions of the ledger)."""
    lg = _ledger(tmp_path)
    _story(lg)
    first = (pipeline(lg), metrics(lg), daily_brief(lg), killday_brief(lg),
             calibration(lg))
    second = (pipeline(lg), metrics(lg), daily_brief(lg), killday_brief(lg),
              calibration(lg))
    assert first == second
    ref = lg.snapshot()
    fresh = Ledger(tmp_path / "restored")
    fresh.restore(ref)
    assert (pipeline(fresh), metrics(fresh)) == (first[0], first[1])


def test_projections_write_nothing(tmp_path):
    """Purity: no projection call changes the ledger."""
    lg = _ledger(tmp_path)
    _story(lg)
    n = len(list(lg.read()))
    pipeline(lg), metrics(lg), daily_brief(lg), killday_brief(lg), calibration(lg)
    gate_brief(lg, "v-alpha")
    assert len(list(lg.read())) == n


def test_gate_brief_schema_and_critic(tmp_path):
    """INV-COND-2: the fixed schema, every field populated, critic.tier from the
    latest artifact_produced."""
    lg = _ledger(tmp_path)
    _story(lg)
    brief = gate_brief(lg, "v-alpha")
    assert brief.venture_id == "v-alpha" and brief.codename == "pods"
    assert brief.state is State.VALIDATING and brief.score == 20
    assert brief.critic.tier == 1
    assert brief.critic.artifact_ref == "ventures/v-alpha/brief.md"
    assert brief.evidence  # the PASS facts surfaced
    assert brief.recommendation in ("ADVANCE", "HOLD", "KILL")


def test_gate_brief_refused_without_critic(tmp_path):
    """INV-COND-2 fail-closed: no critic history → NoCriticForGate; unknown venture →
    UnknownVenture naming it."""
    lg = _ledger(tmp_path)
    _story(lg)
    with pytest.raises(NoCriticForGate):
        gate_brief(lg, "v-beta")  # no artifact/gate history
    with pytest.raises(UnknownVenture, match="v-ghost"):
        gate_brief(lg, "v-ghost")


def test_gate_brief_critic_falls_back_to_gate_decision(tmp_path):
    """§6.1: no artifact events but a prior gate_decision → that critic tier."""
    lg = _ledger(tmp_path)
    _capture(lg, "v-gd", "gd", State.SHAPING)
    a10.seed_gate_decision(lg, "v-gd", tier=2)
    assert gate_brief(lg, "v-gd").critic.tier == 2


def test_daily_brief_triage_and_silence(tmp_path):
    """docs/05 INV-TRIAGE: decisions surface for gate-ready ventures (≤3); an empty
    ledger yields silence — a valid, correct output."""
    lg = _ledger(tmp_path)
    assert daily_brief(lg).decisions == ()  # silence valid
    _story(lg)
    brief = daily_brief(lg)
    assert 0 < len(brief.decisions) <= 3
    assert any("v-alpha" in d for d in brief.decisions)  # PASS-validated → decidable
    assert dict(brief.pending_sends) == {"2026-07-19": 10}


def test_killday_every_active_venture(tmp_path):
    """docs/05 kill-day: every non-terminal venture appears exactly once — briefed or
    named unbriefable (never dropped)."""
    lg = _ledger(tmp_path)
    _story(lg)
    kd = killday_brief(lg)
    briefed = [b.venture_id for b, _rec in kd.rows]
    assert briefed == ["v-alpha"]  # has a critic take
    assert kd.unbriefable == ("v-beta",)  # active, no take — named
    assert "v-dead" not in briefed and "v-dead" not in kd.unbriefable  # terminal


def test_recommendation_mechanics(tmp_path):
    """§6.2 (advisory, deterministic): FAIL verdict → KILL; all-PASS forward facts →
    ADVANCE; no verdicts yet → HOLD."""
    lg = _ledger(tmp_path)
    _story(lg)
    assert gate_brief(lg, "v-alpha").recommendation == "ADVANCE"  # PASS + PASS
    a10.seed_artifact_produced(lg, "v-beta", tier=3)
    assert gate_brief(lg, "v-beta").recommendation == "KILL"  # FAIL evidence
    _capture(lg, "v-hold", "hold", State.VALIDATING)
    a10.seed_artifact_produced(lg, "v-hold", tier=2)
    assert gate_brief(lg, "v-hold").recommendation == "HOLD"  # no verdicts yet


def test_calibration_overrides_vs_outcomes(tmp_path):
    """docs/41 §3: overrides paired with outcomes-so-far; evidence verdicts paired
    with terminal fates."""
    lg = _ledger(tmp_path)
    _story(lg)
    a10.seed_override(lg, "v-dead", kind="override")
    a10.seed_override(lg, "v-alpha", kind="score_override")
    report = calibration(lg)
    overrides = {(vid, kind) for vid, kind, _out in report.overrides}
    assert ("v-dead", "override") in overrides
    assert ("v-alpha", "score_override") in overrides
    dead = next(out for vid, _k, out in report.overrides if vid == "v-dead")
    assert dead == "KILLED"
    verdicts = {vid: (verdict, outcome)
                for vid, verdict, outcome in report.evidence_vs_outcome}
    assert verdicts["v-alpha"][0] == "PASS"
