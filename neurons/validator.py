"""Validator entrypoint for offline and future wire/chain modes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet import archive  # noqa: E402
from dolores_subnet.bridge import validate_submission  # noqa: E402
from dolores_subnet.config import DEFAULT_QUOTA, Mode, SubnetConfig, parse_mode  # noqa: E402
from dolores_subnet.epoch import run_epoch  # noqa: E402
from dolores_subnet.gates import GateContext  # noqa: E402
from dolores_subnet.packaging import loads_wire_json  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Dolores subnet validator epoch.")
    parser.add_argument("--mode", choices=[mode.value for mode in Mode], default="offline")
    parser.add_argument("--submissions", type=Path, required=False)
    parser.add_argument("--work", type=Path, default=Path("work/validator"))
    parser.add_argument("--epoch", type=int, default=1)
    parser.add_argument("--quota", type=int, default=DEFAULT_QUOTA)
    parser.add_argument("--miner-endpoints", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--wallet.name", dest="wallet_name", default="dolores-test")
    parser.add_argument("--wallet.hotkey", dest="wallet_hotkey", default="validator")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    mode = parse_mode(args.mode)
    if mode is Mode.WIRE:
        return run_wire(args)
    if mode not in {Mode.MOCK, Mode.OFFLINE}:
        print(
            f"mode {mode.value} requires chain support and is not implemented yet",
            file=sys.stderr,
        )
        return 2
    if args.submissions is None:
        print("--submissions is required for the M2 offline validator path", file=sys.stderr)
        return 2

    cfg = SubnetConfig.from_env(mode=mode, work_dir=args.work)
    archive.init_archive(cfg)
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
        label = path.stem
        print(
            f"{label} -> {outcome.status}"
            f"{':' + outcome.reason if outcome.reason else ''}"
            f" task_value={outcome.task_value}"
        )
        if outcome.status in {"invalid", "rejected", "infra_error"}:
            failures += int(outcome.status == "infra_error")
    return 1 if failures else 0


def run_wire(args: argparse.Namespace) -> int:
    import bittensor as bt

    from dolores_subnet.wire import parse_miner_endpoints, query_miners

    if not args.miner_endpoints:
        print("--miner-endpoints is required for wire mode", file=sys.stderr)
        return 2
    cfg = SubnetConfig.from_env(
        mode=Mode.WIRE,
        work_dir=args.work,
        wallet_name=args.wallet_name,
        wallet_hotkey=args.wallet_hotkey,
    )
    wallet = bt.Wallet(name=cfg.wallet_name, hotkey=cfg.wallet_hotkey)
    endpoints = parse_miner_endpoints(
        args.miner_endpoints,
        default_coldkey=wallet.coldkeypub.ss58_address,
    )
    miners = query_miners(
        wallet=wallet,
        endpoints=endpoints,
        epoch_id=args.epoch,
        quota=args.quota,
        timeout=args.timeout,
        max_response_bytes=cfg.max_response_bytes,
    )
    result = run_epoch(cfg, miners, epoch_id=args.epoch, quota=args.quota)
    print(f"weights_artifact={result.artifact_path}")
    for hotkey, weight in sorted(result.weights.items()):
        print(f"{hotkey} weight={weight:.6f} epoch_score={result.epoch_scores.get(hotkey, 0):.6f}")
    return 0


def _load_ordered_payloads(root: Path) -> list[tuple[Path, dict]]:
    items: list[tuple[str, Path, dict]] = []
    for path in sorted(root.glob("*.json")):
        payload = loads_wire_json(path)
        package_hash = str(payload.get("package_hash", ""))
        items.append((package_hash, path, payload))
    return [(path, payload) for _, path, payload in sorted(items)]


if __name__ == "__main__":
    raise SystemExit(main())
