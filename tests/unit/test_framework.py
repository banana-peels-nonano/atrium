"""S10 Capability Framework unit suite (capabilities/TESTPLAN.md) — INV-WF-1..3.

Fully live stack (real Config/Ledger/Security/Memory/Router — no stubs); A11
``FakeProvider`` is every transport (INV-TEST-SAFE: no network anywhere).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.capabilities.framework import (
    CHECKLIST_MODEL,
    AuthorityRefused,
    BeatFailed,
    Critique,
    NoCriticTake,
    SpecInvalid,
    StateMismatch,
    UnknownWorkflow,
    WorkflowRegistry,
    WorkflowResult,
    family,
    generate_opencode,
    load_capability_spec,
)
from charterhouse.contracts.events import AUTHORIZATION_REQUIRED, EventType
from charterhouse.contracts.state import State, Venture
from charterhouse.memory import ScopeViolation
from charterhouse.memory.types import Lesson
from charterhouse.security.types import CheckpointError

from tests.fakes import FakeProvider
from tests.fixtures.pii_corpus import POSITIVES
from tests.unit import _a7_support as a7
from tests.unit import _a8_support as a8


# --- the 5-beat orchestration --------------------------------------------------------------


def test_run_happy_path_all_beats(tmp_path):
    """docs/04 §5: run() executes PREPARE→PRODUCE→CRITIQUE→CHECKPOINT and returns the
    GATE-facing result — artifact in the vault, critique attached, tier recorded,
    exactly ONE domain event carrying critic_tier."""
    s = a8.make_stack(tmp_path)
    result = s.workflow.run(State.CAPTURED, s.venture)
    artifact_path = s.vault_dir / result.artifact_ref
    assert artifact_path.is_file()
    assert result.critique is not None and result.critic_tier in (1, 2, 3)
    assert result.capability == "scout" and result.model == "llama3-local"
    events = a8.domain_events(s.ledger)
    assert [e.type for e in events] == [EventType.FRAME]
    assert events[0].payload["critic_tier"] == result.critic_tier
    assert events[0].venture_id == a8.VID
    assert events[0].event_id == result.event_id
    assert events[0].to_state is None  # state-neutral by construction (GATE is human)


def test_prepare_deterministic_no_writes(tmp_path):
    """INV-WF-1 (PREPARE side): deterministic frozen CapInput from live S9 — zero
    events, zero vault files, doctrine + ≤k records included."""
    s = a8.make_stack(tmp_path)
    s.memory.write_lesson(a7.lesson("anti-pattern: cold enterprise outreach stalls",
                                    lesson_id="les-anti", tags=("anti_pattern",)))
    before = len(list(s.ledger.read()))
    one = s.workflow.prepare(s.spec, s.venture, State.CAPTURED)
    two = s.workflow.prepare(s.spec, s.venture, State.CAPTURED)
    assert one == two  # frozen dataclasses, value-equal
    assert one.working_set.doctrine == a7.DOCTRINE
    assert len(one.working_set.records) <= s.spec.k
    assert len(list(s.ledger.read())) == before  # zero appends
    assert a8.vault_artifacts(s.vault_dir) == []


def test_produce_receives_working_memory(tmp_path):
    """PREPARE→PRODUCE contract (docs/04 §7): the transport-visible messages contain
    the spec mission, the Doctrine, and a seeded lesson's text."""
    rec = a8.RecordingProvider(canned="recorded draft")
    s = a8.make_stack(tmp_path, transports={"ollama": rec})
    s.memory.write_lesson(a7.lesson("anti-pattern: broad cold outreach on day one",
                                    lesson_id="les-seed", tags=("anti_pattern",)))
    cap_input = s.workflow.prepare(s.spec, s.venture, State.CAPTURED)
    s.workflow.produce_beat(cap_input)
    (messages,) = rec.seen
    blob = str(messages)
    assert a8.SCOUT_SPEC.mission in blob
    assert a7.DOCTRINE in blob
    assert "broad cold outreach on day one" in blob


