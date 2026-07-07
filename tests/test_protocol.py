from __future__ import annotations

import unittest

from dolores_subnet.protocol import TaskSubmission
from dolores_subnet.scoring import normalize_weights, weighted_score


class ProtocolTests(unittest.TestCase):
    def test_submission_commitment_is_stable(self) -> None:
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
        self.assertEqual(first.commitment(), second.commitment())

    def test_weighted_score_is_clipped(self) -> None:
        score = weighted_score(
            {
                "verifier_quality": 2.0,
                "novelty": 1.0,
                "frontier_signal": 0.5,
                "metadata_clarity": -1.0,
            }
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_normalize_weights_handles_zero_total(self) -> None:
        self.assertEqual(normalize_weights({"a": 0.0, "b": -1.0}), {"a": 0.0, "b": 0.0})


if __name__ == "__main__":
    unittest.main()

