"""S7 Security unit suite — INV-PII-1..4 (docs/24, docs/54 §S7; security/TESTPLAN.md).

The PII corpus (tests/fixtures/pii_corpus.py) is the bar: 100% recall on positives, zero
findings on negatives. The fault-injection test is the docs/24 acceptance line: force a
redaction miss → the independent scan catches it → CHECKPOINT fails closed.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from charterhouse.security import (
    CheckpointError,
    Context,
    PIIRouteBlocked,
    Redactor,
    Scanner,
    Security,
    cloud_route_allowed,
    run_checkpoint,
)

from tests.fixtures.pii_corpus import KNOWN_IDENTITIES, NEGATIVES, POSITIVES
from tests.unit import _a5_support as sup


@pytest.fixture
def scanner() -> Scanner:
    return Scanner(known_identities=KNOWN_IDENTITIES)


@pytest.fixture
def security(tmp_path) -> Security:
    return Security(tmp_path / "vault", known_identities=KNOWN_IDENTITIES)


# --- the deterministic scanner (INV-PII-2) ---------------------------------------------------


def test_scan_corpus_full_recall(scanner):
    """INV-PII-2 (docs/54 §S7): every corpus positive is detected with (at least) its
    expected kind — 100% recall; any miss is a failure. Kinds may overlap (an SSN also looks
    phone-ish); the expected kind must be among the findings covering the planted value."""
    for kind, value in POSITIVES:
        text = f"interview context before {value} and context after"
        findings = scanner.scan(text)
        assert any(f.kind == kind for f in findings), f"missed {kind}: {value!r}"


def test_scan_negatives_no_false_positives(scanner):
    """INV-PII-2 precision (security/RISKS R3): representative clean factory content —
    pricing, scores, hashes, ULIDs, dates, commit ids — produces ZERO findings, else
    CHECKPOINT would dead-lock ordinary work."""
    for line in NEGATIVES:
        assert scanner.scan(line) == (), f"false positive on: {line!r}"
    assert scanner.scan("\n".join(NEGATIVES)) == ()


def test_scan_deterministic(scanner):
    """INV-PII-2: the scanner is pure rules — scanning the same document twice yields
    identical findings (kinds, spans, order). No LLM, no randomness, no state."""
    doc = "\n".join([NEGATIVES[0], POSITIVES[0][1], NEGATIVES[1], POSITIVES[10][1]])
    assert scanner.scan(doc) == scanner.scan(doc)


# --- redaction (INV-PII-1) -------------------------------------------------------------------


def test_redact_moves_pii_to_sidecar(tmp_path, scanner):
    """INV-PII-1 (R-REDACT): redacted text contains no corpus value; the raw values live in
    the *.private.md sidecar under the vault dir; the return is a path ref, not content."""
    redactor = Redactor(tmp_path / "vault", scanner)
    values = [v for _, v in POSITIVES[:8]]
    raw = "notes:\n" + "\n".join(f"- {v}" for v in values)
    clean, ref = redactor.redact(raw, doc_id="interview-01")

    for v in values:
        assert v not in clean, f"raw value leaked into redacted text: {v!r}"
    assert ref is not None
    sidecar = Path(ref)
    assert sidecar.name == "interview-01.private.md"
    assert sidecar.parent == tmp_path / "vault"
    content = sidecar.read_text(encoding="utf-8")
    for v in values:
        assert v in content  # raw preserved locally for the founder


def test_redact_tokens_stable(tmp_path, scanner):
    """INV-PII-1 stable tokens: the same raw value redacts to the same ⟨PII:kind:h8⟩ token in
    two different documents — redacted text stays linkable without exposing the value."""
    redactor = Redactor(tmp_path / "vault", scanner)
    email = POSITIVES[0][1]
    clean_a, _ = redactor.redact(f"first doc: {email}", doc_id="a")
    clean_b, _ = redactor.redact(f"second doc, same person: {email}", doc_id="b")
    token_a = clean_a.removeprefix("first doc: ")
    assert token_a.startswith("⟨PII:") and token_a.endswith("⟩")
    assert token_a in clean_b


def test_vault_dir_validated_at_wiring(tmp_path, scanner):
    """security/RISKS R8: the vault dir is created/validated at construction, so a
    mis-injected vault path fails at wiring (fail closed) — never at first redaction,
    where raw PII would already be in flight."""
    blocker = tmp_path / "vault"
    blocker.write_text("a file sits where the vault dir must go", encoding="utf-8")
    with pytest.raises(OSError):
        Redactor(blocker, scanner)


def test_redact_clean_text_untouched(tmp_path, scanner):
    """INV-PII-1: text with nothing to redact returns unchanged with no sidecar written."""
    redactor = Redactor(tmp_path / "vault", scanner)
    clean, ref = redactor.redact(NEGATIVES[0], doc_id="clean-doc")
    assert clean == NEGATIVES[0]
    assert ref is None
    assert not list((tmp_path / "vault").glob("*.private.md"))


# --- the CHECKPOINT pipeline (INV-PII-1/2) ---------------------------------------------------


def test_checkpoint_order_redact_then_scan(tmp_path):
    """INV-PII-1 pipeline order (docs/24 §The pipeline): checkpoint runs redact FIRST, then
    scans the *redacted* output (never the raw); PII input passes with a sidecar ref."""
    calls: list = []
    scanner = sup.SpyScanner(calls, known_identities=KNOWN_IDENTITIES)
    redactor = sup.SpyRedactor(calls, tmp_path / "vault", scanner)
    raw = f"met {KNOWN_IDENTITIES[0]}, reach her at {POSITIVES[0][1]}"

    result = run_checkpoint(raw, doc_id="beat-7", redactor=redactor, scanner=scanner)

    assert [c[0] for c in calls[:1]] == ["redact"]
    assert "scan" in [c[0] for c in calls[1:]]
    scanned_after_redact = [c[1] for c in calls if c[0] == "scan"][-1]
    assert scanned_after_redact == result.clean  # the scan saw the redacted text
    assert POSITIVES[0][1] not in result.clean
    assert result.sidecar_ref is not None and result.sidecar_ref.endswith(".private.md")


def test_checkpoint_fails_closed_on_residual(tmp_path, scanner):
    """INV-PII-2 fail-closed (R-PRECOMMIT-SCAN; docs/24 acceptance fault injection): a
    misbehaving redactor that redacts nothing → the independent scan catches the residual →
    CheckpointError; no clean text escapes; the error names kinds, never values."""
    raw = f"call {POSITIVES[3][1]} about the {POSITIVES[20][1]} figures"
    with pytest.raises(CheckpointError) as err:
        run_checkpoint(raw, doc_id="beat-8",
                       redactor=sup.MisbehavingRedactor(), scanner=scanner)
    message = str(err.value)
    assert POSITIVES[3][1] not in message and POSITIVES[20][1] not in message
    assert "phone" in message or "financial" in message  # kinds are named


def test_checkpoint_via_facade(security):
    """The Security facade wires the same pipeline (security/API.md): PII in → clean out +
    sidecar + contains_pii result; the raw value is gone."""
    raw = f"ping {POSITIVES[1][1]} tomorrow"
    result = security.checkpoint(raw, doc_id="beat-9")
    assert POSITIVES[1][1] not in result.clean
    assert result.contains_pii is True
    assert result.sidecar_ref is not None


# --- tagging + the cloud-route guard (INV-PII-3) ---------------------------------------------


def test_tag_sets_contains_pii(security):
    """INV-PII-3 input: PII-bearing text is tagged; a context whose sources include a
    .private.md is tagged even with clean text; an already-True tag is never cleared; clean
    context stays untagged."""
    dirty = security.tag(Context(text=f"contact: {POSITIVES[2][1]}"))
    assert dirty.contains_pii

    sidecar_reader = security.tag(
        Context(text=NEGATIVES[0], sources=("vault/interview-01.private.md",))
    )
    assert sidecar_reader.contains_pii

    sticky = security.tag(Context(text=NEGATIVES[0], contains_pii=True))
    assert sticky.contains_pii

    clean = security.tag(Context(text=NEGATIVES[1], sources=("vault/spec.md",)))
    assert not clean.contains_pii


def test_cloud_adapter_blocks_pii(security):
    """INV-PII-3 (S7 side of the joint S7×S8 test; docs/54 §S7 "PII→cloud refused"): an
    adapter honoring the frozen guard refuses a contains_pii context and accepts a clean one.
    Re-run against the real Router when S8 lands (noted in TESTPLAN)."""
    adapter = sup.FakeCloudAdapter()
    tagged = security.tag(Context(text=f"notes on {POSITIVES[0][1]}",
                                  sources=("vault/x.private.md",)))
    assert not cloud_route_allowed(tagged)
    with pytest.raises(PIIRouteBlocked):
        adapter.complete(tagged)

    clean = security.tag(Context(text=NEGATIVES[3]))
    assert cloud_route_allowed(clean)
    assert adapter.complete(clean) == "fake-cloud-response"


# --- sidecar hygiene (INV-PII-4) -------------------------------------------------------------


def test_private_sidecar_gitignored():
    """INV-PII-4: the repo .gitignore carries the **/*.private.md rule so no sidecar can ever
    be committed or pushed (backed by CI gates 6/7 scanning every diff)."""
    gitignore = Path(__file__).resolve().parents[2] / ".gitignore"
    rules = gitignore.read_text(encoding="utf-8").splitlines()
    assert "**/*.private.md" in [r.strip() for r in rules]


