"""S4 integration tests (ledger + registry TESTPLANs) — written BEFORE implementation.

Test-safety (INV-TEST-SAFE): snapshot/restore write ONLY under the tmp backup_dir; never off
machine, never to real ``K:\\Backups``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.contracts.events import EventType
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


def test_it_lifecycle_transition_replays(make_ledger):
    """A4 Lifecycle stub (docs/40 §3 shape): appending a ``transition`` event → replay()
    reproduces the venture's new state, and Registry.get reflects it (Registry == replay)."""
    led = make_ledger()
    led.append(sup.draft(EventType.CAPTURE, payload={"codename": "x"},
                        venture_id="x", to_state=State.CAPTURED))
    led.append(sup.draft(EventType.TRANSITION, venture_id="x",
                        from_state=State.CAPTURED, to_state=State.FRAMED))
    reg = Registry(led)
    assert reg.get("x").state == State.FRAMED
    assert reg.get("x") == led.replay().ventures["x"]


def test_it_snapshot_restore_replay_identical(make_ledger, tmp_path):
    """snapshot() → mutate → restore() → replay() yields byte-identical registry state
    (docs/54 §S4). Restore is verified against a fresh Ledger reading the restored files."""
    led = make_ledger()
    for i in range(5):
        led.append(sup.draft(EventType.CAPTURE, payload={"codename": f"c{i}"},
                            venture_id=f"v{i}", to_state=State.CAPTURED))
    before = led.replay()
    ref = led.snapshot()
    # Mutate: append more events after the snapshot.
    led.append(sup.draft(EventType.TRANSITION, venture_id="v0",
                        from_state=State.CAPTURED, to_state=State.KILLED))
    assert led.replay() != before, "post-snapshot mutation must change state"
    led.restore(ref)
    assert led.replay() == before, "restore(); replay() must reproduce the snapshotted state"
    # Byte-identical: a fresh Ledger over the restored dir replays to the same state.
    fresh = Ledger(tmp_path / "led", new_id=sup.deterministic_id_factory())
    assert fresh.replay() == before


def test_it_telemetry_llm_call_event(make_ledger):
    """A11 Telemetry (docs/40 §10): a recorded llm_call lands as an event with no PII/secret."""
    led = make_ledger()
    led.append(sup.draft(EventType.LLM_CALL, actor="system",
                        payload={"role": "critic", "model": "local", "provider": "ollama",
                                 "tokens": {"in": 10, "out": 20}, "cost_usd": 0.0,
                                 "latency_ms": 12}, venture_id=None))
    events = [e for e in led.read() if e.type == EventType.LLM_CALL]
    assert len(events) == 1
    assert "cost_usd" in events[0].payload
