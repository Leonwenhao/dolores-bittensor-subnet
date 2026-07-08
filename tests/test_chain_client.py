from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from dolores_subnet.chain import LIVE_CONFIRMATION, NullChain, SubtensorChain, _Substrate
from dolores_subnet.config import SubnetConfig
from dolores_subnet.epoch import assert_replay_matches, run_epoch


class FakeSubstrate:
    validator_hotkey = "validator-hotkey"

    def __init__(
        self,
        *,
        hotkey_uids: dict[str, int] | None = None,
        subnet_exists: bool = True,
        permit: bool = True,
        rate_limit: int = 0,
        blocks_since: int | None = 100,
        commit_reveal: bool = False,
        set_success: bool = True,
    ) -> None:
        self.hotkey_uids = hotkey_uids or {
            self.validator_hotkey: 10,
            "miner-a": 1,
            "miner-b": 2,
        }
        self.subnet_exists_value = subnet_exists
        self.permit = permit
        self.rate_limit = rate_limit
        self.blocks_since = blocks_since
        self.commit_reveal = commit_reveal
        self.set_success = set_success
        self.set_weights_calls: list[dict[str, Any]] = []

    def block(self) -> int:
        return 1234

    def subnet_exists(self) -> bool:
        return self.subnet_exists_value

    def hotkey_uid(self, hotkey: str) -> int | None:
        return self.hotkey_uids.get(hotkey)

    def validator_permit(self, uid: int) -> bool:
        del uid
        return self.permit

    def weights_rate_limit(self) -> int:
        return self.rate_limit

    def blocks_since_last_update(self, uid: int) -> int | None:
        del uid
        return self.blocks_since

    def commit_reveal_enabled(self) -> bool:
        return self.commit_reveal

    def process_and_convert(
        self,
        uids: list[int],
        weights: list[float],
    ) -> tuple[list[int], list[int]]:
        return uids, [round(weight * 65535) for weight in weights]

    def set_weights(
        self,
        *,
        uids: list[int],
        weights: list[int],
        version_key: int,
    ) -> dict[str, Any]:
        call = {"uids": uids, "weights": weights, "version_key": version_key}
        self.set_weights_calls.append(call)
        return {
            "success": self.set_success,
            "message": "ok" if self.set_success else "boom",
            "block_hash": "0xblock" if self.set_success else None,
            "extrinsic_hash": "0xxt" if self.set_success else None,
            "included": self.set_success,
            "finalized": False,
        }

    def read_back_weights(self, validator_uid: int) -> dict[str, Any]:
        return {"validator_uid": validator_uid, "matches_submitted": True}


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


def _cfg(tmp_path, *, netuid: int | None = 7) -> SubnetConfig:
    return SubnetConfig.from_env(mode="testnet", work_dir=tmp_path, netuid=netuid)


def _chain(
    fake: FakeSubstrate,
    *,
    netuid: int | None = 7,
    publish: str = "dry-run",
) -> SubtensorChain:
    return SubtensorChain(
        network="test",
        netuid=netuid,
        wallet_name="dolores-test",
        wallet_hotkey="validator",
        publish=publish,
        substrate=fake,
    )


def _apply(chain: SubtensorChain, cfg: SubnetConfig, *, weights: dict[str, float] | None = None):
    resolved_weights = weights or {"miner-a": 0.75, "miner-b": 0.25}
    return chain.apply_weights(
        cfg=cfg,
        epoch_id=1,
        weights=resolved_weights,
        active_hotkeys=list(resolved_weights),
        spec_version=cfg.spec_version,
    )


def _receipt(cfg: SubnetConfig) -> dict[str, Any]:
    return json.loads(
        (cfg.epoch_dir(1) / "chain_receipt_epoch_1.json").read_text(encoding="utf-8")
    )


def test_null_chain_record_remains_unchanged(tmp_path) -> None:
    cfg = _cfg(tmp_path)

    result = NullChain().apply_weights(
        cfg=cfg,
        epoch_id=1,
        weights={"miner": 1.0},
        active_hotkeys=["miner"],
        spec_version=cfg.spec_version,
    )

    assert result.to_record() == {"mode": "fallback", "receipt": None, "reason": "offline"}


def test_dry_run_computes_receipt_without_calling_set_weights(tmp_path) -> None:
    fake = FakeSubstrate()
    cfg = _cfg(tmp_path)

    result = _apply(_chain(fake), cfg, weights={"miner-a": 0.75, "miner-b": 0.25, "missing": 0.1})

    assert result.mode == "dry_run"
    assert result.reason == "dry_run_ok"
    assert fake.set_weights_calls == []
    assert result.receipt == {
        "receipt_file": "chain_receipt_epoch_1.json",
        "payload_digest": result.receipt["payload_digest"],
        "netuid": 7,
        "n_uids": 2,
    }
    receipt = _receipt(cfg)
    assert receipt["submission"] is None
    assert receipt["read_back"] is None
    assert receipt["active_hotkey_to_uid"] == {"miner-a": 1, "miner-b": 2}
    assert receipt["dropped_hotkeys"] == ["missing"]
    assert receipt["payload"]["uids_emitted"] == [1, 2]
    assert receipt["payload_digest"] == result.receipt["payload_digest"]


