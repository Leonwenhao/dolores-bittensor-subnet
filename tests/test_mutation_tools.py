"""Tests for the mutation Fast Path helper scripts.

These exercise scripts/prepare_mutation_task.py and the new validate_task.py
flags. They need the dolores engine (for dedup/load), so this file is
deliberately NOT in the CI public-smoke list in .github/workflows/ci.yml.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PREPARE = REPO_ROOT / "scripts" / "prepare_mutation_task.py"
VALIDATE = REPO_ROOT / "scripts" / "validate_task.py"
HONEST = REPO_ROOT / "examples" / "tasks" / "honest_example"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture
def cleanup_dests() -> Iterator[list[Path]]:
    dests: list[Path] = []
    yield dests
    for dest in dests:
        shutil.rmtree(dest, ignore_errors=True)


def test_prepare_forks_rewrites_id_and_drops_wire(cleanup_dests: list[Path]) -> None:
    dest = REPO_ROOT / "my_task_pytest_fork_me"
    cleanup_dests.append(dest)
    proc = _run([str(PREPARE), "--source", str(HONEST), "--name", "pytest_fork_me"], cwd=REPO_ROOT)
    assert proc.returncode == 0, proc.stderr
    assert dest.is_dir()
    assert not (dest / "wire.json").exists()
    assert (dest / "task.yaml").read_text(encoding="utf-8").startswith("task_id: pytest_fork_me\n")


def test_prepare_rejects_bad_name_and_existing_dir(cleanup_dests: list[Path]) -> None:
    cleanup_dests.append(REPO_ROOT / "my_task_pytest_dup_dir")
    bad = _run([str(PREPARE), "--source", str(HONEST), "--name", "Bad-Name!"], cwd=REPO_ROOT)
    assert bad.returncode == 1
    assert "[a-z0-9_]+" in bad.stdout

    first = _run([str(PREPARE), "--source", str(HONEST), "--name", "pytest_dup_dir"], cwd=REPO_ROOT)
    assert first.returncode == 0, first.stderr
    again = _run([str(PREPARE), "--source", str(HONEST), "--name", "pytest_dup_dir"], cwd=REPO_ROOT)
    assert again.returncode == 1
    assert "already exists" in again.stdout


def test_validate_run_tests_passes_on_honest() -> None:
    proc = _run([str(VALIDATE), "--task-dir", str(HONEST), "--run-tests"], cwd=REPO_ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS --run-tests" in proc.stdout


def test_validate_dedup_flags_a_duplicate() -> None:
    tasks_dir = REPO_ROOT / "examples" / "tasks"
    dup = tasks_dir / "duplicate_example"
    proc = _run(
        [str(VALIDATE), "--task-dir", str(dup), "--dedup-against", str(tasks_dir)],
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 1, proc.stdout
    assert "max duplicate_score = 1.00" in proc.stdout
    assert "ZERO PAY" in proc.stdout
