from __future__ import annotations

import json

import pytest

from dolores_subnet.atomic import LockUnavailable, atomic_write_json
from dolores_subnet.chain import ChainWeightResult
from dolores_subnet.config import SubnetConfig
from dolores_subnet.epoch import (
    chain_attempt_path,
    chain_receipt_path,
    write_epoch_completion_marker,
)
from dolores_subnet.validator_state import (
    AmbiguousWeightSubmissionError,
    ReceiptRecoveryRequired,
    StateCorruptionError,
    ValidatorRuntimeState,
    ValidatorStateError,
    ValidatorStateStore,
)


def _cfg(tmp_path) -> SubnetConfig:  # noqa: ANN001
    return SubnetConfig.from_env(mode="mock", work_dir=tmp_path)


def _store(tmp_path) -> ValidatorStateStore:  # noqa: ANN001
    cfg = _cfg(tmp_path)
    return ValidatorStateStore(cfg.archive_dir / "validator_runtime")


def _write_completion(
    tmp_path,
    *,
    epoch_id: int,
    mode: str = "fallback",
    reason: str = "offline",
):  # noqa: ANN001
    cfg = _cfg(tmp_path)
    miner_state = cfg.epoch_dir(epoch_id) / f"miner_state_epoch_{epoch_id}.json"
    weights = cfg.weights_path(epoch_id)
    panel = cfg.solver_panel_path(epoch_id)
    atomic_write_json(cfg.archive_dir / "miner_state.json", {"miner": 1.0})
    atomic_write_json(miner_state, {"miner": 1.0})
    atomic_write_json(
        weights,
        {
            "epoch_id": epoch_id,
            "config": {"quota": 1},
            "epoch_scores": {"miner": 1.0},
            "ema_state": {"miner": 1.0},
            "weights": {"miner": 1.0},
            "weight_result": {"mode": mode, "reason": reason, "receipt": None},
        },
    )
    atomic_write_json(panel, {"epoch_id": epoch_id, "mode": "mock", "tasks": []})
    receipt_summary = None
    if mode != "fallback":
        receipt = chain_receipt_path(cfg.archive_dir, epoch_id)
        atomic_write_json(
            receipt,
            {
                "epoch_id": epoch_id,
                "mode": mode,
                "reason": reason,
                "payload_digest": "abc123",
            },
        )
        receipt_summary = {
            "receipt_file": receipt.name,
            "payload_digest": "abc123",
        }
    if mode == "submitted":
        attempt = chain_attempt_path(cfg.archive_dir, epoch_id)
        atomic_write_json(
            attempt,
            {
                "version": 1,
                "epoch_id": epoch_id,
                "mode": "live_attempt",
                "status": "completed",
                "receipt_file": chain_receipt_path(cfg.archive_dir, epoch_id).name,
            },
        )
    result = ChainWeightResult(mode=mode, reason=reason, receipt=receipt_summary)
    return write_epoch_completion_marker(
        cfg,
        epoch_id=epoch_id,
        chain_result=result,
        miner_state_path=miner_state,
        weights_path=weights,
        panel_path=panel,
    )


def _pending(store: ValidatorStateStore, *, epoch_id: int = 1) -> None:
    atomic_write_json(
        store.state_path,
        ValidatorRuntimeState(
            next_epoch_id=epoch_id + 1,
            active_epoch_id=epoch_id,
            phase="weights_submitting",
            attempt=1,
        ).to_dict(),
    )


def test_tick_persists_phases_and_commits_only_from_verified_marker(tmp_path) -> None:
    store = _store(tmp_path)

    with store.tick() as tick:
        assert tick.epoch_id == 1
        assert tick.mark_querying().phase == "querying"
        tick.phase_hook("evaluating")
        tick.phase_hook("weights_submitting")
        _write_completion(
            tmp_path,
            epoch_id=1,
            mode="dry_run",
            reason="dry_run_ok",
        )
        tick.phase_hook("committed")

    committed = store.read()
    assert committed.last_completed_epoch == 1
    assert committed.next_epoch_id == 2
    assert committed.last_receipt["mode"] == "dry_run"
    assert committed.last_successful_weight_receipt == committed.last_receipt

    with store.tick() as second:
        assert second.epoch_id == 2
        second.phase_hook("evaluating")
        second.phase_hook("weights_submitting")
        _write_completion(tmp_path, epoch_id=2)
        second.phase_hook("committed")
    assert store.read().last_completed_epoch == 2
    assert store.read().last_successful_weight_receipt == committed.last_receipt