def test_netuid_unset_records_error_without_substrate_call(tmp_path) -> None:
    fake = FakeSubstrate()
    cfg = _cfg(tmp_path, netuid=None)

    result = _apply(_chain(fake, netuid=None), cfg)

    assert result.to_record()["mode"] == "error"
    assert result.reason == "netuid_unset"
    assert fake.set_weights_calls == []


def test_netuid_absent_records_error(tmp_path) -> None:
    fake = FakeSubstrate(subnet_exists=False)
    cfg = _cfg(tmp_path)

    result = _apply(_chain(fake), cfg)

    assert result.mode == "error"
    assert result.reason == "netuid_absent"
    assert fake.set_weights_calls == []


def test_validator_missing_records_validator_unregistered(tmp_path) -> None:
    fake = FakeSubstrate(hotkey_uids={"miner-a": 1})
    cfg = _cfg(tmp_path)

    result = _apply(_chain(fake), cfg)

    assert result.mode == "error"
    assert result.reason == "validator_unregistered"
    assert fake.set_weights_calls == []


def test_no_permit_skips_without_set_weights(tmp_path) -> None:
    fake = FakeSubstrate(permit=False)
    cfg = _cfg(tmp_path)

    result = _apply(_chain(fake), cfg)

    assert result.mode == "skipped"
    assert result.reason == "no_permit"
    assert fake.set_weights_calls == []


def test_no_registered_miners_skips_and_records_dropped_hotkeys(tmp_path) -> None:
    fake = FakeSubstrate(hotkey_uids={FakeSubstrate.validator_hotkey: 10})
    cfg = _cfg(tmp_path)

    result = _apply(_chain(fake), cfg)

    assert result.mode == "skipped"
    assert result.reason == "no_registered_miners"
    receipt = _receipt(cfg)
    assert receipt["dropped_hotkeys"] == ["miner-a", "miner-b"]
    assert fake.set_weights_calls == []


def test_rate_limited_skips_without_set_weights(tmp_path) -> None:
    fake = FakeSubstrate(rate_limit=100, blocks_since=12)
    cfg = _cfg(tmp_path)

    result = _apply(_chain(fake), cfg)

    assert result.mode == "skipped"
    assert result.reason == "rate_limited"
    assert fake.set_weights_calls == []


def test_commit_reveal_enabled_skips_without_set_weights(tmp_path) -> None:
    fake = FakeSubstrate(commit_reveal=True)
    cfg = _cfg(tmp_path)

    result = _apply(_chain(fake), cfg)

    assert result.mode == "skipped"
    assert result.reason == "commit_reveal_enabled"
    assert fake.set_weights_calls == []


def test_substrate_detects_current_sdk_commit_reveal_method() -> None:
    class FakeSubtensor:
        def commit_reveal_enabled(self, *, netuid: int) -> bool:
            assert netuid == 7
            return True

    substrate = object.__new__(_Substrate)
    substrate.subtensor = FakeSubtensor()
    substrate.netuid = 7

    assert substrate.commit_reveal_enabled() is True


def test_all_zero_and_all_infra_reasons_skip(tmp_path) -> None:
    fake = FakeSubstrate()
    cfg_zero = _cfg(tmp_path / "zero")
    cfg_infra = _cfg(tmp_path / "infra")

    zero = _chain(fake).apply_weights(
        cfg=cfg_zero,
        epoch_id=1,
        weights={"miner-a": 0.0},
        active_hotkeys=["miner-a"],
        spec_version=cfg_zero.spec_version,
        fallback_reason="all_zero",
    )
    infra = _chain(fake).apply_weights(
        cfg=cfg_infra,
        epoch_id=1,
        weights={"miner-a": 1.0},
        active_hotkeys=["miner-a"],
        spec_version=cfg_infra.spec_version,
        fallback_reason="epoch_degraded_all_infra",
    )

    assert zero.mode == "skipped"
    assert zero.reason == "all_zero"
    assert infra.mode == "skipped"
    assert infra.reason == "epoch_degraded_all_infra"
    assert fake.set_weights_calls == []


