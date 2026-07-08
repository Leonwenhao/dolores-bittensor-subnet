"""Non-signing chain seam and gated Subtensor weight publication."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from dolores_subnet.config import SubnetConfig, assert_safe_network

LIVE_CONFIRMATION = "I-UNDERSTAND-THIS-WILL-SUBMIT-WEIGHTS"
CHAIN_PUBLISH_MODES = {"off", "dry-run", "live"}


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


@dataclass(frozen=True)
class HotkeyUidMapping:
    """Resolved miner hotkeys that can receive a chain weight payload."""

    hotkey_to_uid: dict[str, int]
    dropped_hotkeys: list[str]


class _Substrate:
    """Thin lazy facade around Bittensor SDK calls.

    This is the only concrete seam that imports Bittensor. Tests inject a fake
    object with the same method names, so importing this module stays
    Bittensor-free.
    """

    def __init__(self, *, network: str, netuid: int, wallet_name: str, wallet_hotkey: str):
        import bittensor as bt

        self.network = network
        self.netuid = netuid
        self.wallet = bt.Wallet(name=wallet_name, hotkey=wallet_hotkey)
        self.subtensor = bt.Subtensor(network=network)
        self._metagraph: Any | None = None

    @property
    def validator_hotkey(self) -> str:
        return str(self.wallet.hotkey.ss58_address)

    def block(self) -> int:
        if hasattr(self.subtensor, "get_current_block"):
            return int(self.subtensor.get_current_block())
        return int(self.subtensor.block)

    def subnet_exists(self) -> bool:
        fn = getattr(self.subtensor, "subnet_exists", None)
        if fn is None:
            netuids = getattr(self.subtensor, "get_all_subnet_netuids", lambda: [])()
            return self.netuid in set(netuids)
        try:
            return bool(fn(netuid=self.netuid))
        except TypeError:
            return bool(fn(self.netuid))

    def sync_metagraph(self) -> Any:
        if self._metagraph is None:
            try:
                self._metagraph = self.subtensor.metagraph(netuid=self.netuid, lite=True)
            except TypeError:
                self._metagraph = self.subtensor.metagraph(self.netuid)
        return self._metagraph

    def hotkey_uid(self, hotkey: str) -> int | None:
        metagraph = self.sync_metagraph()
        hotkeys = [str(item) for item in getattr(metagraph, "hotkeys", [])]
        if hotkey not in hotkeys:
            return None
        index = hotkeys.index(hotkey)
        uids = getattr(metagraph, "uids", [])
        return _to_int(uids[index] if index < len(uids) else index)

    def validator_permit(self, uid: int) -> bool:
        permits = getattr(self.sync_metagraph(), "validator_permit", [])
        return bool(permits[uid]) if uid < len(permits) else False

    def weights_rate_limit(self) -> int:
        for name in ("weights_rate_limit", "get_weights_rate_limit"):
            fn = getattr(self.subtensor, name, None)
            if fn is None:
                continue
            try:
                return int(fn(netuid=self.netuid))
            except TypeError:
                return int(fn(self.netuid))
            except Exception:  # noqa: BLE001 - unavailable hyperparams are non-fatal.
                continue
        return 0

    def blocks_since_last_update(self, uid: int) -> int | None:
        last_updates = getattr(self.sync_metagraph(), "last_update", None)
        if last_updates is None or uid >= len(last_updates):
            return None
        return max(0, self.block() - _to_int(last_updates[uid]))

    def commit_reveal_enabled(self) -> bool | None:
        for name in (
            "commit_reveal_enabled",
            "commit_reveal_weights_enabled",
            "get_commit_reveal_weights_enabled",
        ):
            fn = getattr(self.subtensor, name, None)
            if fn is None:
                continue
            try:
                return bool(fn(netuid=self.netuid))
            except TypeError:
                try:
                    return bool(fn(self.netuid))
                except Exception:  # noqa: BLE001 - unavailable probes fail closed below.
                    continue
            except Exception:  # noqa: BLE001 - unavailable probes fail closed below.
                continue
        return None

    def process_and_convert(
        self,
        uids: list[int],
        weights: list[float],
    ) -> tuple[list[int], list[int]]:
        import numpy as np
        from bittensor.utils import weight_utils

        processed_uids, processed_weights = weight_utils.process_weights_for_netuid(
            uids=np.array(uids, dtype=np.int64),
            weights=np.array(weights, dtype=np.float32),
            netuid=self.netuid,
            subtensor=self.subtensor,
            metagraph=self.sync_metagraph(),
        )
        emit_uids, emit_weights = weight_utils.convert_weights_and_uids_for_emit(
            processed_uids,
            processed_weights,
        )
        return [_to_int(uid) for uid in emit_uids], [_to_int(weight) for weight in emit_weights]

    def set_weights(self, *, uids: list[int], weights: list[int], version_key: int) -> Any:
        return self.subtensor.set_weights(
            wallet=self.wallet,
            netuid=self.netuid,
            uids=uids,
            weights=weights,
            version_key=version_key,
            wait_for_inclusion=True,
            wait_for_finalization=False,
        )

    def read_back_weights(self, validator_uid: int) -> dict[str, Any] | None:
        del validator_uid
        return None

    def miner_endpoints(self, *, exclude_hotkey: str) -> list[dict[str, Any]]:
        metagraph = self.sync_metagraph()
        hotkeys = [str(item) for item in getattr(metagraph, "hotkeys", [])]
        axons = list(getattr(metagraph, "axons", []))
        endpoints: list[dict[str, Any]] = []
        for index, hotkey in enumerate(hotkeys):
            if hotkey == exclude_hotkey or index >= len(axons):
                continue
            axon = axons[index]
            port = _to_int(getattr(axon, "port", 0))
            if port <= 0:
                continue
            endpoints.append(
                {
                    "host": str(getattr(axon, "ip", "127.0.0.1") or "127.0.0.1"),
                    "port": port,
                    "hotkey": hotkey,
                    "uid": self.hotkey_uid(hotkey) or index,
                    "coldkey": str(getattr(axon, "coldkey", "")),
                }
            )
        return endpoints


class SubtensorChain:
    """Read-only, dry-run, and gated-live Subtensor chain client."""

    def __init__(
        self,
        *,
        network: str,
        netuid: int | None,
        wallet_name: str,
        wallet_hotkey: str,
        publish: str = "dry-run",
        allow_extrinsics: bool = False,
        allow_commit_reveal: bool = False,
        confirmation: str = "",
        substrate: Any | None = None,
    ) -> None:
        if publish not in {"dry-run", "live"}:
            raise ValueError(f"unsupported SubtensorChain publish mode: {publish}")
        self.network = assert_safe_network(network)
        self.netuid = netuid
        self.wallet_name = wallet_name
        self.wallet_hotkey = wallet_hotkey
        self.publish = publish
        self.allow_extrinsics = allow_extrinsics
        self.allow_commit_reveal = allow_commit_reveal
        self.confirmation = confirmation
        self._substrate = substrate

    @property
    def substrate(self) -> Any:
        if self.netuid is None:
            raise ChainSetupError("netuid_unset")
        if self._substrate is None:
            self._substrate = _Substrate(
                network=self.network,
                netuid=self.netuid,
                wallet_name=self.wallet_name,
                wallet_hotkey=self.wallet_hotkey,
            )
        return self._substrate

    def preflight(self) -> dict[str, Any]:
        if self.netuid is None:
            return {"mode": "error", "reason": "netuid_unset", "netuid": None}
        substrate = self.substrate
        block = substrate.block()
        subnet_exists = substrate.subnet_exists()
        record: dict[str, Any] = {
            "mode": "read_only",
            "reason": "ok",
            "network": self.network,
            "netuid": self.netuid,
            "block": block,
            "subnet_exists": subnet_exists,
            "validator_hotkey": substrate.validator_hotkey,
            "validator_uid": None,
            "validator_registered": False,
            "validator_permit": False,
            "weights_rate_limit": None,
            "blocks_since_last_update": None,
            "commit_reveal_enabled": None,
            "commit_reveal_probe_failed": False,
        }
        if not subnet_exists:
            record["mode"] = "error"
            record["reason"] = "netuid_absent"
            return record
        validator_uid = substrate.hotkey_uid(substrate.validator_hotkey)
        record["validator_uid"] = validator_uid
        record["validator_registered"] = validator_uid is not None
        if validator_uid is None:
            record["mode"] = "error"
            record["reason"] = "validator_unregistered"
            return record
        record["validator_permit"] = substrate.validator_permit(validator_uid)
        record["weights_rate_limit"] = substrate.weights_rate_limit()
        record["blocks_since_last_update"] = substrate.blocks_since_last_update(validator_uid)
        try:
            commit_reveal_enabled = substrate.commit_reveal_enabled()
        except Exception as exc:  # noqa: BLE001 - probe failures must fail closed.
            record["commit_reveal_enabled"] = None
            record["commit_reveal_probe_failed"] = True
            record["commit_reveal_probe_error"] = str(exc)
            record["mode"] = "error"
            record["reason"] = "commit_reveal_probe_failed"
            return record
        record["commit_reveal_enabled"] = commit_reveal_enabled
        if commit_reveal_enabled is None:
            record["commit_reveal_probe_failed"] = True
            record["mode"] = "error"
            record["reason"] = "commit_reveal_probe_failed"
            return record
        return record

    def map_hotkeys(self, active_hotkeys: list[str]) -> HotkeyUidMapping:
        mapping: dict[str, int] = {}
        dropped: list[str] = []
        for hotkey in active_hotkeys:
            uid = self.substrate.hotkey_uid(hotkey)
            if uid is None:
                dropped.append(hotkey)
            else:
                mapping[hotkey] = uid
        return HotkeyUidMapping(
            hotkey_to_uid=dict(sorted(mapping.items())),
            dropped_hotkeys=dropped,
        )

    def miner_endpoints(self) -> list[dict[str, Any]]:
        return self.substrate.miner_endpoints(exclude_hotkey=self.substrate.validator_hotkey)

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
        if fallback_reason in {"all_zero", "epoch_degraded_all_infra"} or all(
            float(value) == 0.0 for value in weights.values()
        ):
            reason = (
                fallback_reason
                if fallback_reason in {"all_zero", "epoch_degraded_all_infra"}
                else "all_zero"
            )
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode="skipped",
                reason=reason,
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
            )
            return ChainWeightResult(mode="skipped", receipt=receipt, reason=reason)

        if self.netuid is None:
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode="error",
                reason="netuid_unset",
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
            )
            return ChainWeightResult(mode="error", receipt=receipt, reason="netuid_unset")

        try:
            state = self._readiness_state()
        except Exception as exc:  # noqa: BLE001
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode="error",
                reason="rpc_unreachable",
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
                extra={"error": str(exc)},
            )
            return ChainWeightResult(mode="error", receipt=receipt, reason="rpc_unreachable")

        skip_reason = self._readiness_skip_reason(state)
        if skip_reason is not None:
            mode = (
                "error"
                if skip_reason in {"netuid_absent", "validator_unregistered"}
                else "skipped"
            )
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode=mode,
                reason=skip_reason,
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
                state=state,
            )
            return ChainWeightResult(mode=mode, receipt=receipt, reason=skip_reason)

        mapping = self.map_hotkeys(active_hotkeys)
        if not mapping.hotkey_to_uid:
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode="skipped",
                reason="no_registered_miners",
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
                state=state,
                mapping=mapping,
            )
            return ChainWeightResult(
                mode="skipped",
                receipt=receipt,
                reason="no_registered_miners",
            )

        payload = self._payload(weights, mapping, spec_version=spec_version)
        if self.publish == "dry-run":
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode="dry_run",
                reason="dry_run_ok",
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
                state=state,
                mapping=mapping,
                payload=payload,
            )
            return ChainWeightResult(mode="dry_run", receipt=receipt, reason="dry_run_ok")

        if not self._extrinsics_allowed():
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode="error",
                reason="extrinsics_not_allowed",
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
                state=state,
                mapping=mapping,
                payload=payload,
                extra={"missing_gates": self._missing_extrinsic_gates()},
            )
            return ChainWeightResult(
                mode="error",
                receipt=receipt,
                reason="extrinsics_not_allowed",
            )

        try:
            response = self.substrate.set_weights(
                uids=payload["uids_emitted"],
                weights=payload["weights_u16"],
                version_key=spec_version,
            )
        except Exception as exc:  # noqa: BLE001
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode="error",
                reason="extrinsic_failed",
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
                state=state,
                mapping=mapping,
                payload=payload,
                submission=_submission_from_error(exc),
            )
            return ChainWeightResult(mode="error", receipt=receipt, reason="extrinsic_failed")

        submission = _submission_from_response(response)
        if not submission["success"]:
            receipt = self._write_receipt(
                cfg,
                epoch_id=epoch_id,
                mode="error",
                reason="extrinsic_failed",
                weights=weights,
                active_hotkeys=active_hotkeys,
                spec_version=spec_version,
                state=state,
                mapping=mapping,
                payload=payload,
                submission=submission,
            )
            return ChainWeightResult(mode="error", receipt=receipt, reason="extrinsic_failed")

        submit_reason = (
            "submitted_commit_reveal"
            if state.get("commit_reveal_enabled") is True
            else "submitted_ok"
        )
        read_back = self.substrate.read_back_weights(int(state["validator_uid"]))
        receipt = self._write_receipt(
            cfg,
            epoch_id=epoch_id,
            mode="submitted",
            reason=submit_reason,
            weights=weights,
            active_hotkeys=active_hotkeys,
            spec_version=spec_version,
            state=state,
            mapping=mapping,
            payload=payload,
            submission=submission,
            read_back=read_back,
        )
        return ChainWeightResult(mode="submitted", receipt=receipt, reason=submit_reason)

    def _readiness_state(self) -> dict[str, Any]:
        state = self.preflight()
        return state

    def _readiness_skip_reason(self, state: dict[str, Any]) -> str | None:
        if not state.get("subnet_exists", False):
            return "netuid_absent"
        if state.get("validator_uid") is None:
            return "validator_unregistered"
        if not state.get("validator_permit", False):
            return "no_permit"
        limit = state.get("weights_rate_limit")
        since = state.get("blocks_since_last_update")
        if limit is not None and since is not None and int(since) < int(limit):
            return "rate_limited"
        commit_reveal_enabled = state.get("commit_reveal_enabled")
        if commit_reveal_enabled is None or state.get("commit_reveal_probe_failed", False):
            return "commit_reveal_probe_failed"
        if commit_reveal_enabled and not self.allow_commit_reveal:
            return "commit_reveal_enabled"
        return None

    def _payload(
        self,
        weights: dict[str, float],
        mapping: HotkeyUidMapping,
        *,
        spec_version: int,
    ) -> dict[str, Any]:
        mapped = [
            (hotkey, uid, float(weights.get(hotkey, 0.0)))
            for hotkey, uid in sorted(mapping.hotkey_to_uid.items(), key=lambda item: item[1])
            if float(weights.get(hotkey, 0.0)) > 0.0
        ]
        if not mapped:
            uids_emitted: list[int] = []
            weights_u16: list[int] = []
        else:
            total = sum(value for _, _, value in mapped)
            normalized = [(hotkey, uid, value / total) for hotkey, uid, value in mapped]
            uids_emitted, weights_u16 = self.substrate.process_and_convert(
                [uid for _, uid, _ in normalized],
                [value for _, _, value in normalized],
            )
        payload = {
            "netuid": self.netuid,
            "uids_emitted": uids_emitted,
            "weights_u16": weights_u16,
            "version_key": spec_version,
        }
        payload["payload_digest"] = _payload_digest(payload)
        return payload

    def _write_receipt(
        self,
        cfg: SubnetConfig,
        *,
        epoch_id: int,
        mode: str,
        reason: str,
        weights: dict[str, float],
        active_hotkeys: list[str],
        spec_version: int,
        state: dict[str, Any] | None = None,
        mapping: HotkeyUidMapping | None = None,
        payload: dict[str, Any] | None = None,
        submission: dict[str, Any] | None = None,
        read_back: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        epoch_dir = cfg.epoch_dir(epoch_id)
        epoch_dir.mkdir(parents=True, exist_ok=True)
        receipt_name = f"chain_receipt_epoch_{epoch_id}.json"
        path = epoch_dir / receipt_name
        state = state or {}
        mapping = mapping or HotkeyUidMapping(
            hotkey_to_uid={},
            dropped_hotkeys=list(active_hotkeys),
        )
        payload_digest = payload["payload_digest"] if payload else None
        receipt = {
            "epoch_id": epoch_id,
            "mode": mode,
            "reason": reason,
            "network": self.network,
            "netuid": self.netuid,
            "spec_version": spec_version,
            "validator": {
                "hotkey": state.get("validator_hotkey"),
                "uid": state.get("validator_uid"),
            },
            "chain_state": state,
            "active_hotkey_to_uid": mapping.hotkey_to_uid,
            "dropped_hotkeys": mapping.dropped_hotkeys,
            "normalized_weights": {
                hotkey: float(weights.get(hotkey, 0.0)) for hotkey in sorted(active_hotkeys)
            },
            "payload": payload,
            "payload_digest": payload_digest,
            "submission": submission,
            "read_back": read_back,
        }
        if extra:
            receipt["extra"] = extra
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "receipt_file": receipt_name,
            "payload_digest": payload_digest,
            "netuid": self.netuid,
            "n_uids": len(payload["uids_emitted"]) if payload else 0,
        }

    def _extrinsics_allowed(self) -> bool:
        return not self._missing_extrinsic_gates()

    def _missing_extrinsic_gates(self) -> list[str]:
        missing: list[str] = []
        if not self.allow_extrinsics:
            missing.append("client_flag")
        if os.environ.get("DOLORES_ALLOW_EXTRINSICS") != "1":
            missing.append("env")
        if self.publish != "live":
            missing.append("cli_live")
        if self.confirmation != LIVE_CONFIRMATION:
            missing.append("confirmation")
        return missing


class ChainSetupError(RuntimeError):
    """Raised only for internal setup mistakes; public results are recorded."""


def build_chain_client(
    cfg: SubnetConfig,
    *,
    publish: str = "off",
    allow_extrinsics: bool = False,
    confirmation: str = "",
    substrate: Any | None = None,
) -> ChainClient:
    if publish not in CHAIN_PUBLISH_MODES:
        raise ValueError(f"unknown chain publish mode: {publish}")
    if publish == "off":
        return NullChain()
    if cfg.network is None:
        raise ValueError("chain publish requires a configured chain network")
    return SubtensorChain(
        network=cfg.network,
        netuid=cfg.netuid,
        wallet_name=cfg.wallet_name,
        wallet_hotkey=cfg.wallet_hotkey,
        publish=publish,
        allow_extrinsics=allow_extrinsics,
        allow_commit_reveal=cfg.allow_commit_reveal,
        confirmation=confirmation,
        substrate=substrate,
    )


def _payload_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _submission_from_response(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        success = bool(response.get("success", response.get("is_success", False)))
        message = str(response.get("message", response.get("error", "")) or "")
        receipt = response.get("extrinsic_receipt")
        submission = {
            "success": success,
            "message": message,
            "block_hash": _json_scalar(
                response.get("block_hash") or _metadata_value(receipt, "block_hash")
            ),
            "extrinsic_hash": _json_scalar(
                response.get("extrinsic_hash") or _metadata_value(receipt, "extrinsic_hash")
            ),
            "included": _json_scalar(
                response.get("included")
                if response.get("included") is not None
                else _metadata_value(receipt, "is_included", "included")
            ),
            "finalized": _json_scalar(
                response.get("finalized")
                if response.get("finalized") is not None
                else _metadata_value(receipt, "is_finalized", "finalized")
            ),
        }
        _add_optional_submission_field(submission, "block_number", receipt, "block_number")
        _add_optional_submission_field(
            submission,
            "extrinsic_index",
            receipt,
            "extrinsic_idx",
            "extrinsic_index",
        )
        _add_optional_submission_field(submission, "receipt_success", receipt, "is_success")
        return submission
    receipt = getattr(response, "extrinsic_receipt", None)
    submission = {
        "success": bool(
            getattr(response, "success", getattr(response, "is_success", False))
        ),
        "message": str(
            getattr(response, "message", getattr(response, "error_message", "")) or ""
        ),
        "block_hash": _json_scalar(
            getattr(response, "block_hash", None) or _metadata_value(receipt, "block_hash")
        ),
        "extrinsic_hash": _json_scalar(
            getattr(response, "extrinsic_hash", None)
            or _metadata_value(receipt, "extrinsic_hash")
        ),
        "included": _json_scalar(
            getattr(response, "is_included", None)
            if getattr(response, "is_included", None) is not None
            else _metadata_value(receipt, "is_included", "included")
        ),
        "finalized": _json_scalar(
            getattr(response, "is_finalized", None)
            if getattr(response, "is_finalized", None) is not None
            else _metadata_value(receipt, "is_finalized", "finalized")
        ),
    }
    _add_optional_submission_field(submission, "block_number", receipt, "block_number")
    _add_optional_submission_field(
        submission,
        "extrinsic_index",
        receipt,
        "extrinsic_idx",
        "extrinsic_index",
    )
    _add_optional_submission_field(submission, "receipt_success", receipt, "is_success")
    return submission


def _submission_from_error(exc: Exception) -> dict[str, Any]:
    return {
        "success": False,
        "message": str(exc),
        "block_hash": None,
        "extrinsic_hash": None,
        "included": False,
        "finalized": False,
    }


def _to_int(value: Any) -> int:
    if hasattr(value, "item"):
        return int(value.item())
    return int(value)


def _metadata_value(source: Any, *names: str) -> Any:
    if source is None:
        return None
    for name in names:
        if isinstance(source, dict):
            value = source.get(name)
        else:
            value = getattr(source, name, None)
        if value is not None:
            return value
    return None


def _json_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _add_optional_submission_field(
    submission: dict[str, Any],
    target: str,
    source: Any,
    *names: str,
) -> None:
    value = _metadata_value(source, *names)
    if value is not None:
        submission[target] = _json_scalar(value)
