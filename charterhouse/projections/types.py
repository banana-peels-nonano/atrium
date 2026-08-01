"""Public value types + error taxonomy for S13 Projections (projections/API.md;
docs/40 §9, docs/41 §3, docs/05 brief shapes).

Declarations only — every shape is frozen and derived; none is a source of truth
(INV-COND-3). ``GateBrief.critic`` is a REQUIRED field: the fixed schema cannot exist
without a Critic take (INV-COND-2 by construction; assembly refuses with
``NoCriticForGate`` instead of building a schema-broken brief).

Determinism (docs/61 §INV-DET): stdlib + contracts only; no LLM, no clock, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from charterhouse.contracts.state import State


@dataclass(frozen=True)
class BoardRow:
    """One PIPELINE row (docs/41 §3): the venture as replay sees it, plus deadline
    flags derived from ledger facts (evidence TTL, shaping window, experiment clock)."""

    venture_id: str
    codename: str
    state: State
    score: int | None
    state_entered_at: int | None
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Board:
    """The PIPELINE board — rows sorted by venture id (deterministic)."""

    rows: tuple[BoardRow, ...]


@dataclass(frozen=True)
class Metrics:
    """Counts/rates folded from the event stream (docs/41 §3). Pure; no wall clock."""

    by_state: tuple[tuple[str, int], ...]
    frames: int
    kills: int
    graduations: int
    experiments_pass: int
    experiments_fail: int
    llm_cost_usd: float
    spend_usd: float
    sends_by_day: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class CriticTake:
    """The mandatory Gate Brief critic field (INV-COND-2): the recorded tier and the
    artifact it critiqued (from ``artifact_produced`` / ``gate_decision`` history)."""

    tier: int
    artifact_ref: str | None = None
    verdict: str = ""  # additive (docs/43 §7): the critic's own call, e.g. review/flag/pass


@dataclass(frozen=True)
class GateBrief:
    """THE fixed gate schema (docs/40 §8, INV-COND-2). ``critic`` is required — an
    instance without one cannot be constructed; ``recommendation`` is the mechanical
    ADVANCE/HOLD/KILL advisory (the founder's decision is the authority)."""

    venture_id: str
    codename: str
    state: State
    score: int | None
    active_in_state: int | None
    evidence: tuple[str, ...]
    artifacts: tuple[str, ...]
    critic: CriticTake
    recommendation: str
    # Additive (docs/43 §7): the critic's concrete what-to-build-instead / how-to-sharpen
    # direction, so a gate is a STEER and not only kill-or-continue. Empty when the take
    # came from the tier-3 checklist floor or the critic gave no labelled steer — read it
    # together with `critic.tier`, which says where it came from.
    steer: str = ""

    def __post_init__(self) -> None:
        if self.critic is None:  # INV-COND-2 — no gate presentable without a critic
            raise NoCriticForGate(
                f"gate brief for {self.venture_id!r} has no Critic take (INV-COND-2)")


@dataclass(frozen=True)
class DailyBrief:
    """The docs/05 triaged brief. ``decisions == ()`` is the valid 'silence' output
    (INV-TRIAGE) — nothing needing a human is a correct answer, not an error."""

    decisions: tuple[str, ...]
    red_queue: tuple[str, ...]
    pending_sends: tuple[tuple[str, int], ...]
    board: Board


@dataclass(frozen=True)
class KillDayBrief:
    """Every ACTIVE venture, briefed (docs/05): (GateBrief, recommendation) rows, and
    the ventures that cannot be briefed yet (no critic take) — named, never dropped."""

    rows: tuple[tuple[GateBrief, str], ...]
    unbriefable: tuple[str, ...] = ()


@dataclass(frozen=True)
class CalibrationReport:
    """Overrides and evidence verdicts vs outcomes (docs/41 §3; docs/05 monthly)."""

    overrides: tuple[tuple[str, str, str], ...]  # (venture_id, kind, outcome-so-far)
    evidence_vs_outcome: tuple[tuple[str, str, str], ...]  # (venture_id, verdict, outcome)


class ProjectionsError(Exception):
    """Base class for S13 failures."""


class NoCriticForGate(ProjectionsError):
    """No critic take exists for the requested gate brief (INV-COND-2 — the brief is
    refused rather than existing schema-broken). Shared vocabulary with S12."""


class UnknownVenture(ProjectionsError):
    """The requested venture id has no ledger history (named; fail closed)."""
