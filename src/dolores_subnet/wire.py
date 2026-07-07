"""Bittensor wire-mode helpers for local axon/dendrite rehearsals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import bittensor as bt
from pydantic import Field

from dolores_subnet.config import MAX_RESPONSE_BYTES


class DoloresTaskSynapse(bt.Synapse):
    """Request/response envelope for miner-proposed Dolores task packages."""

    epoch_id: int = 0
    quota: int = 1
    submissions: list[dict[str, Any]] = Field(default_factory=list)
    error: str = ""

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
    dendrite = bt.Dendrite(wallet=wallet)
    synapse = DoloresTaskSynapse(epoch_id=epoch_id, quota=quota)
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
            max_response_bytes=max_response_bytes,
        )
        for endpoint, response in zip(endpoints, responses, strict=True)
    ]


def wire_miner_from_response(
    *,
    endpoint: MinerEndpoint,
    response: Any,
    quota: int,
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
