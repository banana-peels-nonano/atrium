"""S9 vector store — LanceDB rows per the docs/33 schema, on ``vectors_dir`` from A1's
``EnvContext`` (memory/API.md "internal wiring"; lancedb==0.34.0 pinned, RISKS R1).

INV-MEM-2 lives here: the store records the embedding-model pin twice — the
``EMBED_MODEL`` marker file (the SAME artifact A1's preflight Check 4 reads, docs/25 §4)
and a per-row ``embed_model`` stamp. ``open()`` on a mismatch raises the reused S2
``EmbedModelMismatch``; the only pin-changing path is the guarded reindex (facade).

INV-MEM-3 shaping: the mutation surface is status flips + row adds + the reindex rebuild.
There is no public delete — ``_remove_unobserved`` exists solely for the write-path
rollback (RISKS R10), called before any reader can observe the row.

Determinism (docs/61 §INV-DET): no LLM, no env read; lancedb + stdlib only.
"""

from __future__ import annotations

from pathlib import Path

import lancedb
import pyarrow as pa

from charterhouse.env.types import EmbedModelMismatch  # one mismatch type across the seam
from charterhouse.memory.types import STATUSES, MemoryEngineError

# The marker file A1 preflight reads (env/preflight.py EMBED_MARKER) — one artifact.
EMBED_MARKER = "EMBED_MODEL"
TABLE = "memory"
_REBUILD_TABLE = "memory_rebuild"

__all__ = ["MemoryStore", "EMBED_MARKER", "EmbedModelMismatch"]


def _schema(dim: int) -> pa.Schema:
    """The docs/33 table schema (frozen shape; the arrow layout is internal)."""
    return pa.schema([
        pa.field("id", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), dim)),
        pa.field("kind", pa.string()),
        pa.field("text", pa.string()),
        pa.field("tags", pa.list_(pa.string())),
        pa.field("venture_id", pa.string()),
        pa.field("segment", pa.string()),
        pa.field("confidence", pa.float64()),
        pa.field("status", pa.string()),
        pa.field("created_active_time", pa.int64()),
        pa.field("source_ref", pa.string()),
        pa.field("embed_model", pa.string()),
    ])


def _table_names(db: "lancedb.DBConnection") -> set[str]:
    """``list_tables()`` returns a response object in lancedb 0.34 — normalize."""
    res = db.list_tables()
    return set(getattr(res, "tables", res) or ())


def _guard_id(lesson_id: str) -> None:
    """Row ids feed SQL-ish where clauses — keep them boring (internal invariant)."""
    if not lesson_id or "'" in lesson_id or '"' in lesson_id:
        raise MemoryEngineError(f"malformed row id (len {len(lesson_id)})")


