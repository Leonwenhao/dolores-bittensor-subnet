from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from dolores_subnet.config import SubnetConfig
from dolores_subnet.epoch import read_jsonl_tolerating_torn_final
from dolores_subnet.validator_state import ValidatorStateStore

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "tests/support/recurring_tick_worker.py"


def test_two_dry_run_epochs_reproduce_across_fresh_processes(tmp_path) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    results = []
    for _ in range(2):
        completed = subprocess.run(
            [sys.executable, str(WORKER), str(tmp_path)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=True,
        )
        results.append(json.loads(completed.stdout))

    assert [item["epoch_id"] for item in results] == [1, 2]
    assert [item["chain_mode"] for item in results] == ["dry_run", "dry_run"]
    assert all(Path(item["completion_marker"]).is_file() for item in results)

    cfg = SubnetConfig.from_env(
        mode="mock",
        work_dir=tmp_path,
        network="test",
        netuid=523,
    )
    state = ValidatorStateStore(cfg.archive_dir / "validator_runtime").read()
    assert state.last_completed_epoch == 2
    assert state.next_epoch_id == 3
    rows = read_jsonl_tolerating_torn_final(cfg.submissions_path)
    assert [row["epoch_id"] for row in rows] == [1, 2]
