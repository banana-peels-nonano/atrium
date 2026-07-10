"""A5-local test support for the S6+S7 (Governance/Security) suite — PROVISIONAL.

Like ``_a3_support``: these doubles (steppable clock, Config stub, acting-subsystem event
builder, misbehaving redactor, fake cloud adapter, governance property oracle) are A5-owned
until the shared A11 harness lands, then the reusable pieces are hoisted and this module is
deleted.

The ``GovOracle`` is deliberately an *independent* re-derivation of expected authorization/
envelope accounting — plain dict bookkeeping, never a call into ``Gov`` internals (it exists
to check them).
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from charterhouse.contracts.authz import Token
from charterhouse.contracts.config_types import Budgets
from charterhouse.contracts.events import Event, EventType
from charterhouse.security.redact import Redactor
from charterhouse.security.scan import Scanner
from charterhouse.security.tag import require_cloud_allowed
from charterhouse.security.types import Context

# 2026-07-07T08:00:00Z — a fixed, readable test epoch.
START = datetime(2026, 7, 7, 8, 0, 0, tzinfo=timezone.utc).timestamp()
DAY0 = "2026-07-07"
DAY1 = "2026-07-08"


class SteppableClock:
    """Deterministic injected clock (seconds). Drives token expiry and event timestamps."""

    def __init__(self, start: float = START) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += float(seconds)

    def advance_days(self, days: float) -> None:
        self.advance(days * 86_400.0)


def iso(t: float) -> str:
    """ISO-8601 wall-clock string for the event envelope ``timestamp``."""
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


class FakeConfig:
    """`ConfigPort` double (docs/43 §2) returning the frozen IF-2 ``Budgets`` shape.
    Swapped for the real S3 Config when A2 lands — same shape, same property."""

    def __init__(self, send_daily: int = 40, monthly_usd: float = 20.0,
                 on_exceeded: str = "degrade") -> None:
        self._budgets = Budgets(monthly_usd=monthly_usd, on_exceeded=on_exceeded,
                                send_daily=send_daily)

    @property
    def budgets(self) -> Budgets:
        return self._budgets


def send_batch_event(venture_id: str, count: int, token_id: str, timestamp: str) -> Event:
    """What the *acting* subsystem (send-assist via Conductor) appends after an authorized
    send — Gov accounts for these by reading the ledger (governance/IMPLEMENTATION §6)."""
    return Event(
        type=EventType.SEND_BATCH,
        actor="conductor",
        payload={"count": count, "audience_tz": "US/Eastern", "per_domain": {}},
        venture_id=venture_id,
        authorization=token_id,
        timestamp=timestamp,
    )


# --- S7 doubles -----------------------------------------------------------------------------


class MisbehavingRedactor(Redactor):
    """Fault injection (docs/24 acceptance): a redactor that redacts nothing. The independent
    CHECKPOINT scan must catch what it misses and fail closed (INV-PII-2)."""

    def __init__(self) -> None:  # deliberately no super().__init__ — holds no state
        pass

    def redact(self, text: str, doc_id: str | None = None) -> tuple[str, str | None]:
        return text, None


class SpyRedactor(Redactor):
    """Records call order/arguments for the pipeline-order test, then behaves normally."""

    def __init__(self, calls: list, vault_dir, scanner: Scanner) -> None:
        super().__init__(vault_dir, scanner)
        self._calls = calls

    def redact(self, text: str, doc_id: str | None = None) -> tuple[str, str | None]:
        self._calls.append(("redact", text))
        return super().redact(text, doc_id)


class SpyScanner(Scanner):
    """Records call order/arguments for the pipeline-order test, then behaves normally."""

    def __init__(self, calls: list, known_identities: tuple[str, ...] = ()) -> None:
        super().__init__(known_identities)
        self._calls = calls

    def scan(self, text: str):
        self._calls.append(("scan", text))
        return super().scan(text)


class FakeCloudAdapter:
    """Stands in for an S8 cloud adapter until the joint S7×S8 test: consults the frozen
    guard before 'sending' (INV-PII-3). Never touches a network."""

    def complete(self, ctx: Context) -> str:
        require_cloud_allowed(ctx)
        return "fake-cloud-response"


# --- Governance property oracle (INV-GOV-1/3/4) ----------------------------------------------


class GovOracle:
    """Independent expected-outcome bookkeeping for seeded op scripts."""

    def __init__(self, clock: SteppableClock) -> None:
        self._clock = clock
        self._tokens: dict[str, tuple[str, str | None, float]] = {}
        self._consumed: set[str] = set()
        self._envelopes: dict[str, list[float]] = {}  # venture -> [cap, running_total]

    def on_grant(self, token: Token) -> None:
        self._tokens[token.id] = (token.scope, token.venture_id, token.expires_at)

    def expect_authorize(self, action_name: str, venture: str, token: Token | None) -> bool:
        if token is None or token.id not in self._tokens:
            return False
        scope, tv, expires = self._tokens[token.id]
        if token.id in self._consumed or self._clock() > expires:
            return False
        return scope == action_name and tv == venture

    def on_authorized(self, token: Token) -> None:
        self._consumed.add(token.id)

    def on_envelope_open(self, venture: str, cap: float) -> None:
        self._envelopes[venture] = [cap, 0.0]

    def expect_spend(self, venture: str, amount: float) -> tuple[bool, float, bool]:
        """(ok, running_total_after, degrade) — refusals leave the total unchanged."""
        env = self._envelopes.get(venture)
        if env is None:
            return (False, 0.0, False)
        cap, total = env
        if total + amount <= cap + 1e-9:
            env[1] = total + amount
            return (True, env[1], env[1] > 0.8 * cap + 1e-9)
        return (False, total, False)

    def envelope(self, venture: str) -> tuple[float, float] | None:
        env = self._envelopes.get(venture)
        return (env[0], env[1]) if env else None


def governance_script(seed: int) -> list[tuple]:
    """One seeded random op script over three ventures: grants, authorize attempts (live,
    forged, reused, missing tokens), envelope opens, spends, and clock jumps."""
    rng = random.Random(seed)
    ventures = ("v1", "v2", "v3")
    ops: list[tuple] = []
    for _ in range(rng.randint(12, 28)):
        v = rng.choice(ventures)
        r = rng.random()
        if r < 0.22:
            ops.append(("grant", v, rng.choice([60.0, 900.0])))
        elif r < 0.50:
            ops.append(("authorize", v, rng.choice(["latest", "forged", "none", "reused"])))
        elif r < 0.62:
            ops.append(("open", v, rng.choice([40.0, 90.0, 120.0])))
        elif r < 0.92:
            ops.append(("spend", v, round(rng.uniform(1.0, 70.0), 2)))
        else:
            ops.append(("advance", rng.choice([30.0, 120.0, 1000.0])))
    return ops
