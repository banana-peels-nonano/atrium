"""The AI verdict loop (feat/ai-verdict) — three core-loop fixes, all against the live
stack with A11 fakes as every transport (no network anywhere, INV-TEST-SAFE):

1. ``advise`` — the CLI/Conductor command that runs the venture's CURRENT-state workflow
   (PRODUCE→CRITIQUE) and records a critic take, making the gate brief presentable
   (INV-COND-2). Governance stays intact (advise is YELLOW: no token; admit/gate/kill stay
   RED), the INV-PII-3 cloud block covers BOTH LLM legs, and the INV-WF-2 cross-family
   critic rule is untouched.
2. ``clock_from_ledger`` — the factory clock is reconstructed at boot, so the paused flag
   and accumulated active time survive across processes.
3. The kill-day read carries the steer, ordered worst-first, still naming unbriefable
   ventures (never dropped).
"""

from __future__ import annotations

import pytest

from charterhouse.capabilities.framework.critic import Critic, checklist
from charterhouse.capabilities.framework.types import Artifact
from charterhouse.contracts.authz import ActionColor
from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State
from charterhouse.governance.classify import classify
from charterhouse.governance.types import Action
from charterhouse.ledger import Ledger
from charterhouse.lifecycle.clock import FactoryClock, clock_from_ledger
from charterhouse.projections.briefs import gate_brief, killday_brief
from charterhouse.router.types import Require

from tests.unit import _a10_support as a10
from tests.unit import _a8_support as a8


# --- 2. clock seeding (S5) ----------------------------------------------------------------


def test_clock_seeds_the_paused_flag_from_the_ledger(tmp_path):
    """`resume` was broken across processes: each boot started unpaused, so it refused
    "factory is not paused". The flag now comes from the ledger's last pause/resume."""
    ledger = Ledger(tmp_path / "ledger")
    assert clock_from_ledger(ledger).paused is False  # empty ledger => unpaused
    ledger.append(Event(type=EventType.PAUSE, actor="lifecycle", payload={"reason": "hol"}))
    assert clock_from_ledger(ledger).paused is True  # survives the process boundary
    ledger.append(Event(type=EventType.RESUME, actor="lifecycle", payload={"reason": "back"}))
    assert clock_from_ledger(ledger).paused is False  # last one wins


def test_clock_seeds_accumulated_active_time_from_the_ledger(tmp_path):
    """Active time no longer resets to 0 every command — it resumes from the high-water
    mark already stamped on the ledger, so active-day guards see real elapsed time."""
    ledger = Ledger(tmp_path / "ledger")
    ledger.append(Event(type=EventType.CAPTURE, actor="conductor", payload={},
                        venture_id="v1", active_time=0))
    ledger.append(Event(type=EventType.EVIDENCE_GATE, actor="conductor", payload={},
                        venture_id="v1", active_time=7))
    assert clock_from_ledger(ledger).now_active == 7
    # A fresh clock is still the injectable default for tests/simulator.
    assert FactoryClock().now_active == 0


def test_clock_seeding_tolerates_absent_active_time_and_timestamps(tmp_path):
    """Every event in the founder's existing ledger carries active_time 0 / timestamp
    None — seeding must degrade to zero, never raise, on that history."""
    ledger = Ledger(tmp_path / "ledger")
    ledger.append(Event(type=EventType.CAPTURE, actor="conductor", payload={},
                        venture_id="v1"))
    clock = clock_from_ledger(ledger)
    assert clock.now_active == 0 and clock.paused is False


# --- 1a. governance: advise is YELLOW, the RED set is untouched ---------------------------


def test_advise_is_yellow_so_only_admit_gate_kill_need_approval():
    """advise spends model tokens (metered, like `build`) but is not a founder decision —
    it must not require --approve, and it must not weaken the RED set."""
    assert classify(Action(name="advise", venture_id="v1")).color is ActionColor.YELLOW
    assert classify(Action(name="advise", venture_id="v1")).two_key is False
    for red in ("admit", "gate", "kill"):
        assert classify(Action(name=red, venture_id="v1")).color is ActionColor.RED


# --- 1b. the critic: PII propagation + the steer ------------------------------------------


