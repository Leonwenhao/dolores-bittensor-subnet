"""Bridge from subnet wire submissions into the Dolores validation pipeline."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dolores.pipeline import run_task_pipeline
from dolores.verifier.docker_runner import DockerRunner

from dolores_subnet import archive
from dolores_subnet.config import SubnetConfig
from dolores_subnet.gates import GateContext, run_pre_gates
from dolores_subnet.holdout import (
    POLICY_VERSION,
    HoldoutPolicyError,
    evaluate_holdout,
    validate_holdout_support,
)
from dolores_subnet.packaging import materialize
from dolores_subnet.scoring import task_value_from_score

RESERVED_WIRE_KEYS = frozenset({"wire_error"})
NON_CONTAINERIZED_ALLOWED_STATUSES = frozenset({"rejected", "review", "invalid", "infra_error"})


@dataclass(frozen=True)
class SubmissionOutcome:
    status: str
    task_id: str
    package_hash: str | None
    task_value: float
    gates: dict[str, bool]
    components: dict[str, float] = field(default_factory=dict)
    verification_summary: dict[str, Any] = field(default_factory=dict)
    holdout_summary: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    # Per-attempt solver-panel rows. Deliberately excluded from to_record so
    # volatile provider telemetry never enters submissions.jsonl / replay.
    panel_rows: list[dict[str, Any]] = field(default_factory=list)

    def to_record(
        self,
        *,
        epoch_id: int,
        miner_hotkey: str,
        miner_uid: int | None,
    ) -> dict[str, Any]:
        return {
            "epoch_id": epoch_id,
            "miner_hotkey": miner_hotkey,
            "miner_uid": miner_uid,
            "task_id": self.task_id,
            "package_hash": self.package_hash,
            "status": self.status,
            "reason": self.reason,
            "pre_gates": self.gates,
            "task_value": self.task_value,
            "components": self.components,
            "verification": self.verification_summary,
            "holdout": self.holdout_summary,
        }


def validate_submission(
    wire: dict[str, Any],
    cfg: SubnetConfig,
    *,
    context: GateContext | None = None,
    miner_hotkey: str = "local-miner",
    panel_path: Path | None = None,
) -> SubmissionOutcome:
    archive.init_archive(cfg)
    reserved = RESERVED_WIRE_KEYS.intersection(wire)
    if reserved:
        key_list = ",".join(sorted(reserved))
        package = wire.get("package", {})
        package_task_id = package.get("task_id") if isinstance(package, dict) else None
        return SubmissionOutcome(
            status="invalid",
            task_id=str(wire.get("task_id", package_task_id or "unknown")),
            package_hash=wire.get("package_hash"),
            task_value=0.0,
            gates={"reserved_keys": False},
            reason=f"invalid:reserved_key:{key_list}",
        )
    gate_context = context or GateContext(quota=cfg.quota)
    decision = run_pre_gates(wire, cfg, gate_context, miner_hotkey=miner_hotkey)
    task_id = str(wire.get("task_id", wire.get("package", {}).get("task_id", "unknown")))
    if not decision.passed:
        failure = decision.failure
        reason = failure.reason if failure else "invalid"
        return SubmissionOutcome(
            status="invalid",
            task_id=task_id,
            package_hash=wire.get("package_hash"),
            task_value=0.0,
            gates=dict(decision.gates),
            reason=reason,
        )

    task = decision.task
    assert task is not None
    if cfg.holdout_required:
        try:
            validate_holdout_support(task)
        except HoldoutPolicyError as exc:
            return SubmissionOutcome(
                status="rejected",
                task_id=task.task_id,
                package_hash=decision.task_hash,
                task_value=0.0,
                gates=dict(decision.gates),
                holdout_summary={
                    "passed": False,
                    "status": "unsupported",
                    "reason": str(exc),
                    "policy_version": POLICY_VERSION,
                    "base_package_hash": decision.task_hash,
                },
                reason=f"holdout:unsupported:{exc}",
            )
    with tempfile.TemporaryDirectory(prefix="dolores-subnet-task-") as temp:
        task_dir = materialize(task, root=Path(temp))
        result = run_task_pipeline(
            task_dir,
            cfg.archive_db,
            panel_path if panel_path is not None else cfg.panel_path,
            backend=cfg.backend,
            mode=cfg.pipeline_mode,
            allow_unsafe_local=False,
            allow_docker_fallback=False,
        )

    holdout_summary: dict[str, Any] = {}
    verification = result.verification
    if cfg.holdout_required and verification is not None and verification.status == "passed":
        evidence = evaluate_holdout(
            task,
            package_hash=decision.task_hash or task.stable_hash(),
            secret=cfg.holdout_secret or "",
            runner=DockerRunner(
                image=cfg.verifier_image,
                allow_fallback=False,
            ),
            require_containerized=True,
        )
        holdout_summary = evidence.to_record()
        if not evidence.passed:
            if decision.task_hash:
                archive.purge_task(cfg.archive_db, decision.task_hash)
            status = "infra_error" if evidence.status == "infra_error" else "rejected"
            return SubmissionOutcome(
                status=status,
                task_id=task.task_id,
                package_hash=decision.task_hash,
                task_value=0.0,
                gates=dict(decision.gates),
                verification_summary=_verification_summary(verification),
                holdout_summary=holdout_summary,
                reason=f"holdout:{evidence.status}:{evidence.reason}",
            )

    return _outcome_from_pipeline(
        result,
        cfg=cfg,
        task_id=task.task_id,
        task_hash=decision.task_hash,
        gates=dict(decision.gates),
        holdout_summary=holdout_summary,
    )


def _outcome_from_pipeline(
    result: Any,
    *,
    cfg: SubnetConfig,
    task_id: str,
    task_hash: str | None,
    gates: dict[str, bool],
    holdout_summary: dict[str, Any] | None = None,
) -> SubmissionOutcome:
    verification = result.verification
    score = result.score
    if result.error or verification is None:
        return SubmissionOutcome(
            status="invalid",
            task_id=task_id,
            package_hash=task_hash,
            task_value=0.0,
            gates=gates,
            holdout_summary=holdout_summary or {},
            reason=f"pipeline:{result.error or result.status}",
        )

    summary = _verification_summary(verification)
    if _is_infra_error(verification):
        if task_hash:
            archive.purge_task(cfg.archive_db, task_hash)
        return SubmissionOutcome(
            status="infra_error",
            task_id=task_id,
            package_hash=task_hash,
            task_value=0.0,
            gates=gates,
            verification_summary=summary,
            holdout_summary=holdout_summary or {},
            reason=verification.fallback_reason or "infrastructure failure",
        )

    if verification.safety_findings:
        return SubmissionOutcome(
            status="rejected",
            task_id=task_id,
            package_hash=task_hash,
            task_value=0.0,
            gates=gates,
            verification_summary=summary,
            holdout_summary=holdout_summary or {},
            reason=f"safety:{verification.safety_findings[0].message}",
        )

    components = score.components.model_dump(mode="json") if score else {}
    lifecycle = score.lifecycle_status if score else result.status
    task_value = task_value_from_score(score) if score else 0.0
    reason = lifecycle
    if verification.status == "failed" and verification.executed:
        reason = "verification failed"
    if cfg.backend == "docker" and not verification.containerized:
        if lifecycle not in NON_CONTAINERIZED_ALLOWED_STATUSES:
            if task_hash:
                archive.purge_task(cfg.archive_db, task_hash)
            return SubmissionOutcome(
                status="infra_error",
                task_id=task_id,
                package_hash=task_hash,
                task_value=0.0,
                gates=gates,
                verification_summary=summary,
                holdout_summary=holdout_summary or {},
                reason="docker accepted without containerized execution",
            )
    return SubmissionOutcome(
        status=lifecycle,
        task_id=task_id,
        package_hash=task_hash,
        task_value=task_value,
        gates=gates,
        components=components,
        verification_summary=summary,
        holdout_summary=holdout_summary or {},
        reason=reason,
        panel_rows=_panel_rows(result),
    )


def _panel_rows(result: Any) -> list[dict[str, Any]]:
    eval_result = getattr(result, "eval_result", None)
    solver_results = getattr(eval_result, "solver_results", None) or []
    rows: list[dict[str, Any]] = []
    for run in solver_results:
        if hasattr(run, "model_dump"):
            rows.append(run.model_dump(mode="json"))
        elif isinstance(run, dict):
            rows.append(dict(run))
    return rows


def _is_infra_error(verification: Any) -> bool:
    return (
        verification.executed is False
        and verification.fallback_reason is not None
        and not verification.safety_findings
    )


def _verification_summary(verification: Any) -> dict[str, Any]:
    return {
        "status": verification.status,
        "backend": verification.backend,
        "requested_backend": verification.requested_backend,
        "execution_mode": verification.execution_mode,
        "executed": verification.executed,
        "containerized": verification.containerized,
        "image": verification.image,
        "fallback_reason": verification.fallback_reason,
        "error_summary": _stable_error_summary(verification.error_summary),
        "safety_findings": [
            finding.model_dump(mode="json") for finding in verification.safety_findings
        ],
    }


def _stable_error_summary(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\bin \d+(?:\.\d+)?s\b", "in <duration>s", value)
