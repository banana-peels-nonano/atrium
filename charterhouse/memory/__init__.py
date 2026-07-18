"""S9 Memory — the compounding knowledge substrate (docs/12, docs/33, docs/40 §6).

Public surface: ``Memory`` (retrieve/write_lesson/consolidate/reindex), the LOCAL-ONLY
``Embeddings``/``OllamaEmbedder``, ``MemoryStore`` (wiring), the frozen value types, and
the fail-closed error taxonomy. ``EmbedModelMismatch`` is re-exported from S2 — one
mismatch-refusal type across the seam (memory/API.md).
"""

from charterhouse.env.types import EmbedModelMismatch
from charterhouse.memory.embeddings import Embeddings, OllamaEmbedder
from charterhouse.memory.facade import Memory
from charterhouse.memory.store import EMBED_MARKER, MemoryStore
from charterhouse.memory.types import (
    KINDS,
    STATUSES,
    ConsolidationReport,
    EmbedFailed,
    Lesson,
    LessonInvalid,
    MemoryEngineError,
    PIIEmbedBlocked,
    RankingComponents,
    RetrievalWeights,
    ScopeViolation,
    ScoredLesson,
    TaskContext,
    UnguardedReindex,
    WorkingSet,
)

__all__ = [
    "EMBED_MARKER",
    "KINDS",
    "STATUSES",
    "ConsolidationReport",
    "EmbedFailed",
    "EmbedModelMismatch",
    "Embeddings",
    "Lesson",
    "LessonInvalid",
    "Memory",
    "MemoryEngineError",
    "MemoryStore",
    "OllamaEmbedder",
    "PIIEmbedBlocked",
    "RankingComponents",
    "RetrievalWeights",
    "ScopeViolation",
    "ScoredLesson",
    "TaskContext",
    "UnguardedReindex",
    "WorkingSet",
]
