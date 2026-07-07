"""Non-signing chain seam for epoch weight publication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from dolores_subnet.config import SubnetConfig


@dataclass(frozen=True)
class ChainWeightResult:
    """Serializable outcome of a weight-publication attempt."""

    mode: str
    receipt: dict[str, Any] | None = None
    reason: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {"mode": self.mode, "receipt": self.receipt, "reason": self.reason}


class ChainClient(Protocol):
    """Small protocol implemented by fallback and future chain clients."""

    def apply_weights(
        self,
        *,
        cfg: SubnetConfig,
        epoch_id: int,
        weights: dict[str, float],
        active_hotkeys: list[str],
        spec_version: int,
        fallback_reason: str | None = None,
    ) -> ChainWeightResult:
        ...


class NullChain:
    """Fallback chain client for offline, mock, and wire-only rehearsals.

    This class intentionally does not import Bittensor and cannot sign or submit
    extrinsics. It preserves the existing fallback weight artifact contract.
    """

    def apply_weights(
        self,
        *,
        cfg: SubnetConfig,
        epoch_id: int,
        weights: dict[str, float],
        active_hotkeys: list[str],
        spec_version: int,
        fallback_reason: str | None = None,
    ) -> ChainWeightResult:
        del cfg, epoch_id, weights, active_hotkeys, spec_version
        return ChainWeightResult(
            mode="fallback",
            receipt=None,
            reason=fallback_reason or "offline",
        )