def test_produce_idempotent(tmp_path):
    """INV-WF-1: the same CapInput twice → the identical frozen Artifact; no files, no
    non-telemetry events."""
    s = a8.make_stack(tmp_path)
    cap_input = s.workflow.prepare(s.spec, s.venture, State.CAPTURED)
    first = s.workflow.produce_beat(cap_input)
    second = s.workflow.produce_beat(cap_input)
    assert first == second
    assert first.model == "llama3-local" and first.venture_id == a8.VID
    assert a8.domain_events(s.ledger) == []
    assert a8.vault_artifacts(s.vault_dir) == []


def test_produce_retries_then_succeeds(tmp_path):
    """INV-WF-1 retryable: one full router failure → attempt 2 succeeds with the
    identical result; still zero state."""
    base = a8.make_stack(tmp_path / "base")
    flaky_stack = a8.make_stack(tmp_path / "flaky")
    flaky = a8.FlakyLLM(flaky_stack.router, failures=1)
    s = a8.make_stack(tmp_path / "run", llm=flaky)
    cap_input = s.workflow.prepare(s.spec, s.venture, State.CAPTURED)
    artifact = s.workflow.produce_beat(cap_input)
    clean_input = base.workflow.prepare(base.spec, base.venture, State.CAPTURED)
    assert artifact.text == base.workflow.produce_beat(clean_input).text
    assert flaky.calls == 2  # failed once, succeeded once
    assert a8.domain_events(s.ledger) == []
    assert a8.vault_artifacts(s.vault_dir) == []


def test_produce_exhausted_never_mutates_state(tmp_path):
    """INV-WF-1 (the founder-gate proof): every provider down → BeatFailed("produce");
    NO vault file, ledger holds ONLY telemetry (llm_call/error), the registry replay
    still shows the venture exactly as seeded."""
    from tests.fakes import ProviderError
    down = {pid: FakeProvider(error=ProviderError("down")) for pid in a8.PROVIDERS}
    s = a8.make_stack(tmp_path, transports=down)
    replay_before = s.ledger.replay().ventures[a8.VID]
    with pytest.raises(BeatFailed, match="produce"):
        s.workflow.run(State.CAPTURED, s.venture)
    assert a8.vault_artifacts(s.vault_dir) == []
    assert a8.domain_events(s.ledger) == []  # telemetry only
    assert s.ledger.replay().ventures[a8.VID] == replay_before
    assert s.ledger.replay().ventures[a8.VID].state is State.CAPTURED


@pytest.mark.parametrize("seed", range(10))
def test_retry_policy_property(tmp_path, seed):
    """INV-WF-1 (property): with the LLM seam failing the first k calls, run succeeds
    iff k < spec.retries (independent recomputation); on failure the zero-mutation
    assert holds."""
    k = seed % 4  # 0..3 failures against retries=2
    inner = a8.make_stack(tmp_path / "inner")
    s = a8.make_stack(tmp_path / "outer", llm=a8.FlakyLLM(inner.router, failures=k))
    should_succeed = k < s.spec.retries  # the independent oracle
    if should_succeed:
        result = s.workflow.run(State.CAPTURED, s.venture)
        assert (s.vault_dir / result.artifact_ref).is_file()
        assert len(a8.domain_events(s.ledger)) == 1
    else:
        with pytest.raises(BeatFailed, match="produce"):
            s.workflow.run(State.CAPTURED, s.venture)
        assert a8.vault_artifacts(s.vault_dir) == []
        assert a8.domain_events(s.ledger) == []


