"""S10 integration suite (capabilities/TESTPLAN.md) — the runner across every live
seam at once, and the load-bearing proof that GATE never advances itself (live S5).

No network (INV-TEST-SAFE): FakeProvider transports, embedded LanceDB, tmp vault.
"""

from __future__ import annotations

import pytest

from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State

from tests.unit import _a4_support as a4
from tests.unit import _a7_support as a7
from tests.unit import _a8_support as a8


def test_it_full_stack_run_with_live_seams(tmp_path):
    """One run over real Config+Ledger+Security+Memory+Router: the seeded lesson feeds
    the produced context, the artifact lands redacted in the vault, ONE domain event
    carries the critic tier, and S8 telemetry shows both LLM beats."""
    rec = a8.RecordingProvider(canned="a shaped scout brief with a score")
    s = a8.make_stack(tmp_path, transports={"ollama": rec})
    s.memory.write_lesson(a7.lesson(
        "anti-pattern: skipping segment interviews before pricing work",
        lesson_id="les-live", tags=("anti_pattern",)))

    result = s.workflow.run(State.CAPTURED, s.venture)

    assert (s.vault_dir / result.artifact_ref).is_file()
    assert "skipping segment interviews" in str(rec.seen)  # memory reached PRODUCE
    domain = a8.domain_events(s.ledger)
    assert [e.type for e in domain] == [EventType.LESSON_WRITTEN, EventType.FRAME]
    frame = domain[-1]  # the ONE workflow event (the lesson write was the test's seed)
    assert frame.payload["critic_tier"] == result.critic_tier
    llm_calls = [e for e in s.ledger.read() if e.type is EventType.LLM_CALL]
    assert len(llm_calls) == 2  # produce + critique (INV-ROUTE-4 under the beats)


def test_it_gate_never_advances_itself(tmp_path):
    """docs/13 "lets no gate advance itself": after a full run the LIVE registry replay
    still shows CAPTURED; only the explicit live-S5 transition (the test playing
    S12/founder at GATE) moves the venture to FRAMED."""
    sim = a4.Sim(tmp_path)
    sim.new(a8.VID, codename="pods")
    stack = a8.make_stack(tmp_path, ledger=sim.ledger, seed=False)
    venture = sim.v(a8.VID)
    assert venture.state is State.CAPTURED

    stack.workflow.run(State.CAPTURED, venture)
    assert sim.v(a8.VID).state is State.CAPTURED  # the runner moved nothing

    sim.frame(a8.VID)  # the human gate decision, via live Lifecycle (IF-4)
    assert sim.v(a8.VID).state is State.FRAMED

    frames = [e for e in sim.ledger.read() if e.type is EventType.FRAME]
    assert len(frames) == 2  # the workflow's domain event + the S5 gate advance
    # The workflow's event is state-neutral; ONLY the live-S5 one carries to_state:
    assert [e.to_state for e in frames].count(None) == 1
    assert [e.to_state for e in frames].count(State.FRAMED.value) == 1
