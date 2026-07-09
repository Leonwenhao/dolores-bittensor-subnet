"""Miner helpers for offline and future wire modes."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.packaging import to_wire  # noqa: E402


@dataclass
class OfflineMiner:
    hotkey: str
    uid: int
    persona: str
    seed: int = 0

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del epoch_id
        if self.persona == "honest":
            return [to_wire(task) for task in _generated_tasks(quota, self.seed)]
        if self.persona == "duplicate_spammer":
            return [to_wire(task) for task in _duplicate_tasks(quota, self.seed)]
        if self.persona == "invalid":
            return [to_wire(task) for task in _invalid_tasks(max(1, quota), self.seed)]
        if self.persona == "lazy":
            return [to_wire(_generated_tasks(1, self.seed)[0])] if quota > 0 else []
        raise ValueError(f"unknown offline miner persona: {self.persona}")


def _generated_tasks(count: int, seed: int):
    from dolores.proposer.families import propose_family

    tasks = propose_family("parser_roundtrip", count=count, seed=seed)
    return [
        task.model_copy(update={"task_id": f"honest_{seed}_{index}_{task.task_id}"})
        for index, task in enumerate(tasks)
    ]


def _duplicate_tasks(count: int, seed: int):
    base = _generated_tasks(1, seed + 10_000)[0]
    return [
        base.model_copy(update={"task_id": f"duplicate_spam_{seed}_{index}"})
        for index in range(count)
    ]


def _invalid_tasks(count: int, seed: int):
    from dolores.schemas.task import TaskPackage

    base = TaskPackage.load(REPO_ROOT / "tests/fixtures/planted/bad_reference_fails")
    return [
        base.model_copy(update={"task_id": f"invalid_reference_{seed}_{index}"})
        for index in range(count)
    ]


@dataclass
class FileMiner:
    """Serve task packages loaded from disk (participant-authored tasks)."""

    hotkey: str
    uid: int
    task_dirs: list[Path]

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del epoch_id
        return [to_wire(task) for task in self._tasks()[:quota]]

    def _tasks(self) -> list[Any]:
        from dolores.schemas.task import TaskPackage

        tasks: list[Any] = []
        for root in self.task_dirs:
            try:
                tasks.append(TaskPackage.load(root))
                continue
            except Exception:  # noqa: BLE001 - fall through to subdirectory scan
                pass
            loaded_any = False
            for child in sorted(path for path in root.iterdir() if path.is_dir()):
                try:
                    tasks.append(TaskPackage.load(child))
                    loaded_any = True
                except Exception:  # noqa: BLE001 - skip non-package dirs
                    continue
            if not loaded_any:
                raise SystemExit(
                    f"--task-dir {root}: not a task package and no loadable "
                    "task package subdirectories found"
                )
        if not tasks:
            raise SystemExit("--task-dir provided but no task packages loaded")
        return tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or serve miner submissions.")
    parser.add_argument("--mode", choices=["offline", "wire"], default="offline")
    parser.add_argument("--persona", choices=["honest", "duplicate_spammer", "invalid", "lazy"])
    parser.add_argument("--quota", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--wallet.name", dest="wallet_name", default="dolores-test")
    parser.add_argument("--wallet.hotkey", dest="wallet_hotkey", default=None)
    parser.add_argument(
        "--task-dir",
        dest="task_dirs",
        action="append",
        default=None,
        help=(
            "serve task packages from this directory instead of a persona; "
            "may be a single package dir or a parent of package dirs; repeatable"
        ),
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help=(
            "publish this axon on-chain via serve_axon (signed by the hotkey; "
            "requires --netuid and an allowlisted --network; off by default)"
        ),
    )
    parser.add_argument("--netuid", type=int, default=None)
    parser.add_argument("--network", default=None)
    parser.add_argument(
        "--external-ip",
        default=None,
        help="IP to publish on-chain (e.g. your LAN IP); bind address stays --host",
    )
    parser.add_argument("--external-port", type=int, default=None)
    return parser


def _build_miner(args: argparse.Namespace, *, hotkey: str, persona: str):
    if args.task_dirs:
        return FileMiner(
            hotkey=hotkey,
            uid=0,
            task_dirs=[Path(path).expanduser() for path in args.task_dirs],
        )
    return OfflineMiner(hotkey=hotkey, uid=0, persona=persona, seed=args.seed)


def main() -> int:
    args = build_parser().parse_args()
    persona = args.persona or "honest"
    if args.mode == "wire":
        return serve_wire(args, persona=persona)
    miner = _build_miner(args, hotkey=f"local-{persona}", persona=persona)
    print(json.dumps(miner.submissions(epoch_id=1, quota=args.quota), indent=2, sort_keys=True))
    return 0


def _publish_axon(args: argparse.Namespace, *, axon: Any) -> None:
    """Publish the axon on-chain via serve_axon — only with explicit --publish.

    Hotkey-signed metadata write (ip/port only; no stake, no weights).
    The network allowlist is asserted before any chain object is built, so a
    mistyped network can never reach mainnet. Failure is non-fatal: the axon
    keeps serving locally and the explicit --miner-endpoints path still works.
    """

    if not args.publish:
        print("axon_publish=skipped reason=no_publish_flag", flush=True)
        return
    from dolores_subnet.config import assert_safe_network

    network = assert_safe_network(args.network)
    if args.netuid is None:
        raise SystemExit("--netuid is required with --publish")
    import bittensor as bt

    external_ip = args.external_ip or args.host
    external_port = args.external_port or args.port
    try:
        subtensor = bt.Subtensor(network=network)
        response = subtensor.serve_axon(netuid=args.netuid, axon=axon)
        success = bool(getattr(response, "success", response))
        message = str(getattr(response, "message", "") or "")
        print(
            f"axon_publish={'ok' if success else 'failed'} netuid={args.netuid} "
            f"external={external_ip}:{external_port} message={message}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001 - publish failure must not kill serving
        print(f"axon_publish=failed netuid={args.netuid} error={exc}", flush=True)


def serve_wire(args: argparse.Namespace, *, persona: str) -> int:
    import bittensor as bt

    from dolores_subnet.wire import DoloresTaskSynapse

    hotkey_name = args.wallet_hotkey or persona
    wallet = bt.Wallet(name=args.wallet_name, hotkey=hotkey_name)
    miner = _build_miner(args, hotkey=wallet.hotkey.ss58_address, persona=persona)

    def forward(synapse: DoloresTaskSynapse) -> DoloresTaskSynapse:
        quota = max(0, min(args.quota, synapse.quota))
        synapse.submissions = miner.submissions(epoch_id=synapse.epoch_id, quota=quota)
        synapse.error = ""
        return synapse

    def verify(synapse: DoloresTaskSynapse) -> None:
        del synapse

    # Bittensor 10.x inspect path expects concrete classes, not postponed annotations.
    forward.__annotations__ = {
        "synapse": DoloresTaskSynapse,
        "return": DoloresTaskSynapse,
    }
    verify.__annotations__ = {"synapse": DoloresTaskSynapse, "return": None}

    axon = bt.Axon(
        wallet=wallet,
        port=args.port,
        ip=args.host,
        external_ip=args.external_ip or args.host,
        external_port=args.external_port or args.port,
    )
    axon.attach(forward_fn=forward, verify_fn=verify).start()
    _publish_axon(args, axon=axon)
    source = f"task_dirs={','.join(args.task_dirs)}" if args.task_dirs else f"persona={persona}"
    print(
        "wire_miner_started "
        f"{source} wallet={args.wallet_name}/{hotkey_name} "
        f"hotkey={wallet.hotkey.ss58_address} endpoint={args.host}:{args.port}",
        flush=True,
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        axon.stop()
        print("wire_miner_stopped", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