def test_checkpoint_only_mutating_beat(tmp_path):
    """INV-WF-1 (beat isolation — the founder-gate proof): after PREPARE + PRODUCE +
    CRITIQUE there is zero state anywhere; the FIRST mutation appears at CHECKPOINT —
    exactly one vault file and one domain event."""
    s = a8.make_stack(tmp_path)
    cap_input = s.workflow.prepare(s.spec, s.venture, State.CAPTURED)
    artifact = s.workflow.produce_beat(cap_input)
    critique = s.workflow.critique_beat(cap_input, artifact)
    # Three beats done — nothing has changed in the world:
    assert a8.vault_artifacts(s.vault_dir) == []
    assert a8.domain_events(s.ledger) == []
    assert s.ledger.replay().ventures[a8.VID].state is State.CAPTURED
    # The fourth beat is the one and only mutation:
    result = s.workflow.checkpoint(s.spec, s.venture, artifact, critique)
    assert len(a8.vault_artifacts(s.vault_dir)) == 1
    assert len(a8.domain_events(s.ledger)) == 1
    assert (s.vault_dir / result.artifact_ref).is_file()


def test_checkpoint_redacts_via_live_s7(tmp_path):
    """CHECKPOINT = live S7 (docs/04 §5): a produced artifact carrying corpus PII lands
    in the vault REDACTED, with the sidecar ref on the result; the event payload holds
    refs only."""
    email = POSITIVES[0][1]
    pii_provider = FakeProvider(canned=f"Brief: contact {email} for the interview")
    s = a8.make_stack(tmp_path, transports={"ollama": pii_provider})
    result = s.workflow.run(State.CAPTURED, s.venture)
    stored = (s.vault_dir / result.artifact_ref).read_text(encoding="utf-8")
    assert email not in stored
    assert result.sidecar_ref is not None
    (event,) = a8.domain_events(s.ledger)
    assert email not in str(event.payload)


def test_checkpoint_failure_leaves_no_partial_state(tmp_path):
    """INV-WF-1 fail-closed: a refusing S7 probe → nothing written, nothing appended;
    a failing-append Ledger probe → the just-written artifact is rolled back."""
    refusing = a8.RefusingSecurity(tmp_path / "refuse" / "vault")
    s = a8.make_stack(tmp_path / "refuse", security=refusing)
    with pytest.raises(CheckpointError):
        s.workflow.run(State.CAPTURED, s.venture)
    assert a8.vault_artifacts(s.vault_dir) == []
    assert a8.domain_events(s.ledger) == []

    failing_ledger = a7.FailingAppendLedger(tmp_path / "append" / "ledger")
    s2 = a8.make_stack(tmp_path / "append", ledger=failing_ledger, seed=False)
    with pytest.raises(RuntimeError, match="R10 probe"):
        s2.workflow.run(State.CAPTURED, s2.venture)
    assert a8.vault_artifacts(s2.vault_dir) == []  # artifact rolled back


# --- INV-WF-2: the Critic degrade ladder ---------------------------------------------------


def test_critic_tier1_diff_family(tmp_path):
    """INV-WF-2: producer family "llama", critic route lands "deepseek" → tier 1, the
    critic model recorded; the family fn is correct over the fixture catalog."""
    s = a8.make_stack(tmp_path)  # ROUTES: critic → deepseek-chat-free
    result = s.workflow.run(State.CAPTURED, s.venture)
    assert result.critic_tier == 1
    assert result.critique.tier == 1
    assert result.critique.model == "deepseek-chat-free"
    assert family("llama3-local") == "llama" == family("llama3-big")
    assert family("deepseek-chat-free") == "deepseek"
    assert family("gemini-flash") == "gemini"
    assert family("claude-sonnet") == "claude"


def test_critic_tier2_same_family_diff_model(tmp_path):
    """INV-WF-2 ladder: the critic chain can only land the producer's family (llama)
    on a DIFFERENT model → tier 2, recorded honestly."""
    s = a8.make_stack(tmp_path, routes=a8.ROUTES_SAMEFAM)  # critic → llama3-big
    result = s.workflow.run(State.CAPTURED, s.venture)
    assert result.critic_tier == 2
    assert result.critique.model == "llama3-big"