class MemoryStore:
    """LanceDB-backed row store (docs/33 table schema). Construct via ``open`` /
    ``open_for_reindex`` only."""

    def __init__(self, db: "lancedb.DBConnection", vectors_dir: Path,
                 embed_model: str, dim: int) -> None:
        self._db = db
        self._vectors_dir = vectors_dir
        self._embed_model = embed_model
        self._dim = dim

    # --- construction ----------------------------------------------------------------

    @classmethod
    def open(cls, vectors_dir: Path, embed_model: str, dim: int) -> "MemoryStore":
        """Init-or-verify: a fresh dir is initialized (marker written — the state A1's
        preflight expects); an existing store's recorded pin must equal ``embed_model``
        or ``EmbedModelMismatch`` is raised (never a silent rebuild — INV-MEM-2)."""
        vectors_dir = Path(vectors_dir)
        vectors_dir.mkdir(parents=True, exist_ok=True)
        marker = vectors_dir / EMBED_MARKER
        if marker.is_file():
            built_with = marker.read_text(encoding="utf-8").strip()
            if built_with != embed_model:
                raise EmbedModelMismatch(
                    f"vector index at {vectors_dir} was built with {built_with!r} but "
                    f"the configured embed model is {embed_model!r}; a silent change "
                    f"corrupts retrieval — run a guarded reindex (INV-MEM-2)")
        else:
            marker.write_text(embed_model + "\n", encoding="utf-8")
        store = cls(lancedb.connect(str(vectors_dir)), vectors_dir, embed_model, dim)
        store._table()  # create-if-missing so preflight sees an initialized store
        return store

    @classmethod
    def open_for_reindex(cls, vectors_dir: Path, embed_model: str,
                         dim: int) -> "MemoryStore":
        """The ONE mismatch-tolerant open, for the guarded reindex path only: rows stay
        readable (their redacted texts drive the re-embed); the pin updates only when
        ``rebuild`` completes (facade ``reindex`` — INV-MEM-2)."""
        vectors_dir = Path(vectors_dir)
        if not (vectors_dir / EMBED_MARKER).is_file():
            raise EmbedModelMismatch(
                f"no vector index at {vectors_dir} to reindex (missing {EMBED_MARKER})")
        return cls(lancedb.connect(str(vectors_dir)), vectors_dir, embed_model, dim)

    def _table(self) -> "lancedb.table.Table":
        if TABLE in _table_names(self._db):
            return self._db.open_table(TABLE)
        return self._db.create_table(TABLE, schema=_schema(self._dim))

    # --- the mutation surface (INV-MEM-3: adds + status flips + rebuild ONLY) ---------

    def add(self, row: dict) -> None:
        _guard_id(str(row.get("id", "")))
        self._table().add([row])

    def set_status(self, lesson_id: str, status: str) -> None:
        """The consolidation view mutation (INV-MEM-3): flips ``status`` only."""
        _guard_id(lesson_id)
        if status not in STATUSES:
            raise MemoryEngineError(f"unknown status {status!r}")
        self._table().update(where=f"id = '{lesson_id}'", values={"status": status})

    def rebuild(self, rows: list[dict], embed_model: str) -> None:
        """Temp-table swap used by the guarded reindex: the fully-built new index exists
        on disk before the old table is dropped (a mid-rebuild failure leaves either the
        original or a recoverable temp — never nothing); marker + pin update only on
        success (INV-MEM-2)."""
        dim = len(rows[0]["vector"]) if rows else self._dim
        if _REBUILD_TABLE in _table_names(self._db):
            self._db.drop_table(_REBUILD_TABLE)
        tmp = self._db.create_table(_REBUILD_TABLE, schema=_schema(dim))
        if rows:
            tmp.add(rows)
        if TABLE in _table_names(self._db):
            self._db.drop_table(TABLE)
        final = self._db.create_table(TABLE, schema=_schema(dim))
        if rows:
            final.add(rows)
        self._db.drop_table(_REBUILD_TABLE)
        (self._vectors_dir / EMBED_MARKER).write_text(embed_model + "\n",
                                                      encoding="utf-8")
        self._embed_model = embed_model
        self._dim = dim

    def _remove_unobserved(self, lesson_id: str) -> None:
        """Write-path rollback ONLY (RISKS R10): remove a row whose ``lesson_written``
        append failed, before any reader can observe it. Not part of the view surface."""
        _guard_id(lesson_id)
        self._table().delete(f"id = '{lesson_id}'")

    # --- reads -------------------------------------------------------------------------

    def active_rows(self) -> list[dict]:
        """Rows with ``status == "active"`` — the ONLY retrieval candidate source
        (INV-MEM-1: retired/superseded are excluded before ranking, not after)."""
        return [r for r in self.all_rows() if r["status"] == "active"]

    def all_rows(self) -> list[dict]:
        """Internal (consolidation/reindex). Never exposed through ``Memory.retrieve``."""
        rows = self._table().to_arrow().to_pylist()
        rows.sort(key=lambda r: r["id"])  # deterministic scan order
        return rows

    def count(self) -> int:
        return self._table().count_rows()

    @property
    def embed_model(self) -> str:
        return self._embed_model

    @property
    def dim(self) -> int:
        return self._dim