def test_findings_never_carry_raw_pii(scanner):
    """INV-PII-4 "never logged": Finding.masked is loggable by construction — it never
    contains the raw matched value for any corpus positive."""
    for kind, value in POSITIVES:
        findings = scanner.scan(f"x {value} y")
        assert findings, f"corpus positive not found: {kind}"
        for f in findings:
            assert value not in f.masked


# --- property: seeded composition vs the planted-set oracle ----------------------------------


@pytest.mark.parametrize("seed", range(20))
def test_scan_property_seeded(scanner, seed):
    """Property (INV-PII-2): documents randomly composed from negatives with known positives
    planted at random offsets — every planted value is found with its kind at its location
    (the planted set IS the oracle), and pure-negative documents stay clean."""
    rng = random.Random(seed)
    planted = rng.sample(list(POSITIVES), k=rng.randint(1, 6))
    lines = list(rng.sample(list(NEGATIVES), k=rng.randint(2, len(NEGATIVES))))
    for i, (_kind, value) in enumerate(planted):
        lines.insert(rng.randrange(len(lines) + 1), f"note {i}: {value} (from interview)")
    doc = "\n".join(lines)

    findings = scanner.scan(doc)
    for kind, value in planted:
        idx = doc.find(value)
        assert idx >= 0
        covered = any(
            f.kind == kind and f.start < idx + len(value) and idx < f.end for f in findings
        )
        assert covered, f"seed {seed}: {kind} not found at its offset: {value!r}"

    pure_negative = "\n".join(rng.sample(list(NEGATIVES), k=4))
    assert scanner.scan(pure_negative) == ()
