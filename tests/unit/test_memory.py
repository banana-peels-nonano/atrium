"""S9 Memory unit suite (memory/TESTPLAN.md) — INV-MEM-1..4.

Real LanceDB store on tmp_path, real tmp-path Ledger (A3 convention), merged S7
``Scanner`` (no fake security), A11 ``FakeEmbedder`` behind a counting spy. No network
anywhere (INV-TEST-SAFE).
"""

from __future__ import annotations

import pytest

from charterhouse.contracts.events import EventType
from charterhouse.memory import (
    EMBED_MARKER,
    EmbedFailed,
    EmbedModelMismatch,
    Lesson,
    LessonInvalid,
    Memory,
    MemoryStore,
    OllamaEmbedder,
    PIIEmbedBlocked,
    RetrievalWeights,
    ScopeViolation,
    TaskContext,
    UnguardedReindex,
)
from tests.fixtures.pii_corpus import NEGATIVES, POSITIVES
from tests.unit import _a7_support as a7


def _events(ledger) -> list:
    return list(ledger.read())


# --- INV-MEM-1: top-K only · Doctrine always · retired/superseded excluded ----------------


def test_retrieve_topk_only_never_full_store(tmp_path):
    """INV-MEM-1: retrieval returns top-K only — k caps the records, an absurd k is
    clamped to ``weights.max_k``, and the full store is never handed out."""
    s = a7.make_memory(tmp_path, weights=RetrievalWeights(max_k=16))
    for i in range(25):
        s.memory.write_lesson(a7.lesson(
            f"lesson row {chr(ord('a') + i)} about the weekly build cadence",
            lesson_id=f"les-{chr(ord('a') + i)}", source_ref=f"vault/lessons/{i}.md"))
    task = TaskContext(text="what should the weekly build cadence be", active_time=10)
    assert len(s.memory.retrieve(task, k=5).records) == 5
    assert len(s.memory.retrieve(task, k=0).records) == 0
    clamped = s.memory.retrieve(task, k=1000)
    assert len(clamped.records) == 16 < s.store.count()


def test_retrieve_doctrine_always_included(tmp_path):
    """INV-MEM-1: Doctrine is ALWAYS in the WorkingSet — with hits, with an empty
    store, and with k=0."""
    s = a7.make_memory(tmp_path)
    task = TaskContext(text="pricing question")
    assert s.memory.retrieve(task, k=3).doctrine == a7.DOCTRINE  # empty store
    assert s.memory.retrieve(task, k=0).doctrine == a7.DOCTRINE  # k=0
    s.memory.write_lesson(a7.lesson("price anchoring beats discounting"))
    ws = s.memory.retrieve(task, k=3)
    assert ws.doctrine == a7.DOCTRINE and len(ws.records) == 1  # with hits


def test_retrieve_missing_doctrine_is_empty_not_error(tmp_path):
    """INV-MEM-1 edge: no DOCTRINE.md is the legitimate pre-doctrine factory state —
    doctrine == "" and retrieval still works (IMPLEMENTATION §6.2)."""
    s = a7.make_memory(tmp_path, doctrine=None)
    s.memory.write_lesson(a7.lesson("first ever lesson"))
    ws = s.memory.retrieve(TaskContext(text="first ever lesson"), k=2)
    assert ws.doctrine == "" and len(ws.records) == 1


def test_retrieve_excludes_retired_and_superseded(tmp_path):
    """INV-MEM-1: retired/superseded rows never surface — even when they are the
    semantically closest match (filtered BEFORE ranking, not after)."""
    s = a7.make_memory(tmp_path)
    query = "the exact channel playbook for smb outreach"
    s.memory.write_lesson(a7.lesson(query, lesson_id="les-retired"))       # identical text
    s.memory.write_lesson(a7.lesson(query, lesson_id="les-superseded"))   # identical text
    s.memory.write_lesson(a7.lesson("an unrelated note on scoring rubrics",
                                    lesson_id="les-active"))
    s.store.set_status("les-retired", "retired")
    s.store.set_status("les-superseded", "superseded")
    ws = s.memory.retrieve(TaskContext(text=query), k=10)
    ids = [r.lesson.lesson_id for r in ws.records]
    assert ids == ["les-active"]


