from __future__ import annotations

from dolores.proposer.families import propose_family

from dolores_subnet.holdout import evaluate_holdout


def test_validator_owned_holdout_is_containerized_and_catches_wrong_solutions() -> None:
    task = None
    for seed in range(500):
        candidate = propose_family("parser_roundtrip", count=1, seed=seed)[0]
        if "archetype:escape_delim" in candidate.descriptors.concepts:
            task = candidate
            break
    assert task is not None

    evidence = evaluate_holdout(
        task,
        package_hash=task.stable_hash(),
        secret="ci-holdout-fixture-only",
    )

    assert evidence.status == "passed"
    assert evidence.passed is True
    assert evidence.containerized is True
    assert evidence.executed is True
    assert evidence.probes_caught
    assert all(evidence.probes_caught.values())
    assert "ci-holdout-fixture-only" not in str(evidence.to_record())
