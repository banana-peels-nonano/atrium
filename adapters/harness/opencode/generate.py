"""OpenCode harness generator — the thin CLI entry (docs/31 layout; A8 deliverable).

Regenerates the OpenCode agent files in THIS directory from the neutral specs in
``agents/`` (the single source of truth). Logic lives in
``charterhouse.capabilities.framework.harness_opencode`` (unit-tested there); this
entry only wires paths. Fails loudly (``SpecInvalid``) while the ``agents/*.agent.md``
stubs are empty — A9 fills them in Phase 5.

Usage (from the repo root, in the project venv):
    python adapters/harness/opencode/generate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from charterhouse.capabilities.framework import (
        generate_opencode,
        load_capability_specs,
    )

    specs = load_capability_specs(REPO_ROOT / "agents")
    written = generate_opencode(specs, Path(__file__).resolve().parent)
    for path in written:
        print(f"generated {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
