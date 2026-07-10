"""S6 token store — single-use, expiring, scoped founder authorizations (INV-GOV-1/3).

Consumption state lives HERE, never on the immutable ``Token`` dataclass (a copied token must
not be able to reset single-use). Validation always runs against the *issued* record, so a
tampered presented copy cannot extend its own expiry or scope. The store is process-local by
design: an unknown token is invalid, so a restart voids outstanding grants — the failure
direction is a re-grant, never an unauthorized action (governance/RISKS R4).
"""

from __future__ import annotations

from collections.abc import Callable

from charterhouse.contracts.authz import Token

from charterhouse.governance.types import Action


class TokenStore:
    """Issues, validates, and consumes tokens against an injected clock + id factory."""

    def __init__(self, *, clock: Callable[[], float], new_id: Callable[[], str]) -> None:
        self._clock = clock
        self._new_id = new_id
        self._issued: dict[str, Token] = {}
        self._consumed: set[str] = set()

    def grant(
        self,
        scope: str,
        venture_id: str | None,
        ttl_s: float,
        cap_usd: float | None = None,
    ) -> Token:
        """Mint a single-use token scoped to ``scope``+``venture_id``, expiring at
        ``clock()+ttl_s``. Empty scope → ``ValueError``."""
        if not scope or not scope.strip():
            raise ValueError("token scope must be a non-empty action name")
        now = self._clock()
        issued = Token(
            id=self._new_id(),
            scope=scope,
            venture_id=venture_id,
            issued_at=now,
            expires_at=now + float(ttl_s),
            cap_usd=cap_usd,
        )
        self._issued[issued.id] = issued
        return issued

    def validate(self, token: Token | None, action: Action) -> str | None:
        """Return ``None`` if ``token`` authorizes ``action``, else the denial reason
        (issued-here ∧ unconsumed ∧ unexpired ∧ scope==action.name ∧ venture match)."""
        if token is None:
            return "RED action requires a founder token; none presented (INV-GOV-1)"
        issued = self._issued.get(token.id)
        if issued is None:
            return f"token {token.id!r} was not issued by this governance store (INV-GOV-1)"
        if token.id in self._consumed:
            return f"token {token.id!r} already consumed — tokens are single-use (INV-GOV-3)"
        if self._clock() > issued.expires_at:
            return f"token {token.id!r} expired (INV-GOV-3)"
        if issued.scope != action.name:
            return (
                f"token scope {issued.scope!r} does not cover action "
                f"{action.name!r} (INV-GOV-1)"
            )
        if issued.venture_id != action.venture_id:
            return "token venture does not match the action's venture (INV-GOV-1)"
        return None

    def consume(self, token_id: str) -> None:
        """Burn the token (single-use). Called only on a successful authorization."""
        self._consumed.add(token_id)
