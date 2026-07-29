""".env loading — the A1 env layer populates the environment from a ``.env`` file at
startup (docs/20 env-boundary: ``charterhouse/env/`` is the sole environment writer, just
as it is the sole reader).

Uses **python-dotenv** — a robust key=value parser, NOT ``bash source``: values are taken
literally, so Windows paths with backslashes (``K:\\the_charter_house``) and ``=`` inside
values survive intact. Existing ``os.environ`` entries win unless ``override`` (a real
environment variable always beats the file). The secret VALUES are never returned, printed,
or logged — only the NAMES loaded are returned, so a caller can report "loaded N vars"
without leaking a key.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["load_env_file"]


def load_env_file(path: str | Path | None = None, *,
                  override: bool = False) -> tuple[str, ...]:
    """Load ``path`` (or the nearest ``.env`` found from the cwd upward) into
    ``os.environ`` and return the variable NAMES loaded, sorted (never the values). A
    missing file is a no-op returning ``()``. Existing environment variables are kept
    unless ``override=True``. Performs no logging — no key value is ever emitted."""
    from dotenv import dotenv_values, find_dotenv, load_dotenv

    target = str(path) if path is not None else find_dotenv(usecwd=True)
    if not target or not Path(target).is_file():
        return ()
    # NAMES only — dotenv_values holds the values transiently but they are never returned,
    # printed, or logged. load_dotenv does the os.environ write (the env-boundary act).
    names = tuple(sorted(dotenv_values(target)))
    load_dotenv(target, override=override)
    return names