class RecordingLLM:
    """Records every (role, require) the critic/producer asks for; returns canned text."""

    def __init__(self, text: str = "FINDINGS: thin evidence.\nSTEER: interview 5 ops leads.",
                 model: str = "gemini-flash") -> None:
        self._text = text
        self._model = model
        self.calls: list[dict] = []

    def call(self, role, messages, tools=None, require=None):  # noqa: ANN001
        self.calls.append({"role": role, "require": require})
        from charterhouse.router.types import LLMResponse

        return LLMResponse(text=self._text, model=self._model, usage={"in": 1, "out": 1},
                           cost_usd=0.0, latency_ms=0)


def _artifact(text: str = "a plausible venture brief with evidence") -> Artifact:
    return Artifact(text=text, capability="analyst", role="reasoning",
                    model="llama3-local", venture_id="v1", state=State.VALIDATING)


def test_critique_propagates_require_so_pii_cannot_reach_a_cloud_critic():
    """The hole this closes: PRODUCE honoured contains_pii but CRITIQUE passed no require,
    so the artifact text (PII and all) could still be sent to a cloud critic."""
    llm = RecordingLLM()
    Critic(llm).critique(_artifact(), a8.SCOUT_SPEC,
                         require=Require(contains_pii=True))
    assert llm.calls[0]["require"] is not None
    assert llm.calls[0]["require"].contains_pii is True


def test_critique_splits_a_concrete_steer_from_the_findings():
    """The gate brief needs a STEER — what to build instead / how to sharpen — not just
    kill/continue. The critic is asked for a labelled STEER section; the split is a plain
    string partition, so a non-compliant answer degrades to no steer rather than garbage."""
    llm = RecordingLLM(text="FINDINGS: segment is too broad.\nSTEER: narrow to SMB ops "
                            "teams and re-run the interview set.")
    critique = Critic(llm).critique(_artifact(), a8.SCOUT_SPEC)
    assert "narrow to SMB ops teams" in critique.steer
    assert "STEER:" not in critique.steer  # the label is stripped, the text kept
    assert "segment is too broad" in critique.findings[0]
    assert "narrow to SMB ops" not in critique.findings[0]  # steer is not duplicated


def test_critique_without_a_steer_section_reports_no_steer():
    llm = RecordingLLM(text="Just prose with no labelled section.")
    critique = Critic(llm).critique(_artifact(), a8.SCOUT_SPEC)
    assert critique.steer == ""
    assert "Just prose" in critique.findings[0]


def test_tier3_checklist_has_no_steer_and_says_so():
    """Honesty: the deterministic floor produces mechanical findings, never a steer — the
    brief must not present a checklist as if a critic had recommended a direction."""
    critique = checklist(_artifact(text="short"), a8.SCOUT_SPEC)
    assert critique.tier == 3 and critique.steer == ""


# --- 1c. advise through the chokepoint ----------------------------------------------------


def _validating_venture(f, vid: str = "v-adv"):
    """Drive a venture to VALIDATING through the real chokepoint (RED admit approved)."""
    f.conductor.command("capture", {"venture_id": vid, "codename": "atrium"})
    f.conductor.command("frame", {"venture_id": vid, "brief_ref": "b", "score": 19,
                                  "quotes": 2})
    f.conductor.command("admit", {"venture_id": vid}, a10.tok(f, "admit", vid))
    return vid


def test_advise_records_a_critic_take_and_makes_the_gate_presentable(tmp_path):
    """The core fix (§7.1): before advise, the gate brief refuses (INV-COND-2); after it,
    the brief exists and carries the critic take the workflow produced."""
    f = a10.make_factory(tmp_path)
    vid = _validating_venture(f)
    from charterhouse.projections.types import NoCriticForGate

    with pytest.raises(NoCriticForGate):
        gate_brief(f.ledger, vid)

    result = f.conductor.command("advise", {"venture_id": vid})
    assert result.ok and result.color == "YELLOW"  # no founder token needed
    brief = gate_brief(f.ledger, vid)  # now presentable
    assert brief.critic.tier in (1, 2, 3)
    assert brief.critic.artifact_ref  # the artifact it critiqued


