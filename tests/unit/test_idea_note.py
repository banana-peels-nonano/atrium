"""The idea note (feat/idea-note) — the founder's actual words reach the model.

Before this, `--note-ref`/`--brief-ref` were opaque strings that nothing ever opened: the
ONLY per-venture text the scout/analyst saw was the codename, so it invented detail from a
title. `capture --note/--note-file` now stores the idea's full text in the vault (through
S7's redact→scan CHECKPOINT) and `advise` threads it into the prompt.

Two disciplines are asserted here, not assumed:
- the note text goes to the VAULT, never into the ledger payload (only a ref + a boolean);
- a note whose text carries PII **auto-degrades advise to local** even when the founder
  forgets `--pii` — the scanner tags it, not the human.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charterhouse.capabilities.framework.capability import assemble_messages
from charterhouse.capabilities.framework.types import CapInput
from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State
from charterhouse.memory.types import WorkingSet

from tests.fixtures import pii_corpus
from tests.unit import _a10_support as a10
from tests.unit import _a8_support as a8

IDEA = ("brain and decision intelligence for now and coming founders: a cockpit that "
        "scores a founder's live decisions against their own past outcomes")


class RecordingTransport:
    """Wraps a transport and keeps the messages each call actually sent."""

    def __init__(self, inner) -> None:  # noqa: ANN001
        self._inner = inner
        self.messages: list[list] = []

    def complete(self, model, messages, tools=None, max_tokens=None):  # noqa: ANN001
        self.messages.append(messages)
        return self._inner.complete(model, messages, tools, max_tokens)

    @property
    def call_count(self) -> int:
        return len(self.messages)


def _capture_with_note(f, vid: str = "v-note", note: str = IDEA, **extra):
    args = {"venture_id": vid, "codename": "atrium", "note": note}
    args.update(extra)
    return f.conductor.command("capture", args)


# --- storage: the vault holds the words, the ledger holds a ref ---------------------------


def test_capture_stores_the_note_text_in_the_vault(tmp_path):
    """The founder's words land in a real file — the ref finally points at something."""
    f = a10.make_factory(tmp_path)
    _capture_with_note(f)
    note_path = f.vault_dir / "ventures" / "v-note" / "note.md"
    assert note_path.is_file()
    assert IDEA in note_path.read_text(encoding="utf-8")

    (capture,) = [e for e in f.ledger.read() if e.type is EventType.CAPTURE]
    assert capture.payload["note_ref"] == "ventures/v-note/note.md"


def test_the_note_text_never_enters_the_ledger(tmp_path):
    """The ledger keeps a REF and a boolean, never the prose: the audit trail must stay
    small and the S4 payload backstop must never see free text."""
    f = a10.make_factory(tmp_path)
    _capture_with_note(f)
    (capture,) = [e for e in f.ledger.read() if e.type is EventType.CAPTURE]
    assert IDEA not in str(capture.payload)
    assert set(capture.payload) >= {"note_ref", "contains_pii"}


def test_capture_without_a_note_behaves_exactly_as_before(tmp_path):
    """Back-compat: no note → no file, and the old opaque default ref is unchanged."""
    f = a10.make_factory(tmp_path)
    f.conductor.command("capture", {"venture_id": "v-plain", "codename": "plain"})
    assert not (f.vault_dir / "ventures" / "v-plain" / "note.md").exists()
    (capture,) = [e for e in f.ledger.read() if e.type is EventType.CAPTURE]
    assert capture.payload["note_ref"] == "note-v-plain"


# --- the prompt: the model reads the founder's words --------------------------------------


def test_assemble_messages_gives_the_idea_its_own_labelled_section():
    """A distinct `IDEA` section, not folded into the VENTURE title line — the label is
    what makes the model treat the words as source material rather than a name."""
    from charterhouse.contracts.state import Venture

    spec = a10.build_registry(a10.AGENTS_DIR).get(State.CAPTURED)
    venture = Venture(id="v1", codename="atrium", state=State.CAPTURED)
    empty = WorkingSet(records=(), doctrine="", k=0)

    def messages(note: str = "") -> str:
        return assemble_messages(CapInput(spec=spec, venture=venture,
                                          state=State.CAPTURED, working_set=empty,
                                          note=note))[1]["content"]

    user = messages(IDEA)
    assert "IDEA (founder's words):" in user
    assert IDEA in user
    assert user.index("IDEA (founder's words):") < user.index("DOCTRINE:")  # source first
    # an absent note leaves the prompt exactly as it was
    assert "IDEA (founder's words):" not in messages()


def test_advise_sends_the_stored_note_to_the_producer(tmp_path):
    """End-to-end through the chokepoint: the words captured yesterday are in the prompt
    the producer actually receives today."""
    f = a10.make_factory(tmp_path)
    for pid in f.transports:
        f.transports[pid] = RecordingTransport(f.transports[pid])
    f.router._transports = f.transports
    _capture_with_note(f)
    f.conductor.command("advise", {"venture_id": "v-note"})
    sent = [m for t in f.transports.values() for msgs in t.messages for m in msgs]
    assert any(IDEA in str(m.get("content", "")) for m in sent), \
        "the producer never saw the founder's words"


