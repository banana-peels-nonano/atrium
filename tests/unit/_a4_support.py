"""A4-local test support for the S5 (Lifecycle) suite — PROVISIONAL.

Like ``_a3_support``/``_a5_support``: fact-event builders (the acting-subsystem role S12/
S10 will play in production), the docs/55 §3 lifecycle Simulator (S5-scope slice), the
independent property oracle, and the seeded script generator. A4-owned until the shared
A11 harness lands, then the reusable pieces are hoisted and this module is deleted.

``EXPECTED_ROWS`` is a deliberately *independent* transcription of docs/42 §3 — the
verbatim-fidelity test and the oracle check the engine against it; neither ever imports
``charterhouse.lifecycle.table`` for expectations. ``LifecycleOracle`` is plain dict
bookkeeping, never a call into S5 internals (it exists to check them).
"""

from __future__ import annotations

import random

from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State
from charterhouse.governance import Gov
from charterhouse.ledger import Ledger
from charterhouse.lifecycle import FactoryClock, Lifecycle
from charterhouse.registry.facade import Registry

from tests.unit import _a3_support as a3
from tests.unit import _a5_support as a5

# --- docs/42 §3, transcribed independently: (from, to) -> (auth_scope, slot, express_ok) ----
# auth_scope None = internal row. The two "(pivot)" rows are the Lifecycle.pivot seam.
S = State
EXPECTED_ROWS: dict[tuple[State, State], tuple[str | None, str | None, bool]] = {
    (S.CAPTURED, S.FRAMED): (None, None, False),
    (S.CAPTURED, S.KILLED): ("kill", None, False),
    (S.FRAMED, S.VALIDATING): ("admit", "validating", False),
    (S.FRAMED, S.PARKED): (None, None, False),
    (S.FRAMED, S.KILLED): ("kill", None, False),
    (S.PARKED, S.VALIDATING): ("admit", "validating", False),
    (S.PARKED, S.ARCHIVED): (None, None, False),
    (S.VALIDATING, S.SHAPING): ("gate", "shaping", False),
    (S.VALIDATING, S.PARKED_SHOVEL_READY): (None, None, False),
    (S.VALIDATING, S.KILLED): ("kill", None, False),
    (S.PARKED_SHOVEL_READY, S.SHAPING): ("gate", "shaping", False),
    (S.PARKED_SHOVEL_READY, S.VALIDATING): ("admit", "validating", False),
    (S.SHAPING, S.BUILDING): ("gate", "building", False),
    (S.SHAPING, S.VALIDATING): ("admit", "validating", False),
    (S.SHAPING, S.KILLED): ("kill", None, False),
    (S.BUILDING, S.LAUNCHED): ("gate", None, False),
    (S.BUILDING, S.KILLED): ("kill", None, False),
    (S.LAUNCHED, S.EARNING): ("gate", None, True),
    (S.LAUNCHED, S.KILLED): ("kill", None, False),
    (S.EARNING, S.GRADUATED): ("graduate", "harvest", False),  # "gate, alumni-slot"
    (S.EARNING, S.KILLED): ("kill", None, False),
    (S.GRADUATED, S.SCALING): ("gate", None, False),
    (S.SCALING, S.HARVEST): ("gate", "harvest", False),
    (S.SCALING, S.EXITED): ("gate", None, False),
    (S.HARVEST, S.EXITED): ("gate", None, False),
    (S.KILLED, S.ARCHIVED): (None, None, False),
}

PIVOT_STATES = frozenset({S.LAUNCHED, S.EARNING})
SLOT_STATES = {"validating": S.VALIDATING, "shaping": S.SHAPING,
               "building": S.BUILDING, "harvest": S.HARVEST}
LIMITS = {"validating": 3, "shaping": 1, "building": 1, "harvest": 3}
TTL_DAYS = 60
SHAPING_MAX = 10
GRAD_WINDOW = 60


# --- fact-event builders (what the acting subsystems append; docs/41 vocabulary) ------------


def capture(ledger: Ledger, clock: FactoryClock, vid: str, codename: str | None = None,
            forked_from: str | None = None) -> str:
    payload: dict = {"source": "inbox", "note_ref": f"note-{vid}", "codename": codename or vid}
    if forked_from is not None:
        payload["forked_from"] = forked_from
    return ledger.append(Event(
        type=EventType.CAPTURE, actor="conductor", payload=payload, venture_id=vid,
        to_state=S.CAPTURED.value, active_time=clock.now_active))


def evidence(ledger: Ledger, clock: FactoryClock, vid: str, verdict: str = "PASS",
             quote_count: int = 22, segment: str = "online") -> str:
    return ledger.append(Event(
        type=EventType.EVIDENCE_GATE, actor="conductor",
        payload={"verdict": verdict, "quote_count": quote_count, "segment_kind": segment},
        venture_id=vid, active_time=clock.now_active))


