#!/usr/bin/env python
"""Invariant harness checker (merge gate 2, docs/63; docs/55 §4).

For a given invariant family (default ``INV-SM``, the lifecycle spine now that S5 is real),
verify BOTH:
  1. completeness — every required member (docs/54) has a mapped test in the manifest;
  2. collectability — every mapped node id is actually collectable by pytest (a typo or a
     deleted/renamed test fails the gate rather than passing silently).

Exit 0 iff the family is fully mapped to collectable tests; else 1 with a precise report.

Usage:
    python scripts/invariant_check.py [FAMILY ...]     # default: INV-SM
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.invariants.manifest import (  # noqa: E402
    INVARIANT_MANIFEST,
    family,
    unmapped,
)


def _collectable(node_ids: list[str]) -> tuple[bool, str]:
    """True iff pytest can collect *exactly* the given node ids (each must resolve to one
    test). One invocation — robust across pytest output-format changes."""
    if not node_ids:
        return True, ""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "--no-header", "-p", "no:cacheprovider", *node_ids],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr)


def check_family(prefix: str) -> list[str]:
    """Return a list of problems for one family (empty = OK)."""
    problems: list[str] = []
    required = family(prefix)
    if not required:
        return [f"{prefix}: unknown invariant family"]
    for miss in unmapped(required):
        problems.append(f"{miss}: UNMAPPED — no test in the manifest (docs/55 §4)")
    # Fast path: collect the whole family in one invocation. Only if that fails do we
    # re-check per node to pinpoint the offender (keeps the gate fast when green).
    all_nodes = [n for inv in required for n in INVARIANT_MANIFEST.get(inv, ())]
    ok, _out = _collectable(all_nodes)
    if not ok:
        for inv in required:
            for node in INVARIANT_MANIFEST.get(inv, ()):
                node_ok, _ = _collectable([node])
                if not node_ok:
                    problems.append(f"{inv}: mapped test not collectable -> {node}")
    return problems


def main(argv: list[str]) -> int:
    families = argv[1:] or ["INV-SM"]
    all_problems: list[str] = []
    for prefix in families:
        probs = check_family(prefix)
        status = "OK" if not probs else "FAIL"
        mapped = sum(len(INVARIANT_MANIFEST.get(i, ())) for i in family(prefix))
        print(f"[invariant-harness] {prefix}: {status} "
              f"({len(family(prefix))} invariants, {mapped} mapped tests)")
        all_problems.extend(probs)
    if all_problems:
        print("INVARIANT HARNESS FAILED (merge gate 2, docs/63 / docs/55 sec 4):",
              file=sys.stderr)
        for p in all_problems:
            print("  " + p, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
