from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dolores_subnet import bridge
from dolores_subnet.chain import SubtensorChain
from dolores_subnet.config import SubnetConfig
from dolores_subnet.epoch import assert_replay_matches, run_epoch
from dolores_subnet.validator_state import ValidatorStateStore


@dataclass
class Miner:
    hotkey: str = "external-fixture-hotkey"
    uid: int = 1

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del quota
        return [
            {
                "schema_version": "dolores-subnet-v1",
                "task_id": f"restart-fixture-{epoch_id}",
                "package_hash": f"restart-fixture-hash-{epoch_id}",
                "package": {},
                "family": "fixture",
                "declared_difficulty": "medium",
            }
        ]


class DryRunSubstrate:
    validator_hotkey = "validator-hotkey"

    def block(self) -> int:
        return 1000

    def subnet_exists(self) -> bool:
        return True

    def hotkey_uid(self, hotkey: str) -> int | None:
        return {self.validator_hotkey: 0, "external-fixture-hotkey": 1}.get(hotkey)

    def validator_permit(self, uid: int) -> bool:
        return uid == 0

    def weights_rate_limit(self) -> int:
        return 0

    def blocks_since_last_update(self, uid: int) -> int:
        del uid
        return 100

    def commit_reveal_enabled(self) -> bool:
        return False

    def process_and_convert(
        self, uids: list[int], weights: list[float]
    ) -> tuple[list[int], list[int]]:
        return uids, [round(value * 65535) for value in weights]


def fake_validate(
    payload: dict[str, Any],
    cfg: SubnetConfig,
    *,
    context: Any,
    miner_hotkey: str,
    **kwargs: Any,
) -> bridge.SubmissionOutcome:
    del cfg, context, miner_hotkey, kwargs
    return bridge.SubmissionOutcome(
        status="accepted",
        task_id=str(payload["task_id"]),
        package_hash=str(payload["package_hash"]),
        task_value=1.0,
        gates={"fixture": True},
        reason="accepted",
    )


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    cfg = SubnetConfig.from_env(
        mode="mock",
        work_dir=work,
        network="test",
        netuid=523,
    )
    bridge.validate_submission = fake_validate
    chain = SubtensorChain(
        network="test",
        netuid=523,
        wallet_name="unused-fixture-wallet",
        wallet_hotkey="unused-fixture-hotkey",
        publish="dry-run",
        substrate=DryRunSubstrate(),
    )
    store = ValidatorStateStore(cfg.archive_dir / "validator_runtime")
    with store.tick() as tick:
        assert tick.epoch_id is not None
        tick.mark_querying()
        result = run_epoch(
            cfg,
            [Miner()],
            epoch_id=tick.epoch_id,
            quota=1,
            chain_client=chain,
            phase_hook=tick.phase_hook,
        )
    assert_replay_matches(cfg, epoch_id=tick.epoch_id)
    print(
        json.dumps(
            {
                "epoch_id": tick.epoch_id,
                "chain_mode": result.chain_result.mode,
                "completion_marker": str(result.completion_marker_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
