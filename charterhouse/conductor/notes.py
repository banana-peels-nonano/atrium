"""The idea note — the founder's own words about a venture (S12 wiring layer).

Before this seam, `note_ref`/`brief_ref` were opaque strings: written into the ledger,
presence-checked by the FRAMED guard, and never opened by anything. The only per-venture
text the scout/analyst saw was the **codename**, so a capability had to invent detail from a
title. `capture --note/--note-file` now stores the idea's full text and `advise` threads it
into the PRODUCE prompt.

Two placements are deliberate:

- **The text goes to the VAULT, never into the ledger payload.** The ledger keeps a ref and
  a boolean, so the audit trail stays small and free text never meets the S4 payload
  backstop. The vault copy is written through S7's CHECKPOINT (redact → independent scan,
  fail closed), so the copy the model reads carries redaction tokens, never raw PII
  (INV-PII-1/2), and the raw original stays in the local-only `.private.md` sidecar.
- **The note reaches the runner as DATA, passed by the caller.** PREPARE/PRODUCE/CRITIQUE
  have no vault path reachable from their frames (beat isolation, INV-WF-1) — reading the
  file here and handing the text to `Workflow.run(note=…)` keeps that structural, rather
  than teaching a beat to open files.

`recorded_note` folds the ledger for a fact the Conductor itself recorded — the same shape
as `_gate` calling `gate_brief`, not a rule re-implemented here (INV-COND-1).
"""

from __future__ import annotations

from pathlib import Path

from charterhouse.contracts.events import EventType

__all__ = ["NOTE_FILE", "note_ref_for", "read_note", "recorded_note", "write_note"]

NOTE_FILE = "note.md"


def note_ref_for(venture_id: str) -> str:
    """The vault-relative ref recorded on the capture event (POSIX, like artifact refs)."""
    return f"ventures/{venture_id}/{NOTE_FILE}"


def write_note(security, vault_dir, venture_id: str, text: str, *,  # noqa: ANN001
               forced_pii: bool = False) -> tuple[str, bool]:
    """CHECKPOINT the founder's text, write the clean copy into the vault, and report
    ``(note_ref, contains_pii)``.

    ``contains_pii`` is the SCANNER's verdict (`CheckpointResult.contains_pii` is true when
    redaction moved something to a sidecar), OR-ed with the founder's explicit flag: the
    human may always over-classify, never under-classify, and the tag never depends on them
    remembering. A residual finding raises ``CheckpointError`` from S7 — nothing is written
    and the caller records nothing (INV-PII-2).
    """
    cp = security.checkpoint(text, doc_id=f"{venture_id}-note")
    path = Path(vault_dir) / "ventures" / venture_id / NOTE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cp.clean, encoding="utf-8")
    return note_ref_for(venture_id), bool(cp.contains_pii or forced_pii)


def read_note(vault_dir, note_ref: str | None) -> str:  # noqa: ANN001
    """The stored note text, or ``""``.

    A ref that resolves to no file means **no note** — never an error. Every ledger written
    before this seam carries the old opaque `note-<vid>` label, so a missing file is the
    normal case on existing history, not a fault.
    """
    if not note_ref or vault_dir is None:
        return ""
    path = Path(vault_dir) / note_ref
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        return ""


def recorded_note(ledger, venture_id: str) -> tuple[str | None, bool]:  # noqa: ANN001
    """``(note_ref, contains_pii)`` from the venture's latest capture event — the fact the
    Conductor recorded at capture, read back at advise time so a PII-tagged idea degrades
    to local routing without the founder re-stating the tag."""
    ref: str | None = None
    contains_pii = False
    for event in ledger.read():
        if event.type is EventType.CAPTURE and event.venture_id == venture_id:
            ref = event.payload.get("note_ref")
            contains_pii = bool(event.payload.get("contains_pii"))
    return ref, contains_pii
