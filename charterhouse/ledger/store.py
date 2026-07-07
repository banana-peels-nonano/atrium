"""Ledger (S4) — append-only, hash-chained event store (docs/40 §2, IF-1).

The append-only source of truth (INV-LEDGER). Every meaningful change is one immutable,
hash-chained event appended to a JSONL segment under ``ledger_dir``. Provides atomic +
totally-ordered ``append``, filtered ``read``, deterministic ``replay`` to world state, and
``snapshot``/``restore``.

Physical format (docs/32, IMPLEMENTATION §3): newline-terminated JSONL records under
``ledger_dir/*.jsonl``, written in **binary** to keep bytes byte-identical across platforms
(the hash chain is computed over the exact on-disk bytes). A single active segment is used;
total order comes from the monotonic ``event_id``, never from file layout, so segmentation is
free to change later. The trailing ``\\n`` is the **commit marker**: a record with no
terminating newline is an interrupted (torn) append and is never visible on read (R1). A
newline-terminated record that fails to parse or whose ``prev_hash`` does not link is
**tampering** → read/replay raise ``ChainBroken`` (fail closed, R2).

Determinism (docs/61 §INV-DET): stdlib only; imports nothing from ``router`` / ``memory`` /
``capabilities``; no LLM. The Ledger records actions; it never performs a GREEN/YELLOW/RED one.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from charterhouse.contracts.events import (
    AUTHORIZATION_REQUIRED,
    GENESIS_PREV_HASH,
    ONCE_PER_LINEAGE,
    CapViolation,
    ChainBroken,
    Event,
    EventType,
    InvalidEnvelope,
    MissingAuthorization,
    PIIInPayload,
    ProjectionError,
    UnknownEventType,
)
from charterhouse.contracts.state import State, Venture, WorldState
from charterhouse.ledger.ulid import monotonic_ulid_factory

_SEGMENT_NAME = "segment-00001.jsonl"

# Structural PII/secret pre-check (defense in depth behind S7 redaction, docs/41 §4.4). Scans
# string values in a payload only; high-signal, low false-positive.
_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("phone", re.compile(r"\+?\d[\d\-\s]{7,}\d")),
)


@dataclass(frozen=True)
class EventFilter:
    """Optional read filter (docs/40 §2): by venture, type, and time range. All fields
    optional; ``None`` means unfiltered on that axis. ``since``/``until`` bound ``active_time``
    (falling back to ``timestamp`` when ``active_time`` is absent)."""

    venture_id: str | None = None
    type: EventType | None = None
    since: int | None = None
    until: int | None = None


def _canonical_bytes(record: dict) -> bytes:
    """The one canonical on-disk encoding. The hash chain is computed over exactly these bytes,
    never a re-serialization — sidestepping float-repr ambiguity in payloads."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _scan_pii(value: object, path: str) -> str | None:
    """Return the field path of the first structural PII/secret hit, or None."""
    if isinstance(value, str):
        for _label, pat in _PII_PATTERNS:
            if pat.search(value):
                return path
    elif isinstance(value, dict):
        for k, v in value.items():
            hit = _scan_pii(v, f"{path}.{k}" if path else str(k))
            if hit:
                return hit
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            hit = _scan_pii(v, f"{path}[{i}]")
            if hit:
                return hit
    return None


