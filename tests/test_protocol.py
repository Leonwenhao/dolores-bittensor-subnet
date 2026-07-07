from __future__ import annotations

from dolores_subnet.config import SCHEMA_VERSION
from dolores_subnet.protocol import TaskSubmission, WireSubmission
from dolores_subnet.scoring import normalize_weights, weighted_score


def test_submission_commitment_is_stable() -> None:
    first = TaskSubmission(
        miner_uid="miner-1",
        task_id="task-a",
        package_uri="local://task-a",
        package_hash="abc",
        metadata={"family": "parser_roundtrip"},
    )
    second = TaskSubmission(
        miner_uid="miner-1",
        task_id="task-a",
        package_uri="local://task-a",
        package_hash="abc",
        metadata={"family": "parser_roundtrip"},
    )
    assert first.commitment() == second.commitment()


def test_wire_submission_commitment_is_stable() -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": "task-a",
        "package_hash": "abc",
        "package": {"task_id": "task-a"},
        "family": "parser_roundtrip",
        "declared_difficulty": "medium",
    }
    first = WireSubmission.from_dict(payload)
    second = WireSubmission.from_dict(dict(reversed(list(payload.items()))))

    assert first.to_dict() == payload
    assert first.commitment() == second.commitment()


def test_weighted_score_is_clipped() -> None:
    score = weighted_score(
        {
            "verifier_quality": 2.0,
            "novelty": 1.0,
            "frontier_signal": 0.5,
            "metadata_clarity": -1.0,
        }
    )
    assert 0.0 <= score <= 1.0


def test_normalize_weights_handles_zero_total() -> None:
    assert normalize_weights({"a": 0.0, "b": -1.0}) == {"a": 0.0, "b": 0.0}
