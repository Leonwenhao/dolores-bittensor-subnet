from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from dolores_subnet.config import MAX_SIGNED_REQUEST_TIMEOUT_SECONDS

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_subnet_metadata_pins_engine_and_sdk_with_validator_extra() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    assert project["version"] == "0.2.0rc2"
    assert "bittensor==10.5.0" in project["dependencies"]
    assert "bittensor-cli==9.23.1" in project["dependencies"]
    assert "async-substrate-interface==2.2.1" in project["dependencies"]
    assert "websockets==16.0" in project["dependencies"]
    assert "dolores-autocurricula==0.2.0rc2" in project["dependencies"]
    assert project["optional-dependencies"]["validator"] == [
        "dolores-autocurricula[validator]==0.2.0rc2"
    ]
    assert project["scripts"]["dolores-miner"] == "dolores_subnet.miner_cli:main"


def test_miner_request_timeout_uses_shared_signed_request_policy() -> None:
    from dolores_subnet import miner_cli

    assert miner_cli.MAX_REQUEST_TIMEOUT_SECONDS == MAX_SIGNED_REQUEST_TIMEOUT_SECONDS


def test_miner_cli_import_does_not_load_validator_only_dependencies() -> None:
    code = r"""
import importlib.abc
import sys

blocked = {"duckdb", "streamlit", "pyarrow", "hypothesis", "pytest"}

class BlockValidatorDeps(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            raise AssertionError(f"miner imported validator-only dependency: {fullname}")
        return None

sys.meta_path.insert(0, BlockValidatorDeps())
from dolores_subnet import miner_cli
assert miner_cli.registration_argv(wallet_name="w", wallet_hotkey="h")[3:7] == [
    "--network", "test", "--netuid", "523"
]
print("miner_boundary=ok")
"""
    env = {**os.environ, "PYTHONPATH": "src"}
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "miner_boundary=ok"
