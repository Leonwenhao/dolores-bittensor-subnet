from __future__ import annotations

import json

import pytest

from dolores_subnet import atomic
from dolores_subnet.atomic import (
    ExclusiveFileLock,
    LockUnavailable,
    append_jsonl_fsync,
    atomic_write_json,
    atomic_write_text,
)


def test_exclusive_lock_is_nonblocking_and_reusable(tmp_path) -> None:
    path = tmp_path / "validator.lock"
    first = ExclusiveFileLock(path)
    second = ExclusiveFileLock(path)

    first.acquire()
    try:
        assert first.held
        with pytest.raises(LockUnavailable, match="already held"):
            second.acquire()
    finally:
        first.release()

    with second:
        assert second.held
    assert not second.held


def test_atomic_write_failure_preserves_previous_file_and_cleans_temp(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "state.json"
    atomic_write_text(path, "old\n")

    def fail_replace(source, destination):  # noqa: ANN001
        del source, destination
        raise OSError("simulated replace crash")

    monkeypatch.setattr(atomic.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace crash"):
        atomic_write_json(path, {"new": True})

    assert path.read_text(encoding="utf-8") == "old\n"
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_jsonl_append_writes_complete_fsynced_records(tmp_path, monkeypatch) -> None:
    path = tmp_path / "submissions.jsonl"
    calls = 0
    real_fsync = atomic.os.fsync

    def recording_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        real_fsync(fd)

    monkeypatch.setattr(atomic.os, "fsync", recording_fsync)
    append_jsonl_fsync(path, {"epoch_id": 1, "task": "a"})
    append_jsonl_fsync(path, {"epoch_id": 1, "task": "b"})

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {"epoch_id": 1, "task": "a"},
        {"epoch_id": 1, "task": "b"},
    ]
    assert calls == 4
