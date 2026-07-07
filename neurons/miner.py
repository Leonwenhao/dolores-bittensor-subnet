"""Minimal miner entrypoint for the Dolores testnet scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dolores_subnet.protocol import TaskSubmission, sha256_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a Dolores task submission payload.")
    parser.add_argument("--miner-uid", default="local-miner-0")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--package", required=True, type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    package_hash = sha256_file(args.package)
    submission = TaskSubmission(
        miner_uid=args.miner_uid,
        task_id=args.task_id,
        package_uri=str(args.package),
        package_hash=package_hash,
    )
    print(json.dumps(submission.to_commit_payload(), indent=2, sort_keys=True))
    print(f"commitment={submission.commitment()}")


if __name__ == "__main__":
    main()

