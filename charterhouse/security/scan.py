"""S7 deterministic scanner — pure rules, NEVER an LLM (INV-PII-2; docs/24 §2).

Rule set (table-driven; each rule = kind + detector): email, phone, ssn, credit_card
(Luhn-validated), secret (provider key shapes + assignments + PEM blocks), high_entropy
(mixed-case+digit tokens, hex excluded so hashes/ULIDs never false-positive), name
(configured known-identities registry + structural field patterns), financial (amount/account
patterns near confidential-context words). The corpus test is the bar: 100% recall on
positives, zero false positives on negatives (security/IMPLEMENTATION §6).
"""

from __future__ import annotations

import math
import re

from charterhouse.security.types import Finding, Findings

# The subsystem's own redaction tokens (redact.py) are never findings: CHECKPOINT re-scans
# redacted output, and flagging our own replacements would dead-lock the pipeline. The shape
# is exact (kind + 8 hex chars), so a raw value cannot hide inside a well-formed token.
_REDACTION_TOKEN_RE = re.compile(r"⟨PII:[a-z_]+:[0-9a-f]{8}⟩")

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

# Separator-grouped digits (international/US shapes). Digit-count bounds and the ISO-date
# exclusion are applied by the detector; contiguous runs (routing numbers, ids) belong to
# the financial/credit_card rules.
_PHONE_RE = re.compile(
    r"(?<![\w.-])"
    r"(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?\d{2,4}(?:[ -]\d{2,4}){1,3}"
    r"(?![\w-])"
)
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

_SSN_RE = re.compile(r"(?<![\w.-])\d{3}-\d{2}-\d{4}(?![\w-])")

# 13–19 digits with optional space/hyphen separators; Luhn-validated by the detector.
_CARD_RE = re.compile(r"(?<![\w.-])\d(?:[ -]?\d){12,18}(?![\w-])")

_SECRET_RES = (
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"(?<![\w-])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?<![\w-])ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![\w-])xox[a-z]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?<![\w:])(?:api[_-]?key|access[_-]?key|secret[_-]?key|secret|token"
        r"|password|passwd|pwd)\s*[:=]\s*\S+"
    ),
)

# Mixed-case+digit runs ≥24 chars above the entropy floor; hex-only runs are excluded so
# content hashes / commit ids / ULIDs never false-positive (ULIDs also lack lowercase).
_ALNUM_RUN_RE = re.compile(r"[A-Za-z0-9]{24,}")
_HEX_ONLY_RE = re.compile(r"(?:0x)?[0-9a-fA-F]+")
_ENTROPY_FLOOR_BITS = 3.5

_NAME_FIELD_RE = re.compile(
    r"(?:\bName\s*:\s*|\b(?:Mr|Ms|Mrs|Dr|Prof)\.\s+)[A-Z][a-z]+(?: [A-Z][a-z]+)+"
)

# Financial hits require a confidential-context word on the SAME line (docs/24: public
# pricing like "$29/mo" must never trip; the window never crosses lines).
_FIN_CONTEXT_RE = re.compile(
    r"(?i)\b(?:unreleased|confidential|private|payroll|salar(?:y|ies)|bank|routing)\b"
)
_FIN_AMOUNT_RE = re.compile(r"\$\d[\d,]*(?:\.\d+)?")
_FIN_ACCOUNT_RE = re.compile(r"(?<![\w.-])\d{8,12}(?![\w.-])")


def _shannon_bits(s: str) -> float:
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class Scanner:
    """Deterministic rule-based PII/secret scanner. ``known_identities`` registers names
    (interview subjects, partners) the deterministic layer must catch (IMPLEMENTATION §6)."""

    def __init__(self, known_identities: tuple[str, ...] = ()) -> None:
        self._identity_res = tuple(
            re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)
            for name in known_identities
            if name
        )

    def scan(self, text: str) -> Findings:
        """Every rule hit, span-ordered; empty tuple = clean. Pure and deterministic."""
        hits: list[tuple[int, int, str]] = []

        for m in _EMAIL_RE.finditer(text):
            hits.append((m.start(), m.end(), "email"))

        for m in _PHONE_RE.finditer(text):
            digits = sum(ch.isdigit() for ch in m.group())
            if 7 <= digits <= 15 and not _ISO_DATE_RE.fullmatch(m.group()):
                hits.append((m.start(), m.end(), "phone"))

        for m in _SSN_RE.finditer(text):
            hits.append((m.start(), m.end(), "ssn"))

        for m in _CARD_RE.finditer(text):
            if _luhn_ok(re.sub(r"\D", "", m.group())):
                hits.append((m.start(), m.end(), "credit_card"))

        for pattern in _SECRET_RES:
            for m in pattern.finditer(text):
                hits.append((m.start(), m.end(), "secret"))

        for m in _ALNUM_RUN_RE.finditer(text):
            run = m.group()
            if (
                any(c.islower() for c in run)
                and any(c.isupper() for c in run)
                and any(c.isdigit() for c in run)
                and not _HEX_ONLY_RE.fullmatch(run)
                and _shannon_bits(run) >= _ENTROPY_FLOOR_BITS
            ):
                hits.append((m.start(), m.end(), "high_entropy"))

        for pattern in self._identity_res:
            for m in pattern.finditer(text):
                hits.append((m.start(), m.end(), "name"))
        for m in _NAME_FIELD_RE.finditer(text):
            hits.append((m.start(), m.end(), "name"))

        offset = 0
        for line in text.split("\n"):
            if _FIN_CONTEXT_RE.search(line):
                for pattern in (_FIN_AMOUNT_RE, _FIN_ACCOUNT_RE):
                    for m in pattern.finditer(line):
                        hits.append((offset + m.start(), offset + m.end(), "financial"))
            offset += len(line) + 1

        excluded = [m.span() for m in _REDACTION_TOKEN_RE.finditer(text)]
        findings: list[Finding] = []
        seen: set[tuple[int, int, str]] = set()
        for start, end, kind in sorted(hits):
            if (start, end, kind) in seen:
                continue
            seen.add((start, end, kind))
            if any(s < end and start < e for s, e in excluded):
                continue
            raw = text[start:end]
            findings.append(
                Finding(kind=kind, masked=f"{raw[0]}…{raw[-1]}", start=start, end=end)
            )
        return tuple(findings)
