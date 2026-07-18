"""S10 ``Critic.critique`` — the CRITIQUE beat + the INV-WF-2 degrade ladder
(docs/40 §7; docs/13; capabilities/API.md).

The ladder is decided by what actually answered, and recorded honestly:
tier 1 — the critic call answers from a DIFFERENT family than the producing model;
tier 2 — same family, different model (the router had no cross-family candidate);
tier 3 — the critic call exhausts its bounded retries (``RouterError``) OR answers with
the SAME model that produced (self-critique refused) → the deterministic checklist
(pure function; no LLM; ALWAYS available — critique exhaustion is degrade, not failure).

Family derivation (IMPLEMENTATION §6.3): the model id's leading alphabetic token,
lowercased (``claude-sonnet``→``claude``, ``llama3.1-8b-local``→``llama``). Isolated in
``family`` pending an additive ``Model.family`` field (A2 cross-note, RISKS R3).
"""

from __future__ import annotations

import re

from charterhouse.router.types import RouterError

from charterhouse.capabilities.framework.types import Artifact, CapabilitySpec, Critique

__all__ = ["Critic", "family", "checklist", "CHECKLIST_MODEL"]

CHECKLIST_MODEL = "deterministic-checklist"

_FAMILY_RE = re.compile(r"[A-Za-z]+")
_MARKER_RE = re.compile(r"\b(TODO|FIXME|XXX)\b")


def family(model_id: str) -> str:
    """The model id's leading alphabetic token, lowercased (deterministic)."""
    m = _FAMILY_RE.match(model_id)
    return m.group(0).lower() if m else model_id.lower()


def checklist(artifact: Artifact, spec: CapabilitySpec | None) -> Critique:
    """Tier 3: the deterministic checklist critique — pure, ordered findings (RISKS R5:
    rules derive from the SPEC's declared outputs, not generic fluff). ``verdict`` is
    ``"flag"`` iff findings exist, else ``"pass"``."""
    findings: list[str] = []
    text = artifact.text
    if not text.strip():
        findings.append("artifact text is empty")
    elif len(text.strip()) < 20:
        findings.append("artifact text is implausibly short (<20 chars)")
    if _MARKER_RE.search(text):
        findings.append("artifact contains dangling TODO/FIXME/XXX markers")
    if spec is not None:
        lowered = text.lower()
        for output in spec.outputs:
            if output.lower() not in lowered:
                findings.append(f"declared output '{output}' is not named in the "
                                "artifact")
    return Critique(
        verdict="flag" if findings else "pass",
        findings=tuple(findings),
        tier=3,
        model=CHECKLIST_MODEL,
    )


def _critique_messages(artifact: Artifact) -> list[dict]:
    return [
        {"role": "system", "content":
            "You are the adversarial Critic of Charter House. Attack the artifact: "
            "name unstated assumptions, missing declared outputs, and evidence gaps. "
            "You have no authority and are stateless — critique only."},
        {"role": "user", "content":
            f"Capability: {artifact.capability} (role {artifact.role}, "
            f"venture {artifact.venture_id}, state {artifact.state.value}).\n\n"
            f"ARTIFACT:\n{artifact.text}"},
    ]


class Critic:
    """The one CRITIQUE path. Constructed with the frozen ``LLMClient`` (S8); the
    critic route is Config's ``critic`` role (INV-ROUTE-1 — no model choice here)."""

    def __init__(self, llm, *, role: str = "critic", retries: int = 2) -> None:  # noqa: ANN001
        self._llm = llm
        self._role = role
        self._retries = max(1, retries)

    def critique(self, artifact: Artifact,
                 spec: CapabilitySpec | None = None) -> Critique:
        """The ladder above. Never raises for provider reasons — tier 3 is the floor.
        ``spec`` (additive, docs/43 §7) feeds the checklist's declared-outputs rules."""
        response = None
        for _attempt in range(self._retries):
            try:
                response = self._llm.call(self._role, _critique_messages(artifact))
                break
            except RouterError:
                continue
        if response is None or response.model == artifact.model:
            # Router exhausted, or self-critique refused → the deterministic floor.
            return checklist(artifact, spec)
        tier = 1 if family(response.model) != family(artifact.model) else 2
        return Critique(verdict="review", findings=(response.text,), tier=tier,
                        model=response.model)
