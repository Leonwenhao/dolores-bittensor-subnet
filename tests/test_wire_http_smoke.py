from __future__ import annotations

import socket
from types import SimpleNamespace
from typing import Tuple  # noqa: UP035 - Bittensor 10.5 signature uses typing.Tuple.

import bittensor as bt

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
