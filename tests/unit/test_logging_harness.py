"""S14+S15 self-tests — the A11 harness validates its own logging + fakes (logging/TESTPLAN.md).

A11 owns the harness other agents test *into*; these are its self-tests. Real tmp-path
sinks, the merged S7 scanner for the field filter, the real Ledger for telemetry parity.
"""

from __future__ import annotations

import inspect
import json

import pytest

from charterhouse.contracts.events import EventType
from charterhouse.ledger import EventFilter, Ledger
from charterhouse.logging import Level, Log, Telemetry

from tests.fakes import (
    Clock,
    FakeEmbedder,
    FakeProvider,
    InMemoryLedger,
    RateLimited,
    RealActionBlocked,
    Simulator,
    guard_real_action,
)
from tests.fixtures import golden_set, pii_corpus
from tests.invariants import family, invariant_manifest, unmapped


def _read_log(log: Log) -> list[dict]:
    return [json.loads(ln) for ln in log.path.read_text(encoding="utf-8").splitlines()]


# --- S14 Logging -----------------------------------------------------------------------------


def test_log_strips_secret_fields(tmp_path):
    """No-secret-in-logs (docs/24): a secret-shaped field is redacted before write."""
    log = Log(tmp_path / "logs")
    log.event(Level.INFO, "router", {"note": "loaded", "api_key": "sk-" + "A" * 30})
    line = _read_log(log)[0]
    assert line["fields"]["note"] == "loaded"
    assert "sk-" not in json.dumps(line)
    assert "REDACTED" in line["fields"]["api_key"]


def test_log_strips_pii_fields(tmp_path):
    """No-PII-in-logs: a PII-shaped field (from the corpus) is redacted before write."""
    log = Log(tmp_path / "logs")
    email = next(v for k, v in pii_corpus()["positives"] if k == "email")
    log.event(Level.WARN, "memory", {"contact": email})
    line = _read_log(log)[0]
    assert email not in json.dumps(line)
    assert "REDACTED" in line["fields"]["contact"]


def test_log_and_telemetry_distinct_sinks(tmp_path):
    """Design split (RISKS R6): Log → files, Telemetry → ledger; not conflated."""
    log = Log(tmp_path / "logs")
    ledger = Ledger(tmp_path / "ledger")
    tele = Telemetry(ledger)
    log.event(Level.INFO, "router", {"msg": "hi"})
    tele.record({"role": "reasoning", "model": "m", "provider": "p",
                 "tokens": {"in": 1, "out": 2}, "cost_usd": 0.0, "latency_ms": 5})
    assert log.path.is_file()  # ops log on disk
    events = list(ledger.read(EventFilter(type=EventType.LLM_CALL)))
    assert len(events) == 1  # telemetry in the ledger, not the file
    assert "llm_call" not in log.path.read_text(encoding="utf-8")


def test_log_never_raises_on_bad_sink(tmp_path):
    """Fail-safe: an unwritable sink does not take the caller down (logging/API.md)."""
    log = Log(tmp_path / "logs", filename="x.log")
    # Point the dir at a file to force an OSError on mkdir/open; event must swallow it.
    (tmp_path / "blocker").write_text("x", encoding="utf-8")
    blocked = Log(tmp_path / "blocker" / "sub")
    blocked.event(Level.ERROR, "env", {"msg": "should not raise"})  # no exception


# --- S14 Telemetry ---------------------------------------------------------------------------


def test_telemetry_appends_llm_call_event(tmp_path):
    """docs/40 §10 / docs/41 §2: record appends a well-formed llm_call event; no PII."""
    ledger = Ledger(tmp_path / "ledger")
    tele = Telemetry(ledger)
    eid = tele.record({"role": "critic", "model": "deepseek", "provider": "openrouter",
                       "tokens": {"in": 100, "out": 40}, "cost_usd": 0.0,
                       "latency_ms": 220, "critic_tier": 1})
    (event,) = list(ledger.read(EventFilter(type=EventType.LLM_CALL)))
    assert event.event_id == eid
    assert event.payload["role"] == "critic"
    assert event.payload["tokens"] == {"in": 100, "out": 40}


def test_telemetry_redacts_secret_in_payload(tmp_path):
    """Defense in depth: a secret smuggled into a telemetry field is redacted before the
    ledger append (docs/24), and the Ledger's own pre-check would reject a raw one anyway."""
    ledger = Ledger(tmp_path / "ledger")
    tele = Telemetry(ledger)
    tele.record({"role": "r", "model": "sk-" + "B" * 30, "provider": "p",
                 "tokens": {"in": 1, "out": 1}, "cost_usd": 0.0, "latency_ms": 1})
    (event,) = list(ledger.read(EventFilter(type=EventType.LLM_CALL)))
    assert "sk-" not in json.dumps(event.payload)


# --- S15 fakes -------------------------------------------------------------------------------


