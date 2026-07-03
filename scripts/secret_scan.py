#!/usr/bin/env python
"""Deterministic build-time secret / PII-sidecar scanner (merge gates 6 & 7, docs/63).

This is a *build tooling* gate that blocks secrets or local-only PII sidecars from
entering a commit. It is rule-based (regex only) — never an LLM — mirroring the
product's own determinism rule for the PII path (docs/24). It is independent of the
runtime Security subsystem (S7), which it does not import.

Usage:
    python scripts/secret_scan.py [path ...]      # scan given paths (default: staged files)
Exit code 0 = clean, 1 = violation found.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Files that must never be committed at all.
FORBIDDEN_NAMES = (
    re.compile(r"\.private\.md$"),          # local-only PII sidecars (INV-PII-4)
    re.compile(r"(^|/)\.env$"),             # real secrets file
    re.compile(r"(^|/)\.env\.[^/]*$"),      # .env.local etc. (but not .env.example)
)
FORBIDDEN_ALLOW = (re.compile(r"(^|/)\.env\.example$"),)

# Secret value patterns (high-signal, low false-positive).
SECRET_PATTERNS = [
    ("openai/anthropic key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("openrouter key", re.compile(r"\bsk-or-[A-Za-z0-9_\-]{20,}\b")),
    ("groq key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("aws access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    # `KEY = "value"` style assignments with a non-empty, non-placeholder value.
    (
        "assigned secret",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"]?"
            r"(?!\s*$)(?!your|placeholder|xxx|changeme|<)[^\s'\"]{12,}"
        ),
    ),
]

TEXT_SUFFIXES = {
    ".py", ".md", ".yaml", ".yml", ".toml", ".txt", ".json", ".cfg",
    ".ini", ".sh", ".ps1", ".env", ".example",
}


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, check=False,
    )
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def is_forbidden(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    if any(a.search(norm) for a in FORBIDDEN_ALLOW):
        return False
    return any(f.search(norm) for f in FORBIDDEN_NAMES)


def scan_content(path: Path) -> list[str]:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    hits = []
    for label, pat in SECRET_PATTERNS:
        for m in pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{path}:{line}: possible {label}")
    return hits


def main(argv: list[str]) -> int:
    targets = argv[1:] or staged_files()
    violations: list[str] = []
    for rel in targets:
        if is_forbidden(rel):
            violations.append(f"{rel}: forbidden file must never be committed (secret/PII sidecar)")
            continue
        p = Path(rel)
        if p.is_file():
            violations.extend(scan_content(p))
    if violations:
        print("SECRET/PII SCAN FAILED (merge gates 6 & 7, docs/63):", file=sys.stderr)
        for v in violations:
            print("  " + v, file=sys.stderr)
        return 1
    print("secret/PII scan: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
