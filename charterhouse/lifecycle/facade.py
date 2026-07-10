"""``Lifecycle`` — the S5 spine (docs/40 §3 frozen surface + documented additive seams;
lifecycle/API.md).

Enforces the docs/42 machine over ledger facts: legality → express check → guards
(slots included) → Gov authorize (IF-3 delegation — no S6 rule re-implemented here) →
exactly one state-changing append. Refusals append one ``error`` event, then raise typed
(fail closed; the venture stays put). Owns NO durable state: every answer is recomputed
from ledger/registry/clock.

Determinism (docs/61 §INV-DET): stdlib + contracts + S4/S6 seams only; no LLM.
"""

from __future__ import annotations

import re
from typing import Protocol

from charterhouse.contracts.authz import ActionColor, AuthClass, Token
from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State, Venture
from charterhouse.governance import Action
from charterhouse.ledger import Ledger
from charterhouse.registry.facade import Registry

from charterhouse.lifecycle.clock import FactoryClock, derive_active_time
from charterhouse.lifecycle.guards import Facts, evaluate
from charterhouse.lifecycle.slots import slot_state
from charterhouse.lifecycle.table import PIVOT_STATES, TRANSITIONS, Rule
from charterhouse.lifecycle.types import (
    ActiveTime,
    AuthorizationDenied,
    ExpressRefused,
    ForkCapExceeded,
    GuardFailed,
    GuardResult,
    IllegalTransition,
    LifecycleLimits,
    OmwExhausted,
    PivotResult,
    Result,
    SlotLimitExceeded,
    SlotState,
    StaleEvidence,
)
from charterhouse.lifecycle.pivot import lineage_has

_ACTOR = "lifecycle"


class GovPort(Protocol):
    """The one slice of IF-3 S5 consumes (IMPLEMENTATION §4): token validation.
    S5 never mints tokens and never classifies."""

    def authorize(self, action, token):  # -> Decision {ok, reason}
        ...