def test_advise_still_works_on_an_old_ledger_with_an_opaque_note_ref(tmp_path):
    """The founder's existing ledgers carry `note-<vid>` labels that resolve to no file.
    A ref that doesn't resolve means "no note" — advise proceeds, never raises."""
    f = a10.make_factory(tmp_path)
    f.ledger.append(Event(type=EventType.CAPTURE, actor="conductor",
                          payload={"source": "inbox", "note_ref": "note-v-old",
                                   "codename": "legacy"},
                          venture_id="v-old", to_state=State.CAPTURED.value))
    result = f.conductor.command("advise", {"venture_id": "v-old"})
    assert result.ok


# --- PII: the scanner tags it, not the founder --------------------------------------------


def _pii_note() -> str:
    email = next(v for k, v in pii_corpus()["positives"] if k == "email")
    return f"{IDEA}. Interviewed the design partner, reach them at {email}."


def test_a_pii_note_is_redacted_before_it_reaches_the_vault(tmp_path):
    """INV-PII-1: the vault copy — the one the model reads — carries the redaction token,
    never the raw value."""
    f = a10.make_factory(tmp_path)
    email = next(v for k, v in pii_corpus()["positives"] if k == "email")
    _capture_with_note(f, vid="v-pii", note=_pii_note())
    stored = (f.vault_dir / "ventures" / "v-pii" / "note.md").read_text(encoding="utf-8")
    assert email not in stored
    assert IDEA.split(":")[0] in stored  # the idea itself survives redaction


def test_a_pii_note_tags_the_venture_even_if_the_founder_forgets_the_flag(tmp_path):
    """The discipline must not depend on the human remembering: capture WITHOUT `--pii`,
    but with a corpus PII value in the text, still records the tag."""
    f = a10.make_factory(tmp_path)
    _capture_with_note(f, vid="v-pii", note=_pii_note())
    (capture,) = [e for e in f.ledger.read() if e.type is EventType.CAPTURE]
    assert capture.payload["contains_pii"] is True


def test_a_pii_tagged_note_degrades_advise_to_local_with_no_flag(tmp_path):
    """The requirement: a PII-tagged idea's text degrades like everything else. The tag was
    recorded at capture, so a later `advise` with NO --pii still makes zero cloud sends."""
    f = a10.make_factory(tmp_path)
    _capture_with_note(f, vid="v-pii", note=_pii_note())
    cloud = [pid for pid in f.transports if f.config.get_provider(pid).kind != "local"]
    before = {pid: f.transports[pid].call_count for pid in cloud}

    f.conductor.command("advise", {"venture_id": "v-pii"})  # no --pii here

    for pid in cloud:
        assert f.transports[pid].call_count == before[pid], (
            f"a PII-tagged note reached cloud provider {pid!r}")


def test_the_explicit_pii_flag_is_additive_to_the_scan(tmp_path):
    """`--pii` on a note the scanner finds clean still tags it — the founder can always
    over-classify, never under-classify."""
    f = a10.make_factory(tmp_path)
    _capture_with_note(f, vid="v-flag", note=IDEA, contains_pii=True)
    (capture,) = [e for e in f.ledger.read() if e.type is EventType.CAPTURE]
    assert capture.payload["contains_pii"] is True


# --- the CLI surface ----------------------------------------------------------------------


def test_cli_note_and_note_file_both_store_the_text(tmp_path):
    from charterhouse.conductor import cli

    f = a10.make_factory(tmp_path)
    assert cli.main(["capture", "--venture", "v-inline", "--codename", "a",
                     "--note", IDEA], factory=f) == 0
    assert IDEA in (f.vault_dir / "ventures" / "v-inline" / "note.md").read_text("utf-8")

    idea_file = tmp_path / "idea.md"
    idea_file.write_text(IDEA + " (from a file)", encoding="utf-8")
    assert cli.main(["capture", "--venture", "v-file", "--codename", "b",
                     "--note-file", str(idea_file)], factory=f) == 0
    assert "from a file" in (
        f.vault_dir / "ventures" / "v-file" / "note.md").read_text("utf-8")


def test_cli_missing_note_file_refuses_before_recording_anything(tmp_path, capsys):
    """Fail closed: a bad path must not half-capture a venture."""
    from charterhouse.conductor import cli

    f = a10.make_factory(tmp_path)
    rc = cli.main(["capture", "--venture", "v-bad", "--codename", "c",
                   "--note-file", str(tmp_path / "nope.md")], factory=f)
    assert rc != 0
    assert "nope.md" in capsys.readouterr().err
    assert not list(f.ledger.read())  # nothing recorded
