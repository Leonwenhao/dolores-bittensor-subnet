"""Validate a task package locally before serving it as a miner.

Checks everything a participant can verify WITHOUT the validator's Docker
gauntlet: the package loads, converts to a wire submission, respects size
limits, and passes the validator's pre-gates (schema, size, parse, hash).
The Docker verification, wrong-solution probes, cross-miner dedup, and
scoring only happen on the validator.

Two opt-in flags approximate what the validator does, locally:
  --run-tests            run the task's reference against its own public +
                         hidden tests (executes the task's code on this box).
  --dedup-against PATH    score the task's duplicate_score against every task
                         under PATH (repeatable), mirroring archive dedup.

Usage:
    python scripts/validate_task.py --task-dir path/to/my_task
    python scripts/validate_task.py --task-dir path/to/my_task --run-tests
    python scripts/validate_task.py --task-dir my_task --dedup-against examples/tasks
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.config import SubnetConfig  # noqa: E402
from dolores_subnet.gates import GateContext, run_pre_gates  # noqa: E402
from dolores_subnet.packaging import WireError, canonical_size, to_wire  # noqa: E402


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_reference_tests(task) -> bool:  # noqa: ANN001
    """Materialize the task like the engine's verifier and run pytest locally.

    Layout mirrors dolores.verifier.pytest_runner: starter + reference files at
    the workspace root, public tests under tests_public/, hidden under
    tests_hidden/, pytest run with cwd=workspace and PYTHONPATH=workspace.
    """
    print("--run-tests: executing the task's OWN reference code + tests locally.")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for path, content in task.starter_files.items():
            _write_file(root / path, content)
        for path, content in task.reference_files.items():
            _write_file(root / path, content)
        for path, content in task.public_tests.items():
            _write_file(root / "tests_public" / Path(path).name, content)
        for path, content in task.hidden_tests.items():
            _write_file(root / "tests_hidden" / Path(path).name, content)

        env = {**os.environ, "PYTHONPATH": str(root)}
        targets = [d for d in ("tests_public", "tests_hidden") if (root / d).exists()]
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *targets],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        print(proc.stdout.strip() or proc.stderr.strip())
        if proc.returncode != 0:
            print(
                "FAIL --run-tests: reference does not pass its own tests (the "
                "invalid_example failure mode — scores zero)."
            )
            return False
    print("PASS --run-tests: reference passes its public and hidden tests.")
    return True


def run_dedup(task, task_dir: Path, archives: list[str]) -> int:  # noqa: ANN001
    """Score duplicate_score of the task vs every loadable task under archives.

    Returns 0 (ok), 1 (fail >=0.85), leaving WARN for >=0.7 non-fatal.
    """
    try:
        from dolores.schemas.task import TaskPackage
        from dolores.scoring.duplicates import (
            _descriptor_tokens,
            _file_hashes,
            duplicate_report_for_rows,
        )
    except ImportError:
        print("--dedup-against: dedup dry-run unavailable in this engine version.")
        return 0

    dirs: list[Path] = []
    for entry in archives:
        base = Path(entry).expanduser()
        if not base.is_dir():
            continue
        candidates = [base, *sorted(p for p in base.iterdir() if p.is_dir())]
        for cand in candidates:
            if (cand / "task.yaml").is_file() or (cand / "task.yml").is_file():
                dirs.append(cand)

    rows = []
    for cand in dirs:
        if cand.resolve() == task_dir.resolve():
            continue
        try:
            other = TaskPackage.load(cand)
        except Exception:  # noqa: BLE001
            continue
        rows.append(
            {
                "task_id": other.task_id,
                "task_hash": other.stable_hash(),
                "prompt": other.prompt,
                "file_hashes": _file_hashes(other),
                "descriptors": _descriptor_tokens(other),
                "_dir": cand,
            }
        )

    if not rows:
        print("--dedup-against: no other task packages found to compare against.")
        return 0

    print(f"--dedup-against: scoring vs {len(rows)} archived task(s):")
    max_score = 0.0
    for row in rows:
        report = duplicate_report_for_rows(task, [row])
        score = report.duplicate_score
        max_score = max(max_score, score)
        print(f"  {score:.2f}  vs {row['task_id']} ({row['_dir']})")
    print(f"--dedup-against: max duplicate_score = {max_score:.2f}")

    if max_score >= 0.85:
        print(
            f"FAIL --dedup-against: max {max_score:.2f} >= 0.85 -> ZERO PAY at the "
            "validator (>=0.95 is rejected outright). Change the file bytes, "
            "prompt, and descriptors; aim for < 0.7."
        )
        return 1
    if max_score >= 0.7:
        print(
            f"WARN --dedup-against: max {max_score:.2f} >= 0.7 — close to the "
            "review band. Mutate more (aim < 0.7) before serving."
        )
    else:
        print(f"OK --dedup-against: max {max_score:.2f} < 0.7 (safe target).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, help="path to a task package directory")
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="run the reference against its own public + hidden tests (executes code locally)",
    )
    parser.add_argument(
        "--dedup-against",
        action="append",
        default=[],
        metavar="PATH",
        help="archive dir (or parent of dirs) to score duplicate_score against; repeatable",
    )
    args = parser.parse_args()

    task_dir = Path(args.task_dir).expanduser()
    if not task_dir.is_dir():
        print(f"FAIL: not a directory: {task_dir}")
        return 1

    from dolores.schemas.task import TaskPackage

    try:
        task = TaskPackage.load(task_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL load: {exc}")
        return 1
    print(f"PASS load: task_id={task.task_id}")

    try:
        wire = to_wire(task)
    except WireError as exc:
        print(f"FAIL to_wire: {exc}")
        return 1
    print(f"PASS to_wire: {canonical_size(wire)} bytes (hash {wire['package_hash'][:16]}…)")

    cfg = SubnetConfig.from_env(mode="mock")
    decision = run_pre_gates(wire, cfg, GateContext(quota=1), miner_hotkey="self-check")
    for gate, passed in decision.gates.items():
        print(f"{'PASS' if passed else 'FAIL'} gate: {gate}")
    if not decision.passed:
        reason = decision.failure.reason if decision.failure else "unknown"
        print(f"FAIL pre-gates: {reason}")
        return 1

    print(
        "PASS pre-gates. Reminder: the validator still runs the Docker "
        "gauntlet (safety scan, hidden tests, wrong-solution probes, dedup) — "
        "run your own tests against your reference solution before serving."
    )

    exit_code = 0
    if args.run_tests:
        if not run_reference_tests(task):
            exit_code = 1
    if args.dedup_against:
        if run_dedup(task, task_dir, args.dedup_against) != 0:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
