#!/usr/bin/env python3
"""Run an offline Dolores subnet epoch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.config import Mode, SubnetConfig, parse_mode  # noqa: E402
from dolores_subnet.epoch import run_epoch  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "neurons"))
from miner import OfflineMiner  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local in-process epoch.")
    parser.add_argument("--mode", choices=[Mode.MOCK.value, Mode.OFFLINE.value], default="offline")
    parser.add_argument("--miners", default="honest,honest,duplicate_spammer,invalid")
    parser.add_argument("--quota", type=int, default=2)
    parser.add_argument("--epoch", type=int, default=1)
    parser.add_argument("--work", type=Path, default=Path("work/m3_demo"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    mode = parse_mode(args.mode)
    cfg = SubnetConfig.from_env(mode=mode, work_dir=args.work)
    personas = [item.strip() for item in args.miners.split(",") if item.strip()]
    miners = [
        OfflineMiner(
            hotkey=f"offline-{index}-{persona}",
            uid=index,
            persona=persona,
            seed=100 + index,
        )
        for index, persona in enumerate(personas)
    ]
    result = run_epoch(cfg, miners, epoch_id=args.epoch, quota=args.quota)
    print(f"weights_artifact={result.artifact_path}")
    for hotkey, weight in sorted(result.weights.items()):
        print(f"{hotkey} weight={weight:.6f} epoch_score={result.epoch_scores.get(hotkey, 0):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
