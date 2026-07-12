from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import bittensor as bt
import pytest
from bittensor.core.axon import V_7_2_0
from bittensor.core.synapse import TerminalInfo

from dolores_subnet.miner_cli import AUTH_RATE_BURST, build_request_verifier
from dolores_subnet.wire import DoloresTaskSynapse

REQUEST_ID = "f" * 32


@pytest.fixture
def auth_fixture():
    validator = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    miner = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    coldkey = bt.Keypair.create_from_mnemonic(bt.Keypair.generate_mnemonic())
    wallet = SimpleNamespace(hotkey=miner, coldkeypub=coldkey)
    axon = bt.Axon(
        wallet=wallet,
        ip="127.0.0.1",
        port=8099,
        external_ip="127.0.0.1",
        external_port=8099,
    )
    return axon, validator, miner


def _signed_request(
    validator,
    miner,
    *,
    nonce=None,
    quota=2,
    timeout=1.0,
    version=V_7_2_0,
    request_uuid="stable-request-uuid",
):
    request = DoloresTaskSynapse(
        request_id=REQUEST_ID,
        epoch_id=7,
        quota=quota,
        timeout=timeout,
        dendrite=TerminalInfo(
            nonce=nonce if nonce is not None else time.time_ns(),
            uuid=request_uuid,
            hotkey=validator.ss58_address,
            version=version,
        ),
    )
    request = request.model_copy(update={"computed_body_hash": request.body_hash})
    message = (
        f"{request.dendrite.nonce}.{request.dendrite.hotkey}."
        f"{miner.ss58_address}.{request.dendrite.uuid}.{request.computed_body_hash}"
    )
    request.dendrite.signature = f"0x{validator.sign(message).hex()}"
    return request


def test_sdk_default_verify_accepts_valid_signed_request(auth_fixture) -> None:
    axon, validator, miner = auth_fixture

    asyncio.run(axon.default_verify(_signed_request(validator, miner)))


def test_sdk_default_verify_rejects_invalid_signature(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    request = _signed_request(validator, miner)
    request.dendrite.signature = "0x" + "00" * 64

    with pytest.raises(Exception, match="Signature mismatch"):
        asyncio.run(axon.default_verify(request))


def test_sdk_default_verify_rejects_stale_first_nonce(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    stale = time.time_ns() - 60_000_000_000

    with pytest.raises(Exception, match="Nonce is too old"):
        asyncio.run(axon.default_verify(_signed_request(validator, miner, nonce=stale)))


def test_sdk_default_verify_rejects_exact_replay(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    request = _signed_request(validator, miner)
    asyncio.run(axon.default_verify(request))

    with pytest.raises(Exception, match="Nonce is too old"):
        asyncio.run(axon.default_verify(request))


def test_sdk_default_verify_rejects_body_tamper(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    signed = _signed_request(validator, miner, quota=2)
    tampered = signed.model_copy(
        update={
            "quota": 1,
            "computed_body_hash": signed.model_copy(update={"quota": 1}).body_hash,
        }
    )

    with pytest.raises(Exception, match="Signature mismatch"):
        asyncio.run(axon.default_verify(tampered))


def test_cohort_verifier_accepts_valid_sdk_request(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    verify = build_request_verifier(axon)

    asyncio.run(verify(_signed_request(validator, miner)))


def test_cohort_verifier_rejects_stale_nonce_even_with_large_timeout(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    verify = build_request_verifier(axon)
    stale = time.time_ns() - 60_000_000_000
    request = _signed_request(validator, miner, nonce=stale, timeout=10_000.0)

    with pytest.raises(ValueError, match="timeout exceeds|nonce is stale"):
        asyncio.run(verify(request))


def test_cohort_verifier_rejects_version_downgrade_nonce_bypass(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    verify = build_request_verifier(axon)
    stale = time.time_ns() - 3_600_000_000_000
    request = _signed_request(
        validator,
        miner,
        nonce=stale,
        version=V_7_2_0 - 1,
    )

    with pytest.raises(ValueError, match="unsupported authenticated request version"):
        asyncio.run(verify(request))


def test_timeout_is_bound_into_request_signature(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    signed = _signed_request(validator, miner, timeout=1.0)
    tampered = signed.model_copy(
        update={
            "timeout": 30.0,
            "computed_body_hash": signed.model_copy(update={"timeout": 30.0}).body_hash,
        }
    )

    with pytest.raises(Exception, match="Signature mismatch"):
        asyncio.run(build_request_verifier(axon)(tampered))


def test_cohort_verifier_rate_limits_authenticated_hotkey(auth_fixture) -> None:
    axon, validator, miner = auth_fixture
    verify = build_request_verifier(axon)
    for index in range(AUTH_RATE_BURST):
        request = _signed_request(
            validator,
            miner,
            nonce=time.time_ns(),
            request_uuid=f"rate-{index}",
        )
        asyncio.run(verify(request))

    rejected = _signed_request(
        validator,
        miner,
        nonce=time.time_ns(),
        request_uuid="rate-rejected",
    )
    with pytest.raises(ValueError, match="authenticated request rate exceeded"):
        asyncio.run(verify(rejected))
