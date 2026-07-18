"""A7-local test support for the S9 (Memory) suite — PROVISIONAL.

Builders wiring the real LanceDB ``MemoryStore`` on tmp_path + real tmp-path ``Ledger``
(A3 convention) + the merged S7 ``Scanner`` + A11's ``FakeEmbedder`` behind a counting
spy (the INV-MEM-4 zero-embed proofs), plus the independent ranking oracle for the
seeded property test (docs/55 §2 — **no network anywhere**).
"""

from __future__ import annotations

import random
import struct
from pathlib import Path
from types import SimpleNamespace

from charterhouse.ledger import Ledger
from charterhouse.memory import Lesson, Memory, MemoryStore, RetrievalWeights, TaskContext
from charterhouse.security.scan import Scanner

from tests.fakes import FakeEmbedder
from tests.fixtures.pii_corpus import KNOWN_IDENTITIES
from tests.unit import _a3_support as a3

DIM = 32
MODEL_A = "fake-embed-v1"
MODEL_B = "fake-embed-v2"
DOCTRINE = "Doctrine: evidence beats optimism; kill fast, salvage always, learn once."

TAG_VOCAB = ("channel", "pricing", "segment", "build", "scoring")
SEGMENTS = ("smb", "dev", "edu")


class SpyEmbedder:
    """A11's ``FakeEmbedder`` behind a call counter — proves ZERO embedder calls on an
    INV-MEM-4 refusal (and lets tests meter the write/query paths separately)."""

    def __init__(self, dim: int = DIM) -> None:
        self._inner = FakeEmbedder(dim)
        self.calls = 0

    def embed(self, text: str) -> tuple[float, ...]:
        self.calls += 1
        return self._inner.embed(text)

    @property
    def dim(self) -> int:
        return self._inner.dim


class FailingAppendLedger(Ledger):
    """A real ``Ledger`` whose ``append`` always fails — the RISKS R10 rollback probe."""

    def append(self, event):  # noqa: ANN001 — mirrors the IF-1 signature
        raise RuntimeError("append refused (R10 probe)")


def lesson(text: str, **kw) -> Lesson:
    """A valid docs/33 lesson with quiet defaults (override any field)."""
    defaults: dict = {"source_ref": "vault/lessons/sample.md", "kind": "lesson",
                      "tags": ("channel",), "confidence": 0.6,
                      "created_active_time": 0}
    defaults.update(kw)
    return Lesson(text=text, **defaults)


def make_memory(tmp_path: Path, *, dim: int = DIM, model: str = MODEL_A,
                weights: RetrievalWeights | None = None,
                doctrine: str | None = DOCTRINE,
                ledger: Ledger | None = None) -> SimpleNamespace:
    """(memory, store, embedder-spy, ledger, paths) over the real store + real Ledger
    + merged Scanner (corpus identities registered) + FakeEmbedder spy."""
    vectors_dir = tmp_path / "vectors"
    store = MemoryStore.open(vectors_dir, model, dim)
    embedder = SpyEmbedder(dim)
    if ledger is None:
        ledger = Ledger(tmp_path / "ledger", new_id=a3.deterministic_id_factory())
    doctrine_path = tmp_path / "vault" / "memory" / "DOCTRINE.md"
    if doctrine is not None:
        doctrine_path.parent.mkdir(parents=True, exist_ok=True)
        doctrine_path.write_text(doctrine, encoding="utf-8")
    scanner = Scanner(KNOWN_IDENTITIES)
    memory = Memory(store, embedder, ledger, scanner, doctrine_path,
                    weights=weights if weights is not None else RetrievalWeights())
    return SimpleNamespace(memory=memory, store=store, embedder=embedder, ledger=ledger,
                           scanner=scanner, vectors_dir=vectors_dir,
                           doctrine_path=doctrine_path, model=model, dim=dim)


# --- The independent ranking oracle (docs/55: property tests vs an oracle) ----------------


def _f32(vec: tuple[float, ...]) -> tuple[float, ...]:
    """Round-trip through float32 — exactly what LanceDB storage does to a vector."""
    return tuple(struct.unpack("f", struct.pack("f", v))[0] for v in vec)


def oracle_scores(task: TaskContext, lessons: list[Lesson], dim: int,
                  weights: RetrievalWeights) -> list[tuple[str, float]]:
    """Recompute the docs/33 score independently of ``charterhouse.memory.retrieval``:
    embed with a fresh ``FakeEmbedder`` (deterministic), apply the float32 store
    round-trip, then the weighted sum — returns [(lesson_id, score)] in the frozen
    order (score desc, lesson_id asc)."""
    emb = FakeEmbedder(dim)
    qv = emb.embed(task.text)  # the query vector is never stored — no f32 round-trip
    out: list[tuple[str, float]] = []
    for les in lessons:
        v = _f32(emb.embed(les.text))  # stored vectors ARE float32 (LanceDB)
        semantic = sum(a * b for a, b in zip(qv, v))
        tag_match = (len(set(task.tags) & set(les.tags)) / len(task.tags)
                     if task.tags else 0.0)
        age = max(0, task.active_time - les.created_active_time)
        recency = 0.5 ** (age / weights.half_life_active)
        segment_match = 1.0 if task.segment and les.segment == task.segment else 0.0
        score = (weights.w_semantic * semantic + weights.w_tag * tag_match
                 + weights.w_recency * recency + weights.w_confidence * les.confidence)
        if task.segment:
            score += weights.w_segment * segment_match
        out.append((les.lesson_id, score))
    out.sort(key=lambda pair: (-pair[1], pair[0]))
    return out


def seeded_corpus(seed: int, n: int = 12) -> list[Lesson]:
    """A deterministic, PII-free lesson corpus for the property test. Texts are plain
    factory prose (no names/emails/digit runs — the S7 scanner must stay quiet)."""
    rng = random.Random(seed)
    topics = ("onboarding flow", "pricing page copy", "cold channel choice",
              "battlecard cadence", "segment sizing", "scoring rubric",
              "landing page build", "evidence interviews")
    out: list[Lesson] = []
    for i in range(n):
        tags = tuple(sorted(rng.sample(TAG_VOCAB, rng.randint(1, 3))))
        out.append(Lesson(
            text=f"lesson {chr(ord('a') + i)}: improve the {rng.choice(topics)} "
                 f"before scaling it",
            source_ref=f"vault/lessons/seed-{chr(ord('a') + i)}.md",
            tags=tags,
            venture_id=rng.choice(("v-alpha", "v-beta", "v-gamma", None)),
            segment=rng.choice(SEGMENTS + (None,)),
            confidence=round(rng.uniform(0.1, 0.95), 2),
            created_active_time=rng.randint(0, 120),
            lesson_id=f"les-{chr(ord('a') + i)}{chr(ord('a') + i)}",
        ))
    return out
