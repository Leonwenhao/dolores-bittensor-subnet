from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from dolores_subnet.chain import NullChain
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


@dataclass
class TerminalMiner:
    hotkey: str
    uid: int
    terminal_status: str
    terminal_reason: str

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del epoch_id, quota
        raise AssertionError("terminal miners should not provide fake payloads")


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


def test_unreachable_terminal_outcome_decays_without_degrading_epoch(tmp_path) -> None:
    cfg = SubnetConfig.from_env(mode="mock", work_dir=tmp_path)
    cfg.archive_dir.mkdir(parents=True, exist_ok=True)
    (cfg.archive_dir / "miner_state.json").write_text('{"down": 0.5}\n', encoding="utf-8")
    miner = TerminalMiner(
        hotkey="down",
        uid=7,
        terminal_status="unreachable",
        terminal_reason="unreachable:Service unavailable at 127.0.0.1:8092",
    )

    result = run_epoch(cfg, [miner], epoch_id=1, quota=2)

    artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in cfg.submissions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[0]["status"] == "unreachable"
    assert rows[0]["package_hash"] is None
    assert "Service unavailable" in rows[0]["reason"]
    assert artifact["degraded"] is False
    assert artifact["epoch_scores"]["down"] == 0.0
    assert artifact["ema_state"]["down"] == 0.35
    assert artifact["weight_result"] == {
        "mode": "fallback",
        "receipt": None,
        "reason": "offline",
    }


def test_default_chain_path_matches_explicit_null_chain(tmp_path) -> None:
    miner = TerminalMiner(
        hotkey="oversized",
        uid=3,
        terminal_status="invalid",
        terminal_reason="response_size:1048577>1048576",
    )
    cfg_default = SubnetConfig.from_env(mode="mock", work_dir=tmp_path / "default")
    cfg_null = SubnetConfig.from_env(mode="mock", work_dir=tmp_path / "null")

    default_result = run_epoch(cfg_default, [miner], epoch_id=1, quota=2)
    null_result = run_epoch(cfg_null, [miner], epoch_id=1, quota=2, chain_client=NullChain())

    default_artifact = json.loads(default_result.artifact_path.read_text(encoding="utf-8"))
    null_artifact = json.loads(null_result.artifact_path.read_text(encoding="utf-8"))
    default_artifact.pop("timing")
    null_artifact.pop("timing")

    assert default_artifact == null_artifact
    assert default_artifact["weight_result"] == {
        "mode": "fallback",
        "receipt": None,
        "reason": "all_zero",
    }
