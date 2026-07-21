"""Merge gate 9 — the ownership map (docs/63 gate 9; docs/60; docs/51 §ownership).

Every tracked file must map to exactly one owning agent by longest-prefix match — an
orphan (no owner) fails the gate: docs/60 "adding a new file requires assigning an
owner in the same PR". The map below transcribes docs/51 §ownership + the docs/00
manifest's Program-owned areas.

Scope note (honest): the local single-author flow has no PR author identity, so the
"changed paths belong to the authoring agent" half of gate 9 is enforced by review at
the merge gate (the tracker's per-branch subsystem scope); THIS check mechanically
enforces the every-file-has-one-owner half and blocks orphan files.

Usage: python scripts/ownership_check.py <tracked files...>   (exit 0 = gate passes)
"""

from __future__ import annotations

import sys

# Longest-prefix ownership map (docs/51 §ownership; forward slashes as git emits).
OWNERS: tuple[tuple[str, str], ...] = (
    ("charterhouse/env/", "A1"),
    ("charterhouse/config/", "A2"),
    ("charterhouse/contracts/", "A3/Interface"),
    ("charterhouse/ledger/", "A3"),
    ("charterhouse/registry/", "A3"),
    ("charterhouse/lifecycle/", "A4"),
    ("charterhouse/governance/", "A5"),
    ("charterhouse/security/", "A5"),
    ("charterhouse/router/", "A6"),
    ("charterhouse/memory/", "A7"),
    ("charterhouse/capabilities/", "A8"),
    ("adapters/harness/", "A8"),
    ("agents/", "A9"),
    ("charterhouse/conductor/", "A10"),
    ("charterhouse/projections/", "A10"),
    ("charterhouse/logging/", "A11"),
    ("tests/", "A11"),
    ("charterhouse/__init__.py", "A0"),
    ("config/", "A2"),          # the committed YAML config (S3 data)
    ("docs/", "Program"),
    ("scripts/", "Program"),
    ("vault/", "Program"),      # scaffold; runtime content is gitignored/local
    ("templates/", "Program"),
    ("data/", "Program"),
    (".claude/", "Program"),
    (".gitignore", "A0"),
    (".gitattributes", "A0"),
    (".env.example", "A0"),
    ("AGENTS.md", "A0"),
    ("README.md", "A0"),
    ("pyproject.toml", "A0"),
    ("uv.lock", "A0"),
)


def owner_of(path: str) -> str | None:
    best: tuple[int, str] | None = None
    for prefix, owner in OWNERS:
        if path == prefix or path.startswith(prefix):
            if best is None or len(prefix) > best[0]:
                best = (len(prefix), owner)
    return best[1] if best else None


def main(paths: list[str]) -> int:
    orphans = [p for p in paths if owner_of(p) is None]
    if orphans:
        print("[gate 9] files with NO owner (docs/60 — assign in the same PR):")
        for p in orphans:
            print(f"  - {p}")
        return 1
    print(f"[gate 9] ownership OK ({len(paths)} tracked files, every one owned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
