from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from types import SimpleNamespace
from typing import Tuple  # noqa: UP035 - Bittensor 10.5 signature uses typing.Tuple.

import bittensor as bt
import pytest

from dolores_subnet.miner_cli import attach_miner_axon, validator_blacklist
from dolores_subnet.wire import (
    BoundedDendrite,
    DoloresTaskSynapse,
    MinerEndpoint,
    sign_response,
    verify_response_signature,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _post_synapse(url: str, synapse: DoloresTaskSynapse) -> tuple[int, str]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(synapse.model_dump()).encode("utf-8"),
        headers={**synapse.to_headers(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            return int(response.status), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8")


@pytest.fixture
def authenticated_http_harness():
    validator = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    miner = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    coldkey = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    wallet = SimpleNamespace(hotkey=miner, coldkeypub=coldkey)
    port = _free_port()
    forward_calls: list[str] = []

    def forward(synapse: DoloresTaskSynapse) -> DoloresTaskSynapse:
        forward_calls.append(synapse.request_id)
        synapse.submissions = [{"task_id": "signed-http-smoke"}]
        synapse.error = ""
        return sign_response(synapse, miner)

    blacklist = validator_blacklist(
        allowed_hotkeys=frozenset({validator.ss58_address}),
        allow_any_signed=False,
    )
    forward.__annotations__ = {
        "synapse": DoloresTaskSynapse,
        "return": DoloresTaskSynapse,
    }
    blacklist.__annotations__ = {
        "synapse": DoloresTaskSynapse,
        "return": Tuple[bool, str],  # noqa: UP006 - exact SDK signature contract.
    }
    axon = bt.Axon(
        wallet=wallet,
        ip="127.0.0.1",
        port=port,
        external_ip="127.0.0.1",
        external_port=port,
    )
    attach_miner_axon(axon, forward=forward, blacklist=blacklist).start()
    dendrite = BoundedDendrite(wallet=validator, max_http_response_bytes=1024 * 1024)
    dendrite.external_ip = "127.0.0.1"
    endpoint = MinerEndpoint(
        host="127.0.0.1",
        port=port,
        hotkey=miner.ss58_address,
        uid=1,
        coldkey=coldkey.ss58_address,
    )

    def prepare(request_id: str) -> DoloresTaskSynapse:
        return dendrite.preprocess_synapse_for_request(
            endpoint.axon_info(),
            DoloresTaskSynapse(request_id=request_id, epoch_id=9, quota=1),
            5.0,
        )

    url = dendrite._get_endpoint_url(
        endpoint.axon_info(),
        request_name=DoloresTaskSynapse.__name__,
    )
    try:
        yield SimpleNamespace(
            validator=validator,
            miner=miner,
            forward_calls=forward_calls,
            prepare=prepare,
            url=url,
        )
    finally:
        dendrite.close_session()
        axon.stop()


def test_real_local_axon_dendrite_signed_wire_round_trip() -> None:
    validator = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    miner = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    coldkey = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    wallet = SimpleNamespace(hotkey=miner, coldkeypub=coldkey)
    port = _free_port()
    request_id = "1" * 32

    def forward(synapse: DoloresTaskSynapse) -> DoloresTaskSynapse:
        synapse.submissions = [{"task_id": "signed-http-smoke"}]
        synapse.error = ""
        return sign_response(synapse, miner)

    blacklist = validator_blacklist(
        allowed_hotkeys=frozenset({validator.ss58_address}),
        allow_any_signed=False,
    )
    forward.__annotations__ = {
        "synapse": DoloresTaskSynapse,
        "return": DoloresTaskSynapse,
    }
    blacklist.__annotations__ = {
        "synapse": DoloresTaskSynapse,
        "return": Tuple[bool, str],  # noqa: UP006 - exact SDK signature contract.
    }
    axon = bt.Axon(
        wallet=wallet,
        ip="127.0.0.1",
        port=port,
        external_ip="127.0.0.1",
        external_port=port,
    )
    attach_miner_axon(axon, forward=forward, blacklist=blacklist).start()
    dendrite = BoundedDendrite(wallet=validator, max_http_response_bytes=1024 * 1024)
    dendrite.external_ip = "127.0.0.1"
    endpoint = MinerEndpoint(
        host="127.0.0.1",
        port=port,
        hotkey=miner.ss58_address,
        uid=1,
        coldkey=coldkey.ss58_address,
    )
    try:
        request = DoloresTaskSynapse(request_id=request_id, epoch_id=9, quota=1)
        responses = dendrite.query(
            axons=[endpoint.axon_info()],
            synapse=request,
            timeout=5.0,
            deserialize=True,
            run_async=True,
        )
        response = responses[0]
        assert response.is_success
        assert response.submissions == [{"task_id": "signed-http-smoke"}]
        verify_response_signature(
            endpoint=endpoint,
            response=response,
            expected_epoch_id=9,
            expected_quota=1,
            expected_request_id=request_id,
            expected_validator_hotkey=validator.ss58_address,
        )
    finally:
        dendrite.close_session()
        axon.stop()


def test_real_http_invalid_signature_is_unauthorized_before_forward(
    authenticated_http_harness,
) -> None:
    request = authenticated_http_harness.prepare("2" * 32)
    assert request.dendrite is not None
    request.dendrite.signature = "0x" + "00" * 64

    status, _ = _post_synapse(authenticated_http_harness.url, request)

    assert status == 401
    assert authenticated_http_harness.forward_calls == []


def test_real_http_stale_signed_request_is_unauthorized_before_forward(
    authenticated_http_harness,
) -> None:
    request = authenticated_http_harness.prepare("3" * 32)
    assert request.dendrite is not None
    request.dendrite.nonce = time.time_ns() - 60_000_000_000
    message = (
        f"{request.dendrite.nonce}.{request.dendrite.hotkey}."
        f"{authenticated_http_harness.miner.ss58_address}.{request.dendrite.uuid}."
        f"{request.computed_body_hash}"
    )
    request.dendrite.signature = (
        "0x" + authenticated_http_harness.validator.sign(message).hex()
    )

    status, _ = _post_synapse(authenticated_http_harness.url, request)

    assert status == 401
    assert authenticated_http_harness.forward_calls == []


def test_real_http_exact_replay_is_unauthorized_without_second_forward(
    authenticated_http_harness,
) -> None:
    request_id = "4" * 32
    request = authenticated_http_harness.prepare(request_id)

    first_status, _ = _post_synapse(authenticated_http_harness.url, request)
    second_status, _ = _post_synapse(authenticated_http_harness.url, request)

    assert first_status == 200
    assert second_status == 401
    assert authenticated_http_harness.forward_calls == [request_id]
