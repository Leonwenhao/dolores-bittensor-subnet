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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    persona = args.persona or "honest"
    if args.mode == "wire":
        return serve_wire(args, persona=persona)
    miner = OfflineMiner(
        hotkey=f"local-{persona}",
        uid=0,
        persona=persona,
        seed=args.seed,
    )
    print(json.dumps(miner.submissions(epoch_id=1, quota=args.quota), indent=2, sort_keys=True))
    return 0


def serve_wire(args: argparse.Namespace, *, persona: str) -> int:
    import bittensor as bt

    from dolores_subnet.wire import DoloresTaskSynapse

    hotkey_name = args.wallet_hotkey or persona
    wallet = bt.Wallet(name=args.wallet_name, hotkey=hotkey_name)
    miner = OfflineMiner(
        hotkey=wallet.hotkey.ss58_address,
        uid=0,
        persona=persona,
        seed=args.seed,
    )

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
        external_ip=args.host,
        external_port=args.port,
    )
    axon.attach(forward_fn=forward, verify_fn=verify).start()
    print(
        "wire_miner_started "
        f"persona={persona} wallet={args.wallet_name}/{hotkey_name} "
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
