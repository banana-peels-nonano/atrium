"""S9 retrieval ranking — the docs/33 weighted score over ACTIVE rows only (INV-MEM-1).

``score = w1·semantic + w2·tag_match + w3·recency + w4·confidence
          (+ w5·segment_match when the task carries a segment)``

- semantic: cosine over unit vectors (dot product).
- tag_match: |task.tags ∩ row.tags| / |task.tags| (0 when the task has no tags).
- recency:  0.5 ** (age_active / half_life_active) — factory ACTIVE-TIME, never wall
  clock (deterministic; docs/42 clock semantics).
- confidence: the row's own confidence.
- segment_match: exact segment equality, applied only when the task has a segment.

Exact scoring at portfolio scale (ANN prefilter later — RISKS R6; internal, no ICR).
Deterministic total order: score desc, then lesson_id asc. ``k`` is clamped to
``weights.max_k`` — the full store is never dumped (docs/33).

Determinism (docs/61 §INV-DET): pure functions, stdlib only, no LLM, no I/O.
"""

from __future__ import annotations

from charterhouse.memory.types import (
    Lesson,
    RankingComponents,
    RetrievalWeights,
    ScoredLesson,
    TaskContext,
)

__all__ = ["rank", "row_to_lesson"]


def row_to_lesson(row: dict) -> Lesson:
    """The docs/33 row → the frozen ``Lesson`` shape (store-stamped fields dropped)."""
    return Lesson(
        text=row["text"],
        source_ref=row["source_ref"],
        kind=row["kind"],
        tags=tuple(row["tags"] or ()),
        venture_id=row["venture_id"],
        segment=row["segment"],
        confidence=float(row["confidence"]),
        status=row["status"],
        created_active_time=int(row["created_active_time"]),
        lesson_id=row["id"],
    )


def rank(query_vector: tuple[float, ...], task: TaskContext, rows: list[dict],
         k: int, weights: RetrievalWeights) -> tuple[ScoredLesson, ...]:
    """Score every (already status-filtered) candidate row and return the top-``k`` in
    the deterministic order. Never returns more than ``min(k, weights.max_k)``."""
    k = max(0, min(k, weights.max_k))
    task_tags = set(task.tags)
    scored: list[ScoredLesson] = []
    for row in rows:
        semantic = sum(q * v for q, v in zip(query_vector, row["vector"]))
        tag_match = (len(task_tags & set(row["tags"] or ())) / len(task_tags)
                     if task_tags else 0.0)
        age = max(0, task.active_time - int(row["created_active_time"]))
        recency = 0.5 ** (age / weights.half_life_active)
        confidence = float(row["confidence"])
        segment_match = (1.0 if task.segment and row["segment"] == task.segment
                         else 0.0)
        score = (weights.w_semantic * semantic
                 + weights.w_tag * tag_match
                 + weights.w_recency * recency
                 + weights.w_confidence * confidence)
        if task.segment:
            score += weights.w_segment * segment_match
        scored.append(ScoredLesson(
            lesson=row_to_lesson(row),
            score=score,
            components=RankingComponents(
                semantic=semantic, tag_match=tag_match, recency=recency,
                confidence=confidence, segment_match=segment_match)))
    scored.sort(key=lambda s: (-s.score, s.lesson.lesson_id))
    return tuple(scored[:k])