def test_pre_evaluation_restart_retries_same_epoch(tmp_path) -> None:
    store = _store(tmp_path)
    with store.tick() as first:
        first.mark_querying()

    with store.tick() as retry:
        assert retry.epoch_id == 1
        assert retry.state.attempt == 2
        retry.phase_hook("evaluating")
        retry.phase_hook("weights_submitting")
        _write_completion(tmp_path, epoch_id=1)
        retry.phase_hook("committed")


def test_evaluation_failure_advances_instead_of_reusing_epoch(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(RuntimeError, match="evaluation crashed"):
        with store.tick() as first:
            first.phase_hook("evaluating")
            raise RuntimeError("evaluation crashed")

    failed = store.read()
    assert failed.active_epoch_id is None
    assert failed.last_failed_epoch == 1
    assert failed.last_error == "evaluation crashed"
    with store.tick() as next_tick:
        assert next_tick.epoch_id == 2


def test_restart_from_durable_evaluating_phase_advances_epoch(tmp_path) -> None:
    store = _store(tmp_path)
    atomic_write_json(
        store.state_path,
        ValidatorRuntimeState(
            next_epoch_id=2,
            active_epoch_id=1,
            phase="evaluating",
            attempt=1,
        ).to_dict(),
    )
    with store.tick() as recovered:
        assert recovered.epoch_id == 2
        assert recovered.state.last_failed_epoch == 1
        assert recovered.state.last_error == "interrupted_during_evaluation"


def test_weights_submitting_without_marker_fails_closed(tmp_path) -> None:
    store = _store(tmp_path)
    _pending(store)

    with pytest.raises(AmbiguousWeightSubmissionError, match="completion marker"):
        with store.tick():
            pass
    assert store.read().phase == "weights_submitting"


def test_receipt_written_before_artifacts_cannot_recover(tmp_path) -> None:
    store = _store(tmp_path)
    _pending(store)
    atomic_write_json(
        store.receipt_path(1),
        {"epoch_id": 1, "mode": "dry_run", "reason": "dry_run_ok"},
    )

    with pytest.raises(AmbiguousWeightSubmissionError, match="before artifacts"):
        store.recover_receipt()
    assert store.read().phase == "weights_submitting"


def test_interrupted_nonlive_receipt_is_failed_safely_on_next_tick(tmp_path) -> None:
    store = _store(tmp_path)
    _pending(store)
    atomic_write_json(
        store.receipt_path(1),
        {"epoch_id": 1, "mode": "dry_run", "reason": "dry_run_ok"},
    )

    with store.tick() as next_tick:
        assert next_tick.epoch_id == 2
        assert next_tick.state.last_failed_epoch == 1
        assert next_tick.state.last_error == (
            "interrupted_after_dry_run_receipt_before_completion"
        )


def test_null_chain_marker_recovery_is_explicit_and_advances(tmp_path) -> None:
    store = _store(tmp_path)
    _pending(store)
    marker = _write_completion(tmp_path, epoch_id=1)

    with pytest.raises(ReceiptRecoveryRequired, match=str(marker)):
        with store.tick():
            pass
    recovered = store.recover_receipt()
    assert recovered.phase == "committed"
    assert recovered.last_completed_epoch == 1
    assert recovered.last_receipt["mode"] == "fallback"
    assert recovered.last_successful_weight_receipt is None
    with store.tick() as next_tick:
        assert next_tick.epoch_id == 2


def test_dry_run_recovery_records_last_successful_receipt(tmp_path) -> None:
    store = _store(tmp_path)
    _pending(store)
    _write_completion(tmp_path, epoch_id=1, mode="dry_run", reason="dry_run_ok")

    recovered = store.recover_receipt()
    assert recovered.last_receipt["mode"] == "dry_run"
    assert recovered.last_receipt["payload_digest"] == "abc123"
    assert recovered.last_successful_weight_receipt == recovered.last_receipt


def test_definite_skipped_completion_recovers_without_becoming_success(tmp_path) -> None:
    store = _store(tmp_path)
    _pending(store)
    _write_completion(tmp_path, epoch_id=1, mode="skipped", reason="rate_limited")

    recovered = store.recover_receipt()
    assert recovered.phase == "committed"
    assert recovered.last_receipt["mode"] == "skipped"
    assert recovered.last_successful_weight_receipt is None


def test_recovery_rejects_artifact_hash_mismatch(tmp_path) -> None:
    store = _store(tmp_path)
    _pending(store)
    _write_completion(tmp_path, epoch_id=1)
    atomic_write_json(_cfg(tmp_path).weights_path(1), {"epoch_id": 1, "tampered": True})

    with pytest.raises(StateCorruptionError, match="hash mismatch"):
        store.recover_receipt()
    assert store.read().phase == "weights_submitting"


def test_ambiguous_live_attempt_is_never_auto_recovered_or_resubmitted(tmp_path) -> None:
    store = _store(tmp_path)
    _pending(store)
    atomic_write_json(
        store.attempt_path(1),
        {
            "version": 1,
            "epoch_id": 1,
            "mode": "live_attempt",
            "status": "ambiguous",
        },
    )

    with pytest.raises(AmbiguousWeightSubmissionError, match="automatic recovery"):
        store.recover_receipt()
    with pytest.raises(AmbiguousWeightSubmissionError, match="automatic recovery"):
        with store.tick():
            pass


def test_definite_pre_submit_failure_can_advance_but_live_attempt_cannot(tmp_path) -> None:
    store = _store(tmp_path)
    with store.tick() as tick:
        tick.phase_hook("evaluating")
        tick.phase_hook("weights_submitting")
        failed = tick.fail_weights("error:rpc_unreachable")
        assert failed.active_epoch_id is None
        assert failed.last_failed_epoch == 1

    with store.tick() as live:
        live.phase_hook("evaluating")
        live.phase_hook("weights_submitting")
        atomic_write_json(
            store.attempt_path(2),
            {
                "version": 1,
                "epoch_id": 2,
                "mode": "live_attempt",
                "status": "started",
            },
        )
        with pytest.raises(AmbiguousWeightSubmissionError, match="cannot be failed"):
            live.fail_weights("transport timeout")


def test_arbitrary_receipt_cannot_replace_verified_receipt(tmp_path) -> None:
    store = _store(tmp_path)
    with store.tick() as tick:
        tick.phase_hook("evaluating")
        tick.phase_hook("weights_submitting")
        _write_completion(tmp_path, epoch_id=1, mode="dry_run", reason="dry_run_ok")
        tick.phase_hook("committed")
        with pytest.raises(ValidatorStateError, match="canonical"):
            tick.record_receipt({"mode": "submitted", "reason": "forged"})


def test_phase_transitions_require_the_locked_tick(tmp_path) -> None:
    tick = _store(tmp_path).tick()
    with pytest.raises(ValidatorStateError, match="active locked tick"):
        tick.transition("querying")


def test_state_store_rejects_a_concurrent_tick_without_blocking(tmp_path) -> None:
    first_store = _store(tmp_path)
    second_store = _store(tmp_path)
    with first_store.tick() as first:
        assert first.epoch_id == 1
        with pytest.raises(LockUnavailable, match="already held"):
            with second_store.tick():
                pass


def test_state_file_corruption_is_not_silently_ignored(tmp_path) -> None:
    store = _store(tmp_path)
    store.state_path.parent.mkdir(parents=True)
    store.state_path.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(StateCorruptionError, match="JSON object"):
        store.read()