@pytest.mark.parametrize("seed", range(20))
def test_ranking_matches_independent_oracle_property(tmp_path, seed):
    """INV-MEM-1 ranking (property): result order == an independent oracle recomputation
    of w1·sem + w2·tag + w3·rec + w4·conf (+ w5·seg) over 20 seeded corpora."""
    import random
    weights = RetrievalWeights()
    s = a7.make_memory(tmp_path / f"s{seed}", weights=weights)
    corpus = a7.seeded_corpus(seed)
    for les in corpus:
        s.memory.write_lesson(les)
    rng = random.Random(1000 + seed)
    task = TaskContext(
        text=f"how should we approach the {rng.choice(('pricing', 'channel', 'build'))} "
             f"work next week",
        tags=tuple(sorted(rng.sample(a7.TAG_VOCAB, rng.randint(0, 2)))),
        segment=rng.choice(a7.SEGMENTS + (None,)),
        active_time=120)
    ws = s.memory.retrieve(task, k=5)
    expected = a7.oracle_scores(task, corpus, a7.DIM, weights)[:5]
    assert [r.lesson.lesson_id for r in ws.records] == [eid for eid, _ in expected]
    for got, (_, want_score) in zip(ws.records, expected):
        assert got.score == pytest.approx(want_score, abs=1e-9)


def test_ranking_component_semantics(tmp_path):
    """Ranking components behave per docs/33: tag overlap boosts, age decays via the
    half-life, confidence separates ties, segment_match applies only with a task
    segment; ``ScoredLesson.components`` exposes every term."""
    text = "identical semantic text for component isolation"
    # tag boost
    s = a7.make_memory(tmp_path / "tags")
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-tagged", tags=("pricing",)))
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-untagged", tags=()))
    ws = s.memory.retrieve(TaskContext(text=text, tags=("pricing",)), k=2)
    assert [r.lesson.lesson_id for r in ws.records] == ["les-tagged", "les-untagged"]
    assert ws.records[0].components.tag_match == 1.0
    assert ws.records[1].components.tag_match == 0.0
    # recency decay (factory active-time, never wall clock)
    s = a7.make_memory(tmp_path / "recency")
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-new", created_active_time=100))
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-old", created_active_time=0))
    ws = s.memory.retrieve(TaskContext(text=text, active_time=100), k=2)
    assert [r.lesson.lesson_id for r in ws.records] == ["les-new", "les-old"]
    assert ws.records[0].components.recency == pytest.approx(1.0)
    assert ws.records[1].components.recency == pytest.approx(0.5 ** (100 / 30.0))
    # confidence separates otherwise-equal rows
    s = a7.make_memory(tmp_path / "conf")
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-sure", confidence=0.9))
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-shaky", confidence=0.4))
    ws = s.memory.retrieve(TaskContext(text=text), k=2)
    assert [r.lesson.lesson_id for r in ws.records] == ["les-sure", "les-shaky"]
    # segment match only when the task has a segment
    s = a7.make_memory(tmp_path / "segment")
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-smb", segment="smb"))
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-dev", segment="dev"))
    ws = s.memory.retrieve(TaskContext(text=text, segment="smb"), k=2)
    assert [r.lesson.lesson_id for r in ws.records] == ["les-smb", "les-dev"]
    assert ws.records[0].components.segment_match == 1.0
    no_seg = s.memory.retrieve(TaskContext(text=text), k=2)
    assert all(r.components.segment_match == 0.0 for r in no_seg.records)


def test_ranking_deterministic_tiebreak(tmp_path):
    """Determinism: equal scores order by lesson_id asc; the identical call returns the
    identical WorkingSet."""
    s = a7.make_memory(tmp_path)
    text = "byte-identical lesson content"
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-bb"))
    s.memory.write_lesson(a7.lesson(text, lesson_id="les-aa"))
    task = TaskContext(text=text)
    first = s.memory.retrieve(task, k=2)
    assert [r.lesson.lesson_id for r in first.records] == ["les-aa", "les-bb"]
    assert s.memory.retrieve(task, k=2) == first