def test_advise_runs_the_ventures_current_state_workflow(tmp_path):
    """advise is state-driven: a VALIDATING venture gets the analyst workflow (docs/13
    table), not a hardcoded one."""
    f = a10.make_factory(tmp_path)
    vid = _validating_venture(f)
    f.conductor.command("advise", {"venture_id": vid})
    produced = [e for e in f.ledger.read()
                if e.type is EventType.ARTIFACT_PRODUCED and e.venture_id == vid]
    assert len(produced) == 1
    assert produced[0].payload["capability"] == "analyst"
    assert produced[0].to_state is None  # state-neutral (INV-WF-1); GATE stays human


def test_advise_refuses_for_a_state_with_no_workflow_row(tmp_path):
    """Fail closed with the owner's words — FRAMED has no workflow row."""
    f = a10.make_factory(tmp_path)
    vid = "v-framed"
    f.conductor.command("capture", {"venture_id": vid, "codename": "x"})
    f.conductor.command("frame", {"venture_id": vid, "brief_ref": "b", "score": 19,
                                  "quotes": 2})
    from charterhouse.conductor.types import ConductorError

    with pytest.raises(ConductorError):
        f.conductor.command("advise", {"venture_id": vid})


def test_advise_never_moves_the_venture_and_gate_still_needs_approval(tmp_path):
    """advise informs the gate; it never crosses it. The RED boundary is unchanged."""
    f = a10.make_factory(tmp_path)
    vid = _validating_venture(f)
    before = f.registry.get(vid).state
    f.conductor.command("advise", {"venture_id": vid})
    assert f.registry.get(vid).state is before  # no advance from an AI opinion
    from charterhouse.conductor.types import ConductorError

    with pytest.raises(ConductorError):  # gate still RED: tokenless is refused
        f.conductor.command("gate", {"venture_id": vid, "decision": "ADVANCE",
                                     "to": "SHAPING"})


def test_pii_advise_makes_zero_cloud_sends_across_both_llm_legs(tmp_path):
    """INV-PII-3 end-to-end over the advise path: with a contains_pii require, NEITHER the
    produce leg nor the critique leg may reach a cloud transport. Local-only is the
    PII-legal path, so the run still completes."""
    f = a10.make_factory(tmp_path)
    vid = _validating_venture(f)
    cloud = [pid for pid in f.transports
             if f.config.get_provider(pid).kind != "local"]
    before = {pid: f.transports[pid].call_count for pid in cloud}

    f.conductor.command("advise", {"venture_id": vid, "contains_pii": True})

    for pid in cloud:
        assert f.transports[pid].call_count == before[pid], (
            f"PII advise sent to cloud provider {pid!r}")
    produced = [e for e in f.ledger.read() if e.type is EventType.ARTIFACT_PRODUCED]
    assert produced, "the local-only run should still have produced an artifact"


def test_advise_records_the_steer_and_verdict_on_the_ledger(tmp_path):
    """The steer must be durable evidence, not console output — it rides the additive
    artifact_produced payload fields so the gate brief can replay it."""
    f = a10.make_factory(tmp_path)
    vid = _validating_venture(f)
    f.conductor.command("advise", {"venture_id": vid})
    (produced,) = [e for e in f.ledger.read()
                   if e.type is EventType.ARTIFACT_PRODUCED and e.venture_id == vid]
    for key in ("artifact_ref", "capability", "critic_tier", "critic_verdict", "steer"):
        assert key in produced.payload, f"payload missing {key!r}"


# --- 1d + 3. the briefs carry the steer ---------------------------------------------------


def test_gate_brief_carries_the_steer_with_its_tier_and_evidence(tmp_path):
    """A verdict packet is kill/continue PLUS a steer, with the evidence it rests on and
    the tier that produced it (so a checklist floor is never read as critic advice)."""
    f = a10.make_factory(tmp_path)
    vid = _validating_venture(f)
    f.conductor.command("validate.evidence", {"venture_id": vid, "verdict": "PASS",
                                              "quote_count": 7})
    f.conductor.command("advise", {"venture_id": vid})
    brief = gate_brief(f.ledger, vid)
    assert brief.recommendation in ("ADVANCE", "HOLD", "KILL")
    assert isinstance(brief.steer, str)
    assert brief.critic.tier in (1, 2, 3)
    assert any("evidence:PASS" in e for e in brief.evidence)


