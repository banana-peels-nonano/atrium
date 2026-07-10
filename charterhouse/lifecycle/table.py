"""The docs/42 §3 transition table, verbatim, as data (INV-SM-1; lifecycle/IMPLEMENTATION §3).

``TRANSITIONS`` is the single source of legality: a ``(from, to)`` pair absent from it is
illegal and MUST be rejected + logged. ``test_table_matches_docs42_verbatim`` pins the
row set, auth scopes, slot kinds, and express markings 1:1 against the doc. The two
"(pivot)" rows of the doc table are the ``Lifecycle.pivot`` seam (docs/42 §5), not
``transition`` rows.

Determinism (docs/61 §INV-DET): stdlib + contracts only; no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass

from charterhouse.contracts.events import EventType
from charterhouse.contracts.state import State


@dataclass(frozen=True)
class Rule:
    """One docs/42 §3 row.

    ``guards``      — names of the pure guard functions that must all hold (guards.py).
    ``auth_scope``  — the Gov action name for gate rows (docs/40 §8 vocabulary);
                      ``None`` = internal (no token).
    ``slot``        — the INV-SM-2 slot kind this transition *enters*
                      ("validating" | "shaping" | "building" | "harvest" | None).
    ``express_ok``  — True ONLY where docs/42 §3 marks Express=yes (INV-SM-4).
    ``event_type``  — the single state-changing event appended (lifecycle/API.md mapping).
    ``gate_type``   — the ``transition`` payload gate_type ("weekly" | "internal");
                      "express" is stamped at call time for an express advance.
    """

    guards: tuple[str, ...]
    auth_scope: str | None
    slot: str | None
    express_ok: bool
    event_type: EventType
    gate_type: str


S = State
E = EventType

TRANSITIONS: dict[tuple[State, State], Rule] = {
    # Sourcing & framing
    (S.CAPTURED, S.FRAMED): Rule(("frame_payload",), None, None, False, E.FRAME, "internal"),
    (S.CAPTURED, S.KILLED): Rule(("founder_reason",), "kill", None, False, E.KILL, "weekly"),
    # Admission & backlog
    (S.FRAMED, S.VALIDATING): Rule(("score_bar_or_override",), "admit", "validating",
                                   False, E.ADMIT, "weekly"),
    (S.FRAMED, S.PARKED): Rule(("score_bar", "validating_full"), None, None, False,
                               E.PARK, "internal"),
    (S.FRAMED, S.KILLED): Rule(("founder_reason",), "kill", None, False, E.KILL, "weekly"),
    (S.PARKED, S.VALIDATING): Rule((), "admit", "validating", False, E.ADMIT, "weekly"),
    (S.PARKED, S.ARCHIVED): Rule(("founder_reason",), None, None, False,
                                 E.TRANSITION, "internal"),
    # Validation (R-EVIDENCE-GATE sub-gates)
    (S.VALIDATING, S.SHAPING): Rule(("sub_gates",), "gate", "shaping", False,
                                    E.TRANSITION, "weekly"),
    (S.VALIDATING, S.PARKED_SHOVEL_READY): Rule(("sub_gates", "shaping_occupied"), None,
                                                None, False, E.SHOVEL_READY, "internal"),
    (S.VALIDATING, S.KILLED): Rule(("founder_reason",), "kill", None, False,
                                   E.KILL, "weekly"),
    # Shovel-ready (INV-SM-6)
    (S.PARKED_SHOVEL_READY, S.SHAPING): Rule(("evidence_fresh",), "gate", "shaping",
                                             False, E.TRANSITION, "weekly"),
    (S.PARKED_SHOVEL_READY, S.VALIDATING): Rule(("evidence_stale",), "admit",
                                                "validating", False, E.ADMIT, "weekly"),
    # Shaping
    (S.SHAPING, S.BUILDING): Rule(("spec_approved", "shaping_window"), "gate",
                                  "building", False, E.TRANSITION, "weekly"),
    (S.SHAPING, S.VALIDATING): Rule(("founder_reason",), "admit", "validating", False,
                                    E.ADMIT, "weekly"),
    (S.SHAPING, S.KILLED): Rule(("founder_reason",), "kill", None, False, E.KILL, "weekly"),
    # Building & launch
    (S.BUILDING, S.LAUNCHED): Rule(("partners_recruited",), "gate", None, False,
                                   E.TRANSITION, "weekly"),
    (S.BUILDING, S.KILLED): Rule(("founder_reason",), "kill", None, False, E.KILL, "weekly"),
    (S.LAUNCHED, S.EARNING): Rule(("activation_pass",), "gate", None, True,
                                  E.TRANSITION, "weekly"),
    (S.LAUNCHED, S.KILLED): Rule(("founder_reason",), "kill", None, False, E.KILL, "weekly"),
    # Earning & graduation (R-ALUMNI-CEILING: "gate, alumni-slot")
    (S.EARNING, S.GRADUATED): Rule(("traction_in_window",), "graduate", "harvest",
                                   False, E.GRADUATE, "weekly"),
    (S.EARNING, S.KILLED): Rule(("founder_reason",), "kill", None, False, E.KILL, "weekly"),
    # Alumni
    (S.GRADUATED, S.SCALING): Rule((), "gate", None, False, E.ALUMNI_TRANSITION, "weekly"),
    (S.SCALING, S.HARVEST): Rule((), "gate", "harvest", False,
                                 E.ALUMNI_TRANSITION, "weekly"),
    (S.SCALING, S.EXITED): Rule(("founder_reason",), "gate", None, False,
                                E.ALUMNI_TRANSITION, "weekly"),
    (S.HARVEST, S.EXITED): Rule(("founder_reason",), "gate", None, False,
                                E.ALUMNI_TRANSITION, "weekly"),
    # Terminal hygiene
    (S.KILLED, S.ARCHIVED): Rule(("salvage_banked",), None, None, False,
                                 E.TRANSITION, "internal"),
}

# The pivot seam's legal source states (docs/42 §3 "(pivot)" rows).
PIVOT_STATES: frozenset[State] = frozenset({S.LAUNCHED, S.EARNING})
