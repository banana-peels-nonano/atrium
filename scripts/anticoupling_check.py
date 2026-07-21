"""Merge gate 5 — the anti-coupling import check (docs/63 gate 5; docs/43 §5/§8).

The allowed cross-package import DAG, encoded as data. Every ``charterhouse.<pkg>``
reference inside a package must name a package in its allowed set — a forbidden import
(e.g. ``lifecycle`` importing ``router``) fails the merge, mechanically. The table
below is docs/43 §5's boundary rules made exhaustive against the as-built graph
(verified at gate activation, 2026-07-22 — the graph already complied; discipline is
now enforcement).

The Conductor (S12) is the deliberate exception: docs/10/§43 §5 — it imports every
subsystem *interface* (and re-implements no rule; that half is INV-COND-1's tests).

Usage: python scripts/anticoupling_check.py   (exit 0 = gate passes)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = ROOT / "charterhouse"

_IMPORT_RE = re.compile(r"(?:from|import)\s+charterhouse\.(\w+)")

# pkg -> the ONLY charterhouse packages it may import (docs/43 §5, as-built DAG).
# None = unrestricted (the S12 integrator).
ALLOWED: dict[str, set[str] | None] = {
    "contracts": set(),  # shared types: stdlib only (docs/43 §6)
    "config": {"contracts"},
    "env": {"contracts", "config"},
    "ledger": {"contracts"},
    "registry": {"contracts", "ledger"},
    "governance": {"contracts", "ledger"},
    "security": set(),  # deterministic scanner/redactor: stdlib only
    "lifecycle": {"contracts", "governance", "ledger", "registry"},  # never router/memory/capabilities
    "logging": {"contracts", "ledger", "security"},  # S7 scanner reuse (A11, no drift)
    "router": {"contracts", "config", "security", "ledger", "logging"},  # docs/43 §5 verbatim
    "memory": {"contracts", "ledger", "security", "env"},  # env: EmbedModelMismatch reuse (A7)
    "capabilities": {"contracts", "ledger", "memory", "router", "security"},  # no authority: never governance/lifecycle
    "projections": {"contracts", "ledger"},  # pure ledger folds (S13)
    "conductor": None,  # the integrator (docs/10)
}


def main() -> int:
    failures: list[str] = []
    packages = {p.name for p in PKG_ROOT.iterdir()
                if p.is_dir() and not p.name.startswith("__")}
    unmapped = packages - set(ALLOWED)
    for pkg in sorted(unmapped):
        failures.append(f"{pkg}: package has no anti-coupling rule — add it to "
                        "ALLOWED (docs/43 §8)")
    for pkg, allowed in sorted(ALLOWED.items()):
        if allowed is None or pkg not in packages:
            continue
        for py in sorted((PKG_ROOT / pkg).rglob("*.py")):
            for match in _IMPORT_RE.finditer(py.read_text(encoding="utf-8")):
                target = match.group(1)
                if target != pkg and target not in allowed:
                    failures.append(
                        f"{pkg}/{py.name}: imports charterhouse.{target} — "
                        f"forbidden (allowed: {sorted(allowed)}; docs/43 §5)")
    if failures:
        print("[gate 5] anti-coupling violations:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"[gate 5] anti-coupling OK ({len(packages)} packages against the "
          "docs/43 §5 DAG)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
