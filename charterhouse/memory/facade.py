"""``Memory`` — the S9 facade wiring the frozen docs/40 §6 surface
(``retrieve/write_lesson/consolidate/reindex``). See memory/API.md for the full
per-method contract; memory/IMPLEMENTATION.md §2 for the INV-MEM-1..4 enforcement map.

INV-MEM-4 lives here: the merged S7 ``Scanner`` gates EVERY text before any embed —
verification, not redaction (redaction stays upstream at CHECKPOINT). A finding refuses
with kinds only: zero embedder calls, zero store writes, zero ledger appends.

Determinism (docs/61 §INV-DET): no LLM (the embedder is a local encoder), no env read —
paths/host/model arrive from A1's ``EnvContext`` at wiring.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from charterhouse.contracts.events import Event, EventType
from charterhouse.ledger import Ledger
from charterhouse.memory.consolidate import plan
from charterhouse.memory.embeddings import Embeddings
from charterhouse.memory.retrieval import rank
from charterhouse.memory.store import MemoryStore
from charterhouse.memory.types import (
    KINDS,
    STATUSES,
    ConsolidationReport,
    Lesson,
    LessonInvalid,
    PIIEmbedBlocked,
    RetrievalWeights,
    ScopeViolation,
    TaskContext,
    UnguardedReindex,
    WorkingSet,
)
from charterhouse.security.scan import Scanner

__all__ = ["Memory"]

# Generated ids use letters only ("les-" + digit-free hex) so a lesson_written payload
# can never trip S4's structural digit-run pre-check (RISKS R7).
_DIGITS_TO_LETTERS = str.maketrans("0123456789", "ghijklmnop")


def _new_lesson_id() -> str:
    return "les-" + uuid.uuid4().hex.translate(_DIGITS_TO_LETTERS)


class Memory:
    """S9 Memory. Constructed by the composition root with the opened ``MemoryStore``,
    the local ``Embeddings``, the real ``Ledger``, the merged S7 ``Scanner``, and the
    vault doctrine path (default ``vault/memory/DOCTRINE.md``, docs/23)."""

    def __init__(self, store: MemoryStore, embedder: Embeddings, ledger: Ledger,
                 scanner: Scanner, doctrine_path: Path,
                 weights: RetrievalWeights | None = None,
                 actor: str = "system") -> None:
        self._store = store
        self._embedder = embedder
        self._ledger = ledger
        self._scanner = scanner
        self._doctrine_path = Path(doctrine_path)
        self._weights = weights if weights is not None else RetrievalWeights()
        self._actor = actor

    # --- retrieval (INV-MEM-1) ----------------------------------------------------------

    def _doctrine(self) -> str:
        """Doctrine text — ``""`` in the legitimate pre-doctrine factory state
        (IMPLEMENTATION §6.2); never an error."""
        try:
            return self._doctrine_path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def retrieve(self, task: TaskContext, k: int) -> WorkingSet:
        """Doctrine ALWAYS + top-``k`` active records (INV-MEM-1). Read-only; never the
        full store (k is clamped to ``weights.max_k``); deterministic order."""
        query_vector = self._embedder.embed(task.text)
        records = rank(query_vector, task, self._store.active_rows(), k, self._weights)
        return WorkingSet(doctrine=self._doctrine(), records=records, k=len(records))

    # --- write path (INV-MEM-4) ---------------------------------------------------------

    @staticmethod
    def _validate(lesson: Lesson) -> None:
        if lesson.kind not in KINDS:
            raise LessonInvalid(f"kind must be one of {KINDS}, got {lesson.kind!r}")
        if lesson.status not in STATUSES:
            raise LessonInvalid(
                f"status must be one of {STATUSES}, got {lesson.status!r}")
        if not 0.0 <= lesson.confidence <= 1.0:
            raise LessonInvalid(
                f"confidence must be within [0.0, 1.0], got {lesson.confidence}")
        if not lesson.text.strip():
            raise LessonInvalid("text must be non-empty")
        if not lesson.source_ref.strip():
            raise LessonInvalid("source_ref must be non-empty")

    def _verify_no_pii(self, text: str) -> None:
        """The INV-MEM-4 verification layer: the merged S7 scanner, kinds-only refusal.
        Runs BEFORE any embed — a finding means zero embedder calls, zero writes."""
        findings = self._scanner.scan(text)
        if findings:
            kinds = ", ".join(sorted({f.kind for f in findings}))
            raise PIIEmbedBlocked(
                f"write refused — scanner findings: {kinds} (INV-MEM-4; redaction "
                f"happens upstream at CHECKPOINT, S7); nothing was embedded")

    def write_lesson(self, lesson: Lesson, *,
                     scope: tuple[str, ...] | None = None) -> str:
        """Verify (S7 scan, INV-MEM-4) → embed locally → store row → ONE
        ``lesson_written`` event. Fail closed at every step; a failed append rolls the
        row back (RISKS R10). ``scope`` is the additive S11 seam (docs/43 §7)."""
        self._validate(lesson)
        if scope is not None and not set(lesson.tags) <= set(scope):
            outside = ", ".join(sorted(set(lesson.tags) - set(scope)))
            raise ScopeViolation(
                f"lesson tags outside the caller's declared memory scope: {outside}")
        self._verify_no_pii("\n".join((lesson.text, lesson.source_ref,
                                       " ".join(lesson.tags))))
        lesson_id = lesson.lesson_id or _new_lesson_id()
        vector = self._embedder.embed(lesson.text)
        self._store.add({
            "id": lesson_id,
            "vector": list(vector),
            "kind": lesson.kind,
            "text": lesson.text,
            "tags": list(lesson.tags),
            "venture_id": lesson.venture_id,
            "segment": lesson.segment,
            "confidence": float(lesson.confidence),
            "status": lesson.status,
            "created_active_time": int(lesson.created_active_time),
            "source_ref": lesson.source_ref,
            "embed_model": self._store.embed_model,
        })
        event = Event(type=EventType.LESSON_WRITTEN, actor=self._actor,
                      payload={"lesson_id": lesson_id, "tags": list(lesson.tags),
                               "confidence": float(lesson.confidence)},
                      venture_id=lesson.venture_id)
        try:
            self._ledger.append(event)
        except Exception:
            # R10: no vector may exist without its ledger event — roll the row back
            # before any reader can observe it, then surface the failure unchanged.
            self._store._remove_unobserved(lesson_id)
            raise
        return lesson_id

    # --- consolidation (INV-MEM-3) -------------------------------------------------------

    def consolidate(self) -> ConsolidationReport:
        """One deterministic view pass (INV-MEM-3): merge/retire/promote + ONE
        ``consolidate`` event. The ledger is never edited."""
        outcome = plan(self._store.all_rows(), self._weights)
        for superseded_id, _kept in outcome.supersede:
            self._store.set_status(superseded_id, "superseded")
        for retired_id in outcome.retire:
            self._store.set_status(retired_id, "retired")
        promoted: list[str] = []
        for playbook in outcome.playbooks:
            self._verify_no_pii(playbook["text"])  # defense in depth (INV-MEM-4)
            vector = self._embedder.embed(playbook["text"])
            self._store.add({**playbook, "vector": list(vector),
                             "embed_model": self._store.embed_model})
            promoted.append(playbook["id"])
        self._ledger.append(Event(
            type=EventType.CONSOLIDATE, actor=self._actor,
            payload={"merged": len(outcome.supersede), "retired": len(outcome.retire),
                     "promoted": len(promoted)}))
        return ConsolidationReport(
            merged=outcome.supersede, retired=outcome.retire,
            promoted=tuple(promoted),
            doctrine_proposals=outcome.doctrine_proposals)

    # --- reindex (INV-MEM-2) --------------------------------------------------------------

    def reindex(self, reason: str) -> None:
        """Guarded full re-embed (INV-MEM-2): a blank reason refuses
        (``UnguardedReindex``); the pin + ``EMBED_MODEL`` marker update only on success."""
        if not reason or not reason.strip():
            raise UnguardedReindex(
                "reindex requires an explicit reason — an embed-model change is never "
                "silent (INV-MEM-2)")
        new_rows = []
        for row in self._store.all_rows():  # id-sorted: deterministic rebuild
            vector = self._embedder.embed(row["text"])
            new_rows.append({**row, "vector": list(vector),
                             "embed_model": self._store.embed_model})
        self._store.rebuild(new_rows, self._store.embed_model)
