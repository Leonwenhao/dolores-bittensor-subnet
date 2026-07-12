from __future__ import annotations

import json

from dolores_subnet import chain
from dolores_subnet.chain import SubtensorChain
from dolores_subnet.config import SubnetConfig


class EndpointSubstrate:
    validator_hotkey = "validator-hotkey"

    def __init__(self) -> None:
        self.endpoints = [
            {"host": "8.8.8.8", "port": 8091, "hotkey": "public", "uid": 1},
            {"host": "192.168.1.5", "port": 8092, "hotkey": "lan", "uid": 2},
            {"host": "127.0.0.1", "port": 8093, "hotkey": "loopback", "uid": 3},
            {"host": "not-an-ip", "port": 8094, "hotkey": "hostname", "uid": 4},
        ]

    def miner_endpoints(self, *, exclude_hotkey: str):  # noqa: ANN201
        assert exclude_hotkey == self.validator_hotkey
        return list(self.endpoints)


def _chain(network: str, substrate: EndpointSubstrate) -> SubtensorChain:
    return SubtensorChain(
        network=network,
        netuid=523,
        wallet_name="unused",
        wallet_hotkey="unused",
        substrate=substrate,
    )


def test_public_testnet_discovery_filters_non_global_ipv4() -> None:
    endpoints = _chain("test", EndpointSubstrate()).miner_endpoints()

    assert endpoints == [
        {"host": "8.8.8.8", "port": 8091, "hotkey": "public", "uid": 1}
    ]


def test_localnet_discovery_retains_private_fixture_addresses() -> None:
    endpoints = _chain("ws://127.0.0.1:9944", EndpointSubstrate()).miner_endpoints()

    assert [endpoint["hotkey"] for endpoint in endpoints] == [
        "public",
        "lan",
        "loopback",
        "hostname",
    ]


def test_chain_receipts_use_atomic_json_writer(tmp_path, monkeypatch) -> None:
    cfg = SubnetConfig.from_env(mode="testnet", work_dir=tmp_path, netuid=523)
    substrate = EndpointSubstrate()
    client = _chain("test", substrate)
    calls: list[str] = []
    real_write = chain.atomic_write_json

    def recording_write(path, payload):  # noqa: ANN001
        calls.append(str(path))
        return real_write(path, payload)

    monkeypatch.setattr(chain, "atomic_write_json", recording_write)
    summary = client._write_receipt(
        cfg,
        epoch_id=9,
        mode="dry_run",
        reason="dry_run_ok",
        weights={"public": 1.0},
        active_hotkeys=["public"],
        spec_version=cfg.spec_version,
    )

    receipt_path = cfg.epoch_dir(9) / summary["receipt_file"]
    assert calls == [str(receipt_path)]
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["epoch_id"] == 9
