"""``Gov`` — the S6 chokepoint (docs/40 §4 frozen surface + two documented additive seams;
governance/API.md).

Classifies, authorizes/denies, and records. Performs NO action: the acting subsystem appends
the action event carrying the consumed token id; Gov accounts by reading the ledger.
Deterministic (injected clock + id factory); fail closed everywhere.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from charterhouse.contracts.authz import ActionColor, AuthClass, Token
from charterhouse.contracts.events import Event, EventType
from charterhouse.ledger import EventFilter, Ledger

from charterhouse.governance.classify import batch_count, is_known
from charterhouse.governance.classify import classify as _classify
from charterhouse.governance.envelope import envelope_state
from charterhouse.governance.send_budget import sent_on
from charterhouse.governance.tokens import TokenStore
from charterhouse.governance.types import (
    Action,
    ConfigPort,
    Decision,
    MissingReason,
    SpendResult,
)

_OVERRIDE_KINDS = frozenset({"admission", "advance", "kill", "score"})


def _default_token_id() -> str:
    return f"tok-{uuid.uuid4().hex}"


class Gov:
    """S6 Governance. See governance/API.md for the full per-function contract."""

    def __init__(
        self,
        ledger: Ledger,
        config: ConfigPort,
        *,
        clock: Callable[[], float],
        new_id: Callable[[], str] | None = None,
    ) -> None:
        budgets = config.budgets  # fail closed at wiring: budgets must be reachable
        if budgets is None or int(budgets.send_daily) < 0:
            raise ValueError("Config.budgets must provide a non-negative send_daily")
        self._ledger = ledger
        self._config = config
        self._clock = clock
        self._store = TokenStore(clock=clock, new_id=new_id or _default_token_id)

    # --- time helpers (single injected clock; deterministic in tests) -----------------------

    def _now_iso(self) -> str:
        return datetime.fromtimestamp(self._clock(), tz=timezone.utc).isoformat()

    def _today(self) -> str:
        return self._now_iso()[:10]

    def _append(
        self,
        type_: EventType,
        venture_id: str | None,
        payload: dict,
        *,
        actor: str = "conductor",
        authorization: str | None = None,
    ) -> str:
        return self._ledger.append(
            Event(
                type=type_,
                actor=actor,
                payload=payload,
                venture_id=venture_id,
                authorization=authorization,
                timestamp=self._now_iso(),
            )
        )

    # --- the frozen docs/40 §4 surface -------------------------------------------------------

    def classify(self, action: Action) -> AuthClass:
        """Frozen class per the docs/14 matrix; unknown → RED (fail closed). Pure."""
        return _classify(action)

    def authorize(self, action: Action, token: Token | None) -> Decision:
        """GREEN/YELLOW → ok (no token consumed). RED → valid+scoped+unconsumed token required
        (INV-GOV-1/3); two-key additionally needs ``action.check.passed`` (INV-GOV-2);
        ``send.stage`` additionally needs budget headroom (INV-GOV-5). Consumes on ok only."""
        if not is_known(action.name):
            return Decision(False, f"unknown action {action.name!r} — denied (fail closed)")
        auth = _classify(action)
        if auth.color is not ActionColor.RED:
            return Decision(True, f"{auth.color.value}: autonomous within rules, logged")

        denial = self._store.validate(token, action)
        if denial is not None:
            return Decision(False, denial)
        if auth.two_key and (action.check is None or not action.check.passed):
            return Decision(
                False,
                "two-key action requires a passing automated check on top of the token "
                "(INV-GOV-2); token not consumed",
            )
        if action.name == "send.stage":
            count = batch_count(action)
            if count is None:
                return Decision(
                    False,
                    "send.stage count must be a clean non-negative integer — refused "
                    "(fail closed, INV-GOV-2/5); token not consumed",
                )
            remaining = self.send_budget_remaining(self._today())
            if count > remaining:
                return Decision(
                    False,
                    f"founder-wide send budget exceeded: batch of {count} > {remaining} "
                    f"remaining today (INV-GOV-5); token not consumed",
                )
        assert token is not None  # validate() guaranteed above
        self._store.consume(token.id)
        return Decision(True, "authorized (token consumed — single-use)")

    def envelope_open(self, venture_id: str, cap_usd: float) -> Token:
        """The authorize-once RED act (INV-GOV-4): mints the envelope token, appends
        ``spend_envelope{cap_usd}`` carrying it, and consumes it (the append IS its single
        use; the returned token is a receipt). Non-positive cap → ``ValueError``."""
        cap = float(cap_usd)
        if not cap > 0:
            raise ValueError("envelope cap_usd must be positive")
        receipt = self._store.grant("spend.envelope", venture_id, ttl_s=3600.0, cap_usd=cap)
        self._store.consume(receipt.id)
        self._append(
            EventType.SPEND_ENVELOPE, venture_id, {"cap_usd": cap}, authorization=receipt.id
        )
        return receipt

    def spend(self, venture_id: str, amount: float) -> SpendResult:
        """Within cap → YELLOW ok + ``spend_meter`` (degrade past 80%); over cap → refused +
        ``spend_breach`` (re-RED required); no envelope → refused, nothing appended."""
        amount = float(amount)
        events = list(self._ledger.read(EventFilter(venture_id=venture_id)))
        state = envelope_state(events)
        if not state.open:
            return SpendResult(
                ok=False, color=None, amount=amount, running_total=0.0, cap_usd=None,
                reason="no spend envelope authorized for this venture — open one first "
                       "(RED envelope_open; INV-GOV-4 authorize-once)",
            )
        if state.running_total + amount <= state.cap_usd + 1e-9:
            new_total = state.running_total + amount
            self._append(
                EventType.SPEND_METER, venture_id,
                {"amount_usd": amount, "running_total": new_total},
            )
            return SpendResult(
                ok=True, color=ActionColor.YELLOW, amount=amount, running_total=new_total,
                cap_usd=state.cap_usd,
                degrade=new_total > 0.8 * state.cap_usd + 1e-9,
                reason="within envelope (YELLOW, logged)",
            )
        attempted = state.running_total + amount
        self._append(
            EventType.SPEND_BREACH, venture_id,
            {"attempted": attempted, "cap": state.cap_usd},
        )
        return SpendResult(
            ok=False, color=None, amount=amount, running_total=state.running_total,
            cap_usd=state.cap_usd,
            reason=f"envelope breach: {attempted} exceeds cap {state.cap_usd} — refused; "
                   f"raising the cap requires a fresh RED envelope_open (INV-GOV-4 re-RED)",
        )

    def send_budget_remaining(self, day: str) -> int:
        """``budgets.send_daily − Σ send_batch.count`` on ``day`` across all ventures; floor 0."""
        events = list(self._ledger.read(EventFilter(type=EventType.SEND_BATCH)))
        return max(0, int(self._config.budgets.send_daily) - sent_on(events, day))

    # --- documented additive seams (API.md v1 notes; docs/43 §7 no-bump) ---------------------

    def grant(
        self,
        scope: str,
        venture_id: str | None,
        ttl_s: float,
        cap_usd: float | None = None,
    ) -> Token:
        """Mint a single-use scoped token — the founder-approval boundary (additive seam,
        API.md v1 note). Tests stop here (INV-TEST-SAFE)."""
        return self._store.grant(scope, venture_id, ttl_s, cap_usd)

    def record_override(
        self,
        kind: str,
        recommendation: str,
        decision: str,
        reason: str,
        venture_id: str,
        old_score: int | None = None,
        new_score: int | None = None,
    ) -> str:
        """Append the founder-override event (INV-GOV-6): ``override`` (or ``score_override``
        for kind="score"). Empty/whitespace reason → ``MissingReason``, nothing appended."""
        if kind not in _OVERRIDE_KINDS:
            raise ValueError(f"unknown override kind {kind!r} (expected one of "
                             f"{sorted(_OVERRIDE_KINDS)})")
        if not reason or not reason.strip():
            raise MissingReason(
                "a founder override MUST carry a non-empty reason (INV-GOV-6); nothing recorded"
            )
        if kind == "score":
            return self._append(
                EventType.SCORE_OVERRIDE, venture_id,
                {"old_score": old_score, "new_score": new_score, "reason": reason},
                actor="founder",
            )
        return self._append(
            EventType.OVERRIDE, venture_id,
            {"recommendation": recommendation, "decision": decision, "reason": reason},
            actor="founder",
        )