def test_live_gates_block_set_weights_until_all_layers_are_present(tmp_path, monkeypatch) -> None:
    fake = FakeSubstrate()
    cfg_blocked = _cfg(tmp_path / "blocked")
    blocked = SubtensorChain(
        network="test",
        netuid=7,
        wallet_name="dolores-test",
        wallet_hotkey="validator",
        publish="live",
        allow_extrinsics=True,
        confirmation=LIVE_CONFIRMATION,
        substrate=fake,
    ).apply_weights(
        cfg=cfg_blocked,
        epoch_id=1,
        weights={"miner-a": 1.0},
        active_hotkeys=["miner-a"],
        spec_version=cfg_blocked.spec_version,
    )

    assert blocked.mode == "error"
    assert blocked.reason == "extrinsics_not_allowed"
    assert fake.set_weights_calls == []

    cfg_live = _cfg(tmp_path / "live")
    monkeypatch.setenv("DOLORES_ALLOW_EXTRINSICS", "1")
    live = SubtensorChain(
        network="test",
        netuid=7,
        wallet_name="dolores-test",
        wallet_hotkey="validator",
        publish="live",
        allow_extrinsics=True,
        confirmation=LIVE_CONFIRMATION,
        substrate=fake,
    ).apply_weights(
        cfg=cfg_live,
        epoch_id=1,
        weights={"miner-a": 1.0},
        active_hotkeys=["miner-a"],
        spec_version=cfg_live.spec_version,
    )

    assert live.mode == "submitted"
    assert live.reason == "submitted_ok"
    assert len(fake.set_weights_calls) == 1


def test_live_extrinsic_failure_is_recorded_with_fake_substrate(tmp_path, monkeypatch) -> None:
    fake = FakeSubstrate(set_success=False)
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("DOLORES_ALLOW_EXTRINSICS", "1")

    result = SubtensorChain(
        network="test",
        netuid=7,
        wallet_name="dolores-test",
        wallet_hotkey="validator",
        publish="live",
        allow_extrinsics=True,
        confirmation=LIVE_CONFIRMATION,
        substrate=fake,
    ).apply_weights(
        cfg=cfg,
        epoch_id=1,
        weights={"miner-a": 1.0},
        active_hotkeys=["miner-a"],
        spec_version=cfg.spec_version,
    )

    assert result.mode == "error"
    assert result.reason == "extrinsic_failed"
    assert len(fake.set_weights_calls) == 1


def test_receipt_file_is_separate_and_replay_stays_stable(tmp_path, monkeypatch) -> None:
    from dolores_subnet import bridge

    def fake_validate(payload, cfg, *, context, miner_hotkey):
        del cfg, context, miner_hotkey
        return bridge.SubmissionOutcome(
            status="accepted",
            task_id=payload["task_id"],
            package_hash=payload["package_hash"],
            task_value=payload["fake_value"],
            gates={"schema_version": True},
            reason="accepted",
        )

    monkeypatch.setattr(bridge, "validate_submission", fake_validate)
    cfg = _cfg(tmp_path)
    fake = FakeSubstrate()
    miner = FakeMiner("miner-a", 1, [1.0])

    result = run_epoch(
        cfg,
        [miner],
        epoch_id=1,
        quota=1,
        chain_client=_chain(fake),
    )

    artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert artifact["weight_result"]["mode"] == "dry_run"
    assert artifact["weight_result"]["receipt"] == {
        "receipt_file": "chain_receipt_epoch_1.json",
        "payload_digest": artifact["weight_result"]["receipt"]["payload_digest"],
        "netuid": 7,
        "n_uids": 1,
    }
    assert "chain_state" not in artifact["weight_result"]["receipt"]
    assert (cfg.epoch_dir(1) / "chain_receipt_epoch_1.json").exists()
    assert_replay_matches(cfg, epoch_id=1)


def test_preflight_chain_readiness_is_read_only(tmp_path) -> None:
    from scripts.preflight import chain_readiness_check

    fake = FakeSubstrate()
    cfg = _cfg(tmp_path)

    status, detail = chain_readiness_check(cfg, substrate=fake)

    assert status == "PASS"
    assert '"reason": "ok"' in detail
    assert fake.set_weights_calls == []


def test_preflight_chain_reachability_uses_current_subtensor_constructor(
    monkeypatch,
    tmp_path,
) -> None:
    from scripts.preflight import chain_reachability_check

    calls: list[str] = []

    class FakeSubtensor:
        def __init__(self, *, network: str) -> None:
            calls.append(network)
            self.block = 42

    monkeypatch.setitem(sys.modules, "bittensor", SimpleNamespace(Subtensor=FakeSubtensor))
    cfg = SubnetConfig.from_env(
        mode="localnet",
        work_dir=tmp_path,
        network="ws://127.0.0.1:9944",
    )

    status, detail = chain_reachability_check(cfg)

    assert status == "PASS"
    assert detail == "ws://127.0.0.1:9944 block=42"
    assert calls == ["ws://127.0.0.1:9944"]
