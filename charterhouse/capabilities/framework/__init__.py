"""S10 Capability Framework — the 5-beat runner, Critic ladder, neutral-spec loader,
and OpenCode harness generator (docs/13, docs/40 §7, IF-5).

Public surface: ``Workflow`` / ``Capability`` / ``Critic`` / ``WorkflowRegistry`` +
the loader/generator + the frozen value types and fail-closed error taxonomy.
S9's ``ScopeViolation`` and S7's ``CheckpointError`` surface unchanged (one refusal
type per rule across seams).
"""

from charterhouse.capabilities.framework.capability import Capability, assemble_messages
from charterhouse.capabilities.framework.critic import CHECKLIST_MODEL, Critic
from charterhouse.capabilities.framework.harness_opencode import (
    GENERATED_STAMP,
    generate_opencode,
)
from charterhouse.capabilities.framework.registry import WorkflowRegistry
from charterhouse.capabilities.framework.runner import Workflow
from charterhouse.capabilities.framework.spec_loader import (
    load_capability_spec,
    load_capability_specs,
)
from charterhouse.capabilities.framework.types import (
    Artifact,
    AuthorityRefused,
    BeatFailed,
    CapInput,
    CapabilitySpec,
    Critique,
    FrameworkError,
    NoCriticTake,
    SpecInvalid,
    StateMismatch,
    UnknownWorkflow,
    WorkflowResult,
    WorkflowSpec,
)

__all__ = [
    "CHECKLIST_MODEL",
    "GENERATED_STAMP",
    "Artifact",
    "AuthorityRefused",
    "BeatFailed",
    "CapInput",
    "Capability",
    "CapabilitySpec",
    "Critic",
    "Critique",
    "FrameworkError",
    "NoCriticTake",
    "SpecInvalid",
    "StateMismatch",
    "UnknownWorkflow",
    "Workflow",
    "WorkflowRegistry",
    "WorkflowResult",
    "WorkflowSpec",
    "assemble_messages",
    "generate_opencode",
    "load_capability_spec",
    "load_capability_specs",
]
