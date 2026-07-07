"""S4 Registry unit tests (charterhouse/registry/TESTPLAN.md) — written BEFORE implementation.

Per the plan, the Registry is exercised against a REAL Ledger on a tmp dir (not the A11
InMemoryLedger fake, which is not built yet) — more faithful to INV-LEDGER and free of the A11
dependency.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charterhouse.contracts.events import ChainBroken, EventType
from charterhouse.contracts.state import State
from charterhouse.ledger import Ledger
from charterhouse.registry import Registry
from tests.unit import _a3_support as sup


@pytest.fixture
def make_ledger(tmp_path: Path):
    def _make(name: str = "led") -> Ledger:
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        return Ledger(d, backup_dir=tmp_path / f"{name}-backups",
                      new_id=sup.deterministic_id_factory())

    return _make


def _seed_three(led: Ledger) -> None:
    """Two VALIDATING ventures and one KILLED, via legal transitions."""
    for vid in ("a", "b"):
        led.append(sup.draft(EventType.CAPTURE, payload={"codename": vid},
                            venture_id=vid, to_state=State.CAPTURED))
        led.append(sup.draft(EventType.TRANSITION, venture_id=vid,
                            from_state=State.CAPTURED, to_state=State.FRAMED))
        led.append(sup.draft(EventType.TRANSITION, venture_id=vid,
                            from_state=State.FRAMED, to_state=State.VALIDATING))
    led.append(sup.draft(EventType.CAPTURE, payload={"codename": "c"},
                        venture_id="c", to_state=State.CAPTURED))
    led.append(sup.draft(EventType.TRANSITION, venture_id="c",
                        from_state=State.CAPTURED, to_state=State.KILLED))


@pytest.mark.parametrize("seed", range(40))
def test_registry_equals_replay(make_ledger, seed):
    """INV-LEDGER: get/query results equal what Ledger.replay() projects for the same events."""
    led = make_ledger(name=f"led{seed}")
    events = sup.legal_sequence(seed)
    for e in events:
        led.append(e)
    reg = Registry(led)
    world = led.replay()
    for vid, v in world.ventures.items():
        assert reg.get(vid) == v
    assert {v.id for v in reg.query()} == set(world.ventures)


def test_get_unknown_returns_none(make_ledger):
    reg = Registry(make_ledger())
    assert reg.get("no-such-venture") is None


def test_query_by_state_filters(make_ledger):
    led = make_ledger()
    _seed_three(led)
    reg = Registry(led)
    validating = reg.query(State.VALIDATING)
    assert {v.id for v in validating} == {"a", "b"}
    assert [v.id for v in validating] == sorted(v.id for v in validating), "order deterministic"
    assert {v.id for v in reg.query(State.KILLED)} == {"c"}


def test_query_all_when_no_filter(make_ledger):
    led = make_ledger()
    _seed_three(led)
    assert {v.id for v in Registry(led).query()} == {"a", "b", "c"}


def test_venture_record_shape(make_ledger):
    """Projected records carry the docs/42 §6 fields."""
    led = make_ledger()
    _seed_three(led)
    v = Registry(led).get("a")
    assert v is not None
    for fld in ("id", "codename", "state", "score", "forked_from", "state_entered_at",
                "experiment_live_at", "active_time_accum", "omw_granted", "evidence_ttl_at",
                "artifact_links", "event_stream_ptr"):
        assert hasattr(v, fld), f"venture record missing field: {fld}"


def test_projection_only_no_mutation(make_ledger):
    """The Registry exposes no state-changing method — only get/query reads (projection-only)."""
    reg = Registry(make_ledger())
    public = {n for n in dir(reg) if not n.startswith("_")}
    assert public == {"get", "query"}, f"unexpected public surface: {public}"


def test_cache_rebuilds_from_replay(make_ledger):
    """A derived index is byte-reproducible from replay(): a second query after more events
    reflects them (the accelerator never serves stale/independent truth)."""
    led = make_ledger()
    _seed_three(led)
    reg = Registry(led)
    assert reg.get("c").state == State.KILLED
    led.append(sup.draft(EventType.TRANSITION, venture_id="c",
                        from_state=State.KILLED, to_state=State.ARCHIVED))
    assert reg.get("c").state == State.ARCHIVED, "query must reflect newly appended events"


def test_chain_break_fails_closed(make_ledger, tmp_path):
    """A Ledger chain break during projection surfaces the error; no stale/guessed state."""
    led = make_ledger()
    _seed_three(led)
    seg = sorted((tmp_path / "led").rglob("*.jsonl"))[-1]
    lines = seg.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"] = {"tampered": True}
    lines[0] = json.dumps(rec)
    seg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reg = Registry(Ledger(tmp_path / "led", new_id=sup.deterministic_id_factory()))
    with pytest.raises(ChainBroken):
        reg.query()
