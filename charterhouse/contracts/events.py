"""Frozen IF-1 event contract — the common envelope, the event-type vocabulary, and the
ledger error taxonomy (docs/41 §1–§2, docs/40 §2).

These are *declarations only* (enums, dataclasses, exception classes, constant sets): the
frozen shapes that consumers A4/A5/A7/A10/A11 build against. All behaviour — canonical
encoding, chain hashing, envelope validation, replay — lives in ``charterhouse/ledger`` /
``charterhouse/registry`` and is added in the implementation step (tests-first: this module
exists so the S4 tests can reference the frozen surface).

Determinism (docs/61 §INV-DET): this module imports only stdlib. It MUST NOT import
``router`` / ``memory`` / ``capabilities`` and MUST NOT call an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ``schema_version`` stamped on every event (docs/41 §5). Additive evolution only; the reader
# supports all prior versions. Start at 1.
SCHEMA_VERSION = 1

# Genesis link for the first event in a ledger (docs/32 tamper-evident chain).
GENESIS_PREV_HASH = "0" * 64


class EventType(str, Enum):
    """The canonical, versioned event vocabulary (docs/41 §2, frozen at IF-1).

    Adding a member is an additive, versioned change (docs/43 §7); removing/renaming one is a
    breaking change requiring an ICR + consumer sign-off (docs/43 §4).
    """

    # Sourcing & framing
    CAPTURE = "capture"
    FRAME = "frame"
    SCORE_OVERRIDE = "score_override"
    # Admission & lifecycle transitions
    ADMIT = "admit"
    TRANSITION = "transition"
    PARK = "park"
    SHOVEL_READY = "shovel_ready"
    OMW_GRANT = "omw_grant"
    OVERRIDE = "override"
    # Validation
    EVIDENCE_GATE = "evidence_gate"
    EXPERIMENT_LIVE = "experiment_live"
    EXPERIMENT_RESULT = "experiment_result"
    # Money & sending (governance)
    SPEND_ENVELOPE = "spend_envelope"
    SPEND_METER = "spend_meter"
    SPEND_BREACH = "spend_breach"
    SEND_BATCH = "send_batch"
    # Build & release
    SPEC_APPROVED = "spec_approved"
    PARTNERS = "partners"
    DEPLOY_PROD = "deploy_prod"
    BILLING_ENABLE = "billing_enable"
    LAUNCH = "launch"
    # Outcomes & memory
    GATE_DECISION = "gate_decision"
    PIVOT_FORK = "pivot_fork"
    KILL = "kill"
    SALVAGE = "salvage"
    GRADUATE = "graduate"
    ALUMNI_TRANSITION = "alumni_transition"
    CONSOLIDATE = "consolidate"
    LESSON_WRITTEN = "lesson_written"
    # System & telemetry
    PAUSE = "pause"
    RESUME = "resume"
    LLM_CALL = "llm_call"
    PII_BLOCK = "pii_block"
    ERROR = "error"


# Event types that, by their docs/41 §2 (gate)/(RED) annotation, ALWAYS carry an
# ``authorization`` token id (docs/41 §4.2). The Ledger validates *presence* only; the
# *classification* of an action as gate/RED is S6's responsibility (docs/24, A5 API.md).
# ``transition`` is intentionally excluded: it spans both gate and internal transitions
# (docs/42 §3), so its authorization requirement is per-(from,to) and not knowable from the
# type alone.
AUTHORIZATION_REQUIRED: frozenset[EventType] = frozenset(
    {
        EventType.ADMIT,
        EventType.SPEC_APPROVED,
        EventType.SPEND_ENVELOPE,
        EventType.SEND_BATCH,
        EventType.DEPLOY_PROD,
        EventType.BILLING_ENABLE,
        EventType.LAUNCH,
    }
)

# Once-per-lineage caps enforced during replay (docs/41 §4.3, INV-SM-5 / OMW-LEDGER). A second
# occurrence in a venture's lineage is a replay-detected violation.
ONCE_PER_LINEAGE: frozenset[EventType] = frozenset(
    {EventType.OMW_GRANT, EventType.PIVOT_FORK}
)


@dataclass(frozen=True)
class Event:
    """The common envelope — every ledger event (docs/41 §1, frozen verbatim at IF-1).

    On ``Ledger.append`` the caller supplies every field except ``event_id`` and ``prev_hash``,
    which the Ledger assigns (monotonic ULID + chain link). The stored record is immutable;
    corrections are new compensating events, never edits (docs/41 §4.1).
    """

    type: EventType
    actor: str
    payload: dict = field(default_factory=dict)
    venture_id: str | None = None
    from_state: str | None = None
    to_state: str | None = None
    authorization: str | None = None
    timestamp: str | None = None  # ISO-8601 wall-clock (for humans)
    active_time: int | None = None  # factory-active-time counter at emission
    schema_version: int = SCHEMA_VERSION
    # Assigned by the Ledger on append (empty on a draft passed to append()).
    event_id: str = ""
    prev_hash: str = ""


# --- Error taxonomy (fail closed, docs/61 §INV-FAILCLOSED) ---------------------------------


class LedgerError(Exception):
    """Base class for every S4 ledger/registry failure."""


class InvalidEnvelope(LedgerError):
    """The event does not conform to the common envelope (missing/misshaped field)."""


class UnknownEventType(LedgerError):
    """The event ``type`` is not in the frozen catalog (docs/41 §2)."""


class MissingAuthorization(LedgerError):
    """A gate/RED-typed event is missing its required ``authorization`` token id."""


class PIIInPayload(LedgerError):
    """A payload contains structural PII/secret (defense in depth behind S7 redaction)."""


class ChainBroken(LedgerError):
    """The tamper-evident hash chain does not verify on read (fail closed)."""


class CapViolation(LedgerError):
    """A once-per-lineage cap (``omw_grant`` / ``pivot_fork``) was exceeded (docs/41 §4.3)."""


class ProjectionError(LedgerError):
    """Replay cannot project a defined world state from an otherwise-valid event stream — e.g. a
    venture that has events but no state-setting event (no ``capture``/transition). Fail closed
    with a named venture rather than a bare ``ValueError`` (docs/61 §INV-FAILCLOSED)."""