def go_live(ledger: Ledger, clock: FactoryClock, vid: str, channel: str = "linkedin") -> str:
    return ledger.append(Event(
        type=EventType.EXPERIMENT_LIVE, actor="conductor",
        payload={"channel": channel, "experiment_live_at": clock.now_active},
        venture_id=vid, active_time=clock.now_active))


def exp_result(ledger: Ledger, clock: FactoryClock, vid: str, metric: str = "conversion",
               verdict: str = "PASS", actual: float = 5.4, threshold: float = 4.0) -> str:
    return ledger.append(Event(
        type=EventType.EXPERIMENT_RESULT, actor="conductor",
        payload={"metric": metric, "actual": actual, "threshold": threshold,
                 "verdict": verdict},
        venture_id=vid, active_time=clock.now_active))


def spec_approved(ledger: Ledger, clock: FactoryClock, vid: str) -> str:
    return ledger.append(Event(
        type=EventType.SPEC_APPROVED, actor="conductor",
        payload={"spec_ref": f"spec-{vid}", "fits_days": 9},
        venture_id=vid, authorization="founder-gate", active_time=clock.now_active))


def partners(ledger: Ledger, clock: FactoryClock, vid: str, count: int = 5) -> str:
    return ledger.append(Event(
        type=EventType.PARTNERS, actor="conductor", payload={"recruited_count": count},
        venture_id=vid, active_time=clock.now_active))


def salvage(ledger: Ledger, clock: FactoryClock, vid: str,
            kinds: tuple[str, ...] = ("anti_pattern",)) -> str:
    return ledger.append(Event(
        type=EventType.SALVAGE, actor="librarian", payload={"asset_types": list(kinds)},
        venture_id=vid, active_time=clock.now_active))


FRAME_PAYLOAD = {"brief_ref": "brief-001", "score": 20, "quotes": 3}


# --- the docs/55 §3 simulator (S5-scope slice) -----------------------------------------------


class Sim:
    """Deterministic driver over the real stack: mints founder tokens at the Gov boundary
    (INV-TEST-SAFE), appends fact events in the acting-subsystem role, and calls the S5
    surface. Assertions stay in the tests; the Sim only drives."""

    def __init__(self, tmp_path, subdir: str = "ledger") -> None:
        self.clock = FactoryClock()
        self.ledger = Ledger(tmp_path / subdir, new_id=a3.deterministic_id_factory())
        self.registry = Registry(self.ledger)
        self.gov = Gov(self.ledger, a5.FakeConfig(), clock=lambda: 0.0)
        self.life = Lifecycle(self.ledger, self.registry, self.gov, self.clock)

    def v(self, vid: str):
        return self.registry.get(vid)

    def mint(self, scope: str, vid: str):
        return self.gov.grant(scope, vid, 3600.0)

    def new(self, vid: str, codename: str | None = None) -> None:
        capture(self.ledger, self.clock, vid, codename)

    def frame(self, vid: str, score: int = 20, quotes: int = 3) -> None:
        self.life.transition(self.v(vid), S.FRAMED,
                             payload={**FRAME_PAYLOAD, "score": score, "quotes": quotes})

    def advance(self, vid: str, to: State, scope: str | None, *, express: bool = False,
                reason: str | None = None, payload: dict | None = None):
        tok = self.mint(scope, vid) if scope else None
        return self.life.transition(self.v(vid), to, tok, express=express,
                                    reason=reason, payload=payload)

    def admit(self, vid: str):
        return self.advance(vid, S.VALIDATING, "admit")

    def pass_validation(self, vid: str) -> None:
        """Both VALIDATING sub-gates PASS (R-EVIDENCE-GATE)."""
        evidence(self.ledger, self.clock, vid, "PASS")
        exp_result(self.ledger, self.clock, vid, "conversion", "PASS")

    def kill(self, vid: str, reason: str):
        return self.advance(vid, S.KILLED, "kill", reason=reason)


def force_state(sim: Sim, vid: str, st: State, codename: str | None = None) -> None:
    """Fixture shortcut: place a venture at ``st`` by appending raw events (the test acting
    as history), bypassing S5 — used only to *construct* scenarios, never to test them."""
    capture(sim.ledger, sim.clock, vid, codename)
    if st is not S.CAPTURED:
        sim.ledger.append(Event(
            type=EventType.TRANSITION, actor="test",
            payload={"reason": "fixture", "gate_type": "internal"},
            venture_id=vid, from_state=S.CAPTURED.value, to_state=st.value,
            active_time=sim.clock.now_active))


# --- independent property oracle (INV-SM-1/2/4/5 + windows) ----------------------------------


