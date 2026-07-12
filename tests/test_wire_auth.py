from __future__ import annotations

import bittensor as bt
import pytest
from bittensor.core.synapse import TerminalInfo
from pydantic import ValidationError

from dolores_subnet.wire import (
    DoloresTaskSynapse,
    MinerEndpoint,
    ResponseAuthenticationError,
    sign_response,
    verify_response_signature,
)

REQUEST_ID = "c" * 32


@pytest.fixture
def keypairs():
    validator = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    miner = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    attacker = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    return validator, miner, attacker


def _response(validator, miner):
    response = DoloresTaskSynapse(
        request_id=REQUEST_ID,
        epoch_id=41,
        quota=2,
        submissions=[{"task_id": "one"}, {"task_id": "two"}],
        dendrite=TerminalInfo(
            status_code=200,
            status_message="OK",
            nonce=987654321,
            uuid="validator-request-uuid",
            hotkey=validator.ss58_address,
        ),
    )
    sign_response(response, miner)
    return response


def _verify(response, validator, miner):
    verify_response_signature(
        endpoint=MinerEndpoint(
            host="127.0.0.1",
            port=8091,
            hotkey=miner.ss58_address,
            uid=1,
        ),
        response=response,
        expected_epoch_id=41,
        expected_quota=2,
        expected_request_id=REQUEST_ID,
        expected_validator_hotkey=validator.ss58_address,
    )


def test_request_body_hash_binds_protocol_request_epoch_quota_and_timeout() -> None:
    base = DoloresTaskSynapse(request_id=REQUEST_ID, epoch_id=3, quota=2)

    assert base.body_hash != DoloresTaskSynapse(
        request_id="d" * 32, epoch_id=3, quota=2
    ).body_hash
    assert base.body_hash != DoloresTaskSynapse(
        request_id=REQUEST_ID, epoch_id=4, quota=2
    ).body_hash
    assert base.body_hash != DoloresTaskSynapse(
        request_id=REQUEST_ID, epoch_id=3, quota=1
    ).body_hash
    assert base.body_hash != DoloresTaskSynapse(
        request_id=REQUEST_ID, epoch_id=3, quota=2, timeout=30.0
    ).body_hash


def test_synapse_rejects_unbounded_quota_and_allows_sdk_header_dummy() -> None:
    with pytest.raises(ValidationError):
        DoloresTaskSynapse(request_id=REQUEST_ID, epoch_id=1, quota=999)
    # Bittensor reconstructs a header-only dummy before merging the JSON body.
    assert DoloresTaskSynapse(epoch_id=1, quota=1).request_id == ""


def test_valid_miner_response_signature_passes(keypairs) -> None:
    validator, miner, _ = keypairs
    _verify(_response(validator, miner), validator, miner)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request_id", "e" * 32, "request id mismatch"),
        ("epoch_id", 42, "epoch mismatch"),
        ("quota", 1, "quota mismatch"),
    ],
)
def test_replayed_or_mutated_response_context_is_rejected(
    keypairs, field, value, message
) -> None:
    validator, miner, _ = keypairs
    response = _response(validator, miner)
    setattr(response, field, value)

    with pytest.raises(ResponseAuthenticationError, match=message):
        _verify(response, validator, miner)


def test_tampered_submissions_are_rejected(keypairs) -> None:
    validator, miner, _ = keypairs
    response = _response(validator, miner)
    response.submissions[0]["task_id"] = "tampered"

    with pytest.raises(ResponseAuthenticationError, match="digest mismatch"):
        _verify(response, validator, miner)


def test_signature_from_wrong_hotkey_is_rejected(keypairs) -> None:
    validator, miner, attacker = keypairs
    response = _response(validator, attacker)
    response.response_hotkey = miner.ss58_address

    with pytest.raises(ResponseAuthenticationError, match="signature mismatch"):
        _verify(response, validator, miner)
