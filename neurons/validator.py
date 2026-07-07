"""Minimal validator entrypoint for the Dolores testnet scaffold."""

from __future__ import annotations

import argparse
import json

from dolores_subnet.protocol import TaskSubmission, ValidationScore
from dolores_subnet.scoring import hard_gates_pass, weighted_score


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score a local Dolores task submission.")
    parser.add_argument("--submission-json", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with open(args.submission_json, encoding="utf-8") as handle:
        payload = json.load(handle)

    submission = TaskSubmission(
        miner_uid=payload["miner_uid"],
        task_id=payload["task_id"],
        package_uri=payload["package_uri"],
        package_hash=payload["package_hash"],
        metadata=payload.get("metadata", {}),
    )

    # Placeholder gates for the scaffold. The next implementation pass should
    # replace these with the real Dolores verifier/scorer bridge.
    gates = {
        "schema_valid": True,
        "safety_clean": True,
        "reference_verified": True,
        "not_duplicate": True,
    }
    components = {
        "verifier_quality": 0.8,
        "novelty": 0.7,
        "frontier_signal": 0.5,
        "metadata_clarity": 0.6,
    }
    valid = hard_gates_pass(gates)
    score = weighted_score(components) if valid else 0.0
    result = ValidationScore(
        task_id=submission.task_id,
        miner_uid=submission.miner_uid,
        valid=valid,
        score=score,
        gates=gates,
        components=components,
        reason="scaffold score; replace with Dolores backend",
    )
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

