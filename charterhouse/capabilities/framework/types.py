"""Public value types + error taxonomy for S10 Capability Framework (capabilities/API.md,
IF-5 frozen shapes).

Declarations only — the frozen seam A9 Content and A10 Conductor build against.
``WorkflowResult`` enforces INV-WF-3 by construction: it cannot exist without an attached
Critic take. ``WorkflowSpec.event_type`` may never be a gate/RED type — validated by the
``WorkflowRegistry`` (no-authority MUST, docs/13).

Determinism (docs/61 §INV-DET): stdlib + contracts + sibling value types only; no LLM.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State, Venture
from charterhouse.memory.types import WorkingSet
from charterhouse.router.types import Require


@dataclass(frozen=True)
class CapabilitySpec:
    """One neutral capability contract (docs/13: contracts, not prompts). Parsed from
    ``agents/<name>.agent.md`` — mission/scope/inputs/outputs/memory scope/escalation;
    the no-authority + stateless literals are asserted at parse time (``SpecInvalid``)."""

    name: str
    mission: str
    scope: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    memory_read: tuple[str, ...]
    memory_write: tuple[str, ...]
    escalation: str


@dataclass(frozen=True)
class WorkflowSpec:
    """One state→workflow table row (DATA, supplied at wiring — S12/A9 own the real
    rows). ``event_type`` is the ONE domain event CHECKPOINT appends; ``payload_fn``
    builds its payload deterministically (default: refs + critic_tier + capability)."""

    capability: CapabilitySpec
    role: str
    event_type: EventType
    artifact_name: str
    payload_fn: Callable[["Artifact", "Critique"], dict] | None = None
    k: int = 5
    retries: int = 2
    require: Require | None = None


@dataclass(frozen=True)
class CapInput:
    """The PREPARE output — everything PRODUCE may see (the PII-safe context,
    docs/04 §7): the workflow row, the venture facts, and the S9 working set.

    ``note`` is the **additive** docs/43 §7 field: the founder's own words about the idea,
    read from the vault by the caller and passed in as DATA (the beats have no vault path —
    keeping that structural is why this arrives as an argument rather than a file read).
    Already CHECKPOINTed at capture, so it carries redaction tokens, never raw PII."""

    spec: WorkflowSpec
    venture: Venture
    state: State
    working_set: WorkingSet
    note: str = ""


@dataclass(frozen=True)
class Artifact:
    """One PRODUCE output. ``model`` is the answering model — the Critic's family input
    (INV-WF-2). Frozen and value-equal: the idempotency tests compare Artifacts whole."""

    text: str
    capability: str
    role: str
    model: str
    venture_id: str
    state: State


@dataclass(frozen=True)
class Critique:
    """The attached Critic take (INV-WF-3). ``tier`` records where on the INV-WF-2
    ladder this critique came from (1 diff-family · 2 same-family-diff-model ·
    3 deterministic checklist); ``model`` is the critic model or
    ``"deterministic-checklist"``.

    ``steer`` is the **additive** docs/43 §7 field: the critic's concrete
    what-to-build-instead / how-to-sharpen recommendation, split from the findings so the
    gate brief can carry direction, not just kill-or-continue. It is empty at tier 3 (the
    deterministic checklist produces mechanical findings and never a steer) and empty when
    a critic answers without the labelled section — an honest blank, never a synthesised
    one, so the founder can always tell advice from a floor."""

    verdict: str
    findings: tuple[str, ...]
    tier: int
    model: str
    steer: str = ""


class FrameworkError(Exception):
    """Base class for every S10 failure."""


class SpecInvalid(FrameworkError):
    """A neutral capability spec is missing a required section or the mandatory
    no-authority/stateless literals. Names the missing piece; nothing is loaded."""


class UnknownWorkflow(FrameworkError):
    """No ``WorkflowSpec`` is registered for the requested state (fail closed)."""


class StateMismatch(FrameworkError):
    """``venture.state`` does not match the requested workflow state — nothing runs."""


class BeatFailed(FrameworkError):
    """An LLM beat exhausted its bounded retries (PRODUCE only — CRITIQUE degrades to
    tier 3 instead, INV-WF-2). Zero state was mutated (INV-WF-1)."""


class NoCriticTake(FrameworkError):
    """A gate-facing result was constructed without an attached Critique (INV-WF-3)."""


class AuthorityRefused(FrameworkError):
    """A workflow definition names a gate/RED (or unknown) event type — a capability
    workflow can never smuggle authority through CHECKPOINT (docs/13 no-authority)."""


@dataclass(frozen=True)
class WorkflowResult:
    """The GATE-facing outcome of one run: the vault artifact ref, the attached Critic
    take (+ tier), and the appended event id. INV-WF-3 by construction: refuses to exist
    without a critique."""

    artifact_ref: str
    critique: Critique
    critic_tier: int
    event_id: str
    capability: str
    model: str
    sidecar_ref: str | None = None

    def __post_init__(self) -> None:
        if self.critique is None:  # INV-WF-3: no gate presentable without a Critic take
            raise NoCriticTake(
                "a WorkflowResult requires an attached Critique (INV-WF-3)")
