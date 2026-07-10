"""``Security`` — the S7 facade wiring the frozen ``Sec.redact/scan/tag`` surface (docs/40
§4) + the composed ``checkpoint`` pipeline (security/API.md)."""

from __future__ import annotations

from pathlib import Path

from charterhouse.security.checkpoint import run_checkpoint
from charterhouse.security.redact import Redactor
from charterhouse.security.scan import Scanner
from charterhouse.security.tag import tag
from charterhouse.security.types import CheckpointResult, Context, Findings


class Security:
    """S7 Security. See security/API.md for the full per-function contract."""

    def __init__(self, vault_dir: str | Path, known_identities: tuple[str, ...] = ()) -> None:
        self._scanner = Scanner(known_identities)
        self._redactor = Redactor(vault_dir, self._scanner)

    def redact(self, text: str, doc_id: str | None = None) -> tuple[str, str | None]:
        """``Sec.redact`` (INV-PII-1) — see ``redact.Redactor.redact``."""
        return self._redactor.redact(text, doc_id)

    def scan(self, text: str) -> Findings:
        """``Sec.scan`` (INV-PII-2) — deterministic, never an LLM."""
        return self._scanner.scan(text)

    def tag(self, ctx: Context) -> Context:
        """``Sec.tag`` (INV-PII-3 input) — sets ``contains_pii``; never clears it."""
        return tag(ctx, self._scanner)

    def checkpoint(self, text: str, doc_id: str | None = None) -> CheckpointResult:
        """The CHECKPOINT pipeline (INV-PII-1/2): redact → independent scan → fail closed."""
        return run_checkpoint(text, doc_id, redactor=self._redactor, scanner=self._scanner)
