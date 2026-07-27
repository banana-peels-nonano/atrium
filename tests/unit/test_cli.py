"""Founder-CLI suite (conductor/cli.py) — the thin shell over Conductor.command.

The CLI adds no rule: every behavior asserted here is an owner's behavior surfacing
through the shell (refusal text, INV-COND-2 gate refusals, Gov-boundary minting).
Fakes injected via build_factory's seams (FakeEmbedder; no network — INV-TEST-SAFE);
the repo root is the real repo (committed config/, agents/), data dirs are tmp.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.conductor import cli
from charterhouse.contracts.state import State

from tests.fakes import FakeEmbedder
from tests.unit import _a10_support as a10

REPO = Path(__file__).resolve().parents[2]
VID = "v-cli"


@pytest.fixture()
def factory(tmp_path):
    return cli.build_factory(REPO, tmp_path / "data", profile="free",
                             embedder=FakeEmbedder(32), embed_model="fake-embed-v1")


def run(factory, *argv):  # noqa: ANN001
    """One CLI invocation against an injected factory (the test seam)."""
    return cli.main(list(argv), factory=factory)


def test_cli_capture_frame_and_pipeline_roundtrip(factory, capsys):
    """The GREEN loop end-to-end: capture + frame ack with OK/color/event id; the
    pipeline read renders the venture."""
    assert run(factory, "capture", "--venture", VID, "--codename", "pods") == 0
    assert run(factory, "frame", "--venture", VID, "--brief-ref", "brief-001",
               "--score", "20", "--quotes", "3") == 0
    assert run(factory, "pipeline") == 0
    out = capsys.readouterr().out
    assert "OK capture" in out and "GREEN" in out
    assert VID in out and "FRAMED" in out and "pods" in out


def test_cli_red_halts_without_approve(factory, capsys):
    """A RED command without --approve runs tokenless and halts with the OWNER's
    refusal (exit 1); the venture does not move."""
    run(factory, "capture", "--venture", VID)
    run(factory, "frame", "--venture", VID, "--brief-ref", "b", "--score", "20",
        "--quotes", "3")
    assert run(factory, "admit", "--venture", VID) == 1
    out = capsys.readouterr().out
    assert "REFUSED" in out
    assert factory.registry.get(VID).state is State.FRAMED


def test_cli_approve_mints_at_gov_boundary(factory, capsys):
    """--approve IS the founder act: the CLI mints the single-use token via gov.grant
    and passes it through; the owner consumes it exactly once."""
    run(factory, "capture", "--venture", VID)
    run(factory, "frame", "--venture", VID, "--brief-ref", "b", "--score", "20",
        "--quotes", "3")
    assert run(factory, "admit", "--venture", VID, "--approve") == 0
    assert factory.registry.get(VID).state is State.VALIDATING
    assert "OK admit" in capsys.readouterr().out


def test_cli_gate_needs_critic_then_advances(factory, capsys):
    """INV-COND-2 through the shell: an unbriefable gate refuses even WITH --approve;
    once a critic take exists the same gate advances and gatebrief shows the tier."""
    run(factory, "capture", "--venture", VID)
    run(factory, "frame", "--venture", VID, "--brief-ref", "b", "--score", "20",
        "--quotes", "3")
    run(factory, "admit", "--venture", VID, "--approve")
    run(factory, "validate-evidence", "--venture", VID, "--verdict", "PASS",
        "--quote-count", "22", "--segment-kind", "online")
    run(factory, "validate-experiment", "--venture", VID, "--metric", "conversion",
        "--actual", "5.4", "--threshold", "4.0", "--verdict", "PASS")
    assert run(factory, "gate", "--venture", VID, "--decision", "ADVANCE",
               "--to", "SHAPING", "--approve") == 1  # no critic take yet
    assert "REFUSED" in capsys.readouterr().out
    a10.seed_artifact_produced(factory.ledger, VID, tier=1)
    assert run(factory, "gate", "--venture", VID, "--decision", "ADVANCE",
               "--to", "SHAPING", "--approve") == 0
    assert factory.registry.get(VID).state is State.SHAPING
    assert run(factory, "gatebrief", "--venture", VID) == 0
    out = capsys.readouterr().out
    assert "critic" in out.lower() and "tier" in out.lower()


def test_cli_daily_brief_silence_and_decisions(factory, capsys):
    """docs/05 INV-TRIAGE through the shell: an empty factory prints the silence
    line; a briefed PASS venture surfaces as a decision."""
    assert run(factory, "brief") == 0
    assert "silence" in capsys.readouterr().out.lower()
    run(factory, "capture", "--venture", VID)
    run(factory, "frame", "--venture", VID, "--brief-ref", "b", "--score", "20",
        "--quotes", "3")
    run(factory, "admit", "--venture", VID, "--approve")
    run(factory, "validate-evidence", "--venture", VID, "--verdict", "PASS",
        "--quote-count", "22", "--segment-kind", "online")
    a10.seed_artifact_produced(factory.ledger, VID, tier=2)
    assert run(factory, "brief") == 0
    out = capsys.readouterr().out
    assert VID in out and "ADVANCE" in out


def test_cli_killday_kill_and_salvage(factory, capsys):
    """The kill-day loop: killday renders briefed + unbriefable ventures; kill needs
    --approve; empty salvage refuses (R-SALVAGE-TYPES); a named salvage lands."""
    run(factory, "capture", "--venture", VID, "--codename", "husk")
    assert run(factory, "killday") == 0
    assert VID in capsys.readouterr().out  # unbriefable — named, never dropped
    assert run(factory, "kill", "--venture", VID, "--reason", "no signal",
               "--approve") == 0
    assert run(factory, "salvage", "--venture", VID) == 1  # no asset types
    assert "asset" in capsys.readouterr().out.lower()
    assert run(factory, "salvage", "--venture", VID, "--asset-type",
               "anti_pattern") == 0
    assert factory.registry.get(VID).state is State.KILLED


def test_cli_factory_wiring_is_live_and_offline(factory):
    """The wiring is the real stack (no fakes beyond the injected embedder) and the
    v1 model path fails closed without touching a network: the default transport stub
    raises, feeding S8's designed exhaustion."""
    assert factory.conductor is not None and factory.registry is not None
    stub = cli.NoTransport()
    with pytest.raises(RuntimeError, match="no live model transport"):
        stub.complete("any-model", [])
