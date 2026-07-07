"""A3-local test support for the S4 (Ledger/Registry) suite — PROVISIONAL.

These helpers (deterministic id factory, seeded legal-sequence generator, independent replay
oracle, PII corpus, event builders) are owned by A3 and live here rather than in
``tests/fakes/`` because the shared A11 harness (InMemoryLedger fake, Clock, PII corpus,
sequence generator) is not built yet (one-subsystem-per-branch, docs/63). When A11 lands, the
reusable pieces are hoisted into the shared harness and this module is deleted.

Nothing here is production logic; the property oracle is deliberately an *independent*
re-derivation of expected state, not a call into ``Ledger.replay`` (which it exists to check).
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Callable

from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State


def deterministic_id_factory() -> Callable[[], str]:
    """A monotonic, lexicographically-sortable id factory for reproducible tests. Called inside
    the Ledger's append critical section, so a plain counter is race-free."""
    counter = itertools.count()
    return lambda: f"{next(counter):026d}"


# --- Event builders -----------------------------------------------------------------------


def draft(
    type: EventType,
    *,
    actor: str = "conductor",
    payload: dict | None = None,
    venture_id: str | None = None,
    from_state: State | str | None = None,
    to_state: State | str | None = None,
    authorization: str | None = None,
    active_time: int | None = None,
) -> Event:
    """Build an append-ready draft Event (no ``event_id``/``prev_hash`` — the Ledger assigns)."""
    return Event(
        type=type,
        actor=actor,
        payload=payload or {},
        venture_id=venture_id,
        from_state=from_state.value if isinstance(from_state, State) else from_state,
        to_state=to_state.value if isinstance(to_state, State) else to_state,
        authorization=authorization,
        active_time=active_time,
    )


# --- Legal state walk (subset of the docs/42 §3 transition table) -------------------------

_LEGAL: dict[State, tuple[State, ...]] = {
    State.CAPTURED: (State.FRAMED,),
    State.FRAMED: (State.VALIDATING, State.PARKED, State.KILLED),
    State.PARKED: (State.VALIDATING, State.ARCHIVED),
    State.VALIDATING: (State.SHAPING, State.PARKED_SHOVEL_READY, State.KILLED),
    State.PARKED_SHOVEL_READY: (State.SHAPING, State.VALIDATING),
    State.SHAPING: (State.BUILDING, State.VALIDATING, State.KILLED),
    State.BUILDING: (State.LAUNCHED, State.KILLED),
    State.LAUNCHED: (State.EARNING, State.KILLED),
    State.EARNING: (State.GRADUATED, State.KILLED),
    State.GRADUATED: (State.SCALING,),
    State.SCALING: (State.HARVEST, State.EXITED),
    State.HARVEST: (State.EXITED,),
    State.KILLED: (State.ARCHIVED,),
    State.ARCHIVED: (),
    State.EXITED: (),
}


def legal_sequence(seed: int) -> list[Event]:
    """Generate one arbitrary *legal* multi-venture event stream from ``seed``.

    Guarantees, so appends never fail validation and replay never trips a cap:
      - a leading ``capture`` (→ CAPTURED) then legal ``transition`` steps per ``_LEGAL``;
      - gate-only auth types are avoided (uses generic ``transition``, which needs no token);
      - at most one ``omw_grant`` and one ``pivot_fork`` per lineage (respects docs/41 §4.3);
      - factory-global telemetry (``llm_call``) interleaved with ``venture_id = None``.
    """
    rng = random.Random(seed)
    events: list[Event] = []
    n_ventures = rng.randint(1, 4)
    at = 0  # active-time counter
    for v in range(n_ventures):
        vid = f"s{seed}-v{v}"
        at += 1
        events.append(
            draft(EventType.CAPTURE, payload={"codename": f"cn-{vid}"},
                  venture_id=vid, to_state=State.CAPTURED, active_time=at)
        )
        if rng.random() < 0.8:
            at += 1
            events.append(draft(EventType.FRAME, payload={"score": rng.randint(10, 25)},
                                venture_id=vid, active_time=at))
        state = State.CAPTURED
        granted_omw = forked = False
        for _ in range(rng.randint(1, 8)):
            nxt = _LEGAL[state]
            if not nxt:
                break
            to = rng.choice(nxt)
            at += 1
            events.append(draft(EventType.TRANSITION, payload={"reason": "test"},
                                venture_id=vid, from_state=state, to_state=to, active_time=at))
            state = to
            if not granted_omw and rng.random() < 0.15:
                granted_omw = True
                at += 1
                events.append(draft(EventType.OMW_GRANT, venture_id=vid, active_time=at))
            if not forked and state == State.KILLED and rng.random() < 0.3:
                forked = True
                at += 1
                events.append(draft(EventType.PIVOT_FORK,
                                    payload={"killed_id": vid, "new_id": f"{vid}-fork",
                                             "inherited": {}}, venture_id=vid, active_time=at))
        if rng.random() < 0.5:
            at += 1
            events.append(draft(EventType.LLM_CALL, actor="system",
                                payload={"role": "critic", "cost_usd": round(rng.random(), 6)},
                                venture_id=None, active_time=at))
    return events


def oracle(events: list[Event]) -> dict[str, dict]:
    """Independent re-derivation of expected per-venture state from an event stream — the
    reference the property test compares ``Ledger.replay`` against. Deliberately NOT a call
    into production replay. Returns ``{venture_id: {state, score, omw_granted}}``."""
    out: dict[str, dict] = {}
    for e in events:
        if e.venture_id is None:
            continue  # factory-global event, not a venture record
        rec = out.setdefault(e.venture_id, {"state": None, "score": None, "omw_granted": False})
        if e.to_state is not None:
            rec["state"] = e.to_state
        if e.type in (EventType.FRAME, EventType.SCORE_OVERRIDE) and "score" in e.payload:
            rec["score"] = e.payload["score"]
        if e.type == EventType.OMW_GRANT:
            rec["omw_granted"] = True
    return out


# --- PII corpus (structural PII only — NONE trip scripts/secret_scan.py) -------------------

PII_CORPUS: tuple[tuple[str, str], ...] = (
    ("email", "jane.doe@example.com"),
    ("phone", "+1-555-0142"),
    ("ssn", "123-45-6789"),
    ("credit_card", "4111 1111 1111 1111"),
)
