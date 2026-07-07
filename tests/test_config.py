from __future__ import annotations

import pytest

from dolores_subnet.config import (
    EMA_ALPHA,
    MAX_PACKAGE_BYTES,
    SPEC_VERSION,
    Mode,
    NetworkSafetyError,
    SubnetConfig,
    assert_safe_network,
    resolve_netuid,
    resolve_network,
)


def test_resolve_network_allows_only_explicit_testnet() -> None:
    assert resolve_network("testnet") == "test"
    assert resolve_network(Mode.LOCALNET) == "ws://127.0.0.1:9944"


@pytest.mark.parametrize("network", [None, "", "finney", "mainnet", "wss://finney.opentensor.ai:443"])
def test_unsafe_or_unset_networks_raise(network: str | None) -> None:
    with pytest.raises(NetworkSafetyError):
        assert_safe_network(network)


def test_unknown_network_is_not_allowlisted() -> None:
    with pytest.raises(NetworkSafetyError):
        assert_safe_network("wss://test.finney.opentensor.ai:443")


def test_netuid_loads_from_config_env_and_explicit_override(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "testnet.json"
    config_path.write_text('{"netuid": 41}\n', encoding="utf-8")

    assert resolve_netuid("testnet", config_path=config_path) == 41
    assert resolve_netuid("testnet", env_value="42", config_path=config_path) == 42
    assert resolve_netuid("testnet", requested=43, env_value="42", config_path=config_path) == 43
    assert resolve_netuid("localnet", config_path=config_path) is None

    monkeypatch.setenv("BT_NETUID", "44")
    assert SubnetConfig.from_env(mode="testnet").netuid == 44
    assert SubnetConfig.from_env(mode="testnet", netuid=45).netuid == 45


def test_mode_defaults_are_fail_closed_for_validator_modes() -> None:
    offline = SubnetConfig.from_env(mode="offline")
    assert offline.backend == "docker"
    assert offline.pipeline_mode == "generated"
    assert offline.network is None

    mock = SubnetConfig.from_env(mode="mock")
    assert mock.backend == "local"
    assert mock.pipeline_mode == "fixture"


def test_plan_constants_are_single_source_values() -> None:
    assert SPEC_VERSION > 0
    assert MAX_PACKAGE_BYTES == 200 * 1024
    assert EMA_ALPHA == pytest.approx(0.3)
