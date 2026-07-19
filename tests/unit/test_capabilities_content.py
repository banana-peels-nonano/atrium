"""S11 Content suite — the six neutral capability contracts (docs/13 table, docs/54
§S11; A9's deliverable `agents/*.agent.md` against A8's frozen loader format).

Written BEFORE the specs (tests-first): the Phase-0 stubs fail ``SpecInvalid`` until A9
fills them. Assertions are contract facts, not prose taste: the docs/13 memory-scope
table verbatim, the v1.1 special rules present, the framework's write-scope enforcement
per capability (docs/54 §S11 "write outside scope is refused"), and a full 5-beat
dry-run per capability over the live stack (docs/13 acceptance).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.capabilities.framework import (
    generate_opencode,
    load_capability_spec,
    load_capability_specs,
)
from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State
from charterhouse.memory import ScopeViolation
from charterhouse.memory.types import Lesson

from tests.unit import _a8_support as a8

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"

CAPABILITIES = ("analyst", "builder", "critic", "growth", "librarian", "scout")

# The docs/13 table, verbatim: declared memory scope per capability (tags the S9
# ``scope=`` seam enforces). Critic writes NOTHING.
DECLARED_SCOPES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "scout": (("anti_pattern", "segment"), ("brief",)),
    "analyst": (("teardown", "segment"), ("research",)),
    "builder": (("build", "template"), ("build", "template")),
    "growth": (("channel",), ("channel",)),
    "librarian": (("all",), ("lesson", "playbook")),
    "critic": (("lesson",), ()),
}

# The docs/13 table, verbatim: what each capability produces.
DECLARED_OUTPUTS: dict[str, tuple[str, ...]] = {
    "scout": ("brief", "score"),
    "analyst": ("research pack", "validation plan"),
    "builder": ("spec", "staging MVP", "templates"),
    "growth": ("copy", "outreach drafts", "launch kit", "partners outreach"),
    "librarian": ("lessons", "playbooks", "index", "calibration"),
    "critic": ("critique",),
}

# The v1.1 special rules (docs/13 table, column "Special rules") — each phrase must be
# load-bearing text in the spec body (mission+scope+escalation), not implied.
V11_PHRASES: dict[str, tuple[str, ...]] = {
    "scout": ("hypothesis", "grace"),                       # R-REACH-HYP + cold-start KPI
    "analyst": ("before", "spend", ".private.md"),          # R-EVIDENCE-GATE + PII sidecar
    "builder": ("two-key", "staging"),                       # R-CHARGE; staging autonomous
    "growth": ("draft", "send budget", "shaping"),           # drafts-only + R-SEND-BUDGET + R-PARTNERS
    "librarian": ("anti-pattern", "reversible", "propose"),  # R-SALVAGE-TYPES + INV-MEM-3 + doctrine
    "critic": ("family", "ladder", "tier"),                  # R-CRITIC-DEGRADE
}


def _spec(name: str):
    return load_capability_spec(AGENTS_DIR / f"{name}.agent.md")


def _body(spec) -> str:
    return " ".join((spec.mission, spec.scope, spec.escalation)).lower()


# --- the six contracts load against the frozen format --------------------------------------


def test_all_six_specs_load(repo_root):
    """docs/51 A9 deliverable: every agents/*.agent.md parses under A8's frozen loader
    (the Phase-0 stubs failed SpecInvalid); the set is exactly the six capabilities."""
    specs = load_capability_specs(repo_root / "agents")
    assert tuple(s.name for s in specs) == CAPABILITIES  # sorted, complete, no extras


@pytest.mark.parametrize("name", CAPABILITIES)
def test_spec_contract_shape(name):
    """docs/13: contracts, not prompts — mission/scope/inputs/outputs/escalation all
    non-empty; the no-authority + stateless literals are in every contract (the loader
    enforces the literals; this pins the semantic fields too)."""
    spec = _spec(name)
    assert spec.mission and spec.scope and spec.escalation
    assert spec.inputs and spec.outputs
    text = (AGENTS_DIR / f"{name}.agent.md").read_text(encoding="utf-8").lower()
    assert "no authority" in text and "stateless" in text


@pytest.mark.parametrize("name", CAPABILITIES)
def test_declared_memory_scope_matches_contract(name):
    """docs/54 §S11 row 1: each capability's declared memory scope matches the docs/13
    table exactly — READ and WRITE tag-for-tag (the framework enforces WRITE)."""
    spec = _spec(name)
    read, write = DECLARED_SCOPES[name]
    assert spec.memory_read == read
    assert spec.memory_write == write


@pytest.mark.parametrize("name", CAPABILITIES)
def test_declared_outputs_match_contract(name):
    """docs/13 table: what each capability produces, verbatim."""
    assert _spec(name).outputs == DECLARED_OUTPUTS[name]


@pytest.mark.parametrize("name", CAPABILITIES)
def test_v11_special_rules_present(name):
    """The v1.1 specifics are load-bearing contract text (docs/13 "Special rules"):
    reachability-as-hypothesis/KPI grace, evidence-before-spend/.private.md, two-key
    RED/staging, drafts-only/send budget/SHAPING, salvage-anti-patterns/reversible/
    propose-doctrine, cross-family ladder/tier."""
    body = _body(_spec(name))
    for phrase in V11_PHRASES[name]:
        assert phrase in body, f"{name}: missing v1.1 phrase {phrase!r}"


# --- the framework enforces the declared write scope (docs/54 §S11 row 2) ------------------


@pytest.mark.parametrize("name", CAPABILITIES)
def test_framework_refuses_out_of_scope_write(tmp_path, name):
    """docs/54 §S11: a write outside the declared scope is refused by the framework
    (S9's scope seam, ScopeViolation); an in-scope write lands. The Critic — whose
    contract declares NO write — is refused for any tagged write."""
    s = a8.make_stack(tmp_path)
    spec = _spec(name)
    wf_spec = a8.workflow_spec(capability=spec)
    out = Lesson(text=f"an out-of-scope note from {name}",
                 source_ref="vault/lessons/oos.md", tags=("pricing",),
                 lesson_id=f"les-{name}-out")
    with pytest.raises(ScopeViolation):
        s.workflow.write_lesson(wf_spec, out)
    if spec.memory_write:  # every writer: the declared tags are accepted
        ok = Lesson(text=f"an in-scope note from {name}",
                    source_ref="vault/lessons/ok.md", tags=spec.memory_write[:1],
                    lesson_id=f"les-{name}-in")
        assert s.workflow.write_lesson(wf_spec, ok) == f"les-{name}-in"
    else:  # the Critic: any tagged write is out of scope by construction
        with pytest.raises(ScopeViolation):
            s.workflow.write_lesson(wf_spec, Lesson(
                text="critic must not write", source_ref="vault/lessons/c.md",
                tags=("lesson",), lesson_id="les-critic"))


# --- every capability dry-runs through the live 5 beats (docs/13 acceptance) ---------------


@pytest.mark.parametrize("name", CAPABILITIES)
def test_capability_dry_run_all_beats(tmp_path, name):
    """docs/13 DoD "dry-run of each capability's beat": the real spec drives a full
    PREPARE→PRODUCE→CRITIQUE→CHECKPOINT run over the live stack — artifact written,
    critique attached with a recorded tier, ONE state-neutral domain event."""
    s = a8.make_stack(tmp_path)
    spec = _spec(name)
    registry_spec = a8.workflow_spec(capability=spec,
                                     artifact_name=f"{name}-dryrun")
    from charterhouse.capabilities.framework import WorkflowRegistry, Workflow
    workflow = Workflow(
        WorkflowRegistry({State.CAPTURED: registry_spec}), s.llm, s.memory,
        s.security, s.ledger, s.vault_dir,
        family_of=lambda mid: s.config.get_model(mid).family)
    result = workflow.run(State.CAPTURED, s.venture)
    assert (s.vault_dir / result.artifact_ref).is_file()
    assert result.capability == name
    assert result.critic_tier in (1, 2, 3)
    domain = a8.domain_events(s.ledger)
    assert [e.type for e in domain] == [EventType.FRAME]
    assert domain[0].to_state is None  # state-neutral; GATE stays human


# --- the harness generator over the real six -----------------------------------------------


def test_opencode_generation_over_real_specs(tmp_path, repo_root):
    """The A8 generator produces six stamped OpenCode files from the real contracts —
    derived artifacts; the neutral specs stay the single source of truth."""
    specs = load_capability_specs(repo_root / "agents")
    written = generate_opencode(specs, tmp_path / "opencode")
    assert [p.name for p in written] == [f"{n}.md" for n in CAPABILITIES]
    for path in written:
        assert "GENERATED-DO-NOT-EDIT" in path.read_text(encoding="utf-8")