class Lifecycle:
    """S5 Lifecycle. See lifecycle/API.md for the full per-function contract."""

    def __init__(
        self,
        ledger: Ledger,
        registry: Registry,
        gov: GovPort,
        clock: FactoryClock,
        limits: LifecycleLimits | None = None,
    ) -> None:
        self._ledger = ledger
        self._registry = registry
        self._gov = gov
        self._clock = clock
        self._limits = limits if limits is not None else LifecycleLimits()

    # --- internals ------------------------------------------------------------------------

    def _fresh(self, v: Venture) -> Venture:
        """The ledger is the truth: re-project the venture; a stale handle never decides."""
        current = self._registry.get(v.id)
        return current if current is not None else v

    def _facts(self, v: Venture, payload: dict | None, reason: str | None) -> Facts:
        from charterhouse.ledger import EventFilter

        return Facts(
            venture=v,
            events=tuple(self._ledger.read(EventFilter(venture_id=v.id))),
            slots=self.slots(),
            now_active=self._clock.now_active,
            limits=self._limits,
            payload=payload or {},
            reason=reason,
        )

    def _log_refusal(self, venture_id: str | None, kind: str, detail: str) -> None:
        """docs/42 §4: reject + log — one ``error`` event per refusal (fail closed).
        Long digit runs (token/event ids in partner reasons) are masked so the log can
        never trip the Ledger's structural PII pre-check (docs/41 §4.4)."""
        self._ledger.append(Event(
            type=EventType.ERROR, actor=_ACTOR,
            payload={"where": "lifecycle", "kind": kind,
                     "detail": re.sub(r"\d{6,}", "<id>", detail),
                     "fail_closed": True},
            venture_id=venture_id, active_time=self._clock.now_active))

    def _authorize(self, scope: str, venture_id: str, token: Token | None,
                   *, log: bool = True) -> None:
        """Delegate to Gov (IF-3) — S5 re-implements no token rule (INV-COND-1 discipline).
        ``log=False`` for the all-or-nothing seams (pivot/OMW), whose refusals append
        nothing (API.md)."""
        decision = self._gov.authorize(Action(scope, venture_id=venture_id), token)
        if not decision.ok:
            if log:
                self._log_refusal(venture_id, "authorization_denied",
                                  decision.reason or scope)
            raise AuthorizationDenied(
                f"gate transition refused by Governance: {decision.reason}")

    # --- frozen surface (docs/40 §3, IF-4) --------------------------------------------------

    def can_transition(self, v: Venture, to: State) -> GuardResult:
        """Pure check of the full docs/42 §3 guard column for ``(v.state, to)`` —
        legality, slots, ledger facts, TTL. Never raises on business grounds, never
        logs, never mutates."""
        v = self._fresh(v)
        rule = TRANSITIONS.get((v.state, to))
        if rule is None:
            return GuardResult(
                ok=False,
                reasons=(f"illegal transition: {v.state.value} -> {to.value} is not in "
                         "the docs/42 §3 table (INV-SM-1)",),
                needs_auth=None)
        reasons: list[str] = []
        facts = self._facts(v, None, None)
        if rule.slot is not None and not facts.slots.free(rule.slot):
            reasons.append(f"no free {rule.slot} slot (INV-SM-2)")
        reasons.extend(evaluate(rule.guards, facts).values())
        needs = AuthClass(ActionColor.RED) if rule.auth_scope else AuthClass(ActionColor.GREEN)
        return GuardResult(ok=not reasons, reasons=tuple(reasons), needs_auth=needs)

    def transition(
        self,
        v: Venture,
        to: State,
        token: Token | None = None,
        *,
        express: bool = False,
        reason: str | None = None,
        payload: dict | None = None,
    ) -> Result:
        """Execute one legal, guarded, authorized transition: exactly one state-changing
        append on success; ``error`` append + typed raise on refusal (INV-SM-1..6)."""
        v = self._fresh(v)
        frm = v.state
        rule = TRANSITIONS.get((frm, to))
        if rule is None:
            detail = f"{frm.value} -> {to.value} not in the docs/42 §3 table"
            self._log_refusal(v.id, "illegal_transition", detail)
            raise IllegalTransition(f"illegal transition (INV-SM-1): {detail}")
        if express and not rule.express_ok:
            detail = (f"{frm.value} -> {to.value} is not an express row; slot-consuming "
                      "advances occur only at a deliberate gate (R-SLOT-GATE)")
            self._log_refusal(v.id, "express_refused", detail)
            raise ExpressRefused(f"express refused (INV-SM-4): {detail}")
        facts = self._facts(v, payload, reason)
        if rule.slot is not None and not facts.slots.free(rule.slot):
            count, limit = getattr(facts.slots, rule.slot)
            detail = f"{rule.slot} WIP is {count}/{limit}; no free slot for {to.value}"
            self._log_refusal(v.id, "slot_limit", detail)
            raise SlotLimitExceeded(f"WIP limit (INV-SM-2): {detail}")
        failures = evaluate(rule.guards, facts)
        if failures:
            detail = "; ".join(failures.values())
            self._log_refusal(v.id, "guard_failed", detail)
            if "evidence_fresh" in failures:
                raise StaleEvidence(f"stale evidence (INV-SM-6): {failures['evidence_fresh']}")
            raise GuardFailed(f"guard failed (docs/42 §3): {detail}")
        if rule.auth_scope is not None:
            scope = "advance.express" if express else rule.auth_scope
            self._authorize(scope, v.id, token)
        event_id = self._ledger.append(self._build_event(rule, v, to, express, reason,
                                                         payload or {}, token))
        return Result(ok=True, event_id=event_id, from_state=frm, to_state=to)

    def _build_event(self, rule: Rule, v: Venture, to: State, express: bool,
                     reason: str | None, payload: dict, token: Token | None) -> Event:
        """The single state-changing append per row (lifecycle/API.md event mapping)."""
        now = self._clock.now_active
        et = rule.event_type
        if et is EventType.FRAME:
            body = {"brief_ref": payload.get("brief_ref"), "score": payload.get("score"),
                    "quotes": payload.get("quotes"), "reach_is_hypothesis": True}
        elif et is EventType.ADMIT:
            body = {"slot": "validating"}
        elif et is EventType.PARK:
            body = {"reason": reason or "no validating slot free"}
        elif et is EventType.SHOVEL_READY:
            body = {"evidence_ttl_at": now + self._limits.evidence_ttl_days}
        elif et is EventType.KILL:
            body = {"reason": reason}
        elif et is EventType.GRADUATE:
            body = {}
        elif et is EventType.ALUMNI_TRANSITION:
            body = {"to": to.value}
        else:
            body = {"reason": reason or "",
                    "gate_type": "express" if express else rule.gate_type}
        return Event(
            type=et, actor=_ACTOR, payload=body, venture_id=v.id,
            from_state=v.state.value, to_state=to.value,
            authorization=(token.id if (token is not None and rule.auth_scope) else None),
            active_time=now)

    def slots(self) -> SlotState:
        """Current WIP counts vs limits (INV-SM-2), fresh from the Registry."""
        return slot_state(self._registry, self._limits)

    def clock(self, v: Venture) -> ActiveTime:
        """Active-time answer for ``v`` (INV-SM-3): deadlines from
        ``experiment_live_at``; state windows from ``state_entered_at``; pause freezes."""
        return derive_active_time(self._fresh(v), self._clock, self._limits)

    # --- documented additive seams (API.md v1 notes; docs/43 §7 no-bump) --------------------

    def pivot(
        self,
        v: Venture,
        token: Token | None,
        *,
        new_id: str,
        codename: str,
        inherited: dict,
        reason: str,
    ) -> PivotResult:
        """Kill-and-fork per docs/42 §5 (INV-SM-5). All checks run before the first
        append; ``kill`` leads the sequence so a torn run degrades to a plain kill
        (RISKS R2)."""
        v = self._fresh(v)
        # Pivot refusals append NOTHING (API.md): the whole recipe is all-or-nothing,
        # so a refusal must leave the ledger byte-identical (RISKS R2).
        if v.state not in PIVOT_STATES:
            raise IllegalTransition(
                f"illegal pivot (docs/42 §3): defined from LAUNCHED/EARNING, "
                f"not {v.state.value}")
        if not reason or not reason.strip():
            raise GuardFailed("pivot requires a non-empty founder reason")
        if self._registry.get(new_id) is not None or new_id == v.id:
            raise GuardFailed(f"fork id {new_id!r} is already a venture")
        if lineage_has(self._ledger, self._registry, v.id, EventType.PIVOT_FORK):
            raise ForkCapExceeded(
                "fork cap (INV-SM-5): this lineage already holds its one fork; a second "
                "pivot must clear a fresh full validation as a new lineage")
        self._authorize("pivot", v.id, token, log=False)
        now = self._clock.now_active
        token_id = token.id if token is not None else None
        e1 = self._ledger.append(Event(
            type=EventType.KILL, actor=_ACTOR, payload={"reason": reason},
            venture_id=v.id, from_state=v.state.value, to_state=State.KILLED.value,
            authorization=token_id, active_time=now))
        e2 = self._ledger.append(Event(
            type=EventType.PIVOT_FORK, actor=_ACTOR,
            payload={"killed_id": v.id, "new_id": new_id, "inherited": inherited},
            venture_id=v.id, authorization=token_id, active_time=now))
        e3 = self._ledger.append(Event(
            type=EventType.CAPTURE, actor=_ACTOR,
            payload={"source": "pivot", "note_ref": f"fork-of-{v.id}",
                     "codename": codename, "forked_from": v.id},
            venture_id=new_id, to_state=State.CAPTURED.value, active_time=now))
        e4 = self._ledger.append(Event(
            type=EventType.TRANSITION, actor=_ACTOR,
            payload={"reason": "pivot fork re-entry for re-scoring (docs/42 §5)",
                     "gate_type": "internal"},
            venture_id=new_id, from_state=State.CAPTURED.value,
            to_state=State.FRAMED.value, active_time=now))
        return PivotResult(killed_id=v.id, new_id=new_id, events=(e1, e2, e3, e4))

    def grant_omw(self, v: Venture, token: Token | None) -> str:
        """Record a ONE-MORE-WEEK grant (R-OMW-LEDGER): first-class ledger event; a
        second grant anywhere in the lineage is refused against the ledger, never
        memory."""
        v = self._fresh(v)
        # Same all-or-nothing shape as pivot: a refused grant appends nothing.
        if lineage_has(self._ledger, self._registry, v.id, EventType.OMW_GRANT):
            raise OmwExhausted("OMW cap (R-OMW-LEDGER): this lineage already consumed "
                               "its single ONE-MORE-WEEK")
        self._authorize("gate", v.id, token, log=False)
        return self._ledger.append(Event(
            type=EventType.OMW_GRANT, actor=_ACTOR, payload={}, venture_id=v.id,
            authorization=(token.id if token is not None else None),
            active_time=self._clock.now_active))

    def pause(self, reason: str) -> str:
        """Freeze factory-active time (INV-SM-3) + append the factory-global ``pause``."""
        if self._clock.paused:
            self._log_refusal(None, "pause_refused", "factory is already paused")
            raise GuardFailed("factory is already paused")
        event_id = self._ledger.append(Event(
            type=EventType.PAUSE, actor=_ACTOR, payload={"reason": reason},
            venture_id=None, active_time=self._clock.now_active))
        self._clock.pause()
        return event_id

    def resume(self, reason: str) -> str:
        """Restart factory-active time + append the factory-global ``resume``."""
        if not self._clock.paused:
            self._log_refusal(None, "resume_refused", "factory is not paused")
            raise GuardFailed("factory is not paused")
        event_id = self._ledger.append(Event(
            type=EventType.RESUME, actor=_ACTOR, payload={"reason": reason},
            venture_id=None, active_time=self._clock.now_active))
        self._clock.resume()
        return event_id
