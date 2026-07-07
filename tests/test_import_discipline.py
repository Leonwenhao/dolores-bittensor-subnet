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

from dolores_subnet.chain import NullChain
from dolores_subnet.config import SubnetConfig

cfg = SubnetConfig.from_env(mode="mock")
result = NullChain().apply_weights(
    cfg=cfg,
    epoch_id=1,
    weights={"miner": 1.0},
    active_hotkeys=["miner"],
    spec_version=cfg.spec_version,
)
assert result.to_record() == {"mode": "fallback", "receipt": None, "reason": "offline"}
"""
    env = {**os.environ, "PYTHONPATH": f"src{os.pathsep}."}

    subprocess.check_call([sys.executable, "-c", code], env=env)