class LifecycleOracle:
    """Expected accept/reject + state bookkeeping, re-derived from EXPECTED_ROWS and plain
    dicts. Mirrors exactly the facts the script driver plants (score 20, sub-gates PASS,
    spec, partners, activation/mrr PASS, salvage — always appended before the attempt), so
    the only live questions are legality, slots, express, windows, TTL, and lineage caps."""

    def __init__(self) -> None:
        self.state: dict[str, State] = {}
        self.entered: dict[str, int] = {}
        self.ttl_at: dict[str, int] = {}
        self.root: dict[str, str] = {}
        self.forked: set[str] = set()
        self.omw: set[str] = set()
        self.now = 0
        self.paused = False

    # -- world ops
    def new(self, vid: str) -> None:
        self.state[vid] = S.CAPTURED
        self.entered[vid] = self.now
        self.root.setdefault(vid, vid)

    def tick(self, days: int) -> None:
        if not self.paused:
            self.now += days

    def set_paused(self, paused: bool) -> bool:
        ok = paused != self.paused
        if ok:
            self.paused = paused
        return ok

    def count(self, st: State) -> int:
        return sum(1 for s in self.state.values() if s is st)

    def slot_free(self, kind: str) -> bool:
        return self.count(SLOT_STATES[kind]) < LIMITS[kind]

    # -- the expected-outcome rules (independent re-derivation of docs/42 §3)
    def expect_advance(self, vid: str, to: State, express: bool) -> bool:
        frm = self.state.get(vid)
        if frm is None or (frm, to) not in EXPECTED_ROWS:
            return False  # INV-SM-1
        _scope, slot, express_ok = EXPECTED_ROWS[(frm, to)]
        if express and not express_ok:
            return False  # INV-SM-4
        if slot is not None and not self.slot_free(slot):
            return False  # INV-SM-2
        if (frm, to) == (S.FRAMED, S.PARKED) and self.slot_free("validating"):
            return False  # overflow row: only when no validating slot
        if (frm, to) == (S.VALIDATING, S.PARKED_SHOVEL_READY) and self.slot_free("shaping"):
            return False  # overflow row: only when SHAPING occupied
        if (frm, to) == (S.PARKED_SHOVEL_READY, S.SHAPING) and self.now > self.ttl_at[vid]:
            return False  # INV-SM-6 (scripts never re-confirm)
        if (frm, to) == (S.PARKED_SHOVEL_READY, S.VALIDATING) and self.now <= self.ttl_at[vid]:
            return False  # mini re-validation is the stale path
        if (frm, to) == (S.SHAPING, S.BUILDING) and self.now - self.entered[vid] > SHAPING_MAX:
            return False  # ≤10 active-days window
        if (frm, to) == (S.EARNING, S.GRADUATED):
            if self.now - self.entered[vid] > GRAD_WINDOW:
                return False  # 60 active-day graduation window
            if not self.slot_free("harvest"):
                return False  # alumni-capacity gate
        return True

    def on_advanced(self, vid: str, to: State) -> None:
        if to is S.PARKED_SHOVEL_READY:
            self.ttl_at[vid] = self.now + TTL_DAYS
        self.state[vid] = to
        self.entered[vid] = self.now

    def expect_pivot(self, vid: str) -> bool:
        return (self.state.get(vid) in PIVOT_STATES
                and self.root[vid] not in self.forked)

    def on_pivoted(self, vid: str, new_id: str) -> None:
        self.forked.add(self.root[vid])
        self.state[vid] = S.KILLED
        self.entered[vid] = self.now
        self.root[new_id] = self.root[vid]
        self.new_fork_state(new_id)

    def new_fork_state(self, new_id: str) -> None:
        self.state[new_id] = S.FRAMED
        self.entered[new_id] = self.now

    def expect_omw(self, vid: str) -> bool:
        return self.root[vid] not in self.omw

    def on_omw(self, vid: str) -> None:
        self.omw.add(self.root[vid])


def lifecycle_script(seed: int) -> list[tuple]:
    """One seeded random op script over four ventures: frames, advances (legal and
    illegal targets, occasional express), kills, pivots, OMWs, pauses, clock ticks."""
    rng = random.Random(seed)
    ventures = ("v1", "v2", "v3", "v4")
    targets = list(S)
    ops: list[tuple] = [("new", v) for v in ventures] + [("frame", v) for v in ventures]
    for _ in range(rng.randint(18, 34)):
        v = rng.choice(ventures)
        r = rng.random()
        if r < 0.55:
            ops.append(("advance", v, rng.choice(targets), rng.random() < 0.10))
        elif r < 0.68:
            ops.append(("kill", v))
        elif r < 0.78:
            ops.append(("pivot", v))
        elif r < 0.84:
            ops.append(("omw", v))
        elif r < 0.90:
            ops.append(("pause",) if rng.random() < 0.5 else ("resume",))
        else:
            ops.append(("tick", rng.randint(1, 8)))
    return ops
