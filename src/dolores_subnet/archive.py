"""Subnet archive helpers around the Dolores ArchiveDB."""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dolores_subnet.atomic import append_jsonl_fsync, atomic_replace_file
from dolores_subnet.config import SubnetConfig


def init_archive(cfg: SubnetConfig) -> None:
    from dolores.archive.db import ArchiveDB

    cfg.archive_dir.mkdir(parents=True, exist_ok=True)
    with ArchiveDB(cfg.archive_db) as db:
        db.init()
    cfg.submissions_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.submissions_path.touch(exist_ok=True)


def append_submission(cfg: SubnetConfig, record: dict[str, Any]) -> None:
    cfg.submissions_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _jsonable(record)
    payload.setdefault("created_at", datetime.now(UTC).isoformat())
    append_jsonl_fsync(cfg.submissions_path, payload)


def purge_task(db_path: Path, task_hash: str) -> None:
    import duckdb

    conn = duckdb.connect(str(db_path))
    try:
        for table in (
            "task_files",
            "verification_runs",
            "solver_runs",
            "scores",
            "lineage",
            "tasks",
        ):
            conn.execute(f"DELETE FROM {table} WHERE task_hash = ?", [task_hash])
    finally:
        conn.close()


def public_safe_archive_copy(source_db: Path, destination_db: Path) -> Path:
    """Create a source-consistent sanitized DuckDB and atomically publish it."""

    if source_db.resolve() == destination_db.resolve():
        raise ValueError("public archive destination must differ from the source")
    destination_db.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(
        prefix=f".{destination_db.name}.",
        suffix=".tmp",
        dir=destination_db.parent,
    )
    os.close(fd)
    temp_db = Path(raw_temp)
    temp_db.unlink()
    try:
        import duckdb

        conn = duckdb.connect()
        try:
            conn.execute(f"ATTACH {_sql_literal(source_db)} AS source_db (READ_ONLY)")
            conn.execute(f"ATTACH {_sql_literal(temp_db)} AS public_db")
            conn.execute("COPY FROM DATABASE source_db TO public_db")
            conn.execute("DELETE FROM public_db.task_files WHERE file_role = 'hidden_tests'")
            conn.execute("CHECKPOINT public_db")
            conn.execute("DETACH public_db")
            conn.execute("DETACH source_db")
        finally:
            conn.close()
        os.chmod(temp_db, 0o600)
        return atomic_replace_file(temp_db, destination_db)
    finally:
        temp_db.unlink(missing_ok=True)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _sql_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"