# --- write path: round trip, events, validation, INV-MEM-4 --------------------------------


def test_write_lesson_roundtrip_retrievable(tmp_path):
    """docs/54 §S9 embed→store→retrieve round trip; the row carries the docs/33 schema
    incl. the embed_model pin."""
    s = a7.make_memory(tmp_path)
    lid = s.memory.write_lesson(a7.lesson(
        "design partners convert best from warm referrals", lesson_id="les-warm",
        tags=("channel",), venture_id="v-alpha", confidence=0.8))
    assert lid == "les-warm"
    ws = s.memory.retrieve(
        TaskContext(text="design partners convert best from warm referrals"), k=1)
    assert ws.records[0].lesson.lesson_id == "les-warm"
    assert ws.records[0].lesson.text.startswith("design partners")
    (row,) = s.store.all_rows()
    assert row["embed_model"] == a7.MODEL_A
    assert len(row["vector"]) == a7.DIM
    assert row["status"] == "active" and row["kind"] == "lesson"


def test_write_lesson_assigns_id_when_blank(tmp_path):
    """A blank lesson_id gets a store-assigned id (returned, non-empty, retrievable)."""
    s = a7.make_memory(tmp_path)
    lid = s.memory.write_lesson(a7.lesson("assigned id lesson"))
    assert isinstance(lid, str) and lid
    assert s.store.all_rows()[0]["id"] == lid


def test_write_lesson_appends_lesson_written_event(tmp_path):
    """docs/41 §2: exactly one lesson_written{lesson_id, tags, confidence} per write,
    venture-scoped in the envelope."""
    s = a7.make_memory(tmp_path)
    lid = s.memory.write_lesson(a7.lesson(
        "one write one event", lesson_id="les-evt", tags=("scoring",),
        venture_id="v-alpha", confidence=0.7))
    events = _events(s.ledger)
    assert len(events) == 1
    (evt,) = events
    assert evt.type is EventType.LESSON_WRITTEN
    assert evt.venture_id == "v-alpha"
    assert evt.payload == {"lesson_id": lid, "tags": ["scoring"], "confidence": 0.7}


@pytest.mark.parametrize("field,bad", [
    ("kind", "poem"),
    ("status", "zombie"),
    ("confidence", 1.5),
    ("confidence", -0.1),
    ("text", ""),
    ("source_ref", ""),
])
def test_write_lesson_invalid_shapes_refused(tmp_path, field, bad):
    """Fail closed: a docs/33 shape violation → LessonInvalid naming the field; store
    and ledger untouched."""
    s = a7.make_memory(tmp_path)
    base = a7.lesson("a perfectly valid lesson body")
    from dataclasses import replace
    with pytest.raises(LessonInvalid, match=field):
        s.memory.write_lesson(replace(base, **{field: bad}))
    assert s.store.count() == 0
    assert _events(s.ledger) == []


@pytest.mark.parametrize("kind,value", POSITIVES)
def test_write_lesson_pii_blocked_before_embed(tmp_path, kind, value):
    """INV-MEM-4: every corpus positive is refused with PIIEmbedBlocked BEFORE any
    embedding — zero embedder calls, zero rows, zero ledger appends; the message names
    the finding kind, never the value."""
    s = a7.make_memory(tmp_path)
    with pytest.raises(PIIEmbedBlocked) as exc:
        s.memory.write_lesson(a7.lesson(f"note from the call: {value} — follow up"))
    assert s.embedder.calls == 0
    assert s.store.count() == 0
    assert _events(s.ledger) == []
    assert kind in str(exc.value)
    assert value not in str(exc.value)


@pytest.mark.parametrize("clean", NEGATIVES)
def test_write_lesson_clean_text_accepted(tmp_path, clean):
    """INV-MEM-4 complement (precision guard): ordinary factory content embeds and
    stores — memory must not dead-lock on clean text."""
    s = a7.make_memory(tmp_path)
    lid = s.memory.write_lesson(a7.lesson(clean))
    assert s.store.count() == 1
    assert s.store.all_rows()[0]["id"] == lid


