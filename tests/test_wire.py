from __future__ import annotations

import pytest

from dolores_subnet.config import MAX_RESPONSE_BYTES
from dolores_subnet.wire import (
    DoloresTaskSynapse,
    parse_miner_endpoints,
    response_payload_size,
    sign_response,
    wire_miner_from_response,
)

REQUEST_ID = "a" * 32


def _signed_response(*, payloads, epoch_id=1, quota=1):
    import bittensor as bt
    from bittensor.core.synapse import TerminalInfo

    validator = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    miner = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    response = DoloresTaskSynapse(
        request_id=REQUEST_ID,
        epoch_id=epoch_id,
        quota=quota,
        submissions=payloads,
        dendrite=TerminalInfo(
            status_code=200,
            status_message="OK",
            nonce=123456789,
            uuid="request-uuid",
            hotkey=validator.ss58_address,
        ),
    )
    sign_response(response, miner)
    return response, validator, miner


def test_wire_synapse_round_trips_submissions() -> None:
    synapse = DoloresTaskSynapse(
        request_id=REQUEST_ID,
        epoch_id=7,
        quota=2,
        submissions=[{"task_id": "task-a"}],
    )

    assert synapse.deserialize() is synapse
    assert synapse.epoch_id == 7
    assert synapse.submissions == [{"task_id": "task-a"}]


def test_wire_synapse_pydantic_json_round_trip_near_response_limit() -> None:
    # Bittensor 10.x exposes the Synapse as a Pydantic model in-process. The
    # validator cap is measured on the aggregate submissions list before epoch
    # validation; the full synapse JSON adds SDK envelope fields around it.
    payloads = [{"task_id": "near-limit", "padding": "x" * (MAX_RESPONSE_BYTES - 4096)}]
    while response_payload_size(payloads) > MAX_RESPONSE_BYTES:
        payloads[0]["padding"] = payloads[0]["padding"][:-1024]
    assert response_payload_size(payloads) > MAX_RESPONSE_BYTES * 0.95

    synapse = DoloresTaskSynapse(
        request_id=REQUEST_ID,
        epoch_id=7,
        quota=1,
        submissions=payloads,
    )
    encoded = synapse.model_dump_json()
    recovered = DoloresTaskSynapse.model_validate_json(encoded)

    assert recovered.epoch_id == 7
    assert recovered.quota == 1
    assert recovered.submissions == payloads


def test_parse_miner_endpoints_uses_default_coldkey() -> None:
    endpoints = parse_miner_endpoints(
        "127.0.0.1:8091:hotkey-a,127.0.0.1:8092:hotkey-b",
        default_coldkey="coldkey",
    )

    assert [endpoint.uid for endpoint in endpoints] == [0, 1]
    assert [endpoint.hotkey for endpoint in endpoints] == ["hotkey-a", "hotkey-b"]
    assert endpoints[0].axon_info().coldkey == "coldkey"


def test_parse_miner_endpoints_rejects_bad_shape() -> None:
    with pytest.raises(ValueError):
        parse_miner_endpoints("127.0.0.1:8091")


def test_wire_response_size_cap_becomes_terminal_invalid() -> None:
    response, validator, miner_keypair = _signed_response(
        payloads=[
            {"task_id": "too-large", "padding": "x" * (MAX_RESPONSE_BYTES + 1)}
        ],
    )
    endpoint = parse_miner_endpoints(
        f"127.0.0.1:8091:{miner_keypair.ss58_address}"
    )[0]

    miner = wire_miner_from_response(
        endpoint=endpoint,
        response=response,
        quota=1,
        expected_epoch_id=1,
        expected_request_id=REQUEST_ID,
        expected_validator_hotkey=validator.ss58_address,
        max_response_bytes=MAX_RESPONSE_BYTES,
    )

    assert miner.payloads == []
    assert miner.terminal_status == "invalid"
    assert miner.terminal_reason.startswith("response_size:")


def test_failed_wire_response_becomes_terminal_unreachable() -> None:
    endpoint = parse_miner_endpoints("127.0.0.1:8092:hotkey-b")[0]
    response = DoloresTaskSynapse(
        request_id=REQUEST_ID,
        error="Service unavailable at 127.0.0.1:8092",
    )

    miner = wire_miner_from_response(
        endpoint=endpoint,
        response=response,
        quota=1,
        expected_epoch_id=1,
        expected_request_id=REQUEST_ID,
        expected_validator_hotkey="validator-hotkey",
    )

    assert miner.payloads == []
    assert miner.terminal_status == "unreachable"
    assert "Service unavailable" in miner.terminal_reason
