"""S10 ``Critic.critique`` — the CRITIQUE beat + the INV-WF-2 degrade ladder
(docs/40 §7; docs/13; capabilities/API.md).

The ladder is decided by what actually answered, and recorded honestly:
tier 1 — the critic call answers from a DIFFERENT family than the producing model;
tier 2 — same family, different model (the router had no cross-family candidate);
tier 3 — the critic call exhausts its bounded retries (``RouterError``) OR answers with
the SAME model that produced (self-critique refused) → the deterministic checklist
(pure function; no LLM; ALWAYS available — critique exhaustion is degrade, not failure).

Family lookup (RISKS R3 RETIRED, founder follow-up at the A8 gate): the family comes
from the CATALOG's additive ``Model.family`` field via an injected ``family_of``
callable (the wiring passes ``lambda mid: config.get_model(mid).family``). No id
parsing happens here anymore — the canonical derivation lives ONLY in
``contracts.config_types.default_family``, which S3's loader uses to default the field
and which serves as this module's standalone fallback when no lookup is wired.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from charterhouse.contracts.config_types import default_family
from charterhouse.router.types import RouterError

from charterhouse.capabilities.framework.types import Artifact, CapabilitySpec, Critique

__all__ = ["Critic", "checklist", "CHECKLIST_MODEL"]

CHECKLIST_MODEL = "deterministic-checklist"

_MARKER_RE = re.compile(r"\b(TODO|FIXME|XXX)\b")


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

    def __init__(self, llm, *, role: str = "critic", retries: int = 2,
                 family_of: Callable[[str], str] | None = None) -> None:  # noqa: ANN001
        self._llm = llm
        self._role = role
        self._retries = max(1, retries)
        # Additive seam (docs/43 §7): the catalog family lookup. None = standalone
        # fallback to the canonical contracts derivation (never a local parse).
        self._family_of = family_of if family_of is not None else default_family

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
        tier = (1 if self._family_of(response.model) != self._family_of(artifact.model)
                else 2)
        return Critique(verdict="review", findings=(response.text,), tier=tier,
                        model=response.model)