def test_write_lesson_scope_seam(tmp_path):
    """Additive scope seam (docs/54 §S11 boundary): a supplied capability scope must
    cover the lesson's tags; None = trusted Conductor path."""
    s = a7.make_memory(tmp_path)
    ok = a7.lesson("pricing ladder works", lesson_id="les-in", tags=("pricing",))
    s.memory.write_lesson(ok, scope=("pricing", "build"))
    out = a7.lesson("channel note", lesson_id="les-out", tags=("channel",))
    with pytest.raises(ScopeViolation):
        s.memory.write_lesson(out, scope=("pricing", "build"))
    s.memory.write_lesson(out, scope=None)
    assert {r["id"] for r in s.store.all_rows()} == {"les-in", "les-out"}


def test_write_lesson_rollback_on_append_failure(tmp_path):
    """RISKS R10: a failed lesson_written append propagates AND rolls the row back —
    no vector exists without its ledger event."""
    failing = a7.FailingAppendLedger(tmp_path / "ledger")
    s = a7.make_memory(tmp_path, ledger=failing)
    with pytest.raises(RuntimeError, match="R10 probe"):
        s.memory.write_lesson(a7.lesson("this row must not survive"))
    assert s.store.count() == 0


# --- INV-MEM-2: pin, mismatch refusal, guarded reindex -------------------------------------


def test_store_records_pin_and_marker(tmp_path):
    """INV-MEM-2: a fresh store writes the EMBED_MODEL marker (the file A1's preflight
    Check 4 reads) and stamps every row with the pinned model id."""
    s = a7.make_memory(tmp_path)
    marker = s.vectors_dir / EMBED_MARKER
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8").strip() == a7.MODEL_A
    s.memory.write_lesson(a7.lesson("pin stamped on the row"))
    assert s.store.all_rows()[0]["embed_model"] == a7.MODEL_A
    assert s.store.embed_model == a7.MODEL_A


def test_open_with_changed_model_refused(tmp_path):
    """INV-MEM-2: reopening under a different configured model refuses with the reused
    S2 EmbedModelMismatch — never a silent rebuild; rows untouched."""
    s = a7.make_memory(tmp_path)
    s.memory.write_lesson(a7.lesson("existing knowledge", lesson_id="les-keep"))
    with pytest.raises(EmbedModelMismatch, match=a7.MODEL_A):
        MemoryStore.open(s.vectors_dir, a7.MODEL_B, a7.DIM)
    again = MemoryStore.open(s.vectors_dir, a7.MODEL_A, a7.DIM)
    assert [r["id"] for r in again.all_rows()] == ["les-keep"]


def test_reindex_requires_reason(tmp_path):
    """INV-MEM-2 guard: a blank/whitespace reason → UnguardedReindex; nothing changes."""
    s = a7.make_memory(tmp_path)
    s.memory.write_lesson(a7.lesson("stable row"))
    before = s.store.all_rows()
    for blank in ("", "   "):
        with pytest.raises(UnguardedReindex):
            s.memory.reindex(blank)
    assert s.store.all_rows() == before
    assert (s.vectors_dir / EMBED_MARKER).read_text(
        encoding="utf-8").strip() == a7.MODEL_A


def test_reindex_updates_pin_and_reembeds(tmp_path):
    """INV-MEM-2: the guarded reindex is the ONLY pin-change path — marker + every
    row's embed_model update, vectors are recomputed at the new dim, and the old model
    is refused afterwards."""
    s = a7.make_memory(tmp_path)
    s.memory.write_lesson(a7.lesson("survives the model change", lesson_id="les-1"))
    s.memory.write_lesson(a7.lesson("also survives", lesson_id="les-2"))
    new_dim = 16
    store_b = MemoryStore.open_for_reindex(s.vectors_dir, a7.MODEL_B, new_dim)
    memory_b = Memory(store_b, a7.SpyEmbedder(new_dim), s.ledger, s.scanner,
                      s.doctrine_path)
    memory_b.reindex("embed model change fake-embed-v1 -> fake-embed-v2 (founder run)")
    assert (s.vectors_dir / EMBED_MARKER).read_text(
        encoding="utf-8").strip() == a7.MODEL_B
    rows = MemoryStore.open(s.vectors_dir, a7.MODEL_B, new_dim).all_rows()
    assert {r["id"] for r in rows} == {"les-1", "les-2"}
    assert all(r["embed_model"] == a7.MODEL_B for r in rows)
    assert all(len(r["vector"]) == new_dim for r in rows)
    with pytest.raises(EmbedModelMismatch):
        MemoryStore.open(s.vectors_dir, a7.MODEL_A, a7.DIM)


