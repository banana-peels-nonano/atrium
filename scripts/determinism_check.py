"""Merge gate 10 — the determinism import check (docs/63 gate 10; docs/61 §INV-DET).

The deterministic subsystems (docs/55 §7: S1–S7, S12–S15 minus the integrator's
composition) may NEVER import the LLM-path packages — ``router``, ``memory`` (the
embed path), ``capabilities`` (the PRODUCE/CRITIQUE path). A deterministic module
acquiring an LLM dependency is an architecture break, not a refactor.

The Conductor (S12) is the documented exception: docs/10 — it *composes* the LLM path
behind the chokepoint while remaining deterministic itself; its INV-COND-1 tests (not
this scan) hold it to call-through.

Usage: python scripts/determinism_check.py   (exit 0 = gate passes)
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = ROOT / "charterhouse"

_IMPORT_RE = re.compile(r"(?:from|import)\s+charterhouse\.(\w+)")

DETERMINISTIC = ("contracts", "config", "env", "ledger", "registry", "governance",
                 "security", "lifecycle", "logging", "projections")
LLM_PATH = frozenset({"router", "memory", "capabilities"})


def main() -> int:
    failures: list[str] = []
    for pkg in DETERMINISTIC:
        for py in sorted((PKG_ROOT / pkg).rglob("*.py")):
            for match in _IMPORT_RE.finditer(py.read_text(encoding="utf-8")):
                if match.group(1) in LLM_PATH:
                    failures.append(
                        f"{pkg}/{py.name}: imports charterhouse.{match.group(1)} — "
                        "a deterministic module may never touch the LLM path "
                        "(INV-DET, docs/61)")
    if failures:
        print("[gate 10] determinism violations:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"[gate 10] determinism OK ({len(DETERMINISTIC)} deterministic packages "
          "clear of router/memory/capabilities)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
