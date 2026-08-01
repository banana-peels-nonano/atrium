"""S10 ``Workflow`` — the 5-beat runner (docs/04 §5, docs/13, docs/40 §7 — IF-5).

PREPARE (det: ``Memory.retrieve`` → frozen ``CapInput``; zero writes)
→ PRODUCE (``Capability.produce`` via S8; bounded retries; zero state)
→ CRITIQUE (``Critic.critique`` — the INV-WF-2 ladder; never fails the run)
→ CHECKPOINT (det, THE ONLY MUTATING BEAT — INV-WF-1: live-S7 redact+scan fail-closed
  → write the clean artifact to the vault → append exactly ONE state-neutral domain
  event, ``to_state`` never set)
→ GATE (human — the runner NEVER advances state; Lifecycle is the sole transition path).

Beat isolation is structural: ``prepare``/``produce_beat``/``critique_beat`` have no
vault path and no ``Ledger.append`` reachable from their frames; only ``checkpoint``
touches either, write-then-append with artifact rollback (no artifact without its
event). S8's ``llm_call``/``error`` telemetry during the LLM beats is observability,
not venture state (IMPLEMENTATION §6.5).

Determinism (docs/61 §INV-DET): deterministic except the two Router-mediated beats; no
env read (vault dir arrives from wiring — A1's ``EnvContext`` at composition).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from charterhouse.contracts.events import Event
from charterhouse.contracts.state import State, Venture
from charterhouse.ledger import Ledger
from charterhouse.memory.facade import Memory
from charterhouse.memory.types import Lesson, TaskContext
from charterhouse.router.types import RouterError
from charterhouse.security import Security

from charterhouse.capabilities.framework.capability import Capability
from charterhouse.capabilities.framework.critic import Critic
from charterhouse.capabilities.framework.registry import WorkflowRegistry
from charterhouse.capabilities.framework.types import (
    Artifact,
    BeatFailed,
    CapInput,
    Critique,
    NoCriticTake,
    StateMismatch,
    WorkflowResult,
    WorkflowSpec,
)

__all__ = ["Workflow"]


class Workflow:
    """The IF-5 runner. Wired by the composition root with the live seams — no stubs."""

    def __init__(self, registry: WorkflowRegistry, llm, memory: Memory,  # noqa: ANN001
                 security: Security, ledger: Ledger, vault_dir: str | Path,
                 actor: str = "system",
                 family_of=None) -> None:  # noqa: ANN001 — additive (docs/43 §7)
        self._registry = registry
        self._memory = memory
        self._security = security
        self._ledger = ledger
        self._vault_dir = Path(vault_dir)
        self._actor = actor
        self._capability = Capability(llm)
        self._llm = llm
        # Additive seam (feat/a2-accessors): the catalog Model.family lookup the wiring
        # supplies (`lambda mid: config.get_model(mid).family`) — INV-WF-2's cross-family
        # check follows the catalog, not an id parse (capabilities RISKS R3 retired).
        self._family_of = family_of

    # --- the frozen surface (IF-5) ------------------------------------------------------

    def run(self, state: State, venture: Venture, *,
            require=None) -> WorkflowResult:  # noqa: ANN001 — Require (IF-2)
        """All four machine beats in order (GATE is human). Fail closed at every step;
        a model failure never corrupts state (INV-WF-1).

        ``require`` (additive, docs/43 §7) overrides the row's routing constraint for THIS
        run and applies to BOTH LLM beats — the caller's way to say ``contains_pii``, which
        confines produce AND critique to local models (INV-PII-3)."""
        spec = self._registry.get(state)
        if require is not None:
            spec = replace(spec, require=require)  # per-run override; the row is frozen
        if venture.state is not state:
            raise StateMismatch(
                f"venture {venture.id!r} is in {venture.state.value}, not "
                f"{state.value} — refusing to run a stale workflow (RISKS R10)")
        cap_input = self.prepare(spec, venture, state)
        artifact = self.produce_beat(cap_input)
        critique = self.critique_beat(cap_input, artifact)
        return self.checkpoint(spec, venture, artifact, critique)

    # --- beat methods (exposed for tests/S12; decomposition internal, not frozen) -------

    def prepare(self, spec: WorkflowSpec, venture: Venture, state: State) -> CapInput:
        """PREPARE (deterministic): ``Memory.retrieve`` → frozen ``CapInput``. Zero
        writes, zero events (INV-WF-1)."""
        task = TaskContext(
            text=f"{spec.capability.mission} — venture {venture.codename} "
                 f"in state {state.value}",
            tags=spec.capability.memory_read,
            venture_id=venture.id,
            active_time=venture.active_time_accum,
        )
        working_set = self._memory.retrieve(task, spec.k)
        return CapInput(spec=spec, venture=venture, state=state,
                        working_set=working_set)

    def produce_beat(self, cap_input: CapInput) -> Artifact:
        """PRODUCE with the bounded retry loop (``spec.retries`` total attempts on
        ``RouterError``; a PII hard-stop propagates immediately — never retried).
        Exhaustion → ``BeatFailed`` with zero state mutated (INV-WF-1)."""
        retries = max(1, cap_input.spec.retries)
        last: RouterError | None = None
        for _attempt in range(retries):
            try:
                return self._capability.produce(cap_input)
            except RouterError as exc:  # PIIRouteBlocked is a SecurityError: propagates
                last = exc
        raise BeatFailed(
            f"produce exhausted {retries} attempts for capability "
            f"{cap_input.spec.capability.name!r}: {type(last).__name__} — zero state "
            "mutated (INV-WF-1)") from last

    def critique_beat(self, cap_input: CapInput, artifact: Artifact) -> Critique:
        """CRITIQUE via the INV-WF-2 ladder — never fails the run (tier 3 floor). The
        row's ``require`` rides along, so a ``contains_pii`` run keeps the critic local
        too (INV-PII-3 across both LLM legs)."""
        critic = Critic(self._llm, retries=max(1, cap_input.spec.retries),
                        family_of=self._family_of)
        return critic.critique(artifact, cap_input.spec.capability,
                               require=cap_input.spec.require)

    def checkpoint(self, spec: WorkflowSpec, venture: Venture, artifact: Artifact,
                   critique: Critique) -> WorkflowResult:
        """THE ONLY MUTATING BEAT (INV-WF-1): live-S7 ``Security.checkpoint`` (fail
        closed) → vault write → ONE state-neutral domain event (``critic_tier`` in the
        payload). Append failure removes the just-written artifact. Requires the
        Critique (INV-WF-3)."""
        if critique is None:
            raise NoCriticTake(
                "CHECKPOINT refuses to run without an attached Critique (INV-WF-3)")
        # 1. Redact + scan, fail closed (CheckpointError propagates: nothing written).
        cp = self._security.checkpoint(
            artifact.text, doc_id=f"{venture.id}-{spec.artifact_name}")
        # 2. Write the CLEAN artifact into the vault.
        artifact_ref = f"ventures/{venture.id}/{spec.artifact_name}.md"
        path = self._vault_dir / "ventures" / venture.id / f"{spec.artifact_name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(cp.clean, encoding="utf-8")
        # 3. Append the ONE domain event — state-neutral by construction (to_state is
        #    never set; GATE is human and Lifecycle owns transitions).
        if spec.payload_fn is not None:
            payload = spec.payload_fn(artifact, critique)
        else:
            payload = {"artifact_ref": artifact_ref, "critic_tier": critique.tier,
                       "capability": artifact.capability}
        event = Event(type=spec.event_type, actor=self._actor, payload=payload,
                      venture_id=venture.id)
        try:
            event_id = self._ledger.append(event)
        except Exception:
            path.unlink(missing_ok=True)  # no artifact without its event (R2)
            raise
        return WorkflowResult(
            artifact_ref=artifact_ref,
            critique=critique,
            critic_tier=critique.tier,
            event_id=event_id,
            capability=artifact.capability,
            model=artifact.model,
            sidecar_ref=cp.sidecar_ref,
        )

    # --- scoped memory writes (docs/54 §S11, framework half) ----------------------------

    def write_lesson(self, spec: WorkflowSpec, lesson: Lesson) -> str:
        """A capability-initiated lesson write, scoped to the spec's declared
        ``memory_write`` via S9's ``scope=`` seam — out-of-scope surfaces S9's
        ``ScopeViolation`` unchanged."""
        return self._memory.write_lesson(lesson,
                                         scope=spec.capability.memory_write)
