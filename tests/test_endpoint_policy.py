from __future__ import annotations

from types import SimpleNamespace

import pytest

from dolores_subnet.endpoints import (
    EndpointPolicyError,
    metagraph_has_exact_axon,
    require_cohort_target,
    require_port,
    require_public_ipv4,
)


@pytest.mark.parametrize(
    "value",
    [
        "127.0.0.1",
        "0.0.0.0",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.1.1",
        "224.0.0.1",
        "::1",
        "localhost",
    ],
)
def test_public_endpoint_rejects_non_global_addresses(value: str) -> None:
    with pytest.raises(EndpointPolicyError):
        require_public_ipv4(value)


def test_public_endpoint_accepts_literal_global_ipv4() -> None:
    assert require_public_ipv4("8.8.8.8") == "8.8.8.8"


def test_public_cohort_target_is_fixed() -> None:
    require_cohort_target("test", 523)
    with pytest.raises(EndpointPolicyError):
        require_cohort_target("test", 1)
    with pytest.raises(EndpointPolicyError):
        require_cohort_target("ws://127.0.0.1:9944", 523)


def test_port_range_is_strict() -> None:
    assert require_port(8091) == 8091
    for value in (0, -1, 65536):
        with pytest.raises(EndpointPolicyError):
            require_port(value)


def test_metagraph_readback_requires_exact_hotkey_host_and_port() -> None:
    graph = SimpleNamespace(
        hotkeys=["miner-a"],
        axons=[SimpleNamespace(ip="8.8.8.8", port=8091)],
    )

    assert metagraph_has_exact_axon(
        graph, hotkey="miner-a", host="8.8.8.8", port=8091
    )
    assert not metagraph_has_exact_axon(
        graph, hotkey="miner-b", host="8.8.8.8", port=8091
    )
    assert not metagraph_has_exact_axon(
        graph, hotkey="miner-a", host="8.8.4.4", port=8091
    )
