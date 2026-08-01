"""S10 ``Capability.produce`` — the PRODUCE beat (docs/40 §7; capabilities/API.md).

One deterministic message assembly (spec contract + Doctrine + top-K working memory +
venture facts — exactly the PREPARE output, docs/04 §7) → one ``LLMClient.call`` via the
frozen IF-2 seam. **No authority, no durable state**: this module can write nothing,
append nothing, and holds no token path — that is structural (INV-WF-1), not policy.
Retryable by construction: same ``CapInput`` → the same call (the runner owns the retry
loop; provider failures propagate as ``RouterError``).
"""

from __future__ import annotations

from charterhouse.capabilities.framework.types import Artifact, CapInput

__all__ = ["Capability", "assemble_messages"]


def assemble_messages(cap_input: CapInput) -> list[dict]:
    """Deterministic PREPARE→PRODUCE context: the neutral contract (mission/scope/
    outputs) as the system message; Doctrine + retrieved lesson texts + venture facts as
    the user message. Collections are emitted in stored order (already deterministic —
    S9's frozen ranking order)."""
    cap = cap_input.spec.capability
    system = (
        f"You are the {cap.name} capability of Charter House.\n"
        f"MISSION: {cap.mission}\n"
        f"SCOPE: {cap.scope}\n"
        f"REQUIRED OUTPUTS: {', '.join(cap.outputs)}\n"
        "You have no authority and are stateless: you cannot send, spend, deploy, or "
        "cross a gate — you produce the artifact below and nothing else."
    )
    lessons = "\n".join(
        f"- [{scored.lesson.lesson_id}] {scored.lesson.text}"
        for scored in cap_input.working_set.records
    )
    # The founder's own words get their OWN labelled section, first: a capability given only
    # a codename invents the detail it lacks, and a distinct label is what makes the model
    # treat the text as the source material rather than as a title.
    idea = (f"IDEA (founder's words):\n{cap_input.note.strip()}\n\n"
            if cap_input.note and cap_input.note.strip() else "")
    user = (
        f"{idea}"
        f"DOCTRINE:\n{cap_input.working_set.doctrine}\n\n"
        f"WORKING MEMORY (top-{len(cap_input.working_set.records)}):\n"
        f"{lessons or '- (none yet)'}\n\n"
        f"VENTURE: {cap_input.venture.codename} ({cap_input.venture.id}) "
        f"in state {cap_input.state.value}, "
        f"active-time {cap_input.venture.active_time_accum}.\n\n"
        f"Produce: {', '.join(cap.outputs)}."
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]


class Capability:
    """The one PRODUCE path. Constructed with the frozen ``LLMClient`` (S8)."""

    def __init__(self, llm) -> None:  # noqa: ANN001 — LLMClient (IF-2 frozen seam)
        self._llm = llm

    def produce(self, cap_input: CapInput) -> Artifact:
        """One ``LLMClient.call(spec.role, messages, require=spec.require)`` →
        ``Artifact`` (the answering model recorded — the Critic's family input)."""
        spec = cap_input.spec
        response = self._llm.call(spec.role, assemble_messages(cap_input),
                                  require=spec.require)
        return Artifact(
            text=response.text,
            capability=spec.capability.name,
            role=spec.role,
            model=response.model,
            venture_id=cap_input.venture.id,
            state=cap_input.state,
        )
