"""Installed one-shot and supervised recurring validator CLI."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from dolores_subnet import archive
from dolores_subnet.bridge import validate_submission
from dolores_subnet.chain import (
    LIVE_CONFIRMATION,
    SubtensorChain,
    build_chain_client,
)
from dolores_subnet.config import (
    DEFAULT_QUOTA,
    LOCALNET_ALT_NETWORK,
    LOCALNET_NETWORK,
    Mode,
    SubnetConfig,
    parse_mode,
)
from dolores_subnet.endpoints import require_cohort_target
from dolores_subnet.epoch import EpochCompletionError, repair_jsonl_tail, run_epoch
from dolores_subnet.gates import GateContext
from dolores_subnet.packaging import loads_wire_json
from dolores_subnet.validator_state import ValidatorStateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dolores-validator",
        description="Operate a serialized Dolores validator tick.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    tick = subparsers.add_parser("tick", help="run one locked automatically numbered epoch")
    _runtime_args(tick)
    tick.set_defaults(handler=tick_command)

    health = subparsers.add_parser("health", help="report local and read-only chain health")
    _health_args(health)
    health.set_defaults(handler=health_command)

    recover = subparsers.add_parser(
        "recover-receipt",
        help="finish a weights-submitting epoch from its canonical completion marker",
    )
    recover.add_argument("--work", type=Path, required=True)
    recover.set_defaults(handler=recover_receipt_command)

    once = subparsers.add_parser("once", help="run the legacy offline fixture validator")
    once.add_argument("--submissions", type=Path, required=True)
    once.add_argument("--work", type=Path, required=True)
    once.add_argument("--epoch", type=int, required=True)
    once.add_argument("--quota", type=int, default=DEFAULT_QUOTA)
    once.set_defaults(handler=once_command)
    return parser


def _runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=[Mode.WIRE.value, Mode.LOCALNET.value, Mode.TESTNET.value],
        default=Mode.TESTNET.value,
    )
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--quota", type=int, default=DEFAULT_QUOTA)
    parser.add_argument("--miner-endpoints", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--wallet.name", dest="wallet_name", required=True)
    parser.add_argument("--wallet.hotkey", dest="wallet_hotkey", required=True)
    parser.add_argument("--network")
    parser.add_argument("--netuid", type=int)
    parser.add_argument("--chain", choices=["off", "dry-run", "live"], default="dry-run")
    parser.add_argument("--allow-extrinsics", action="store_true")
    parser.add_argument("--allow-commit-reveal", action="store_true")
    parser.add_argument("--confirm-live", default="")
    parser.add_argument("--panel-mode", choices=["mock", "calibrate"], default=None)
    parser.add_argument("--panel-max-tasks", type=int, default=None)
    parser.add_argument("--panel-dry-run", action="store_true")
    parser.add_argument("--allow-provider-spend", action="store_true")


def _health_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=[Mode.LOCALNET.value, Mode.TESTNET.value],
        default=Mode.TESTNET.value,
    )
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--wallet.name", dest="wallet_name", required=True)
    parser.add_argument("--wallet.hotkey", dest="wallet_hotkey", required=True)
    parser.add_argument("--network")
    parser.add_argument("--netuid", type=int)
    parser.add_argument(
        "--probe-wire",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="require a signed quota-zero reachability probe (enabled by default)",
    )
    parser.add_argument("--timeout", type=float, default=10.0)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except Exception as exc:  # noqa: BLE001 - CLI emits one stable failure line.
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


def tick_command(args: argparse.Namespace) -> int:
    mode = parse_mode(args.mode)
    _validate_tick_target(args, mode)
    if not 1 <= args.quota <= DEFAULT_QUOTA:
        raise ValueError(f"quota must be within 1..{DEFAULT_QUOTA}")
    cfg = SubnetConfig.from_env(
        mode=mode,
        work_dir=args.work,
        wallet_name=args.wallet_name,
        wallet_hotkey=args.wallet_hotkey,
        network=args.network,
        netuid=args.netuid,
        allow_commit_reveal=args.allow_commit_reveal,
        panel_mode=args.panel_mode,
        panel_max_tasks=args.panel_max_tasks,
        panel_dry_run=args.panel_dry_run or None,
        allow_provider_spend=args.allow_provider_spend,
    )
    if cfg.holdout_required and not cfg.holdout_secret:
        raise ValueError("DOLORES_HOLDOUT_SECRET is required (value not displayed)")
    confirmation = _live_confirmation(args, cfg)
    chain_client = build_chain_client(
        cfg,
        publish=args.chain,
        allow_extrinsics=args.allow_extrinsics,
        confirmation=confirmation,
    )
    store = _state_store(cfg)
    with store.tick() as tick:
        assert tick.epoch_id is not None
        tick.mark_querying()
        miners = _query_miners_for_tick(
            args=args,
            cfg=cfg,
            chain_client=chain_client,
            epoch_id=tick.epoch_id,
        )
        try:
            result = run_epoch(
                cfg,
                miners,
                epoch_id=tick.epoch_id,
                quota=args.quota,
                chain_client=chain_client,
                phase_hook=tick.phase_hook,
            )
        except EpochCompletionError as exc:
            # A dry, pre-submit error/skip is definite and may advance. Live
            # attempt ambiguity raises a different exception and deliberately
            # leaves the durable phase at weights_submitting.
            tick.fail_weights(str(exc))
            raise

    print(f"epoch_id={tick.epoch_id}")
    print(f"weights_artifact={result.artifact_path}")
    print(
        f"chain_mode={result.chain_result.mode} "
        f"chain_reason={result.chain_result.reason or ''}"
    )
    for hotkey, weight in sorted(result.weights.items()):
        print(f"{hotkey} weight={weight:.6f} epoch_score={result.epoch_scores.get(hotkey, 0):.6f}")
    reachable = [miner for miner in miners if not getattr(miner, "terminal_status", None)]
    if not reachable or result.chain_result.mode == "error":
        return 1
    return 0


def _validate_tick_target(args: argparse.Namespace, mode: Mode) -> None:
    if mode is Mode.TESTNET:
        if args.network is None or args.netuid is None:
            raise ValueError("testnet tick requires explicit --network test --netuid 523")
        require_cohort_target(args.network, args.netuid)
        if args.miner_endpoints:
            raise ValueError(
                "testnet tick requires metagraph discovery; manual endpoints forbidden"
            )
        if args.chain == "off":
            raise ValueError("testnet discovery requires --chain dry-run or --chain live")
    elif mode is Mode.WIRE:
        if not args.miner_endpoints:
            raise ValueError("wire tick requires --miner-endpoints")
        if args.chain != "off":
            raise ValueError("wire tick requires --chain off")
    elif mode is Mode.LOCALNET:
        _require_localnet_target(args.network, args.netuid, operation="localnet tick")
        if args.chain == "off" and not args.miner_endpoints:
            raise ValueError("localnet chain-off tick requires --miner-endpoints")


def _query_miners_for_tick(
    *,
    args: argparse.Namespace,
    cfg: SubnetConfig,
    chain_client: Any,
    epoch_id: int,
) -> list[Any]:
    import bittensor as bt

    from dolores_subnet.wire import MinerEndpoint, parse_miner_endpoints, query_miners

    wallet = bt.Wallet(name=cfg.wallet_name, hotkey=cfg.wallet_hotkey)
    if args.miner_endpoints:
        endpoints = parse_miner_endpoints(
            args.miner_endpoints,
            default_coldkey=wallet.coldkeypub.ss58_address,
        )
    else:
        if not isinstance(chain_client, SubtensorChain):
            raise RuntimeError("metagraph discovery requires a SubtensorChain")
        discovered = chain_client.miner_endpoints()
        endpoints = [
            MinerEndpoint(
                host=str(item["host"]),
                port=int(item["port"]),
                hotkey=str(item["hotkey"]),
                uid=int(item["uid"]),
                coldkey=str(item.get("coldkey") or wallet.coldkeypub.ss58_address),
            )
            for item in discovered
        ]
    if not endpoints:
        raise RuntimeError("no eligible miner axons discovered")
    return query_miners(
        wallet=wallet,
        endpoints=endpoints,
        epoch_id=epoch_id,
        quota=args.quota,
        timeout=args.timeout,
        max_response_bytes=cfg.max_response_bytes,
    )


def health_command(args: argparse.Namespace) -> int:
    mode = parse_mode(args.mode)
    _validate_health_target(args, mode)
    cfg = SubnetConfig.from_env(
        mode=mode,
        work_dir=args.work,
        wallet_name=args.wallet_name,
        wallet_hotkey=args.wallet_hotkey,
        network=args.network,
        netuid=args.netuid,
    )
    state = _state_store(cfg).read()
    docker = _docker_health(cfg.verifier_image)
    chain = SubtensorChain(
        network=cfg.network or "",
        netuid=cfg.netuid,
        wallet_name=cfg.wallet_name,
        wallet_hotkey=cfg.wallet_hotkey,
        publish="dry-run",
    )
    try:
        chain_state = chain.preflight()
        endpoints = chain.miner_endpoints() if chain_state.get("mode") != "error" else []
    except Exception as exc:  # noqa: BLE001 - health must emit structured failure.
        chain_state = {
            "mode": "error",
            "reason": "rpc_or_wallet_unreachable",
            "error_type": type(exc).__name__,
        }
        endpoints = []
    signed_reachable: int | None = None
    probe_error_type: str | None = None
    if args.probe_wire and endpoints:
        try:
            signed_reachable = _signed_health_probe(
                cfg=cfg,
                endpoint_rows=endpoints,
                epoch_id=state.next_epoch_id,
                timeout=args.timeout,
            )
        except Exception as exc:  # noqa: BLE001 - never leak wallet/path details.
            signed_reachable = 0
            probe_error_type = type(exc).__name__
    ambiguous = state.phase == "weights_submitting"
    degraded_conditions: list[str] = []
    if not docker["ok"]:
        degraded_conditions.append(str(docker.get("reason") or "docker_unhealthy"))
    if not cfg.holdout_secret:
        degraded_conditions.append("holdout_secret_missing")
    if chain_state.get("mode") == "error":
        degraded_conditions.append(
            f"chain:{chain_state.get('reason') or 'readiness_error'}"
        )
    if not endpoints:
        degraded_conditions.append("no_public_miners_discovered")
    if not args.probe_wire:
        degraded_conditions.append("signed_reachability_probe_disabled")
    elif signed_reachable != len(endpoints):
        degraded_conditions.append(
            f"signed_reachability:{signed_reachable or 0}/{len(endpoints)}"
        )
    if ambiguous:
        degraded_conditions.append("ambiguous_weight_submission")
    if state.last_error:
        degraded_conditions.append("last_epoch_failed")
    if state.last_receipt and state.last_receipt.get("mode") == "error":
        degraded_conditions.append(
            f"last_chain_receipt:{state.last_receipt.get('reason') or 'error'}"
        )
    ok = bool(
        not degraded_conditions
    )
    payload = {
        "ok": ok,
        "network": cfg.network,
        "netuid": cfg.netuid,
        "runtime_state": state.to_dict(),
        "last_completed_epoch": state.last_completed_epoch,
        "last_successful_weight_receipt": state.last_successful_weight_receipt,
        "ambiguous_weight_submission": ambiguous,
        "holdout_secret_configured": bool(cfg.holdout_secret),
        "docker": docker,
        "chain": chain_state,
        "blocks_since_validator_update": chain_state.get("blocks_since_last_update"),
        "discovered_public_miners": len(endpoints),
        "signed_probe_requested": bool(args.probe_wire),
        "signed_reachable_miners": signed_reachable,
        "reachable_miner_count": signed_reachable,
        "probe_error_type": probe_error_type,
        "degraded_conditions": degraded_conditions,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if ok else 1


def _validate_health_target(args: argparse.Namespace, mode: Mode) -> None:
    if args.network is None or args.netuid is None:
        raise ValueError("health requires explicit --network and --netuid")
    if mode is Mode.TESTNET:
        require_cohort_target(args.network, args.netuid)
    elif mode is Mode.LOCALNET:
        _require_localnet_target(args.network, args.netuid, operation="localnet health")


def _require_localnet_target(
    network: str | None,
    netuid: int | None,
    *,
    operation: str,
) -> None:
    allowed = {LOCALNET_NETWORK, LOCALNET_ALT_NETWORK}
    if network is None or netuid is None:
        raise ValueError(f"{operation} requires explicit --network and --netuid")
    if network not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(
            f"{operation} requires a loopback Subtensor network ({choices}); "
            "public network test is forbidden"
        )
    if netuid < 0:
        raise ValueError(f"{operation} netuid must be non-negative")


def _signed_health_probe(
    *,
    cfg: SubnetConfig,
    endpoint_rows: list[dict[str, Any]],
    epoch_id: int,
    timeout: float,
) -> int:
    import bittensor as bt

    from dolores_subnet.wire import MinerEndpoint, query_miners

    wallet = bt.Wallet(name=cfg.wallet_name, hotkey=cfg.wallet_hotkey)
    endpoints = [
        MinerEndpoint(
            host=str(item["host"]),
            port=int(item["port"]),
            hotkey=str(item["hotkey"]),
            uid=int(item["uid"]),
            coldkey=str(item.get("coldkey") or wallet.coldkeypub.ss58_address),
        )
        for item in endpoint_rows
    ]
    miners = query_miners(
        wallet=wallet,
        endpoints=endpoints,
        epoch_id=epoch_id,
        quota=0,
        timeout=timeout,
        max_response_bytes=cfg.max_response_bytes,
    )
    return sum(1 for miner in miners if not miner.terminal_status)


def _docker_health(image: str) -> dict[str, object]:
    docker = shutil.which("docker")
    if docker is None:
        return {"ok": False, "reason": "docker_cli_missing", "image": image}
    daemon = subprocess.run(
        [docker, "version", "--format", "{{.Server.Version}}"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if daemon.returncode != 0:
        return {"ok": False, "reason": "docker_daemon_unavailable", "image": image}
    inspect = subprocess.run(
        [docker, "image", "inspect", image],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    return {
        "ok": inspect.returncode == 0,
        "reason": "ok" if inspect.returncode == 0 else "verifier_image_missing",
        "server_version": daemon.stdout.strip(),
        "image": image,
    }


def recover_receipt_command(args: argparse.Namespace) -> int:
    archive_dir = args.work.expanduser().resolve() / "subnet_archive"
    store = ValidatorStateStore(archive_dir / "validator_runtime")
    state = store.recover_receipt()
    print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
    return 0


def once_command(args: argparse.Namespace) -> int:
    cfg = SubnetConfig.from_env(mode=Mode.OFFLINE, work_dir=args.work)
    archive.init_archive(cfg)
    repair_jsonl_tail(cfg.submissions_path)
    context = GateContext(quota=args.quota)
    failures = 0
    for path, payload in _load_ordered_payloads(args.submissions):
        outcome = validate_submission(
            payload,
            cfg,
            context=context,
            miner_hotkey=f"fixture:{path.stem}",
        )
        archive.append_submission(
            cfg,
            outcome.to_record(
                epoch_id=args.epoch,
                miner_hotkey=f"fixture:{path.stem}",
                miner_uid=None,
            ),
        )
        print(f"{path.stem} -> {outcome.status}:{outcome.reason}")
        failures += int(outcome.status == "infra_error")
    return 1 if failures else 0


def _state_store(cfg: SubnetConfig) -> ValidatorStateStore:
    return ValidatorStateStore(cfg.archive_dir / "validator_runtime")


def _live_confirmation(args: argparse.Namespace, cfg: SubnetConfig) -> str:
    if args.chain != "live":
        return ""
    if args.confirm_live:
        return str(args.confirm_live)
    if not sys.stdin.isatty():
        return ""
    return input(
        f"Type {LIVE_CONFIRMATION} to allow live set_weights on "
        f"network={cfg.network} netuid={cfg.netuid}: "
    )


def _load_ordered_payloads(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    items: list[tuple[str, Path, dict[str, Any]]] = []
    for path in sorted(root.glob("*.json")):
        payload = loads_wire_json(path)
        items.append((str(payload.get("package_hash", "")), path, payload))
    return [(path, payload) for _, path, payload in sorted(items)]


if __name__ == "__main__":
    raise SystemExit(main())
