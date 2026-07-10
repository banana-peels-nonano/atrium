"""S7 redaction — raw PII moves to a local-only ``*.private.md`` sidecar; the shared tier
gets stable tokens (INV-PII-1; R-REDACT).

Tokens are ``⟨PII:kind:h8⟩`` with ``h8 = sha256(raw)[:8]`` — the same value redacts to the
same token across documents/runs, so redacted text stays linkable without exposing the value.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from charterhouse.security.scan import Scanner
from charterhouse.security.types import Finding, Findings

# When two rules claim the same span (an SSN is also phone-shaped), the replacement token
# takes the most specific kind. Internal — free to change (security/API.md).
_KIND_PRIORITY = (
    "secret", "credit_card", "ssn", "email", "phone", "financial", "name", "high_entropy",
)


def _token(kind: str, raw: str) -> str:
    h8 = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"⟨PII:{kind}:{h8}⟩"


def _resolve_overlaps(findings: Findings) -> list[Finding]:
    """One finding per region: longest span first at each position, kind priority on ties."""
    ordered = sorted(
        findings,
        key=lambda f: (f.start, f.start - f.end, _KIND_PRIORITY.index(f.kind)),
    )
    kept: list[Finding] = []
    for finding in ordered:
        if not kept or finding.start >= kept[-1].end:
            kept.append(finding)
    return kept


class Redactor:
    """Writes sidecars only under the injected local ``vault_dir`` (A1 EnvContext when S2
    lands; ``tmp_path`` in tests)."""

    def __init__(self, vault_dir: str | Path, scanner: Scanner) -> None:
        self._vault_dir = Path(vault_dir)
        # Fail closed at wiring (RISKS R8): a mis-injected vault path raises here, never at
        # first redaction with raw PII already in flight.
        self._vault_dir.mkdir(parents=True, exist_ok=True)
        self._scanner = scanner

    def redact(self, text: str, doc_id: str | None = None) -> tuple[str, str | None]:
        """Replace every scanner hit with its stable token; write raw original + token map to
        ``<vault>/<doc_id>.private.md``; return ``(clean, sidecar_path)`` — ``(text, None)``
        when nothing was found. Clean text is never returned without its sidecar persisted."""
        findings = self._scanner.scan(text)
        if not findings:
            return text, None

        pieces: list[str] = []
        token_map: list[tuple[str, str]] = []
        cursor = 0
        for finding in _resolve_overlaps(findings):
            raw = text[finding.start : finding.end]
            replacement = _token(finding.kind, raw)
            pieces.append(text[cursor : finding.start])
            pieces.append(replacement)
            token_map.append((replacement, raw))
            cursor = finding.end
        pieces.append(text[cursor:])
        clean = "".join(pieces)

        if doc_id is None:
            doc_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        map_lines = "\n".join(f"- `{tok}` ← {raw}" for tok, raw in token_map)
        sidecar = (
            "# Redaction sidecar — LOCAL ONLY\n"
            "(INV-PII-4: never committed, embedded, logged, or pushed)\n\n"
            f"doc_id: {doc_id}\n\n"
            f"## Token map\n{map_lines}\n\n"
            f"## Original\n{text}\n"
        )
        # Fail closed on I/O: the write raises before clean text is ever returned.
        path = self._vault_dir / f"{doc_id}.private.md"
        path.write_text(sidecar, encoding="utf-8")
        return clean, str(path)
