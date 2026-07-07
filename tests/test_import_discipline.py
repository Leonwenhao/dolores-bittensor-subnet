from __future__ import annotations

import os
import subprocess
import sys


def test_non_wire_modules_import_without_bittensor() -> None:
    code = r"""
import importlib
import importlib.abc


class BlockBittensor(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "bittensor" or fullname.startswith("bittensor."):
            raise AssertionError(f"unexpected bittensor import: {fullname}")
        return None


import sys
sys.meta_path.insert(0, BlockBittensor())

for name in [
    "dolores_subnet.archive",
    "dolores_subnet.bridge",
    "dolores_subnet.chain",
    "dolores_subnet.config",
    "dolores_subnet.epoch",
    "dolores_subnet.gates",
    "dolores_subnet.packaging",
    "dolores_subnet.scoring",
    "neurons.miner",
    "neurons.validator",
]:
    importlib.import_module(name)

from dolores_subnet.chain import NullChain, SubtensorChain
from dolores_subnet.config import SubnetConfig
from tempfile import TemporaryDirectory

tmpdir = TemporaryDirectory()
cfg = SubnetConfig.from_env(mode="mock", work_dir=tmpdir.name)
result = NullChain().apply_weights(
    cfg=cfg,
    epoch_id=1,
    weights={"miner": 1.0},
    active_hotkeys=["miner"],
    spec_version=cfg.spec_version,
)
assert result.to_record() == {"mode": "fallback", "receipt": None, "reason": "offline"}


class FakeSubstrate:
    validator_hotkey = "validator"

    def block(self):
        return 1

    def subnet_exists(self):
        return True

    def hotkey_uid(self, hotkey):
        return {"validator": 0, "miner": 1}.get(hotkey)

    def validator_permit(self, uid):
        return True

    def weights_rate_limit(self):
        return 0

    def blocks_since_last_update(self, uid):
        return 100

    def commit_reveal_enabled(self):
        return False

    def process_and_convert(self, uids, weights):
        return uids, [65535 for _ in weights]

    def set_weights(self, **kwargs):
        raise AssertionError("set_weights must not be called")


dry = SubtensorChain(
    network="test",
    netuid=1,
    wallet_name="dolores-test",
    wallet_hotkey="validator",
    substrate=FakeSubstrate(),
)
dry_result = dry.apply_weights(
    cfg=cfg,
    epoch_id=1,
    weights={"miner": 1.0},
    active_hotkeys=["miner"],
    spec_version=cfg.spec_version,
)
assert dry_result.mode == "dry_run"
tmpdir.cleanup()
"""
    env = {**os.environ, "PYTHONPATH": f"src{os.pathsep}."}

    subprocess.check_call([sys.executable, "-c", code], env=env)