def test_critic_tier3_router_exhausted(tmp_path):
    """INV-WF-2 floor: the critic call exhausts the router → the deterministic
    checklist critique (byte-identical for the same artifact), run still completes."""
    switchable = {pid: a8.SwitchableProvider(canned=f"draft from {pid}")
                  for pid in a8.PROVIDERS}
    s = a8.make_stack(tmp_path, transports=switchable)
    cap_input = s.workflow.prepare(s.spec, s.venture, State.CAPTURED)
    artifact = s.workflow.produce_beat(cap_input)
    for provider in switchable.values():  # everything down AFTER produce
        provider.fail = True
    one = s.workflow.critique_beat(cap_input, artifact)
    two = s.workflow.critique_beat(cap_input, artifact)
    assert one.tier == 3 and one.model == CHECKLIST_MODEL
    assert one == two  # deterministic


def test_critic_tier3_self_critique_refused(tmp_path):
    """INV-WF-2: the critic route answering with the SAME model that produced →
    tier 3 (never self-critique)."""
    s = a8.make_stack(tmp_path, routes=a8.ROUTES_SELF)  # critic → llama3-local
    result = s.workflow.run(State.CAPTURED, s.venture)
    assert result.critic_tier == 3
    assert result.critique.model == CHECKLIST_MODEL


def test_critique_never_fails_the_run(tmp_path):
    """INV-WF-2 always-available: with every cloud provider down (critic chain dead,
    local producer alive), run completes with a tier-3 critique attached."""
    from tests.fakes import ProviderError
    down = {pid: FakeProvider(error=ProviderError("down"))
            for pid in ("openrouter", "gemini")}
    s = a8.make_stack(tmp_path, transports=down)
    result = s.workflow.run(State.CAPTURED, s.venture)
    assert result.critic_tier == 3
    assert result.critique.model == CHECKLIST_MODEL
    assert len(a8.domain_events(s.ledger)) == 1


# --- INV-WF-3 + no-authority guards --------------------------------------------------------


def test_gate_needs_critic_take(tmp_path):
    """INV-WF-3: a WorkflowResult without a critique cannot exist; checkpoint refuses
    critique=None."""
    with pytest.raises(NoCriticTake):
        WorkflowResult(artifact_ref="x.md", critique=None, critic_tier=1,
                       event_id="e", capability="scout", model="m")
    s = a8.make_stack(tmp_path)
    cap_input = s.workflow.prepare(s.spec, s.venture, State.CAPTURED)
    artifact = s.workflow.produce_beat(cap_input)
    with pytest.raises(NoCriticTake):
        s.workflow.checkpoint(s.spec, s.venture, artifact, None)
    assert a8.vault_artifacts(s.vault_dir) == []
    assert a8.domain_events(s.ledger) == []


@pytest.mark.parametrize("red_type", sorted(AUTHORIZATION_REQUIRED, key=lambda t: t.value))
def test_registry_refuses_gate_red_event_types(red_type):
    """No-authority MUST (docs/13, RISKS R1): a workflow row naming a gate/RED event
    type is refused at construction — before anything can run."""
    with pytest.raises(AuthorityRefused, match=red_type.value):
        WorkflowRegistry({State.CAPTURED: a8.workflow_spec(event_type=red_type)})


def test_registry_refuses_unknown_event_type():
    """The event_type must be a frozen docs/41 catalog member."""
    with pytest.raises(AuthorityRefused):
        WorkflowRegistry({State.CAPTURED: a8.workflow_spec(event_type="made_up")})


def test_write_scope_enforced_via_memory_seam(tmp_path):
    """docs/54 §S11 (framework half): lesson writes are scoped to the spec's declared
    WRITE tags via S9's seam — out-of-scope surfaces ScopeViolation, nothing stored."""
    s = a8.make_stack(tmp_path)
    in_scope = Lesson(text="a shaped brief lesson", source_ref="vault/lessons/b.md",
                      tags=("brief",), lesson_id="les-in")
    assert s.workflow.write_lesson(s.spec, in_scope) == "les-in"
    out_scope = Lesson(text="a pricing lesson", source_ref="vault/lessons/p.md",
                       tags=("pricing",), lesson_id="les-out")
    with pytest.raises(ScopeViolation):
        s.workflow.write_lesson(s.spec, out_scope)
    stored = {r["id"] for r in s.mem.store.all_rows()}
    assert "les-in" in stored and "les-out" not in stored