def test_reindex_deterministic(tmp_path):
    """docs/54 §S9 reindex determinism: two reindex passes with the same embedder yield
    the identical row set (ids, vectors, pins)."""
    s = a7.make_memory(tmp_path)
    for i in range(3):
        s.memory.write_lesson(a7.lesson(f"deterministic row {chr(ord('a') + i)}",
                                        lesson_id=f"les-{chr(ord('a') + i)}"))
    s.memory.reindex("first deterministic pass")
    first = sorted(s.store.all_rows(), key=lambda r: r["id"])
    s.memory.reindex("second deterministic pass")
    second = sorted(s.store.all_rows(), key=lambda r: r["id"])
    assert first == second


# --- INV-MEM-3: consolidation — reversible view, ledger never edited -----------------------


def test_consolidate_merges_duplicates(tmp_path):
    """INV-MEM-3: near-identical lessons (same kind) merge — highest confidence stays
    active, the rest are marked superseded (a status flip, never a delete)."""
    s = a7.make_memory(tmp_path)
    dup = "pricing page: annual toggle lifts conversion"
    s.memory.write_lesson(a7.lesson(dup, lesson_id="les-high", confidence=0.9))
    s.memory.write_lesson(a7.lesson(dup, lesson_id="les-low", confidence=0.5))
    s.memory.write_lesson(a7.lesson("unrelated scoring note", lesson_id="les-other"))
    report = s.memory.consolidate()
    assert report.merged == (("les-low", "les-high"),)
    rows = {r["id"]: r for r in s.store.all_rows()}
    assert rows["les-high"]["status"] == "active"
    assert rows["les-low"]["status"] == "superseded"
    assert rows["les-other"]["status"] == "active"
    assert len(rows) == 3  # nothing deleted


def test_consolidate_retires_low_confidence(tmp_path):
    """INV-MEM-3: active lessons under retire_below are retired; the rest stay."""
    s = a7.make_memory(tmp_path, weights=RetrievalWeights(retire_below=0.2))
    s.memory.write_lesson(a7.lesson("weak hunch about edu segment",
                                    lesson_id="les-weak", confidence=0.1))
    s.memory.write_lesson(a7.lesson("solid channel evidence",
                                    lesson_id="les-solid", confidence=0.6))
    report = s.memory.consolidate()
    assert report.retired == ("les-weak",)
    rows = {r["id"]: r for r in s.store.all_rows()}
    assert rows["les-weak"]["status"] == "retired"
    assert rows["les-solid"]["status"] == "active"


def test_consolidate_promotes_recurring_to_playbook(tmp_path):
    """INV-MEM-3 promotion: a tag spanning >= promote_min_ventures distinct ventures
    yields exactly ONE deterministic playbook row (no LLM); doctrine is proposals-only;
    a second pass is idempotent."""
    s = a7.make_memory(tmp_path, weights=RetrievalWeights(promote_min_ventures=3))
    for i, vid in enumerate(("v-alpha", "v-beta", "v-gamma")):
        s.memory.write_lesson(a7.lesson(
            f"pricing recurrence {chr(ord('a') + i)} from {vid}",
            lesson_id=f"les-{chr(ord('a') + i)}", tags=("pricing",), venture_id=vid,
            confidence=0.7))
    doctrine_before = s.doctrine_path.read_text(encoding="utf-8")
    report = s.memory.consolidate()
    assert len(report.promoted) == 1
    playbooks = [r for r in s.store.all_rows() if r["kind"] == "playbook"]
    assert len(playbooks) == 1
    (pb,) = playbooks
    assert pb["id"] == report.promoted[0]
    assert list(pb["tags"]) == ["pricing"] and pb["status"] == "active"
    assert report.doctrine_proposals  # proposals returned...
    assert s.doctrine_path.read_text(encoding="utf-8") == doctrine_before  # ...never written
    second = s.memory.consolidate()  # idempotent: no re-promotion
    assert second.promoted == ()
    assert len([r for r in s.store.all_rows() if r["kind"] == "playbook"]) == 1


