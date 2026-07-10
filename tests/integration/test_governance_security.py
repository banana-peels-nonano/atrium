"""S6+S7 integration suite (governance/TESTPLAN.md, security/TESTPLAN.md): the Stress-Test
Venture-A envelope arc against the real Ledger, and the S7→S4 defense-in-depth seam.

Integration tests carry the ``test_it_`` prefix (A3 convention).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.contracts.events import EventType, PIIInPayload
from charterhouse.governance import Gov
from charterhouse.ledger import EventFilter, Ledger
from charterhouse.security import Security

from tests.fixtures.pii_corpus import KNOWN_IDENTITIES, POSITIVES
from tests.unit import _a3_support as a3
from tests.unit import _a5_support as sup


def test_it_stress_a_envelope_arc(tmp_path):
    """INV-GOV-4 end-to-end — the Venture-A `battlecard` arc (Stress Test §1, defect A3 /
    R-ENVELOPE): founder authorizes $120 once (RED); ~12 days of $10 boosts are YELLOW
    spends; day 13 breaches and is refused (re-RED); a fresh envelope resumes spending. The
    ledger stream records the whole story in order."""
    ledger = Ledger(tmp_path / "ledger", new_id=a3.deterministic_id_factory())
    gov = Gov(ledger, sup.FakeConfig(), clock=sup.SteppableClock())

    gov.envelope_open("battlecard", 120.0)
    for day in range(12):  # $10/day LinkedIn boost, 12 days = the full $120
        result = gov.spend("battlecard", 10.0)
        assert result.ok, f"day {day} spend refused"
        assert result.degrade == (result.running_total > 96.0)  # past 80% of 120

    breach = gov.spend("battlecard", 10.0)  # day 13: would be 130 > 120
    assert not breach.ok

    gov.envelope_open("battlecard", 60.0)  # the founder's re-RED
    resumed = gov.spend("battlecard", 10.0)
    assert resumed.ok and resumed.running_total == pytest.approx(10.0)

    types = [e.type for e in ledger.read(EventFilter(venture_id="battlecard"))]
    assert types == (
        [EventType.SPEND_ENVELOPE]
        + [EventType.SPEND_METER] * 12
        + [EventType.SPEND_BREACH, EventType.SPEND_ENVELOPE, EventType.SPEND_METER]
    )


def test_it_redacted_payload_accepted_raw_rejected(tmp_path):
    """Defense in depth (docs/24; INV-PII-1 × S4 backstop): a payload built from the S7
    CHECKPOINT output appends cleanly (tokens + a sidecar *name* ref), while the same notes
    raw are rejected by the Ledger's independent structural PII pre-check."""
    ledger = Ledger(tmp_path / "ledger", new_id=a3.deterministic_id_factory())
    security = Security(tmp_path / "vault", known_identities=KNOWN_IDENTITIES)

    raw = (
        f"Interview with {KNOWN_IDENTITIES[0]} — reach her at {POSITIVES[0][1]} "
        f"or {POSITIVES[3][1]}. SSN on file: {POSITIVES[6][1]}."
    )
    result = security.checkpoint(raw, doc_id="podcaster-interviews")

    clean_event = a3.draft(
        EventType.CONSOLIDATE,
        payload={"notes": result.clean, "sidecar_ref": Path(result.sidecar_ref).name},
        venture_id="clipscribe",
    )
    assert ledger.append(clean_event)  # redacted output passes the S4 backstop

    with pytest.raises(PIIInPayload):
        ledger.append(
            a3.draft(EventType.CONSOLIDATE, payload={"notes": raw}, venture_id="clipscribe")
        )
