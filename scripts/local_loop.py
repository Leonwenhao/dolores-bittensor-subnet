"""Run a tiny offline miner/validator loop without chain dependencies."""

from __future__ import annotations

import argparse
import json

from dolores_subnet.dolores_bridge import propose_v3_family
from dolores_subnet.protocol import TaskSubmission, sha256_text
from dolores_subnet.scoring import normalize_weights, weighted_score


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run a local Dolores subnet loop.")
    parser.add_argument("--dry-run", action="store_true", help="Do not call the Dolores backend.")
    parser.add_argument("--family", default="parser_roundtrip")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.dry_run:
        task_ids = ["dry_parser_task", "dry_bugfix_task"]
    else:
        tasks = propose_v3_family(family=args.family, count=args.count, seed=args.seed)
        task_ids = [task.task_id for task in tasks]

    submissions = [
        TaskSubmission(
            miner_uid=f"miner-{index}",
            task_id=task_id,
            package_uri=f"local://{task_id}",
            package_hash=sha256_text(task_id),
            metadata={"source": "local_loop"},
        )
        for index, task_id in enumerate(task_ids)
    ]

    miner_scores = {}
    for index, submission in enumerate(submissions):
        components = {
            "verifier_quality": 0.8,
            "novelty": 0.75 - index * 0.1,
            "frontier_signal": 0.6,
            "metadata_clarity": 0.7,
        }
        miner_scores[submission.miner_uid] = weighted_score(components)

    print(
        json.dumps(
            {
                "submissions": [submission.to_commit_payload() for submission in submissions],
                "scores": miner_scores,
                "weights": normalize_weights(miner_scores),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