def test_unknown_state_and_mismatch_refused(tmp_path):
    """Fail-closed preconditions: no spec for the state → UnknownWorkflow; a stale
    venture snapshot → StateMismatch; both before any beat (zero events)."""
    s = a8.make_stack(tmp_path)
    before = len(list(s.ledger.read()))
    with pytest.raises(UnknownWorkflow):
        s.workflow.run(State.BUILDING, Venture(id=a8.VID, codename="pods",
                                               state=State.BUILDING))
    stale = Venture(id=a8.VID, codename="pods", state=State.FRAMED)
    with pytest.raises(StateMismatch):
        s.workflow.run(State.CAPTURED, stale)
    assert len(list(s.ledger.read())) == before


def test_framework_imports_no_authority():
    """docs/43 §5/§8 (static): nothing under capabilities/ imports governance or
    lifecycle — the framework structurally cannot authorize or transition."""
    root = Path(__file__).resolve().parents[2] / "charterhouse" / "capabilities"
    offenders = []
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for needle in ("charterhouse.governance", "charterhouse.lifecycle"):
            if needle in text:
                offenders.append(f"{py.name}: {needle}")
    assert not offenders, f"authority-granting import in S10: {offenders}"


# --- neutral-spec loader + harness generator ----------------------------------------------


def test_spec_loader_parses_neutral_format(tmp_path):
    """The frozen *.agent.md format: a valid spec parses into every CapabilitySpec
    field; name comes from the filename stem."""
    path = tmp_path / "scout.agent.md"
    path.write_text(a8.spec_markdown(), encoding="utf-8")
    spec = load_capability_spec(path)
    assert spec.name == "scout"
    assert spec.mission.startswith("Find and frame")
    assert spec.inputs == ("captured note",)
    assert spec.outputs == ("brief", "score")
    assert spec.memory_read == ("anti_pattern", "segment")
    assert spec.memory_write == ("brief",)
    assert spec.escalation.startswith("Flag thin evidence")


@pytest.mark.parametrize("missing", ["Mission", "Scope", "Inputs", "Outputs",
                                     "Memory Scope", "Escalation"])
def test_spec_loader_missing_section_refused(tmp_path, missing):
    """SpecInvalid names the missing required section (fail closed)."""
    path = tmp_path / "scout.agent.md"
    path.write_text(a8.spec_markdown(drop_section=missing), encoding="utf-8")
    with pytest.raises(SpecInvalid, match=missing):
        load_capability_spec(path)


@pytest.mark.parametrize("literal", ["no authority", "stateless"])
def test_spec_loader_missing_literal_refused(tmp_path, literal):
    """The mandatory no-authority/stateless literals are load-bearing (docs/13)."""
    path = tmp_path / "scout.agent.md"
    path.write_text(a8.spec_markdown(drop_literal=literal), encoding="utf-8")
    with pytest.raises(SpecInvalid, match=literal):
        load_capability_spec(path)


def test_spec_loader_empty_stub_refused(repo_root):
    """The Phase-0 stubs in agents/ fail loudly, never silently (RISKS R7)."""
    with pytest.raises(SpecInvalid):
        load_capability_spec(repo_root / "agents" / "scout.agent.md")


def test_opencode_generator_deterministic(tmp_path):
    """The harness adapter is a byte-deterministic generator: one stamped file per
    spec; regeneration is identical; hand-edit drift would show as a diff."""
    out = tmp_path / "opencode"
    first = generate_opencode([a8.SCOUT_SPEC], out)
    assert [p.name for p in first] == ["scout.md"]
    content = first[0].read_text(encoding="utf-8")
    assert "GENERATED-DO-NOT-EDIT" in content
    assert a8.SCOUT_SPEC.mission in content
    assert "no authority" in content.lower()
    again = generate_opencode([a8.SCOUT_SPEC], out)
    assert again[0].read_bytes() == first[0].read_bytes()
