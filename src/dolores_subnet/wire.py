"""Bittensor wire-mode helpers for local axon/dendrite rehearsals."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

import aiohttp
import bittensor as bt
from pydantic import Field

from dolores_subnet.config import DEFAULT_QUOTA, MAX_RESPONSE_BYTES

WIRE_PROTOCOL_VERSION = "dolores-wire-v1"
RESPONSE_ENVELOPE_OVERHEAD_BYTES = 64 * 1024


class ResponseAuthenticationError(ValueError):
    """A miner response is missing, stale, replayed, or not signed by its hotkey."""


class TransportResponseTooLarge(ValueError):
    """The HTTP response exceeded the cap before JSON materialization."""


class BoundedDendrite(bt.Dendrite):
    """Dendrite that caps decompressed response bytes before JSON parsing."""

    def __init__(self, *args: Any, max_http_response_bytes: int, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.max_http_response_bytes = int(max_http_response_bytes)
        if self.max_http_response_bytes < 1:
            raise ValueError("max_http_response_bytes must be positive")

    async def call(
        self,
        target_axon: Any,
        synapse: Any = None,
        timeout: float = 12.0,
        deserialize: bool = True,
    ) -> Any:
        """Send one request while bounding the body before ``json.loads``."""

        if synapse is None:
            synapse = bt.Synapse()
        started = time.time()
        if isinstance(target_axon, bt.Axon):
            target_axon = target_axon.info()
        request_name = synapse.__class__.__name__
        url = self._get_endpoint_url(target_axon, request_name=request_name)
        synapse = self.preprocess_synapse_for_request(target_axon, synapse, timeout)
        try:
            self._log_outgoing_request(synapse)
            async with (await self.session).post(
                url=url,
                headers=synapse.to_headers(),
                json=synapse.model_dump(),
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                json_response = await _bounded_response_json(
                    response,
                    max_bytes=self.max_http_response_bytes,
                )
                self.process_server_response(response, json_response, synapse)
            synapse.dendrite.process_time = str(time.time() - started)
        except Exception as exc:  # noqa: BLE001 - preserve Dendrite error contract.
            synapse = self.process_error_message(synapse, request_name, exc)
        finally:
            self._log_incoming_response(synapse)
            self.synapse_history.append(bt.Synapse.from_headers(synapse.to_headers()))
        return synapse.deserialize() if deserialize else synapse


async def _bounded_response_json(response: Any, *, max_bytes: int) -> dict[str, Any]:
    """Read a decompressed HTTP response with a strict pre-parse byte cap."""

    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise ValueError("invalid HTTP Content-Length") from exc
        if declared > max_bytes:
            raise TransportResponseTooLarge(f"declared response exceeds {max_bytes} bytes")
    body = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        if len(body) + len(chunk) > max_bytes:
            raise TransportResponseTooLarge(f"streamed response exceeds {max_bytes} bytes")
        body.extend(chunk)
    decoded = json.loads(body)
    if not isinstance(decoded, dict):
        raise ValueError("wire response must be a JSON object")
    return decoded


class DoloresTaskSynapse(bt.Synapse):
    """Request/response envelope for miner-proposed Dolores task packages."""

    required_hash_fields: ClassVar[tuple[str, ...]] = (
        "protocol_version",
        "request_id",
        "epoch_id",
        "quota",
        "timeout",
    )

    protocol_version: Literal["dolores-wire-v1"] = WIRE_PROTOCOL_VERSION
    # A default is required because Bittensor first reconstructs a dummy
    # header-only Synapse before merging the signed JSON body. Runtime handlers
    # reject an empty/non-hex request id before serving content.
    request_id: str = ""
    epoch_id: int = Field(default=0, ge=0)
    quota: int = Field(default=1, ge=0, le=DEFAULT_QUOTA)
    submissions: list[dict[str, Any]] = Field(default_factory=list)
    error: str = ""
    response_hotkey: str = ""
    response_digest: str = ""
    response_signature: str = ""

    def deserialize(self) -> DoloresTaskSynapse:
        return self


@dataclass(frozen=True)
class MinerEndpoint:
    """A local miner endpoint address plus public hotkey identity."""

    host: str
    port: int
    hotkey: str
    uid: int
    coldkey: str = ""

    @classmethod
    def parse(cls, value: str, *, uid: int = 0, default_coldkey: str = "") -> MinerEndpoint:
        parts = value.split(":")
        if len(parts) not in {3, 4}:
            raise ValueError(
                "miner endpoint must be host:port:hotkey or host:port:hotkey:coldkey"
            )
        host, port_text, hotkey = parts[:3]
        coldkey = parts[3] if len(parts) == 4 else default_coldkey
        if not host:
            raise ValueError("miner endpoint host is required")
        if not hotkey:
            raise ValueError("miner endpoint hotkey is required")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError(f"miner endpoint port must be an integer: {port_text!r}") from exc
        return cls(host=host, port=port, hotkey=hotkey, uid=uid, coldkey=coldkey)

    def axon_info(self) -> bt.AxonInfo:
        return bt.AxonInfo(
            version=1,
            ip=self.host,
            port=self.port,
            ip_type=4,
            hotkey=self.hotkey,
            coldkey=self.coldkey,
        )


@dataclass(frozen=True)
class WireMiner:
    """Miner-like wrapper for submissions received from a remote axon."""

    hotkey: str
    uid: int
    payloads: list[dict[str, Any]]
    terminal_status: str | None = None
    terminal_reason: str = ""

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del epoch_id
        if self.terminal_status:
            return []
        return self.payloads[:quota]


def parse_miner_endpoints(values: str, *, default_coldkey: str = "") -> list[MinerEndpoint]:
    endpoints: list[MinerEndpoint] = []
    for index, raw in enumerate(item.strip() for item in values.split(",")):
        if not raw:
            continue
        endpoints.append(MinerEndpoint.parse(raw, uid=index, default_coldkey=default_coldkey))
    if not endpoints:
        raise ValueError("at least one miner endpoint is required")
    return endpoints


def query_miners(
    *,
    wallet: bt.Wallet,
    endpoints: list[MinerEndpoint],
    epoch_id: int,
    quota: int,
    timeout: float,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> list[WireMiner]:
    dendrite = BoundedDendrite(
        wallet=wallet,
        max_http_response_bytes=max_response_bytes + RESPONSE_ENVELOPE_OVERHEAD_BYTES,
    )
    request_id = secrets.token_hex(16)
    synapse = DoloresTaskSynapse(request_id=request_id, epoch_id=epoch_id, quota=quota)
    try:
        responses = dendrite.query(
            axons=[endpoint.axon_info() for endpoint in endpoints],
            synapse=synapse,
            timeout=timeout,
            deserialize=True,
            run_async=True,
        )
    except Exception as exc:  # pragma: no cover - exercised by live wire smoke.
        return [
            WireMiner(
                hotkey=endpoint.hotkey,
                uid=endpoint.uid,
                payloads=[],
                terminal_status="unreachable",
                terminal_reason=f"unreachable:wire query failed: {exc}",
            )
            for endpoint in endpoints
        ]
    finally:
        dendrite.close_session()
    return [
        wire_miner_from_response(
            endpoint=endpoint,
            response=response,
            quota=quota,
            expected_epoch_id=epoch_id,
            expected_request_id=request_id,
            expected_validator_hotkey=wallet.hotkey.ss58_address,
            max_response_bytes=max_response_bytes,
        )
        for endpoint, response in zip(endpoints, responses, strict=True)
    ]


def wire_miner_from_response(
    *,
    endpoint: MinerEndpoint,
    response: Any,
    quota: int,
    expected_epoch_id: int,
    expected_request_id: str,
    expected_validator_hotkey: str,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> WireMiner:
    """Convert a dendrite response into miner input for the epoch engine."""

    if not _is_success_response(response):
        return WireMiner(
            hotkey=endpoint.hotkey,
            uid=endpoint.uid,
            payloads=[],
            terminal_status="unreachable",
            terminal_reason=f"unreachable:{_response_error(response)}",
        )

    try:
        verify_response_signature(
            endpoint=endpoint,
            response=response,
            expected_epoch_id=expected_epoch_id,
            expected_quota=quota,
            expected_request_id=expected_request_id,
            expected_validator_hotkey=expected_validator_hotkey,
        )
    except ResponseAuthenticationError as exc:
        return WireMiner(
            hotkey=endpoint.hotkey,
            uid=endpoint.uid,
            payloads=[],
            terminal_status="invalid",
            terminal_reason=f"response_auth:{exc}",
        )

    payloads = list(response.submissions)
    response_bytes = response_payload_size(payloads)
    if response_bytes > max_response_bytes:
        return WireMiner(
            hotkey=endpoint.hotkey,
            uid=endpoint.uid,
            payloads=[],
            terminal_status="invalid",
            terminal_reason=f"response_size:{response_bytes}>{max_response_bytes}",
        )
    return WireMiner(hotkey=endpoint.hotkey, uid=endpoint.uid, payloads=payloads[:quota])


def response_payload_size(payloads: list[dict[str, Any]]) -> int:
    """Return the canonical aggregate submission-list size in bytes."""

    return len(
        json.dumps(payloads, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    )


def submissions_digest(payloads: list[dict[str, Any]]) -> str:
    """Return the miner-signed digest of the canonical response payload."""

    canonical = json.dumps(
        payloads,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def sign_response(synapse: DoloresTaskSynapse, keypair: Any) -> DoloresTaskSynapse:
    """Bind scored response content to the request and the miner hotkey."""

    if synapse.dendrite is None:
        raise ResponseAuthenticationError("missing request terminal")
    if not request_id_is_valid(synapse.request_id):
        raise ResponseAuthenticationError("invalid request id")
    miner_hotkey = str(keypair.ss58_address)
    digest = submissions_digest(synapse.submissions)
    message = _response_message(
        protocol_version=synapse.protocol_version,
        request_id=synapse.request_id,
        request_nonce=synapse.dendrite.nonce,
        request_uuid=synapse.dendrite.uuid,
        validator_hotkey=synapse.dendrite.hotkey,
        miner_hotkey=miner_hotkey,
        epoch_id=synapse.epoch_id,
        quota=synapse.quota,
        digest=digest,
    )
    synapse.response_hotkey = miner_hotkey
    synapse.response_digest = digest
    synapse.response_signature = f"0x{keypair.sign(message).hex()}"
    return synapse


def verify_response_signature(
    *,
    endpoint: MinerEndpoint,
    response: DoloresTaskSynapse,
    expected_epoch_id: int,
    expected_quota: int,
    expected_request_id: str,
    expected_validator_hotkey: str,
) -> None:
    """Verify application-layer response integrity against the metagraph hotkey."""

    if response.dendrite is None:
        raise ResponseAuthenticationError("missing request terminal")
    if response.protocol_version != WIRE_PROTOCOL_VERSION:
        raise ResponseAuthenticationError("protocol version mismatch")
    if response.request_id != expected_request_id:
        raise ResponseAuthenticationError("request id mismatch")
    if response.epoch_id != expected_epoch_id:
        raise ResponseAuthenticationError("epoch mismatch")
    if response.quota != expected_quota:
        raise ResponseAuthenticationError("quota mismatch")
    if response.dendrite.hotkey != expected_validator_hotkey:
        raise ResponseAuthenticationError("validator hotkey mismatch")
    if response.response_hotkey != endpoint.hotkey:
        raise ResponseAuthenticationError("miner hotkey mismatch")
    digest = submissions_digest(response.submissions)
    if not secrets.compare_digest(response.response_digest, digest):
        raise ResponseAuthenticationError("submissions digest mismatch")
    if not response.response_signature:
        raise ResponseAuthenticationError("missing response signature")
    message = _response_message(
        protocol_version=response.protocol_version,
        request_id=response.request_id,
        request_nonce=response.dendrite.nonce,
        request_uuid=response.dendrite.uuid,
        validator_hotkey=response.dendrite.hotkey,
        miner_hotkey=response.response_hotkey,
        epoch_id=response.epoch_id,
        quota=response.quota,
        digest=digest,
    )
    keypair = bt.Keypair(ss58_address=endpoint.hotkey)
    if not keypair.verify(message, response.response_signature):
        raise ResponseAuthenticationError("response signature mismatch")


def _response_message(
    *,
    protocol_version: str,
    request_id: str,
    request_nonce: int | None,
    request_uuid: str | None,
    validator_hotkey: str | None,
    miner_hotkey: str,
    epoch_id: int,
    quota: int,
    digest: str,
) -> bytes:
    payload = {
        "protocol_version": protocol_version,
        "request_id": request_id,
        "request_nonce": request_nonce,
        "request_uuid": request_uuid,
        "validator_hotkey": validator_hotkey,
        "miner_hotkey": miner_hotkey,
        "epoch_id": epoch_id,
        "quota": quota,
        "submissions_digest": digest,
    }
    return (
        "dolores-response-v1:"
        + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    ).encode()


def request_id_is_valid(value: str) -> bool:
    return 32 <= len(value) <= 64 and all(char in "0123456789abcdef" for char in value)


def _is_success_response(response: Any) -> bool:
    return (
        isinstance(response, DoloresTaskSynapse)
        and response.is_success
        and not response.error
    )


def _response_error(response: Any) -> str:
    return (
        str(getattr(response, "error", "") or "")
        or str(getattr(getattr(response, "dendrite", None), "status_message", "") or "")
        or "wire query failed"
    )
