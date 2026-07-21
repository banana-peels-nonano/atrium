"""Public value types + error taxonomy for S12 Conductor (conductor/API.md;
docs/40 §8).

``CommandRefused`` always carries the OWNING subsystem's reason verbatim — the
conductor authors no rule text of its own (INV-COND-1). ``NoCriticForGate`` is
RE-EXPORTED from S13 (one INV-COND-2 refusal type across the seam — the A6/A7
precedent).

Determinism (docs/61 §INV-DET): stdlib + contracts only at this layer; no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass

from charterhouse.projections.types import NoCriticForGate  # noqa: F401 — one type

__all__ = ["CommandResult", "ConductorError", "CommandRefused", "NoCriticForGate"]


@dataclass(frozen=True)
class CommandResult:
    """One command's outcome: the S6 classification color it ran under, the owning
    subsystem's event id where one was appended, and any projection/data payload."""

    ok: bool
    command: str
    color: str
    venture_id: str | None = None
    event_id: str | None = None
    data: object | None = None
    reason: str = ""


class ConductorError(Exception):
    """Base class for every S12 failure."""


class CommandRefused(ConductorError):
    """A command was refused — the message is the OWNER's reason (S5's typed guard
    text, S6's denial reason, docs/41 shape violations). Fail closed; pre-act
    refusals leave the ledger untouched."""
