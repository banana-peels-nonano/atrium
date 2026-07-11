"""K:-storage discipline (docs/23) — the path resolver + growing-category guard
(env/IMPLEMENTATION §3).

Growing-data categories (ledger/vectors/cache/logs/weights/backups) MUST live under the
configured K: data root; a target that escapes it fails closed (``KDisciplineError``).
Structural paths are derived from the three env roots. No drive letter is hard-coded — the
"growing root" is injected (K: in production), so the rule is testable on any filesystem.

Determinism (docs/61 §INV-DET): stdlib + contracts only; no LLM; env is read only by the
caller (``preflight``) and injected here as already-resolved paths.
"""

from __future__ import annotations

from pathlib import Path

from charterhouse.contracts.env_context import GROWING_KINDS, PathKind

from charterhouse.env.types import KDisciplineError


def is_within(target: Path, root: Path) -> bool:
    """True iff ``target`` is ``root`` or lives beneath it (normalized; case-insensitive
    on Windows via ``os.path.normcase``)."""
    import os

    t = os.path.normcase(os.path.normpath(str(target)))
    r = os.path.normcase(os.path.normpath(str(root)))
    return t == r or t.startswith(r + os.sep)


def guard_growing(kind: PathKind, target: Path, *, growing_root: Path) -> Path:
    """Return ``target`` for a growing category iff it is within ``growing_root``; else
    ``KDisciplineError`` (docs/23). Structural kinds pass through unchecked."""
    if kind in GROWING_KINDS and not is_within(target, growing_root):
        raise KDisciplineError(
            f"{kind.value} is a growing-data category and must live under the K: data "
            f"root {growing_root} (docs/23); refusing off-root target {target}")
    return target
