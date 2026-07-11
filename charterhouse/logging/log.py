"""S14 operational logging — ``Log.event`` → structured lines under ``logs_dir``
(logging/API.md, docs/40 §10).

Operational logs go to files (``K:\\Logs\\`` in production, path from ``EnvContext``); this
is a **distinct sink** from telemetry, which goes to the ledger (logging/IMPLEMENTATION §3,
RISKS R6). Secret/PII-shaped fields are redacted before write (docs/24). ``event`` never
raises on a normal log — observability must not take the caller down.

Determinism (docs/61 §INV-DET): stdlib + S7 filter only; no LLM.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from charterhouse.logging.types import Level, filter_fields

_LOG_FILE = "charterhouse.log"


class Log:
    """Structured operational logger. Construct with the ``logs_dir`` an ``EnvContext``
    supplies (``EnvContext.logs_dir``); tests pass a tmp dir directly (no env read here)."""

    def __init__(self, logs_dir: str | Path, *, filename: str = _LOG_FILE) -> None:
        self._dir = Path(logs_dir)
        self._path = self._dir / filename

    def event(self, level: Level, where: str, fields: Mapping) -> None:
        """Write one structured, secret/PII-filtered line (docs/40 §10). Fail-safe: an I/O
        error is swallowed (logging must never break the caller); nothing raw is written."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": Level(level).value,
            "where": where,
            "fields": filter_fields(fields),
        }
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        except OSError:
            return  # fail-safe: never raise on a normal log

    @property
    def path(self) -> Path:
        return self._path
