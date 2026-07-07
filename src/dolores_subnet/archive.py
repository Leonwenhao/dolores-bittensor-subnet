"""Subnet archive helpers around the Dolores ArchiveDB."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    with cfg.submissions_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


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
    destination_db.parent.mkdir(parents=True, exist_ok=True)
    if destination_db.exists():
        destination_db.unlink()
    shutil.copy2(source_db, destination_db)
    import duckdb

    conn = duckdb.connect(str(destination_db))
    try:
        conn.execute("DELETE FROM task_files WHERE file_role = 'hidden_tests'")
    finally:
        conn.close()
    return destination_db


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
