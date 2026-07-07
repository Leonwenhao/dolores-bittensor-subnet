#!/usr/bin/env python3
"""Render a markdown leaderboard from a subnet archive."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.config import SubnetConfig  # noqa: E402
from dolores_subnet.epoch import assert_replay_matches  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a Dolores subnet epoch report.")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--replay-check", type=int, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cfg = SubnetConfig.from_env(mode="offline", work_dir=args.work)
    if args.replay_check is not None:
        assert_replay_matches(cfg, epoch_id=args.replay_check)
        print("REPLAY OK")
        return 0
    report = render_report(cfg, epoch_id=args.epoch)
    path = cfg.epoch_dir(args.epoch) / f"report_epoch_{args.epoch}.md"
    path.write_text(report, encoding="utf-8")
    print(report)
    return 0


def render_report(cfg: SubnetConfig, *, epoch_id: int) -> str:
    artifact = json.loads(cfg.weights_path(epoch_id).read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in cfg.submissions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [row for row in rows if row["epoch_id"] == epoch_id]
    miners = sorted(artifact["weights"])
    lines = [
        f"# Epoch {epoch_id} Leaderboard",
        "",
        "| miner | submitted | accepted | rejected/invalid | epoch_score | "
        "ema | weight | reasons |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for miner in miners:
        miner_rows = [row for row in rows if row["miner_hotkey"] == miner]
        accepted = sum(1 for row in miner_rows if row["status"] == "accepted")
        rejected = sum(1 for row in miner_rows if row["status"] != "accepted")
        reasons = "; ".join(
            sorted({row["reason"] for row in miner_rows if row["status"] != "accepted"})
        )
        lines.append(
            "| {miner} | {submitted} | {accepted} | {rejected} | {score:.6f} | "
            "{ema:.6f} | {weight:.6f} | {reasons} |".format(
                miner=miner,
                submitted=len(miner_rows),
                accepted=accepted,
                rejected=rejected,
                score=float(artifact["epoch_scores"].get(miner, 0.0)),
                ema=float(artifact["ema_state"].get(miner, 0.0)),
                weight=float(artifact["weights"].get(miner, 0.0)),
                reasons=reasons or "-",
            )
        )
    lines.append("")
    lines.append(f"degraded: `{artifact['degraded']}`")
    lines.append(f"weight_result: `{artifact['weight_result']['mode']}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