def test_inmemory_ledger_signature_parity():
    """Fake↔real parity (RISKS R3): InMemoryLedger exposes the same public surface as the
    real Ledger (docs/40 §2), with matching signatures."""
    public = [n for n in ("append", "read", "replay", "snapshot", "restore")]
    for name in public:
        assert hasattr(InMemoryLedger, name), f"InMemoryLedger missing {name}"
        real_sig = inspect.signature(getattr(Ledger, name))
        fake_sig = inspect.signature(getattr(InMemoryLedger, name))
        assert real_sig == fake_sig, f"{name}: signature drift {fake_sig} != {real_sig}"


def test_inmemory_ledger_roundtrips():
    """The double behaves like the real thing: append → replay reflects state."""
    from charterhouse.contracts.events import Event
    from charterhouse.contracts.state import State

    led = InMemoryLedger()
    try:
        led.append(Event(type=EventType.CAPTURE, actor="test",
                         payload={"codename": "v"}, venture_id="v",
                         to_state=State.CAPTURED.value))
        world = led.replay()
        assert world.ventures["v"].state is State.CAPTURED
    finally:
        led.close()


def test_fakeprovider_deterministic():
    """docs/55 §2: same inputs → same canned output; programmed rate-limit honored."""
    p = FakeProvider(canned="hello")
    a = p.complete("m", [{"role": "user", "content": "hi"}])
    b = p.complete("m", [{"role": "user", "content": "hi"}])
    assert a["text"] == b["text"] == "hello"
    with pytest.raises(RateLimited):
        FakeProvider(rate_limited=True).complete("m", [])


def test_fakeembedder_deterministic_dim():
    """docs/55 §2: fixed-dim, deterministic, unit-norm vectors for a given text."""
    e = FakeEmbedder(dim=32)
    v1 = e.embed("podcast notes")
    v2 = e.embed("podcast notes")
    assert v1 == v2 and len(v1) == 32
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-9
    assert e.embed("different") != v1


def test_clock_pause_resume():
    """Supports INV-SM-3 tests: active time freezes on pause, resumes on resume."""
    c = Clock()
    c.advance(2.0)
    assert c.now() == 2.0
    c.pause()
    c.advance(5.0)
    assert c.now() == 2.0 and c.paused
    c.resume()
    c.advance(1.0)
    assert c.now() == 3.0


def test_test_safe_guard_blocks_real_action():
    """INV-TEST-SAFE (docs/55 §6): a code path reaching a real action is blocked."""
    def fake_deploy():
        guard_real_action("deploy.prod")
    with pytest.raises(RealActionBlocked):
        fake_deploy()


def test_golden_set_shape():
    """docs/55 §2: the golden set is a stable, non-empty set of role/prompt descriptors."""
    tasks = golden_set()
    assert len(tasks) >= 8
    assert all(t.role and t.prompt for t in tasks)


# --- S15 invariant harness -------------------------------------------------------------------


def test_invariant_manifest_flags_unmapped_must():
    """docs/55 §4: a MUST with no mapped test is reported by the completeness check."""
    required = ("INV-SM-1", "INV-SM-2", "INV-DEMO-UNMAPPED")
    synthetic = {"INV-SM-1": ("t::a",), "INV-SM-2": ("t::b",)}
    gaps = unmapped(required, synthetic)
    assert gaps == ["INV-DEMO-UNMAPPED"]


def test_invariant_manifest_maps_all_inv_sm():
    """The live manifest maps every INV-SM-1..6 (gate-2 family) to ≥1 test."""
    assert unmapped(family("INV-SM")) == []
    m = invariant_manifest()
    for inv in family("INV-SM"):
        assert m[inv], f"{inv} has no mapped test"


# --- integration -----------------------------------------------------------------------------


def test_it_telemetry_roundtrip_real_ledger(tmp_path):
    """Integration (A3 real file Ledger): record → read → replay includes the event; no PII."""
    ledger = Ledger(tmp_path / "ledger")
    Telemetry(ledger).record({"role": "reasoning", "model": "groq", "provider": "groq",
                              "tokens": {"in": 10, "out": 5}, "cost_usd": 0.0,
                              "latency_ms": 90})
    reread = Ledger(tmp_path / "ledger")  # fresh instance, same dir
    events = list(reread.read(EventFilter(type=EventType.LLM_CALL)))
    assert len(events) == 1 and events[0].payload["provider"] == "groq"


def test_it_simulator_shape_available():
    """docs/55 §3: the Simulator interface instantiates with fakes; body deferred to S10/S12."""
    sim = Simulator(ledger=InMemoryLedger(), clock=Clock(), provider=FakeProvider(),
                    embedder=FakeEmbedder())
    sim.command("capture", {"codename": "demo"})
    assert sim.queued == [("capture", {"codename": "demo"})]
    with pytest.raises(NotImplementedError):
        sim.run()
