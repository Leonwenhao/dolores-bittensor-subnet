from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from dolores_subnet.chain import ChainReadTimeout, _Substrate, bounded_call

VALIDATOR = "5DyNfValidatorHotkey"
MINER_A = "5FHEMinerAHotkey"
MINER_B = "5DhPMinerBHotkey"


def _substrate_with_metagraph(axons, hotkeys, uids) -> _Substrate:
    substrate = object.__new__(_Substrate)
    substrate._metagraph = SimpleNamespace(hotkeys=hotkeys, axons=axons, uids=uids)
    return substrate


def test_miner_endpoints_maps_published_axons_and_filters_unpublished() -> None:
    axons = [
        SimpleNamespace(ip="0.0.0.0", port=0, coldkey=""),  # validator, unpublished
        SimpleNamespace(ip="192.168.1.50", port=8091, coldkey="5ColdA"),  # published
        SimpleNamespace(ip="0.0.0.0", port=0, coldkey=""),  # miner, unpublished
    ]
    substrate = _substrate_with_metagraph(axons, [VALIDATOR, MINER_A, MINER_B], [0, 1, 2])
    endpoints = substrate.miner_endpoints(exclude_hotkey=VALIDATOR)
    assert endpoints == [
        {
            "host": "192.168.1.50",
            "port": 8091,
            "hotkey": MINER_A,
            "uid": 1,
            "coldkey": "5ColdA",
        }
    ]


def test_miner_endpoints_never_fabricates_loopback() -> None:
    axons = [SimpleNamespace(ip="", port=8091, coldkey="")]
    substrate = _substrate_with_metagraph(axons, [MINER_A], [7])
    assert substrate.miner_endpoints(exclude_hotkey=VALIDATOR) == []


def test_miner_endpoints_preserves_uid_zero() -> None:
    # A legitimate uid 0 miner must not be replaced by its list index.
    axons = [
        SimpleNamespace(ip="10.0.0.9", port=8091, coldkey="5Cold0"),
        SimpleNamespace(ip="0.0.0.0", port=0, coldkey=""),
    ]
    substrate = _substrate_with_metagraph(axons, [MINER_A, VALIDATOR], [0, 1])
    endpoints = substrate.miner_endpoints(exclude_hotkey=VALIDATOR)
    assert endpoints[0]["uid"] == 0


def test_bounded_call_raises_on_hang() -> None:
    started = time.monotonic()
    with pytest.raises(ChainReadTimeout, match="hang guard"):
        bounded_call(time.sleep, 5, timeout=0.1)
    assert time.monotonic() - started < 2.0


def test_bounded_call_passes_through_results_and_errors() -> None:
    assert bounded_call(lambda value: value * 2, 21, timeout=1.0) == 42
    with pytest.raises(ValueError, match="boom"):
        bounded_call(lambda: (_ for _ in ()).throw(ValueError("boom")), timeout=1.0)


def test_miner_publish_off_by_default(capsys) -> None:
    from neurons.miner import _publish_axon

    args = SimpleNamespace(
        publish=False, netuid=None, network=None,
        external_ip=None, external_port=None, host="127.0.0.1", port=8091,
    )
    _publish_axon(args, axon=object())  # must not touch bittensor at all
    assert "axon_publish=skipped reason=no_publish_flag" in capsys.readouterr().out


def test_miner_publish_refuses_unsafe_network() -> None:
    from dolores_subnet.config import NetworkSafetyError
    from neurons.miner import _publish_axon

    args = SimpleNamespace(
        publish=True, netuid=523, network="finney",
        external_ip="10.0.0.5", external_port=8091, host="0.0.0.0", port=8091,
    )
    with pytest.raises(NetworkSafetyError):
        _publish_axon(args, axon=object())
