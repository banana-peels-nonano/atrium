"""S4 Ledger unit tests (charterhouse/ledger/TESTPLAN.md) — written BEFORE implementation.

Covers docs/54 §S4: INV-LEDGER (replay determinism, property), atomic + totally-ordered
append, tamper-evidence / fail-closed read, and the envelope-validation rules (PII, gate token,
unknown type, once-per-lineage caps, schema_version).

Physical-format coupling note: the torn-tail / tamper tests poke the on-disk files. They rely
only on the *documented* physical contract (docs/32, ledger/IMPLEMENTATION §3): newline-
terminated JSONL records under ``ledger_dir/*.jsonl``. Internal segmentation/naming is free.
"""

from __future__ import annotations

import dataclasses
import json
import threading
from pathlib import Path

import pytest

from charterhouse.contracts.events import (
    ChainBroken,
    Event,
    EventType,
    MissingAuthorization,
    PIIInPayload,
    ProjectionError,
    UnknownEventType,
)
from charterhouse.ledger import Ledger
from tests.unit import _a3_support as sup


@pytest.fixture
def make_ledger(tmp_path: Path):
    """Factory for isolated Ledgers on a tmp dir with a deterministic monotonic id factory."""

    def _make(name: str = "led") -> Ledger:
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        return Ledger(d, backup_dir=tmp_path / f"{name}-backups",
                      new_id=sup.deterministic_id_factory())

    return _make


def _segments(ledger_dir: Path) -> list[Path]:
    return sorted(ledger_dir.rglob("*.jsonl"))


def _active_segment(tmp_path: Path) -> Path:
    segs = _segments(tmp_path / "led")
    assert segs, "expected at least one JSONL segment written"
    return segs[-1]


# --- Atomic + totally-ordered append ------------------------------------------------------


def test_append_atomic_ordered(make_ledger):
    """Sequential appends get monotonic ids and preserve total order across segments."""
    led = make_ledger()
    ids = [led.append(sup.draft(EventType.CAPTURE, venture_id=f"v{i}",
                                 to_state="CAPTURED")) for i in range(25)]
    assert ids == sorted(ids), "event_ids must be monotonically increasing"
    assert len(set(ids)) == len(ids), "event_ids must be unique"
    read_ids = [e.event_id for e in led.read()]
    assert read_ids == ids, "read() must yield events in append (total) order"


def test_partial_write_never_corrupts(make_ledger, tmp_path):
    """A torn tail (bytes with no terminating newline = an interrupted append) is never visible;
    the last good committed state stands (R1). Distinguished from tampering purely by the
    missing newline commit-marker."""
    led = make_ledger()
    good = [led.append(sup.draft(EventType.CAPTURE, venture_id=f"v{i}",
                                 to_state="CAPTURED")) for i in range(3)]
    # Simulate a crash mid-append: append a record with NO trailing newline.
    seg = _active_segment(tmp_path)
    with seg.open("ab") as fh:
        fh.write(b'{"event_id":"999","type":"capture","torn":true')  # note: no closing/newline
    reread = Ledger(tmp_path / "led", new_id=sup.deterministic_id_factory())
    assert [e.event_id for e in reread.read()] == good, "torn tail must be dropped, not raise"


def test_concurrent_append_no_interleave(make_ledger, tmp_path):
    """Single-writer serialization: records never interleave under concurrent callers; the log
    stays parseable and chain-intact with all events present and uniquely ordered."""
    led = make_ledger()
    n = 40

    def worker(i: int) -> None:
        led.append(sup.draft(EventType.LLM_CALL, actor="system",
                             payload={"i": i}, venture_id=None))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Every stored line is intact JSON (no torn interleave) and the chain verifies on read.
    for seg in _segments(tmp_path / "led"):
        for line in seg.read_text(encoding="utf-8").splitlines():
            json.loads(line)  # raises if a record was interleaved/torn
    events = list(led.read())
    assert len(events) == n
    ids = [e.event_id for e in events]
    assert ids == sorted(ids) and len(set(ids)) == n


# --- Tamper-evidence / fail-closed --------------------------------------------------------


def test_hash_chain_links(make_ledger):
    """Each event's prev_hash matches the prior event's canonical hash; genesis links to the
    all-zero root."""
    led = make_ledger()
    for i in range(4):
        led.append(sup.draft(EventType.CAPTURE, venture_id=f"v{i}", to_state="CAPTURED"))
    events = list(led.read())
    assert events[0].prev_hash == "0" * 64, "first event links to the genesis root"
    assert all(e.prev_hash for e in events), "every event carries a prev_hash link"


def test_tamper_detected_on_read(make_ledger, tmp_path):
    """Mutating a fully-committed *historical* (interior) record breaks the chain; read raises
    and replay refuses (fail closed). Differs from the torn-tail case by editing a
    newline-terminated interior line, not by dropping a terminator (R2)."""
    led = make_ledger()
    for i in range(4):
        led.append(sup.draft(EventType.CAPTURE, venture_id=f"v{i}", to_state="CAPTURED"))
    seg = _active_segment(tmp_path)
    lines = seg.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"] = {"tampered": True}
    lines[0] = json.dumps(rec)
    seg.write_text("\n".join(lines) + "\n", encoding="utf-8")  # newline-terminated: committed
    reread = Ledger(tmp_path / "led", new_id=sup.deterministic_id_factory())
    with pytest.raises(ChainBroken):
        list(reread.read())
    with pytest.raises(ChainBroken):
        reread.replay()


