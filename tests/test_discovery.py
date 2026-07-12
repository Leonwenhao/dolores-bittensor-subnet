from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
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


def test_bounded_call_timeout_does_not_delay_one_shot_process_exit() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    code = """
import time
from dolores_subnet.chain import ChainReadTimeout, bounded_call
try:
    bounded_call(time.sleep, 30, timeout=0.05)
except ChainReadTimeout:
    print("timed_out")
"""
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )

    assert completed.stdout.strip() == "timed_out"
    assert time.monotonic() - started < 3


def test_bounded_call_restores_prior_signal_handler() -> None:
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer[0] > 0 or previous_timer[1] > 0:
        pytest.skip("test runner already owns ITIMER_REAL")

    def prior_handler(signum, frame):  # noqa: ANN001
        del signum, frame

    signal.signal(signal.SIGALRM, prior_handler)
    try:
        assert bounded_call(lambda: 42, timeout=1.0) == 42
        assert signal.getsignal(signal.SIGALRM) is prior_handler
        assert signal.getitimer(signal.ITIMER_REAL) == pytest.approx((0.0, 0.0))
        with pytest.raises(ChainReadTimeout):
            bounded_call(time.sleep, 1, timeout=0.05)
        assert signal.getsignal(signal.SIGALRM) is prior_handler
        assert signal.getitimer(signal.ITIMER_REAL) == pytest.approx((0.0, 0.0))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_nested_bounded_call_fails_closed_and_restores_outer_alarm() -> None:
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer[0] > 0 or previous_timer[1] > 0:
        pytest.skip("test runner already owns ITIMER_REAL")

    def nested() -> None:
        bounded_call(lambda: None, timeout=0.5)

    with pytest.raises(ChainReadTimeout, match="SIGALRM timer is active"):
        bounded_call(nested, timeout=1.0)
    assert signal.getsignal(signal.SIGALRM) == previous_handler
    assert signal.getitimer(signal.ITIMER_REAL) == pytest.approx(previous_timer)


def test_bounded_call_non_main_thread_fails_closed_without_calling_target() -> None:
    called = False
    errors: list[BaseException] = []

    def target() -> None:
        nonlocal called
        called = True

    def worker() -> None:
        try:
            bounded_call(target, timeout=1.0)
        except BaseException as exc:  # noqa: BLE001 - capture thread assertion evidence.
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert called is False
    assert len(errors) == 1
    assert isinstance(errors[0], ChainReadTimeout)
    assert "main thread" in str(errors[0])


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


def test_miner_publish_refuses_lan_address_before_bittensor_call() -> None:
    from dolores_subnet.endpoints import EndpointPolicyError
    from neurons.miner import _publish_axon

    args = SimpleNamespace(
        publish=True,
        netuid=523,
        network="test",
        external_ip="192.168.1.50",
        external_port=8091,
        host="0.0.0.0",
        port=8091,
    )
    with pytest.raises(EndpointPolicyError):
        _publish_axon(args, axon=object())
