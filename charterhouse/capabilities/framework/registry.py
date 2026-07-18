"""S10 ``WorkflowRegistry`` — the state→workflow table, validated at construction
(capabilities/API.md; the docs/13 no-authority MUST).

The table is DATA supplied at wiring (S12/A9 own the real rows — IMPLEMENTATION §6.1).
Validation is fail-closed and happens BEFORE anything can run: every ``event_type`` must
be a frozen docs/41 catalog member and must NOT be gate/RED (``AUTHORIZATION_REQUIRED``)
— a workflow definition can never smuggle a send/spend/deploy/gate action through
CHECKPOINT (``AuthorityRefused``, RISKS R1).

Determinism (docs/61 §INV-DET): pure data validation; stdlib + contracts only; no LLM.
"""

from __future__ import annotations

from collections.abc import Mapping

from charterhouse.contracts.events import AUTHORIZATION_REQUIRED, EventType
from charterhouse.contracts.state import State

from charterhouse.capabilities.framework.types import (
    AuthorityRefused,
    UnknownWorkflow,
    WorkflowSpec,
)

__all__ = ["WorkflowRegistry"]


class WorkflowRegistry:
    """The runner's only state→workflow source."""

    def __init__(self, specs: Mapping[State, WorkflowSpec]) -> None:
        for state, spec in specs.items():
            if not isinstance(spec.event_type, EventType):
                raise AuthorityRefused(
                    f"workflow for {state.value}: event type {spec.event_type!r} is "
                    "not in the frozen docs/41 catalog")
            if spec.event_type in AUTHORIZATION_REQUIRED:
                raise AuthorityRefused(
                    f"workflow for {state.value}: event type "
                    f"'{spec.event_type.value}' is gate/RED — a capability workflow "
                    "holds no authority (docs/13); the Conductor owns that action")
        self._specs = dict(specs)

    def get(self, state: State) -> WorkflowSpec:
        """The row for ``state`` — ``UnknownWorkflow`` if none is registered."""
        try:
            return self._specs[state]
        except KeyError:
            raise UnknownWorkflow(
                f"no workflow is registered for state {state.value}") from None
