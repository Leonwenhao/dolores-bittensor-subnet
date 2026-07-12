"""Public endpoint policy for the controlled HackerQuest cohort."""

from __future__ import annotations

import ipaddress
from typing import Any

COHORT_NETWORK = "test"
COHORT_NETUID = 523


class EndpointPolicyError(ValueError):
    """An endpoint or chain target is unsafe for the public cohort."""


def require_cohort_target(network: str, netuid: int) -> None:
    if network != COHORT_NETWORK or netuid != COHORT_NETUID:
        raise EndpointPolicyError(
            f"public cohort is fixed to network={COHORT_NETWORK} netuid={COHORT_NETUID}"
        )


def require_public_ipv4(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise EndpointPolicyError("external IP must be a literal IPv4 address") from exc
    if not isinstance(address, ipaddress.IPv4Address):
        raise EndpointPolicyError("external IP must be IPv4")
    if (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise EndpointPolicyError(f"external IP is not globally routable: {address}")
    return str(address)


def require_port(value: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise EndpointPolicyError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise EndpointPolicyError(f"port is outside 1..65535: {port}")
    return port


def metagraph_has_exact_axon(
    metagraph: Any,
    *,
    hotkey: str,
    host: str,
    port: int,
) -> bool:
    hotkeys = [str(item) for item in getattr(metagraph, "hotkeys", [])]
    if hotkey not in hotkeys:
        return False
    index = hotkeys.index(hotkey)
    axons = list(getattr(metagraph, "axons", []))
    if index >= len(axons):
        return False
    axon = axons[index]
    return str(getattr(axon, "ip", "") or "") == host and int(
        getattr(axon, "port", 0) or 0
    ) == port
