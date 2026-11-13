"""Deterministic register writer and canonical dump (L1 §5.6, §7; NFR-2)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import Any

Row = Sequence[Any]
TABLES = (
    "source_document", "ingredient", "product", "product_ingredient", "crop", "crop_alias", "use_record",
    "use_record_pest", "restriction", "anomaly",
)  # fmt: skip


def schema() -> str:
    return resources.files("labelclaim.register").joinpath("schema.sql").read_text(encoding="utf-8")


def write(path: Path, tables: Mapping[str, Iterable[Row]], info: Mapping[str, str]) -> str:
    """Write a fresh register file; return the build hash (SHA-256 of the canonical dump)."""
    tmp = path.with_suffix(".partial")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(schema())
        for table in TABLES:
            rows = list(tables.get(table, ()))
            if rows:
                marks = ",".join("?" * len(rows[0]))
                conn.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)  # noqa: S608 - fixed names
        build_hash = canonical_hash(conn)
        conn.executemany(
            "INSERT INTO build_info VALUES (?, ?)", sorted({**info, "build_hash": build_hash}.items())
        )
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()
    tmp.replace(path)
    return build_hash


def canonical_dump(conn: sqlite3.Connection) -> Iterable[str]:
    """Every row of every data table, ordered by all columns, as JSON lines (build_info excluded)."""
    for table in TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        order = ", ".join(cols)
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order}"):  # noqa: S608 - fixed names
            yield json.dumps([table, *row], ensure_ascii=False, separators=(",", ":"))


def canonical_hash(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for line in canonical_dump(conn):
        digest.update(line.encode("utf-8") + b"\n")
    return digest.hexdigest()


def open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True, check_same_thread=True)
