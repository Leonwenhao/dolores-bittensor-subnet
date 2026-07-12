from __future__ import annotations

import json

import pytest

from dolores_subnet import archive
from dolores_subnet.config import SubnetConfig


def _seed_archive(tmp_path):  # noqa: ANN001
    from dolores.archive.db import ArchiveDB
    from dolores.schemas.task import TaskPackage

    cfg = SubnetConfig.from_env(mode="mock", work_dir=tmp_path)
    archive.init_archive(cfg)
    task = TaskPackage.load("examples/tasks/honest_example")
    with ArchiveDB(cfg.archive_db) as db:
        db.add_task(task)
    return cfg


def test_public_copy_uses_consistent_database_copy_and_atomic_publish(tmp_path) -> None:
    cfg = _seed_archive(tmp_path / "source")
    destination = tmp_path / "public" / "archive.duckdb"

    result = archive.public_safe_archive_copy(cfg.archive_db, destination)

    assert result == destination
    import duckdb

    conn = duckdb.connect(str(destination), read_only=True)
    try:
        hidden = conn.execute(
            "SELECT count(*) FROM task_files WHERE file_role = 'hidden_tests'"
        ).fetchone()[0]
        public = conn.execute(
            "SELECT count(*) FROM task_files WHERE file_role = 'public_tests'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert hidden == 0
    assert public > 0
    assert list(destination.parent.glob(".archive.duckdb.*.tmp")) == []


def test_public_copy_failure_preserves_previous_destination(tmp_path, monkeypatch) -> None:
    cfg = _seed_archive(tmp_path / "source")
    destination = tmp_path / "public" / "archive.duckdb"
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps({"old": True}), encoding="utf-8")

    def fail_publish(source, destination_path):  # noqa: ANN001
        del source, destination_path
        raise OSError("simulated publish crash")

    monkeypatch.setattr(archive, "atomic_replace_file", fail_publish)
    with pytest.raises(OSError, match="simulated publish crash"):
        archive.public_safe_archive_copy(cfg.archive_db, destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {"old": True}
    assert list(destination.parent.glob(".archive.duckdb.*.tmp")) == []
