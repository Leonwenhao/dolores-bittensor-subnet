from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from dolores_subnet import epoch
from dolores_subnet.config import SubnetConfig
from dolores_subnet.validator_state import ValidatorStateStore


@dataclass
class TerminalMiner:
    hotkey: str = "offline-miner"
    uid: int = 4
    terminal_status: str = "unreachable"
    terminal_reason: str = "offline fixture"

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del epoch_id, quota
        raise AssertionError("terminal miner must not submit payloads")


def test_run_epoch_emits_durable_phases_and_exposes_chain_result(
    tmp_path, monkeypatch
) -> None:
    cfg = SubnetConfig.from_env(mode="mock", work_dir=tmp_path)
    phases: list[str] = []
    writes: list[str] = []
    real_atomic_write = epoch.atomic_write_json

    def recording_write(path, payload):  # noqa: ANN001
        writes.append(str(path))
        return real_atomic_write(path, payload)

    monkeypatch.setattr(epoch, "atomic_write_json", recording_write)
    result = epoch.run_epoch(
        cfg,
        [TerminalMiner()],
        epoch_id=7,
        quota=1,
        phase_hook=phases.append,
    )

    assert phases == ["evaluating", "weights_submitting", "committed"]
    assert result.chain_result.mode == "fallback"
    assert result.chain_result.reason == "all_zero"
    assert str(cfg.archive_dir / "miner_state.json") in writes
    assert str(cfg.epoch_dir(7) / "miner_state_epoch_7.json") in writes
    assert str(cfg.weights_path(7)) in writes
    assert str(cfg.solver_panel_path(7)) in writes
    assert str(epoch.completion_marker_path(cfg.archive_dir, 7)) in writes
    assert writes.index(str(cfg.archive_dir / "miner_state.json")) > writes.index(
        str(epoch.completion_marker_path(cfg.archive_dir, 7))
    )
    assert writes.index(str(cfg.epoch_dir(7) / "miner_state_epoch_7.json")) < writes.index(
        str(epoch.completion_marker_path(cfg.archive_dir, 7))
    )
    assert writes.index(str(cfg.weights_path(7))) < writes.index(
        str(epoch.completion_marker_path(cfg.archive_dir, 7))
    )
    assert writes.index(str(cfg.solver_panel_path(7))) < writes.index(
        str(epoch.completion_marker_path(cfg.archive_dir, 7))
    )
    artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert artifact["weight_result"] == result.chain_result.to_record()
    verified = epoch.verify_epoch_completion(cfg.archive_dir, 7)
    assert verified["mode"] == "fallback"
    assert verified["epoch_id"] == 7
    # The mutable current EMA state may advance on later epochs; the marker
    # binds an epoch-scoped snapshot and remains independently verifiable.
    (cfg.archive_dir / "miner_state.json").write_text(
        '{"later-miner": 0.5}\n',
        encoding="utf-8",
    )
    assert epoch.verify_epoch_completion(cfg.archive_dir, 7)["epoch_id"] == 7


def test_null_chain_crash_after_marker_before_state_commit_is_recoverable(
    tmp_path,
) -> None:
    cfg = SubnetConfig.from_env(mode="mock", work_dir=tmp_path)
    store = ValidatorStateStore(cfg.archive_dir / "validator_runtime")

    with pytest.raises(RuntimeError, match="crash after marker"):
        with store.tick() as tick:
            assert tick.epoch_id == 1

            def crash_on_commit(phase: str) -> None:
                if phase == "committed":
                    raise RuntimeError("crash after marker")
                tick.phase_hook(phase)

            epoch.run_epoch(
                cfg,
                [TerminalMiner()],
                epoch_id=1,
                quota=1,
                phase_hook=crash_on_commit,
            )

    assert store.read().phase == "weights_submitting"
    assert epoch.completion_marker_path(cfg.archive_dir, 1).is_file()
    recovered = store.recover_receipt()
    assert recovered.phase == "committed"
    assert recovered.last_completed_epoch == 1
    assert recovered.last_receipt["mode"] == "fallback"


def test_jsonl_reader_ignores_only_torn_unterminated_final_line(tmp_path) -> None:
    path = tmp_path / "submissions.jsonl"
    path.write_bytes(b'{"epoch_id": 1}\n{"epoch_id": 2')

    assert epoch.read_jsonl_tolerating_torn_final(path) == [{"epoch_id": 1}]


def test_jsonl_tail_is_repaired_before_future_appends_can_bury_it(tmp_path) -> None:
    path = tmp_path / "submissions.jsonl"
    path.write_bytes(b'{"epoch_id": 1}\n{"epoch_id": 2')

    assert epoch.repair_jsonl_tail(path) is True
    assert path.read_bytes() == b'{"epoch_id": 1}\n'
    with path.open("ab") as handle:
        handle.write(b'{"epoch_id": 3}\n')
    assert epoch.read_jsonl_tolerating_torn_final(path) == [
        {"epoch_id": 1},
        {"epoch_id": 3},
    ]


@pytest.mark.parametrize(
    "payload",
    [
        b'{"epoch_id": 1}\nnot-json\n{"epoch_id": 2}\n',
        b'{"epoch_id": 1}\nnot-json\n',
    ],
)
def test_jsonl_reader_rejects_interior_or_terminated_corruption(
    tmp_path,
    payload,
) -> None:
    path = tmp_path / "submissions.jsonl"
    path.write_bytes(payload)

    with pytest.raises(ValueError, match="corrupt JSONL record at line 2"):
        epoch.read_jsonl_tolerating_torn_final(path)
