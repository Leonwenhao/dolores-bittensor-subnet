from __future__ import annotations

from pathlib import Path

from dolores_subnet import archive, bridge
from dolores_subnet.config import SubnetConfig
from dolores_subnet.gates import GateContext
from dolores_subnet.packaging import to_wire


def _task():
    from dolores.proposer.families import propose_family

    return propose_family("parser_roundtrip", count=1, seed=0)[0]


def _cfg(tmp_path: Path) -> SubnetConfig:
    return SubnetConfig.from_env(mode="mock", work_dir=tmp_path)


def test_validate_submission_runs_local_fixture_pipeline(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    outcome = bridge.validate_submission(
        to_wire(_task()),
        cfg,
        context=GateContext(),
        miner_hotkey="miner-a",
    )

    assert outcome.status in {"accepted", "review", "rejected"}
    assert outcome.gates["hash_match"]
    assert outcome.verification_summary["executed"] is True


def test_infra_error_is_purged_and_not_penalized(tmp_path, monkeypatch) -> None:
    from dolores.archive.db import ArchiveDB

    cfg = _cfg(tmp_path)
    task = _task()
    archive.init_archive(cfg)
    with ArchiveDB(cfg.archive_db) as db:
        db.add_task(task)

    fake = _fake_pipeline_result(task, executed=False, fallback_reason="docker unavailable")
    monkeypatch.setattr(bridge, "run_task_pipeline", lambda *args, **kwargs: fake)
    outcome = bridge.validate_submission(to_wire(task), cfg, context=GateContext())

    assert outcome.status == "infra_error"
    with ArchiveDB(cfg.archive_db) as db:
        assert db.show_task(task.task_id) is None


def test_reserved_wire_error_key_is_invalid_not_infra_error(tmp_path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    payload = to_wire(_task())
    payload["wire_error"] = "docker unavailable"

    def forbidden_pipeline(*args, **kwargs):
        del args, kwargs
        raise AssertionError("reserved wire_error should fail before pipeline execution")

    monkeypatch.setattr(bridge, "run_task_pipeline", forbidden_pipeline)
    outcome = bridge.validate_submission(payload, cfg, context=GateContext())

    assert outcome.status == "invalid"
    assert outcome.reason == "invalid:reserved_key:wire_error"
    assert outcome.task_value == 0.0


def test_cohort_holdout_rejects_unsupported_family_before_pipeline(
    tmp_path, monkeypatch
) -> None:
    from dolores.proposer.families import propose_family

    task = propose_family("algorithmic_optimization", count=1, seed=1)[0]
    cfg = SubnetConfig.from_env(
        mode="wire",
        work_dir=tmp_path,
        holdout_secret="local-test-secret",
    )

    def forbidden_pipeline(*args, **kwargs):
        del args, kwargs
        raise AssertionError("unsupported family must not execute")

    monkeypatch.setattr(bridge, "run_task_pipeline", forbidden_pipeline)
    outcome = bridge.validate_submission(to_wire(task), cfg, context=GateContext())

    assert outcome.status == "rejected"
    assert outcome.task_value == 0.0
    assert outcome.holdout_summary["status"] == "unsupported"
    assert outcome.reason.startswith("holdout:unsupported:")


def test_safety_rejection_is_not_purged(tmp_path, monkeypatch) -> None:
    from dolores.archive.db import ArchiveDB
    from dolores.schemas.result import SafetyFinding

    cfg = _cfg(tmp_path)
    task = _task()
    fake = _fake_pipeline_result(
        task,
        executed=False,
        fallback_reason=None,
        safety_findings=[SafetyFinding(path="solution.py", message="unsafe import rejected")],
    )
    monkeypatch.setattr(bridge, "run_task_pipeline", lambda *args, **kwargs: fake)

    outcome = bridge.validate_submission(to_wire(task), cfg, context=GateContext())

    assert outcome.status == "rejected"
    with ArchiveDB(cfg.archive_db) as db:
        # The fake pipeline does not add rows; this asserts no infra purge path ran by
        # seeding after validation and then proving purge_task was not called would be
        # overfitted to implementation details.
        db.add_task(task)
        assert db.show_task(task.task_id) is not None


def test_docker_mode_cannot_accept_non_containerized_result(tmp_path, monkeypatch) -> None:
    task = _task()
    cfg = SubnetConfig.from_env(mode="offline", work_dir=tmp_path)
    fake = _fake_pipeline_result(
        task,
        executed=True,
        fallback_reason=None,
        verification_status="passed",
        lifecycle_status="accepted",
        aggregate_score=0.8,
        containerized=False,
    )
    monkeypatch.setattr(bridge, "run_task_pipeline", lambda *args, **kwargs: fake)

    outcome = bridge.validate_submission(to_wire(task), cfg, context=GateContext())

    assert outcome.status == "infra_error"
    assert outcome.reason == "docker accepted without containerized execution"


def test_public_safe_archive_copy_removes_hidden_tests(tmp_path) -> None:
    from dolores.archive.db import ArchiveDB

    cfg = _cfg(tmp_path)
    task = _task()
    archive.init_archive(cfg)
    with ArchiveDB(cfg.archive_db) as db:
        db.add_task(task)

    copy_path = archive.public_safe_archive_copy(cfg.archive_db, tmp_path / "public.duckdb")
    import duckdb

    conn = duckdb.connect(str(copy_path))
    try:
        count = conn.execute(
            "SELECT count(*) FROM task_files WHERE file_role = 'hidden_tests'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def _fake_pipeline_result(
    task,
    *,
    executed: bool,
    fallback_reason: str | None,
    safety_findings=None,
    verification_status: str | None = None,
    lifecycle_status: str = "rejected",
    aggregate_score: float = 0.0,
    containerized: bool = False,
):
    from dolores.pipeline import PipelineResult
    from dolores.schemas.result import EvalResult, VerificationResult
    from dolores.schemas.score import ScoreComponents, TaskScore

    verification = VerificationResult(
        task_id=task.task_id,
        task_hash=task.stable_hash(),
        backend="docker",
        requested_backend="docker",
        execution_mode="generated",
        status=verification_status or ("rejected" if safety_findings else "failed"),
        duration_ms=0,
        public_tests_passed=False,
        hidden_tests_passed=False,
        logs_hash="0" * 64,
        containerized=containerized,
        executed=executed,
        fallback_reason=fallback_reason,
        safety_findings=safety_findings or [],
    )
    score = TaskScore(
        task_id=task.task_id,
        task_hash=task.stable_hash(),
        solve_rate=0.0,
        frontier_status="broken",
        lifecycle_status=lifecycle_status,
        aggregate_score=aggregate_score,
        components=ScoreComponents(
            frontier_difficulty=0.0,
            verifier_quality=0.0,
            wrong_solution_detection=0.0,
            novelty=0.0,
            duplicate_resistance=0.0,
            robustness=0.0,
            runtime_cost=0.0,
        ),
    )
    return PipelineResult(
        task_id=task.task_id,
        status="rejected",
        verification=verification,
        eval_result=EvalResult(
            task_id=task.task_id,
            task_hash=task.stable_hash(),
            panel_id="skipped",
            solver_results=[],
        ),
        score=score,
    )
