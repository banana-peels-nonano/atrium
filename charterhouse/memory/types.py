"""Public value types + error taxonomy for S9 Memory (memory/API.md, docs/33 schema).

Declarations only — the frozen shapes S10 stubs against (docs/12 "interface frozen
early"). ``PIIEmbedBlocked`` messages name finding *kinds*, never values (INV-PII-4:
errors must be loggable). ``EmbedModelMismatch`` is deliberately NOT declared here — it
is reused from S2 (``charterhouse.env.types``), one mismatch-refusal type across the seam.

Determinism (docs/61 §INV-DET): stdlib only; no LLM anywhere in S9.
"""

from __future__ import annotations

from dataclasses import dataclass

# docs/33 table schema vocabularies (frozen).
KINDS: tuple[str, ...] = ("lesson", "playbook", "research_chunk", "segment_insight")
STATUSES: tuple[str, ...] = ("active", "retired", "superseded")


@dataclass(frozen=True)
class TaskContext:
    """The retrieval query (docs/40 §6): the task's (already-redacted) text plus the
    signals the docs/33 ranking terms consume. ``active_time`` is the factory
    active-time counter at query time — recency never uses wall clock (deterministic)."""

    text: str
    tags: tuple[str, ...] = ()
    venture_id: str | None = None
    segment: str | None = None
    active_time: int = 0


@dataclass(frozen=True)
class Lesson:
    """One memory record as the caller supplies it (docs/33 schema minus the
    store-stamped fields ``vector``/``embed_model``). ``text`` MUST already be redacted —
    S9 verifies (INV-MEM-4) but never redacts. ``lesson_id`` empty = assigned on write."""

    text: str
    source_ref: str
    kind: str = "lesson"
    tags: tuple[str, ...] = ()
    venture_id: str | None = None
    segment: str | None = None
    confidence: float = 0.5
    status: str = "active"
    created_active_time: int = 0
    lesson_id: str = ""


@dataclass(frozen=True)
class RankingComponents:
    """The per-term breakdown of one retrieval score (auditability — the gate brief can
    show *why* a lesson surfaced). Each term is the raw component BEFORE its weight."""

    semantic: float
    tag_match: float
    recency: float
    confidence: float
    segment_match: float


@dataclass(frozen=True)
class ScoredLesson:
    """One retrieved record: the lesson, its total weighted score, and the breakdown."""

    lesson: Lesson
    score: float
    components: RankingComponents


@dataclass(frozen=True)
class WorkingSet:
    """The docs/12 working memory: Doctrine ALWAYS (``""`` in the legitimate
    pre-doctrine state) + at most ``k`` active records (INV-MEM-1). Never the full store."""

    doctrine: str
    records: tuple[ScoredLesson, ...]
    k: int


@dataclass(frozen=True)
class ConsolidationReport:
    """What one consolidation pass did (INV-MEM-3 — view mutations only).
    ``merged`` pairs are ``(superseded_id, kept_id)``; ``doctrine_proposals`` are
    proposals ONLY (the founder writes Doctrine, never this code)."""

    merged: tuple[tuple[str, str], ...]
    retired: tuple[str, ...]
    promoted: tuple[str, ...]
    doctrine_proposals: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalWeights:
    """The docs/33 ranking weights + consolidation thresholds as frozen data — injected
    at wiring (IMPLEMENTATION §6.1; a future additive ``Config.memory`` accessor feeds
    this). ``half_life_active`` is in factory active-time units."""

    w_semantic: float = 0.5
    w_tag: float = 0.2
    w_recency: float = 0.15
    w_confidence: float = 0.15
    w_segment: float = 0.1
    half_life_active: float = 30.0
    dup_threshold: float = 0.995
    retire_below: float = 0.2
    promote_min_ventures: int = 3
    # The hard working-memory bound: ``retrieve``'s k is clamped to this, so "the full
    # store is never dumped into a prompt" (docs/33) holds even for an absurd k.
    max_k: int = 16


# --- Error taxonomy (fail closed, docs/61 §INV-FAILCLOSED) ---------------------------------


class MemoryEngineError(Exception):
    """Base class for every S9 failure. (Named to avoid the ``MemoryError`` builtin.)"""


class LessonInvalid(MemoryEngineError):
    """A lesson violates the docs/33 shape (kind/status vocabulary, confidence range,
    empty text/source_ref). Names the offending field; nothing is written."""


class PIIEmbedBlocked(MemoryEngineError):
    """The merged S7 scanner found PII/secret content on the write path (INV-MEM-4).
    Nothing was embedded, stored, or appended. The message names finding *kinds* only."""


class UnguardedReindex(MemoryEngineError):
    """``reindex`` was invoked without a reason — a re-index is never silent (INV-MEM-2)."""


class ScopeViolation(MemoryEngineError):
    """A caller-supplied capability scope does not cover the lesson's tags (docs/54 §S11
    boundary; additive ``scope`` seam)."""


class EmbedFailed(MemoryEngineError):
    """The local embedding endpoint failed (transport/shape). No retry, no cloud fallback
    — there is no cloud path in S9."""
