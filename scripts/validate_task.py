"""Validate a task package locally before serving it as a miner.

Checks everything a participant can verify WITHOUT the validator's Docker
gauntlet: the package loads, converts to a wire submission, respects size
limits, and passes the validator's pre-gates (schema, size, parse, hash).
The Docker verification, wrong-solution probes, cross-miner dedup, and
scoring only happen on the validator.

Usage:
    python scripts/validate_task.py --task-dir path/to/my_task
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.config import SubnetConfig  # noqa: E402
from dolores_subnet.gates import GateContext, run_pre_gates  # noqa: E402
from dolores_subnet.packaging import WireError, canonical_size, to_wire  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, help="path to a task package directory")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
