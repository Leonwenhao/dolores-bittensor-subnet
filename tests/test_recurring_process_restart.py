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
CRASH_AFTER_DURABLE_ROW = r"""
import os
import sys
from pathlib import Path

from dolores_subnet import archive, bridge
from dolores_subnet.config import SubnetConfig
from dolores_subnet.validator_state import ValidatorStateStore

work = Path(sys.argv[1]).resolve()
cfg = SubnetConfig.from_env(
    mode="mock",
    work_dir=work,
    network="test",
    netuid=523,
)
archive.init_archive(cfg)
store = ValidatorStateStore(cfg.archive_dir / "validator_runtime")
with store.tick() as tick:
    assert tick.epoch_id == 1
    tick.mark_querying()
    tick.phase_hook("evaluating")
    partial = bridge.SubmissionOutcome(
        status="accepted",
        task_id="crash-fixture-1",
        package_hash="crash-fixture-hash-1",
        task_value=1.0,
        gates={"fixture": True},
        reason="accepted",
    )
    archive.append_submission(
        cfg,
        partial.to_record(
            epoch_id=tick.epoch_id,
            miner_hotkey="external-fixture-hotkey",
            miner_uid=1,
        ),
    )
    os._exit(73)
"""


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


def test_hard_crash_after_partial_durable_row_advances_without_duplicate(tmp_path) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    crashed = subprocess.run(
        [sys.executable, "-c", CRASH_AFTER_DURABLE_ROW, str(tmp_path)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert crashed.returncode == 73, crashed.stderr
    cfg = SubnetConfig.from_env(
        mode="mock",
        work_dir=tmp_path,
        network="test",
        netuid=523,
    )
    store = ValidatorStateStore(cfg.archive_dir / "validator_runtime")
    interrupted = store.read()
    assert interrupted.active_epoch_id == 1
    assert interrupted.phase == "evaluating"
    assert interrupted.next_epoch_id == 2
    partial_rows = read_jsonl_tolerating_torn_final(cfg.submissions_path)
    assert [(row["epoch_id"], row["task_id"]) for row in partial_rows] == [
        (1, "crash-fixture-1")
    ]

    restarted = subprocess.run(
        [sys.executable, str(WORKER), str(tmp_path)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    result = json.loads(restarted.stdout)

    assert result["epoch_id"] == 2
    assert result["chain_mode"] == "dry_run"
    assert Path(result["completion_marker"]).is_file()
    recovered = store.read()
    assert recovered.last_failed_epoch == 1
    assert recovered.last_completed_epoch == 2
    assert recovered.next_epoch_id == 3
    rows = read_jsonl_tolerating_torn_final(cfg.submissions_path)
    assert [(row["epoch_id"], row["task_id"]) for row in rows] == [
        (1, "crash-fixture-1"),
        (2, "restart-fixture-2"),
    ]
    assert sum(row["epoch_id"] == 1 for row in rows) == 1