def test_cli_advise_prints_a_verdict_summary_not_a_prose_dump(tmp_path, capsys):
    """The CLI must RENDER a WorkflowResult. Without its own branch the generic fallback
    prints the whole dataclass — including the critic's full prose inside `findings` — as
    one unbounded blob."""
    from charterhouse.conductor import cli

    f = a10.make_factory(tmp_path)
    vid = _validating_venture(f)
    assert cli.main(["advise", "--venture", vid], factory=f) == 0
    out = capsys.readouterr().out
    assert "OK advise" in out and "YELLOW" in out
    assert "critic tier" in out  # provenance is shown next to the advice
    assert "Critique(" not in out and "findings=" not in out  # no dataclass dump


def test_cli_gatebrief_shows_the_steer_with_its_tier(tmp_path, capsys):
    from charterhouse.conductor import cli

    f = a10.make_factory(tmp_path)
    vid = _validating_venture(f)
    cli.main(["advise", "--venture", vid], factory=f)
    capsys.readouterr()
    assert cli.main(["gatebrief", "--venture", vid], factory=f) == 0
    out = capsys.readouterr().out
    assert "recommendation:" in out and "critic tier:" in out
    assert "steer:" in out  # the direction, not just kill/continue


def test_build_factory_seeds_the_clock_from_the_ledger(tmp_path):
    """The composition root wires the reconstructed clock, so a pause issued by one
    command is still in force for the next process."""
    from charterhouse.conductor import cli
    from tests.fakes import FakeEmbedder

    repo = a10.AGENTS_DIR.parent
    data = tmp_path / "data"
    first = cli.build_factory(repo, data, profile="free", embedder=FakeEmbedder(32),
                              embed_model="fake-embed-v1")
    first.conductor.command("pause", {"reason": "holiday"})
    second = cli.build_factory(repo, data, profile="free", embedder=FakeEmbedder(32),
                               embed_model="fake-embed-v1")
    assert second.clock.paused is True  # survived the process boundary
    assert second.conductor.command("resume", {"reason": "back"}).ok  # no longer refuses


def test_build_factory_live_wires_the_real_transports_without_network(tmp_path):
    """`live=True` is the production boot seam: it wires the real HTTP transports and the
    local embedder. Constructing them opens no socket — and the default stays fail-closed
    so no test can reach the network by omission (INV-TEST-SAFE)."""
    from charterhouse.conductor import cli
    from charterhouse.conductor.transport import HttpOllamaTransport

    stub = cli.build_factory(a10.AGENTS_DIR.parent, tmp_path / "d1", profile="free")
    assert isinstance(stub.router._transports["ollama"], cli.NoTransport)

    live = cli.build_factory(a10.AGENTS_DIR.parent, tmp_path / "d2", profile="free",
                             live=True)
    assert isinstance(live.router._transports["ollama"], HttpOllamaTransport)


def test_killday_orders_worst_first_and_still_names_the_unbriefable(tmp_path):
    """The daily read: briefable ventures ordered KILL → HOLD → ADVANCE so the decisions
    that end things come first — and ventures with no critic take are still NAMED, never
    silently dropped (the honesty property)."""
    f = a10.make_factory(tmp_path)
    keep = _validating_venture(f, "v-keep")
    f.conductor.command("validate.evidence", {"venture_id": keep, "verdict": "PASS",
                                              "quote_count": 9})
    f.conductor.command("advise", {"venture_id": keep})
    doomed = _validating_venture(f, "v-doomed")
    f.conductor.command("validate.evidence", {"venture_id": doomed, "verdict": "FAIL",
                                              "quote_count": 1})
    f.conductor.command("advise", {"venture_id": doomed})
    _validating_venture(f, "v-silent")  # no advise => no critic take

    brief = killday_brief(f.ledger)
    recs = [rec for _b, rec in brief.rows]
    assert recs == sorted(recs, key=lambda r: {"KILL": 0, "HOLD": 1, "ADVANCE": 2}[r])
    assert recs[0] == "KILL" and any(b.venture_id == doomed for b, _ in brief.rows)
    assert "v-silent" in brief.unbriefable  # named, never dropped
