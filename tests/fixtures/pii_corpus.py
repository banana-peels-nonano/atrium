"""The PII corpus — the fixture that defines the S7 scanner's bar (docs/55 §2, docs/54 §S7):
**100% recall on POSITIVES, zero findings on NEGATIVES** (security/IMPLEMENTATION §6).

Every value is ASSEMBLED AT RUNTIME by concatenation so no committed line ever trips
``scripts/secret_scan.py`` (CI gates 6/7) — the A3 precedent (`_a3_support.PII_CORPUS`).
All values are synthetic: documentation-reserved numbers (555 phones, 4111… test PAN,
AWS's published example key id), invented names, invented figures.

Extending this corpus is how the scanner's bar tightens over time (S9/S12 add retrieval-path
and checkpoint-path samples); a new PII shape found in the wild gets a POSITIVES row first,
then a rule.
"""

from __future__ import annotations


def _j(*parts: str) -> str:
    """Assemble a sensitive-looking value at runtime (never committed contiguously)."""
    return "".join(parts)


# Names the deterministic layer must catch via the known-identities registry
# (security/IMPLEMENTATION §6 — free-text name inference is the redaction layer's job).
KNOWN_IDENTITIES: tuple[str, ...] = (
    "Priya Raghunathan",
    "Daniel Okafor",
    "Marta Kowalczyk",
)

# (kind, value) — every value MUST be found by Scanner.scan with (at least) this kind.
POSITIVES: tuple[tuple[str, str], ...] = (
    ("email", _j("maria.gonzalez", "@", "podmail.com")),
    ("email", _j("jane.doe", "@", "example.com")),
    ("email", _j("d.okafor+pods", "@", "mailhost.co.uk")),
    ("phone", _j("+1-555", "-", "0142")),
    ("phone", _j("(415) 555", " ", "2671")),
    ("phone", _j("+44 20 7946", " ", "0958")),
    ("ssn", _j("123-45", "-", "6789")),
    ("credit_card", _j("4111 1111", " ", "1111 1111")),
    ("credit_card", _j("5500-0000", "-", "0000-0004")),
    ("secret", _j("AKIA", "IOSFODNN7EXAMPLE")),
    ("secret", _j("sk-", "proj-Ab12Cd34Ef56Gh78Ij90Kl12")),
    ("secret", _j("ghp_", "Abc123Def456Ghi789Jkl012Mno345Pqr678")),
    ("secret", _j("xoxb-", "1234567890-abcdefghijklmnop")),
    ("secret", _j("password", " = ", "hunter2secret!")),
    ("secret", _j("api_key", ": ", "9f8e7d6c5b4a39281706")),
    ("secret", _j("-----BEGIN RSA ", "PRIVATE KEY-----")),
    ("high_entropy", _j("aB3xK9mQ2rT7", "wP5nY8vC1sD4fG6hJ0kL")),
    ("name", "Priya Raghunathan"),
    ("name", "Daniel Okafor"),
    ("name", _j("Name: ", "Sofia Lindqvist")),
    ("financial", _j("unreleased Q3 revenue: ", "$412,000")),
    ("financial", _j("bank routing ", "021000021")),
    ("financial", _j("salary is ", "$185,000 per year")),
)

# Clean text the scanner MUST NOT flag (precision guard — a false positive here would
# dead-lock CHECKPOINT on ordinary factory content; security/RISKS R3).
NEGATIVES: tuple[str, ...] = (
    "Weekly competitor-review battlecards emailed to B2B SaaS founders.",
    "Pricing hypothesis: $29/mo, tested against $39/mo on the landing page.",
    "Factory Score 20/25 (Pain 5, Reach 4, Build 4, Money 4, Compounding 3).",
    "Day 14: 312 visitors, 17 email-plus-title conversions (5.4% > 4% threshold). PASS.",
    "Deadline is 60 active-days from experiment_live_at, never wall-clock.",
    "event 01JZC9EXAMPLEULID000000000 links prev_hash "
    "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00",
    "commit 408c37b12b64f8ca457a38ad9e6a964312dad94e on branch feat/a5-governance",
    "Deploy tag v1.2.3 shipped to staging; smoke suite green in 8 minutes.",
    "Gate review scheduled 2026-07-04, evidence TTL stamped 2026-09-02 (60 active-days).",
    "The kill gate fires at churn>15%/mo after fixes, or CAC > 6-month LTV.",
    "MRR crossed $390 with 12 paying customers on Day 88.",
)


def compose(seed_positives: tuple[tuple[str, str], ...], filler: tuple[str, ...]) -> str:
    """Interleave positives into filler prose (one paragraph per line) — a convenience for
    building scan targets; tests do their own seeded composition for the property test."""
    lines: list[str] = list(filler)
    for i, (_kind, value) in enumerate(seed_positives):
        lines.insert(min(len(lines), i * 2 + 1), f"note {i}: {value} (captured in interview)")
    return "\n".join(lines)