def test_consolidate_never_edits_ledger(tmp_path):
    """INV-MEM-3: the ledger is NEVER edited — every pre-pass byte survives verbatim
    (append-only growth) and the pass adds exactly one consolidate event."""
    s = a7.make_memory(tmp_path)
    dup = "duplicate insight to be merged"
    s.memory.write_lesson(a7.lesson(dup, lesson_id="les-x", confidence=0.9))
    s.memory.write_lesson(a7.lesson(dup, lesson_id="les-y", confidence=0.4))
    ledger_files = {p: p.read_bytes()
                    for p in (tmp_path / "ledger").rglob("*") if p.is_file()}
    n_before = len(_events(s.ledger))
    s.memory.consolidate()
    for path, old in ledger_files.items():
        assert path.read_bytes().startswith(old)  # append-only, byte-identical prefix
    events = _events(s.ledger)
    assert len(events) == n_before + 1
    assert events[-1].type is EventType.CONSOLIDATE
    assert set(events[-1].payload) == {"merged", "retired", "promoted"}


def test_consolidate_reversible_from_ledger(tmp_path):
    """INV-MEM-3 reversibility: the pre-consolidation lesson set survives — every
    lesson_written event is intact and every original row keeps its text in the store
    (status flips are the ONLY mutation; the ledger replays the true history)."""
    s = a7.make_memory(tmp_path)
    originals = {}
    dup = "the same lesson learned twice"
    for lid, conf in (("les-p", 0.8), ("les-q", 0.3)):
        s.memory.write_lesson(a7.lesson(dup, lesson_id=lid, confidence=conf))
        originals[lid] = dup
    s.memory.write_lesson(a7.lesson("weak one", lesson_id="les-r", confidence=0.05))
    originals["les-r"] = "weak one"
    s.memory.consolidate()
    written_ids = {e.payload["lesson_id"] for e in _events(s.ledger)
                   if e.type is EventType.LESSON_WRITTEN}
    assert written_ids == set(originals)  # the truth survives in the ledger
    rows = {r["id"]: r for r in s.store.all_rows()}
    for lid, text in originals.items():
        assert rows[lid]["text"] == text  # view flipped status, never content


# --- INV-MEM-4 locality: the local embedder ------------------------------------------------


def test_ollama_embedder_local_shape(tmp_path):
    """INV-MEM-4 locality: OllamaEmbedder posts {model, prompt} to the injected local
    transport and returns the vector; failures → EmbedFailed; and S9's embeddings
    module surface contains NO cloud embedder."""
    calls: list[tuple[str, dict]] = []

    def transport(url: str, body: dict) -> dict:
        calls.append((url, body))
        return {"embedding": [0.1] * 8}

    emb = OllamaEmbedder("http://127.0.0.1:11434", "nomic-embed-text", 8,
                         transport=transport)
    vec = emb.embed("hello factory")
    assert vec == tuple([0.1] * 8) and emb.dim == 8
    (url, body), = calls
    assert url.startswith("http://127.0.0.1:11434")
    assert body == {"model": "nomic-embed-text", "prompt": "hello factory"}

    def broken(url: str, body: dict) -> dict:
        raise OSError("endpoint down")

    with pytest.raises(EmbedFailed):
        OllamaEmbedder("http://127.0.0.1:11434", "nomic-embed-text", 8,
                       transport=broken).embed("x")

    def wrong_dim(url: str, body: dict) -> dict:
        return {"embedding": [0.1] * 4}

    with pytest.raises(EmbedFailed):
        OllamaEmbedder("http://127.0.0.1:11434", "nomic-embed-text", 8,
                       transport=wrong_dim).embed("x")

    from charterhouse.memory import embeddings as module
    assert module.__all__ == ["Embeddings", "OllamaEmbedder", "EmbedFailed"]
