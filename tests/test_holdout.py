from __future__ import annotations

from dolores.proposer.families import propose_family
from dolores.verifier.pytest_runner import PytestRunner

from dolores_subnet.holdout import (
    build_holdout_plan,
    evaluate_holdout,
    evidence_contains_active_material,
)


def _core_parser(archetype: str):
    for seed in range(500):
        task = propose_family("parser_roundtrip", count=1, seed=seed)[0]
        if f"archetype:{archetype}" in task.descriptors.concepts:
            return task
    raise AssertionError(f"no generated task for {archetype}")


def test_holdout_is_deterministic_but_secret_keyed() -> None:
    task = _core_parser("escape_delim")
    digest = task.stable_hash()

    first = build_holdout_plan(task, package_hash=digest, secret="validator-a")
    replay = build_holdout_plan(task, package_hash=digest, secret="validator-a")
    other = build_holdout_plan(task, package_hash=digest, secret="validator-b")

    assert first.case_digest == replay.case_digest
    assert first.seed_digest == replay.seed_digest
    assert first.case_count == replay.case_count == 24
    assert first.case_digest != other.case_digest
    assert first.seed_digest != other.seed_digest
    assert first.task.stable_hash() != digest
    assert first.seed_digest not in repr(first)
    assert "CASES" not in repr(first)


def test_core_parser_reference_passes_and_wrong_probes_are_caught() -> None:
    task = _core_parser("error_contract")
    evidence = evaluate_holdout(
        task,
        package_hash=task.stable_hash(),
        secret="local-test-secret",
        runner=PytestRunner(),
        require_containerized=False,
    )

    assert evidence.status == "passed"
    assert evidence.passed is True
    assert evidence.reference_passed is True
    assert evidence.probes_caught
    assert all(evidence.probes_caught.values())


def test_alternate_repr_codec_passes_author_roundtrips_but_fails_private_grammar() -> None:
    task = _core_parser("escape_delim")
    concepts = {
        key: value
        for concept in task.descriptors.concepts
        if ":" in concept
        for key, value in [concept.split(":", 1)]
    }
    from dolores.proposer.families.parser import DELIM_BY_SLUG, ESC_BY_SLUG

    delimiter = str(DELIM_BY_SLUG[concepts["delim"]]["char"])
    escape = str(ESC_BY_SLUG[concepts["special"]]["char"])
    module_path = next(iter(task.reference_files))
    cheat = f'''import ast

DELIMITER = {delimiter!r}
ESCAPE = {escape!r}

def format_record(fields):
    if all(DELIMITER not in field and ESCAPE not in field for field in fields):
        return DELIMITER.join(fields)
    return repr(fields)

def parse_record(text):
    if text.startswith("["):
        return ast.literal_eval(text)
    return text.split(DELIMITER)
'''
    candidate = {module_path: cheat}

    # Miner-authored round-trip tests alone accept this semantically wrong codec.
    assert PytestRunner().verify(task, candidate).status == "passed"
    adversarial_task = task.model_copy(update={"reference_files": candidate})
    evidence = evaluate_holdout(
        adversarial_task,
        package_hash=adversarial_task.stable_hash(),
        secret="local-test-secret",
        runner=PytestRunner(),
        require_containerized=False,
    )

    assert evidence.status == "failed"
    assert evidence.reference_passed is False
    assert evidence.passed is False


def test_unsupported_family_fails_closed_without_running() -> None:
    task = propose_family("algorithmic_optimization", count=1, seed=1)[0]
    evidence = evaluate_holdout(
        task,
        package_hash=task.stable_hash(),
        secret="local-test-secret",
        runner=PytestRunner(),
        require_containerized=False,
    )

    assert evidence.status == "unsupported"
    assert evidence.passed is False
    assert evidence.executed is False
    assert "unsupported family" in evidence.reason


def test_missing_validator_secret_is_an_infrastructure_error() -> None:
    task = _core_parser("escape_delim")
    evidence = evaluate_holdout(
        task,
        package_hash=task.stable_hash(),
        secret="",
        runner=PytestRunner(),
        require_containerized=False,
    )

    assert evidence.status == "infra_error"
    assert evidence.executed is False


def test_public_evidence_never_contains_active_cases_or_test_source() -> None:
    task = _core_parser("quoted_fields")
    evidence = evaluate_holdout(
        task,
        package_hash=task.stable_hash(),
        secret="do-not-serialize-this",
        runner=PytestRunner(),
        require_containerized=False,
    )
    record = evidence.to_record()

    assert evidence_contains_active_material(record) is False
    assert "do-not-serialize-this" not in str(record)
    assert evidence.case_count == 24
    assert "seed_digest" not in record
    assert set(record) == {
        "passed",
        "status",
        "reason",
        "policy_version",
        "family",
        "archetype",
        "base_package_hash",
        "case_count",
        "case_digest",
        "reference_passed",
        "containerized",
        "executed",
        "logs_hash",
        "probes_caught",
    }
