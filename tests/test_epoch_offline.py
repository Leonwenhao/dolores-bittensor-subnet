from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from dolores_subnet.config import SubnetConfig
from dolores_subnet.epoch import assert_replay_matches, run_epoch


@dataclass
class FakeMiner:
    hotkey: str
    uid: int
    values: list[float]

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del epoch_id
        return [
            {
                "schema_version": "dolores-subnet-v0",
                "task_id": f"{self.hotkey}-{index}",
                "package_hash": f"{self.hotkey}-{index}",
                "package": {},
                "family": "test",
                "declared_difficulty": "medium",
                "fake_value": value,
            }
            for index, value in enumerate(self.values[:quota])
        ]


def test_run_epoch_writes_replayable_weight_artifact(tmp_path, monkeypatch) -> None:
    from dolores_subnet import bridge

    def fake_validate(payload, cfg, *, context, miner_hotkey):
        del cfg, context
        return bridge.SubmissionOutcome(
            status="accepted" if payload["fake_value"] else "rejected",
            task_id=payload["task_id"],
            package_hash=payload["package_hash"],
            task_value=payload["fake_value"],
            gates={
                "schema_version": True,
                "size": True,
                "parse": True,
                "hash_match": True,
                "quota": True,
                "epoch_duplicate": True,
            },
            reason="accepted" if payload["fake_value"] else "rejected",
        )

    monkeypatch.setattr(bridge, "validate_submission", fake_validate)
    cfg = SubnetConfig.from_env(mode="mock", work_dir=tmp_path)
    miners = [FakeMiner("honest", 0, [0.9, 0.8]), FakeMiner("invalid", 1, [0.0])]

    result = run_epoch(cfg, miners, epoch_id=1, quota=2)

    artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert artifact["weights"]["honest"] == 1.0
    assert artifact["weights"]["invalid"] == 0.0
    assert "duration_ms" in artifact["timing"]
    assert_replay_matches(cfg, epoch_id=1)
