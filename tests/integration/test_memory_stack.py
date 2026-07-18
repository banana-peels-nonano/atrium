"""S9 integration suite (memory/TESTPLAN.md) — the memory engine across its real seams:
S7 CHECKPOINT upstream (INV-MEM-4 joint), S4 Ledger events, real LanceDB store.

No network (INV-TEST-SAFE): FakeEmbedder spy, embedded LanceDB on tmp_path.
"""

from __future__ import annotations

import pytest

from charterhouse.contracts.events import Event, EventType
from charterhouse.memory import PIIEmbedBlocked, TaskContext
from charterhouse.security import Security

from tests.fixtures.pii_corpus import KNOWN_IDENTITIES, POSITIVES
from tests.unit import _a7_support as a7


def test_it_checkpoint_to_memory_pii_flow(tmp_path):
    """INV-MEM-4 (joint S7, docs/54 §S9): redaction happens UPSTREAM at CHECKPOINT —
    the redacted output embeds and retrieves; the raw text presented directly is
    refused with zero embedder calls."""
    email = POSITIVES[0][1]  # a corpus email, assembled at runtime
    raw = f"Interview follow-up: contact {email} about the pods pricing objection."
    security = Security(tmp_path / "vault", known_identities=KNOWN_IDENTITIES)
    checkpoint = security.checkpoint(raw, doc_id="lead-01")
    assert email not in checkpoint.clean  # S7 did its job upstream

    s = a7.make_memory(tmp_path)
    lid = s.memory.write_lesson(a7.lesson(
        checkpoint.clean, lesson_id="les-clean", tags=("pricing",),
        source_ref="vault/lessons/lead-01.md"))
    ws = s.memory.retrieve(TaskContext(text="pricing objection follow-up",
                                       tags=("pricing",)), k=3)
    assert lid in [r.lesson.lesson_id for r in ws.records]  # redacted → retrievable

    calls_before = s.embedder.calls
    with pytest.raises(PIIEmbedBlocked) as exc:
        s.memory.write_lesson(a7.lesson(raw))  # the raw text must never reach the embedder
    assert s.embedder.calls == calls_before
    assert email not in str(exc.value)
    assert {r["id"] for r in s.store.all_rows()} == {"les-clean"}


def test_it_kill_salvage_lesson_retrievable_at_next_gate(tmp_path):
    """docs/54 §S9 acceptance loop: kill → salvage → lesson → retrievable at the next
    gate — the dead venture's anti-pattern surfaces in a DIFFERENT venture's working
    memory, alongside the kill/salvage/lesson_written trail on the real ledger."""
    s = a7.make_memory(tmp_path)
    s.ledger.append(Event(type=EventType.KILL, actor="conductor", venture_id="v-dead",
                          payload={"reason": "no pull after two experiments"}))
    s.ledger.append(Event(type=EventType.SALVAGE, actor="conductor",
                          venture_id="v-dead",
                          payload={"asset_types": ["anti_pattern"]}))
    lid = s.memory.write_lesson(a7.lesson(
        "anti-pattern: cold enterprise outreach stalls pre-validation ventures",
        lesson_id="les-anti", tags=("channel", "anti_pattern"), venture_id="v-dead",
        confidence=0.8, created_active_time=10,
        source_ref="vault/lessons/v-dead-salvage.md"))

    # The NEXT venture's gate preparation retrieves working memory for its channel task.
    ws = s.memory.retrieve(TaskContext(
        text="choosing the outreach channel for the new venture",
        tags=("channel",), venture_id="v-new", active_time=25), k=3)
    assert lid in [r.lesson.lesson_id for r in ws.records]
    assert ws.doctrine == a7.DOCTRINE  # Doctrine rides along at the gate

    types = [e.type for e in s.ledger.read()]
    assert types == [EventType.KILL, EventType.SALVAGE, EventType.LESSON_WRITTEN]