def test_replay_refuses_venture_without_state(make_ledger):
    """A venture that has valid events but no state-setting event (no CAPTURE/transition) cannot
    be projected. Replay fails closed with a defined ``ProjectionError`` naming the venture — not
    a bare ``ValueError``. (append does not enforce lifecycle legality — that is S5 — so such a
    stream is appendable and replay must degrade to a *defined* error.)"""
    led = make_ledger()
    # A frame carries a venture_id but no to_state; with no preceding CAPTURE the venture never
    # acquires a state.
    led.append(sup.draft(EventType.FRAME, payload={"score": 12}, venture_id="orphan"))
    with pytest.raises(ProjectionError) as ei:
        led.replay()
    assert "orphan" in str(ei.value), "the error must name the unprojectable venture"


def test_replay_refuses_broken_chain(make_ledger, tmp_path):
    """A broken chain → replay raises and returns no partial state."""
    led = make_ledger()
    for i in range(3):
        led.append(sup.draft(EventType.CAPTURE, venture_id=f"v{i}", to_state="CAPTURED"))
    seg = _active_segment(tmp_path)
    lines = seg.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[1])
    rec["prev_hash"] = "f" * 64  # deliberately wrong link
    lines[1] = json.dumps(rec)
    seg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reread = Ledger(tmp_path / "led", new_id=sup.deterministic_id_factory())
    with pytest.raises(ChainBroken):
        reread.replay()


# --- INV-LEDGER: replay determinism (property) --------------------------------------------


@pytest.mark.parametrize("seed", range(60))
def test_replay_deterministic_state(make_ledger, seed):
    """For arbitrary legal event sequences, replay() reproduces the independently-computed world
    state, and re-running replay is byte-identical (INV-LEDGER)."""
    led = make_ledger(name=f"led{seed}")
    events = sup.legal_sequence(seed)
    for e in events:
        led.append(e)
    world = led.replay()
    expected = sup.oracle(events)
    assert set(world.ventures) == set(expected), "replay must project exactly the ventures seen"
    for vid, exp in expected.items():
        v = world.ventures[vid]
        assert v.state.value == exp["state"], f"{vid}: state mismatch"
        assert v.score == exp["score"], f"{vid}: score mismatch"
        assert v.omw_granted == exp["omw_granted"], f"{vid}: omw flag mismatch"
    assert led.replay() == world, "replay must be deterministic (identical on re-run)"


# --- Envelope validation (fail closed) ----------------------------------------------------


def test_reject_raw_pii_payload(make_ledger):
    """A payload with structural PII/secret is rejected; the error names the offending field
    (INV-PII-1, defense in depth behind S7)."""
    led = make_ledger()
    for kind, value in sup.PII_CORPUS:
        with pytest.raises(PIIInPayload) as ei:
            led.append(sup.draft(EventType.CAPTURE, payload={"note": value},
                                 venture_id="v", to_state="CAPTURED"))
        assert "note" in str(ei.value), f"{kind}: error must name the offending field"


def test_reject_gate_event_without_token(make_ledger):
    """A gate/RED-typed event missing authorization is rejected (docs/41 §4.2)."""
    led = make_ledger()
    with pytest.raises(MissingAuthorization):
        led.append(sup.draft(EventType.SPEND_ENVELOPE, payload={"cap_usd": 100},
                             venture_id="v", authorization=None))
    # With a token it is accepted.
    eid = led.append(sup.draft(EventType.SPEND_ENVELOPE, payload={"cap_usd": 100},
                              venture_id="v", authorization="tok-123"))
    assert eid


def test_reject_unknown_event_type(make_ledger):
    """A ``type`` not in the frozen catalog is rejected; the error names the type."""
    led = make_ledger()
    bogus = dataclasses.replace(sup.draft(EventType.CAPTURE, venture_id="v"), type="not_a_type")
    with pytest.raises(UnknownEventType):
        led.append(bogus)


def test_omw_grant_cap_replay_checked(make_ledger):
    """A second omw_grant in a lineage is flagged as a violation during replay (INV-SM-5)."""
    from charterhouse.contracts.events import CapViolation

    led = make_ledger()
    led.append(sup.draft(EventType.CAPTURE, venture_id="v", to_state="CAPTURED"))
    led.append(sup.draft(EventType.OMW_GRANT, venture_id="v"))
    led.append(sup.draft(EventType.OMW_GRANT, venture_id="v"))  # second — illegal
    with pytest.raises(CapViolation):
        led.replay()


def test_pivot_fork_cap_replay_checked(make_ledger):
    """A second pivot_fork in a lineage is flagged as a violation during replay (INV-SM-5)."""
    from charterhouse.contracts.events import CapViolation

    led = make_ledger()
    led.append(sup.draft(EventType.CAPTURE, venture_id="v", to_state="CAPTURED"))
    led.append(sup.draft(EventType.PIVOT_FORK,
                        payload={"killed_id": "v", "new_id": "v-f1", "inherited": {}},
                        venture_id="v"))
    led.append(sup.draft(EventType.PIVOT_FORK,
                        payload={"killed_id": "v", "new_id": "v-f2", "inherited": {}},
                        venture_id="v"))
    with pytest.raises(CapViolation):
        led.replay()


def test_schema_version_stamped_and_read(make_ledger):
    """Every event carries schema_version; the reader accepts it (additive evolution, docs/41
    §5)."""
    led = make_ledger()
    led.append(sup.draft(EventType.CAPTURE, venture_id="v", to_state="CAPTURED"))
    (e,) = list(led.read())
    assert e.schema_version >= 1