class Ledger:
    """The append-only source of truth (INV-LEDGER)."""

    def __init__(
        self,
        ledger_dir: str | Path,
        backup_dir: str | Path | None = None,
        *,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        self._dir = Path(ledger_dir)
        self._backup_dir = Path(backup_dir) if backup_dir is not None else self._dir.parent / "backups"
        self._new_id = new_id if new_id is not None else monotonic_ulid_factory()
        self._seg = self._dir / _SEGMENT_NAME
        self._lock = threading.Lock()
        self._loaded = False
        self._last_hash = GENESIS_PREV_HASH

    # --- append -------------------------------------------------------------------------

    def append(self, event: Event) -> str:
        """Durably append ``event`` atomically and in total order, linking ``prev_hash``;
        return the assigned monotonic ``event_id``. Fail closed (event NOT written) on invalid
        envelope, unknown ``type``, missing required ``authorization``, structural PII/secret in
        payload, or I/O failure."""
        with self._lock:
            self._ensure_loaded()
            self._validate(event)
            eid = self._new_id()
            record = self._to_record(event, event_id=eid, prev_hash=self._last_hash)
            line = _canonical_bytes(record)
            self._dir.mkdir(parents=True, exist_ok=True)
            with open(self._seg, "ab") as fh:
                fh.write(line + b"\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._last_hash = sha256(line).hexdigest()
            return eid

    def _validate(self, event: Event) -> None:
        if not isinstance(event, Event):
            raise InvalidEnvelope("append() requires an Event")
        if not isinstance(event.type, EventType):
            raise UnknownEventType(f"unknown event type: {event.type!r}")
        if not isinstance(event.actor, str) or not event.actor:
            raise InvalidEnvelope("event.actor must be a non-empty string")
        if not isinstance(event.payload, dict):
            raise InvalidEnvelope("event.payload must be an object")
        if event.type in AUTHORIZATION_REQUIRED and not event.authorization:
            raise MissingAuthorization(
                f"{event.type.value} is a gate/RED event and requires an authorization token id"
            )
        hit = _scan_pii(event.payload, "")
        if hit is not None:
            raise PIIInPayload(f"structural PII/secret in payload field: {hit!r}")

    @staticmethod
    def _to_record(event: Event, *, event_id: str, prev_hash: str) -> dict:
        return {
            "event_id": event_id,
            "schema_version": event.schema_version,
            "timestamp": event.timestamp,
            "active_time": event.active_time,
            "venture_id": event.venture_id,
            "actor": event.actor,
            "type": event.type.value,
            "from_state": event.from_state,
            "to_state": event.to_state,
            "payload": event.payload,
            "authorization": event.authorization,
            "prev_hash": prev_hash,
        }

    def _ensure_loaded(self) -> None:
        """On the first append, verify the existing (committed) log and recover the chain tail.
        A broken chain refuses further appends (cannot append onto a corrupt log)."""
        if self._loaded:
            return
        last = GENESIS_PREV_HASH
        for _record, line in self._verified_lines():
            last = sha256(line).hexdigest()
        self._last_hash = last
        self._loaded = True

    # --- read / verify ------------------------------------------------------------------

    def read(self, filter: EventFilter | None = None) -> Iterator[Event]:
        """Yield events in total order (optionally filtered), verifying the hash chain as it
        streams. A broken chain raises ``ChainBroken`` immediately (fail closed)."""
        for record, _line in self._verified_lines():
            if self._matches(record, filter):
                yield self._from_record(record)

    def _committed_lines(self) -> list[bytes]:
        """All newline-committed record lines across segments, in total order. The trailing
        element after the final ``\\n`` (empty on a clean file, a torn remnant on a crash) is
        always dropped — the commit marker (R1)."""
        lines: list[bytes] = []
        for seg in sorted(self._dir.rglob("*.jsonl")):
            raw = seg.read_bytes()
            if not raw:
                continue
            parts = raw.split(b"\n")
            lines.extend(parts[:-1])
        return lines

    def _verified_lines(self) -> Iterator[tuple[dict, bytes]]:
        """Iterate ``(record, raw_line_bytes)`` verifying the chain. Any committed line that
        fails to parse, or whose ``prev_hash`` does not link the prior record's canonical bytes,
        raises ``ChainBroken`` (fail closed)."""
        prev = GENESIS_PREV_HASH
        for line in self._committed_lines():
            try:
                record = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ChainBroken(f"unparseable committed record: {exc}") from exc
            if record.get("prev_hash") != prev:
                raise ChainBroken(
                    f"hash-chain break at event {record.get('event_id')!r}: "
                    "prev_hash does not link the prior record"
                )
            prev = sha256(line).hexdigest()
            yield record, line

    @staticmethod
    def _matches(record: dict, filter: EventFilter | None) -> bool:
        if filter is None:
            return True
        if filter.venture_id is not None and record.get("venture_id") != filter.venture_id:
            return False
        if filter.type is not None and record.get("type") != filter.type.value:
            return False
        t = record.get("active_time")
        if t is None:
            t = record.get("timestamp")
        if filter.since is not None and (t is None or t < filter.since):
            return False
        if filter.until is not None and (t is None or t > filter.until):
            return False
        return True

    @staticmethod
    def _from_record(record: dict) -> Event:
        return Event(
            type=EventType(record["type"]),
            actor=record["actor"],
            payload=record.get("payload") or {},
            venture_id=record.get("venture_id"),
            from_state=record.get("from_state"),
            to_state=record.get("to_state"),
            authorization=record.get("authorization"),
            timestamp=record.get("timestamp"),
            active_time=record.get("active_time"),
            schema_version=record.get("schema_version", 1),
            event_id=record["event_id"],
            prev_hash=record["prev_hash"],
        )

    # --- replay -------------------------------------------------------------------------

    def replay(self, upto: str | None = None) -> WorldState:
        """Pure fold ``events -> WorldState`` (all events, or up to and including ``upto``),
        enforcing the replay-checked once-per-lineage caps. Raises on a broken chain
        (``ChainBroken``) or a cap violation (``CapViolation``); returns no partial state."""
        acc: dict[str, dict] = {}
        caps: dict[tuple[str, str], int] = {}
        for record, _line in self._verified_lines():
            self._apply(record, acc, caps)
            if upto is not None and record["event_id"] == upto:
                break
        ventures = {vid: self._materialize(vid, r) for vid, r in acc.items()}
        return WorldState(ventures=ventures)

    @staticmethod
    def _apply(record: dict, acc: dict[str, dict], caps: dict[tuple[str, str], int]) -> None:
        et = record["type"]
        vid = record.get("venture_id")
        if et in {t.value for t in ONCE_PER_LINEAGE} and vid is not None:
            caps[(vid, et)] = caps.get((vid, et), 0) + 1
            if caps[(vid, et)] > 1:
                raise CapViolation(
                    f"once-per-lineage cap exceeded for {et} in lineage {vid!r}"
                )
        if vid is None:
            return  # factory-global event: no venture record
        payload = record.get("payload") or {}
        rec = acc.setdefault(vid, _blank())
        if et == EventType.CAPTURE.value:
            rec["codename"] = payload.get("codename", vid)
            if "forked_from" in payload:
                rec["forked_from"] = payload["forked_from"]
        if record.get("to_state") is not None:
            rec["state"] = record["to_state"]
            rec["state_entered_at"] = record.get("active_time")
        if et == EventType.FRAME.value and "score" in payload:
            rec["score"] = payload["score"]
        if et == EventType.SCORE_OVERRIDE.value and "new_score" in payload:
            rec["score"] = payload["new_score"]
        if et == EventType.OMW_GRANT.value:
            rec["omw_granted"] = True
        if et == EventType.EXPERIMENT_LIVE.value:
            rec["experiment_live_at"] = payload.get("experiment_live_at", record.get("active_time"))
        if et in (EventType.PARK.value, EventType.SHOVEL_READY.value) and "evidence_ttl_at" in payload:
            rec["evidence_ttl_at"] = payload["evidence_ttl_at"]
        rec["event_stream_ptr"] = record["event_id"]

    @staticmethod
    def _materialize(vid: str, rec: dict) -> Venture:
        if rec["state"] is None:
            raise ProjectionError(
                f"venture {vid!r} has events but no state-setting event "
                "(no capture/transition); cannot project a defined state"
            )
        return Venture(
            id=vid,
            codename=rec["codename"] if rec["codename"] is not None else vid,
            state=State(rec["state"]),
            score=rec["score"],
            forked_from=rec["forked_from"],
            state_entered_at=rec["state_entered_at"],
            experiment_live_at=rec["experiment_live_at"],
            active_time_accum=rec["active_time_accum"],
            omw_granted=rec["omw_granted"],
            evidence_ttl_at=rec["evidence_ttl_at"],
            artifact_links=tuple(rec["artifact_links"]),
            event_stream_ptr=rec["event_stream_ptr"],
        )

    # --- snapshot / restore -------------------------------------------------------------

    def snapshot(self) -> str:
        """Copy the ledger segments to a dated ``backup_dir/YYYY-MM-DD/<stamp>/`` folder
        (CRITICAL class, docs/23); return the snapshot ref."""
        now = datetime.now(timezone.utc)
        ref = self._backup_dir / now.strftime("%Y-%m-%d") / now.strftime("%H%M%S-%f")
        ref.mkdir(parents=True, exist_ok=True)
        for seg in sorted(self._dir.rglob("*.jsonl")):
            shutil.copy2(seg, ref / seg.name)
        return str(ref)

    def restore(self, snapshot_ref: str) -> None:
        """Reproduce state from a snapshot such that ``restore(); replay()`` yields
        byte-identical registry state. A corrupt snapshot (chain fails) refuses restore; the
        prior state is retained (fail closed)."""
        ref = Path(snapshot_ref)
        # Verify the snapshot chain BEFORE touching current state.
        Ledger(ref, backup_dir=ref).replay()
        with self._lock:
            self._dir.mkdir(parents=True, exist_ok=True)
            for seg in self._dir.rglob("*.jsonl"):
                seg.unlink()
            for seg in sorted(ref.rglob("*.jsonl")):
                shutil.copy2(seg, self._dir / seg.name)
            self._loaded = False
            self._last_hash = GENESIS_PREV_HASH


def _blank() -> dict:
    return {
        "codename": None,
        "state": None,
        "score": None,
        "forked_from": None,
        "state_entered_at": None,
        "experiment_live_at": None,
        "active_time_accum": 0,
        "omw_granted": False,
        "evidence_ttl_at": None,
        "artifact_links": (),
        "event_stream_ptr": None,
    }
