"""Mode-agnostic epoch engine for offline and future chain-backed runs."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from dolores_subnet import archive, bridge
from dolores_subnet.atomic import atomic_write_bytes, atomic_write_json
from dolores_subnet.chain import ChainClient, ChainWeightResult, NullChain
from dolores_subnet.config import SubnetConfig
from dolores_subnet.gates import GateContext
from dolores_subnet.panel import PanelSession
from dolores_subnet.scoring import (
    normalize_active_weights,
    recalibrated_task_value,
    top_k_epoch_scores,
    update_ema_scores,
)


class MinerLike(Protocol):
    hotkey: str
    uid: int

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class EpochResult:
    artifact_path: Path
    report_path: Path
    weights: dict[str, float]
    epoch_scores: dict[str, float]
    chain_result: ChainWeightResult
    completion_marker_path: Path | None = None


RECOVERABLE_CHAIN_MODES = frozenset(
    {"dry_run", "submitted", "fallback", "skipped", "error"}
)
COMPLETION_MARKER_VERSION = 1


class EpochCompletionError(RuntimeError):
    """A definite chain outcome is not eligible to complete an epoch."""

    def __init__(self, *, mode: str, reason: str) -> None:
        super().__init__(f"epoch chain outcome is not complete: {mode}:{reason}")
        self.mode = mode
        self.reason = reason


class EpochCompletionValidationError(RuntimeError):
    """A canonical completion marker or one of its artifacts is invalid."""


def run_epoch(
    cfg: SubnetConfig,
    miners: list[MinerLike],
    *,
    epoch_id: int,
    quota: int,
    chain_client: ChainClient | None = None,
    phase_hook: Callable[[str], None] | None = None,
) -> EpochResult:
    started = time.monotonic()
    _emit_phase(phase_hook, "evaluating")
    archive.init_archive(cfg)
    repair_jsonl_tail(cfg.submissions_path)
    panel_session = PanelSession(cfg)
    context = GateContext(quota=quota)
    outcomes: list[tuple[MinerLike, bridge.SubmissionOutcome]] = []
    for miner in miners:
        terminal = _terminal_outcome(miner)
        if terminal is None:
            continue
        archive.append_submission(
            cfg,
            terminal.to_record(epoch_id=epoch_id, miner_hotkey=miner.hotkey, miner_uid=miner.uid),
        )
        outcomes.append((miner, terminal))

    collected = _collect(miners, epoch_id=epoch_id, quota=quota)
    for miner, payload in sorted(collected, key=lambda item: str(item[1].get("package_hash", ""))):
        submission_hash = payload.get("package_hash")
        plan = panel_session.plan(submission_hash)
        panel_kwargs: dict[str, Any] = (
            {"panel_path": panel_session.panel_path_for(plan)} if panel_session.active else {}
        )
        outcome = bridge.validate_submission(
            payload,
            cfg,
            context=context,
            miner_hotkey=miner.hotkey,
            **panel_kwargs,
        )
        if plan == "live" and not outcome.panel_rows:
            # Gate/verification failure meant the real panel never ran.
            panel_session.refund()
            plan = "gate_failed"
        if plan == "cache":
            cached_rate = panel_session.cached_solve_rate(outcome.package_hash)
            outcome = dataclasses.replace(
                outcome,
                task_value=recalibrated_task_value(
                    outcome.task_value, outcome.components, cached_rate
                ),
            )
            panel_session.record(
                plan=plan,
                task_id=outcome.task_id,
                task_hash=outcome.package_hash,
                rows=[],
                cached_rate=cached_rate,
            )
        elif plan != "mock":
            panel_session.record(
                plan=plan,
                task_id=outcome.task_id,
                task_hash=outcome.package_hash,
                rows=outcome.panel_rows,
            )
        archive.append_submission(
            cfg,
            outcome.to_record(epoch_id=epoch_id, miner_hotkey=miner.hotkey, miner_uid=miner.uid),
        )
        outcomes.append((miner, outcome))

    active_hotkeys = [miner.hotkey for miner in miners]
    miner_values = {hotkey: [] for hotkey in active_hotkeys}
    miner_statuses = {hotkey: [] for hotkey in active_hotkeys}
    task_values: dict[str, float] = {}
    for miner, outcome in outcomes:
        miner_statuses[miner.hotkey].append(outcome.status)
        if outcome.status != "infra_error":
            miner_values[miner.hotkey].append(outcome.task_value)
        if outcome.package_hash:
            task_values[outcome.package_hash] = outcome.task_value

    previous_ema = _load_miner_state(cfg)
    epoch_scores = top_k_epoch_scores(miner_values, top_k=quota)
    infra_only = {
        hotkey
        for hotkey, statuses in miner_statuses.items()
        if statuses and all(status == "infra_error" for status in statuses)
    }
    degraded = any(
        status == "infra_error"
        for statuses in miner_statuses.values()
        for status in statuses
    )
    ema_state = update_ema_scores(
        previous_ema,
        epoch_scores,
        alpha=cfg.ema_alpha,
        infra_only_miners=infra_only,
    )
    weights = normalize_active_weights(ema_state, active_hotkeys)
    weight_reason = None
    if all(value == 0.0 for value in weights.values()):
        weight_reason = "all_zero"
    if outcomes and all(outcome.status == "infra_error" for _, outcome in outcomes):
        weight_reason = "epoch_degraded_all_infra"
    _emit_phase(phase_hook, "weights_submitting")
    chain_result = (chain_client or NullChain()).apply_weights(
        cfg=cfg,
        epoch_id=epoch_id,
        weights=weights,
        active_hotkeys=active_hotkeys,
        spec_version=cfg.spec_version,
        fallback_reason=weight_reason or "offline",
    )

    artifact = {
        "epoch_id": epoch_id,
        "config": {"quota": quota, "top_k": quota, "ema_alpha": cfg.ema_alpha},
        "task_values": dict(sorted(task_values.items())),
        "epoch_scores": dict(sorted(epoch_scores.items())),
        "ema_state": dict(sorted(ema_state.items())),
        "weights": dict(sorted(weights.items())),
        "degraded": degraded,
        "weight_result": chain_result.to_record(),
        "timing": {
            "created_at": datetime.now(UTC).isoformat(),
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    }
    miner_state_snapshot = _save_miner_state(cfg, ema_state, epoch_id=epoch_id)
    epoch_dir = cfg.epoch_dir(epoch_id)
    epoch_dir.mkdir(parents=True, exist_ok=True)
    panel_path = _persist_panel_sidecar(cfg, panel_session, epoch_id=epoch_id)
    artifact_path = cfg.weights_path(epoch_id)
    atomic_write_json(artifact_path, artifact)
    report_path = epoch_dir / f"report_epoch_{epoch_id}.md"
    if chain_result.mode not in RECOVERABLE_CHAIN_MODES:
        raise EpochCompletionError(
            mode=chain_result.mode,
            reason=chain_result.reason or "unknown",
        )
    marker_path = write_epoch_completion_marker(
        cfg,
        epoch_id=epoch_id,
        chain_result=chain_result,
        miner_state_path=miner_state_snapshot,
        weights_path=artifact_path,
        panel_path=panel_path,
    )
    # The epoch-scoped snapshot is the committed source. Publish the rolling
    # cache only after the marker exists; recovery can repeat this idempotently.
    atomic_write_json(_miner_state_path(cfg), dict(sorted(ema_state.items())))
    _emit_phase(phase_hook, "committed")
    return EpochResult(
        artifact_path=artifact_path,
        report_path=report_path,
        weights=weights,
        epoch_scores=epoch_scores,
        chain_result=chain_result,
        completion_marker_path=marker_path,
    )


def replay_epoch(cfg: SubnetConfig, *, epoch_id: int) -> dict[str, Any]:
    artifact = json.loads(cfg.weights_path(epoch_id).read_text(encoding="utf-8"))
    rows = read_jsonl_tolerating_torn_final(cfg.submissions_path)
    rows = [row for row in rows if row["epoch_id"] == epoch_id]
    quota = int(artifact["config"]["quota"])
    miner_values: dict[str, list[float]] = {}
    for row in rows:
        miner_values.setdefault(row["miner_hotkey"], [])
        if row["status"] != "infra_error":
            miner_values[row["miner_hotkey"]].append(float(row["task_value"]))
    epoch_scores = top_k_epoch_scores(miner_values, top_k=quota)
    weights = normalize_active_weights(artifact["ema_state"], list(artifact["weights"]))
    return {"epoch_scores": epoch_scores, "weights": weights}


def assert_replay_matches(cfg: SubnetConfig, *, epoch_id: int) -> None:
    artifact = json.loads(cfg.weights_path(epoch_id).read_text(encoding="utf-8"))
    replay = replay_epoch(cfg, epoch_id=epoch_id)
    if replay["epoch_scores"] != artifact["epoch_scores"]:
        raise AssertionError(
            f"epoch_scores mismatch: {replay['epoch_scores']} != {artifact['epoch_scores']}"
        )
    if replay["weights"] != artifact["weights"]:
        raise AssertionError(f"weights mismatch: {replay['weights']} != {artifact['weights']}")


def _collect(
    miners: list[MinerLike],
    *,
    epoch_id: int,
    quota: int,
) -> list[tuple[MinerLike, dict[str, Any]]]:
    rows: list[tuple[MinerLike, dict[str, Any]]] = []
    for miner in miners:
        if getattr(miner, "terminal_status", None):
            continue
        for payload in miner.submissions(epoch_id=epoch_id, quota=quota):
            rows.append((miner, payload))
    return rows


def _terminal_outcome(miner: MinerLike) -> bridge.SubmissionOutcome | None:
    status = getattr(miner, "terminal_status", None)
    if not status:
        return None
    reason = str(getattr(miner, "terminal_reason", "") or status)
    gates = {"transport": False} if status == "unreachable" else {"wire": False}
    return bridge.SubmissionOutcome(
        status=str(status),
        task_id=f"terminal_{status}_{miner.uid}",
        package_hash=None,
        task_value=0.0,
        gates=gates,
        reason=reason,
    )


def _miner_state_path(cfg: SubnetConfig) -> Path:
    return cfg.archive_dir / "miner_state.json"


def _load_miner_state(cfg: SubnetConfig) -> dict[str, float]:
    path = _miner_state_path(cfg)
    if not path.exists():
        return {}
    return {str(key): float(value) for key, value in json.loads(path.read_text()).items()}


def _save_miner_state(
    cfg: SubnetConfig,
    state: dict[str, float],
    *,
    epoch_id: int,
) -> Path:
    payload = dict(sorted(state.items()))
    snapshot = cfg.epoch_dir(epoch_id) / f"miner_state_epoch_{epoch_id}.json"
    atomic_write_json(snapshot, payload)
    return snapshot


def completion_marker_path(archive_dir: str | Path, epoch_id: int) -> Path:
    root = Path(archive_dir)
    return root / "epochs" / f"epoch_{epoch_id}" / f"completion_epoch_{epoch_id}.json"


def chain_receipt_path(archive_dir: str | Path, epoch_id: int) -> Path:
    root = Path(archive_dir)
    return root / "epochs" / f"epoch_{epoch_id}" / f"chain_receipt_epoch_{epoch_id}.json"


def chain_attempt_path(archive_dir: str | Path, epoch_id: int) -> Path:
    root = Path(archive_dir)
    return root / "epochs" / f"epoch_{epoch_id}" / f"chain_attempt_epoch_{epoch_id}.json"


def write_epoch_completion_marker(
    cfg: SubnetConfig,
    *,
    epoch_id: int,
    chain_result: ChainWeightResult,
    miner_state_path: Path,
    weights_path: Path,
    panel_path: Path,
) -> Path:
    """Publish the final epoch commit point after every dependency is durable."""

    mode = chain_result.mode
    reason = chain_result.reason or ""
    if mode not in RECOVERABLE_CHAIN_MODES:
        raise EpochCompletionError(mode=mode, reason=reason or "unknown")

    receipt_path: Path | None = None
    attempt_path: Path | None = None
    if mode != "fallback":
        expected_receipt = chain_receipt_path(cfg.archive_dir, epoch_id)
        receipt_file = (chain_result.receipt or {}).get("receipt_file")
        if receipt_file != expected_receipt.name:
            raise EpochCompletionValidationError(
                f"{mode} epoch requires canonical receipt {expected_receipt.name}"
            )
        receipt_path = expected_receipt
    elif chain_result.receipt is not None:
        raise EpochCompletionValidationError("fallback epoch cannot carry a chain receipt")

    if mode == "submitted":
        attempt_path = chain_attempt_path(cfg.archive_dir, epoch_id)

    artifacts = {
        "miner_state": _artifact_record(cfg.archive_dir, miner_state_path),
        "weights": _artifact_record(cfg.archive_dir, weights_path),
        "panel_sidecar": _artifact_record(cfg.archive_dir, panel_path),
        "chain_receipt": (
            _artifact_record(cfg.archive_dir, receipt_path) if receipt_path else None
        ),
        "chain_attempt": (
            _artifact_record(cfg.archive_dir, attempt_path) if attempt_path else None
        ),
    }
    marker = {
        "version": COMPLETION_MARKER_VERSION,
        "epoch_id": epoch_id,
        "mode": mode,
        "reason": reason,
        "artifacts": artifacts,
    }
    path = completion_marker_path(cfg.archive_dir, epoch_id)
    atomic_write_json(path, marker)
    # Read back and hash-check the just-published marker before state is allowed
    # to transition to committed.
    verify_epoch_completion(cfg.archive_dir, epoch_id)
    return path


def verify_epoch_completion(archive_dir: str | Path, epoch_id: int) -> dict[str, Any]:
    """Verify the canonical marker and all exact-path artifacts it commits."""

    root = Path(archive_dir)
    marker_path = completion_marker_path(root, epoch_id)
    marker = _load_json_object(marker_path, label="completion marker")
    if marker.get("version") != COMPLETION_MARKER_VERSION:
        raise EpochCompletionValidationError("unsupported completion marker version")
    if marker.get("epoch_id") != epoch_id:
        raise EpochCompletionValidationError(
            f"completion marker epoch {marker.get('epoch_id')!r} != {epoch_id}"
        )
    mode = marker.get("mode")
    reason = marker.get("reason")
    if mode not in RECOVERABLE_CHAIN_MODES or not isinstance(reason, str):
        raise EpochCompletionValidationError(
            "completion marker must have a recoverable mode and string reason"
        )
    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, dict):
        raise EpochCompletionValidationError("completion marker artifacts must be an object")

    canonical = {
        "miner_state": (
            root / "epochs" / f"epoch_{epoch_id}" / f"miner_state_epoch_{epoch_id}.json"
        ),
        "weights": root / "epochs" / f"epoch_{epoch_id}" / f"weights_epoch_{epoch_id}.json",
        "panel_sidecar": (
            root / "epochs" / f"epoch_{epoch_id}" / f"solver_panel_epoch_{epoch_id}.json"
        ),
        "chain_receipt": chain_receipt_path(root, epoch_id),
        "chain_attempt": chain_attempt_path(root, epoch_id),
    }
    required = {"miner_state", "weights", "panel_sidecar"}
    if mode != "fallback":
        required.add("chain_receipt")
    if mode == "submitted":
        required.add("chain_attempt")

    resolved: dict[str, Path] = {}
    for name, expected_path in canonical.items():
        entry = artifacts.get(name)
        if name not in required:
            if entry is not None:
                raise EpochCompletionValidationError(
                    f"completion marker has unexpected {name} artifact for mode {mode}"
                )
            if expected_path.exists():
                raise EpochCompletionValidationError(
                    f"unexpected canonical {name} exists for mode {mode}"
                )
            continue
        if not isinstance(entry, dict):
            raise EpochCompletionValidationError(f"missing completion artifact: {name}")
        expected_relative = expected_path.relative_to(root).as_posix()
        if entry.get("path") != expected_relative:
            raise EpochCompletionValidationError(
                f"completion artifact {name} must use canonical path {expected_relative}"
            )
        digest = entry.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise EpochCompletionValidationError(f"invalid sha256 for {name}")
        if not expected_path.is_file():
            raise EpochCompletionValidationError(f"missing completion artifact file: {name}")
        if _sha256_file(expected_path) != digest:
            raise EpochCompletionValidationError(f"completion artifact hash mismatch: {name}")
        resolved[name] = expected_path

    miner_state = _load_json_object(resolved["miner_state"], label="miner state")
    if any(not isinstance(value, (int, float)) for value in miner_state.values()):
        raise EpochCompletionValidationError("miner state values must be numeric")
    weights = _load_json_object(resolved["weights"], label="weights artifact")
    weight_result = weights.get("weight_result")
    if weights.get("epoch_id") != epoch_id or not isinstance(weight_result, dict):
        raise EpochCompletionValidationError("weights artifact epoch or result is invalid")
    if weight_result.get("mode") != mode or (weight_result.get("reason") or "") != reason:
        raise EpochCompletionValidationError("weights artifact mode/reason mismatch")
    panel = _load_json_object(resolved["panel_sidecar"], label="panel sidecar")
    if panel.get("epoch_id") != epoch_id:
        raise EpochCompletionValidationError("panel sidecar epoch mismatch")

    receipt_summary: dict[str, object] = {"mode": mode, "reason": reason}
    if mode != "fallback":
        receipt = _load_json_object(resolved["chain_receipt"], label="chain receipt")
        if receipt.get("epoch_id") != epoch_id:
            raise EpochCompletionValidationError("chain receipt epoch mismatch")
        if receipt.get("mode") != mode or receipt.get("reason") != reason:
            raise EpochCompletionValidationError("chain receipt mode/reason mismatch")
        receipt_summary.update(
            {
                "path": str(resolved["chain_receipt"]),
                "payload_digest": receipt.get("payload_digest"),
                "sha256": _sha256_file(resolved["chain_receipt"]),
            }
        )
    if mode == "submitted":
        attempt = _load_json_object(resolved["chain_attempt"], label="chain attempt")
        if (
            attempt.get("epoch_id") != epoch_id
            or attempt.get("mode") != "live_attempt"
            or attempt.get("status") != "completed"
            or attempt.get("receipt_file") != resolved["chain_receipt"].name
        ):
            raise EpochCompletionValidationError(
                "submitted epoch requires a completed canonical chain attempt"
            )
    return {
        "marker_path": str(marker_path),
        "epoch_id": epoch_id,
        "mode": mode,
        "reason": reason,
        "receipt": receipt_summary,
        "miner_state": miner_state,
    }


def read_jsonl_tolerating_torn_final(path: str | Path) -> list[dict[str, Any]]:
    """Read JSONL, ignoring only an unterminated malformed final record."""

    source = Path(path)
    raw = source.read_bytes()
    terminated = raw.endswith(b"\n")
    lines = raw.split(b"\n")
    if terminated:
        lines = lines[:-1]
    rows: list[dict[str, Any]] = []
    for index, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        is_unterminated_final = not terminated and index == len(lines)
        try:
            line = raw_line.decode("utf-8")
            payload = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            if is_unterminated_final:
                break
            raise ValueError(f"corrupt JSONL record at line {index}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"JSONL record at line {index} must be an object")
        rows.append(payload)
    return rows


def repair_jsonl_tail(path: str | Path) -> bool:
    """Atomically repair a torn tail before any later append can bury it."""

    destination = Path(path)
    if not destination.exists():
        return False
    raw = destination.read_bytes()
    if not raw or raw.endswith(b"\n"):
        # Validate complete lines even when no repair is necessary. Interior
        # corruption is never converted into an apparently healthy log.
        read_jsonl_tolerating_torn_final(destination)
        return False

    last_newline = raw.rfind(b"\n")
    prefix = raw[: last_newline + 1] if last_newline >= 0 else b""
    tail = raw[last_newline + 1 :]
    if prefix:
        # A temporary view is unnecessary: every prefix line is terminated, so
        # validate it directly before deciding what to do with the final tail.
        for index, raw_line in enumerate(prefix.split(b"\n")[:-1], start=1):
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"corrupt JSONL record at line {index}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL record at line {index} must be an object")
    try:
        final_payload = json.loads(tail.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        repaired = prefix
    else:
        if not isinstance(final_payload, dict):
            raise ValueError("unterminated JSONL final record must be an object")
        repaired = raw + b"\n"
    atomic_write_bytes(destination, repaired)
    return True


def _persist_panel_sidecar(
    cfg: SubnetConfig,
    panel_session: PanelSession,
    *,
    epoch_id: int,
) -> Path:
    path = panel_session.write_sidecar(epoch_id)
    if path is None:
        path = cfg.solver_panel_path(epoch_id)
        payload: dict[str, Any] = {"epoch_id": epoch_id, "mode": "mock", "tasks": []}
    else:
        payload = _load_json_object(path, label="panel sidecar")
    # PanelSession predates the recurring validator and writes directly. Republish
    # the sidecar atomically/fsynced before it can enter the completion marker.
    atomic_write_json(path, payload)
    return path


def _artifact_record(archive_dir: Path, path: Path) -> dict[str, str]:
    if not path.is_file():
        raise EpochCompletionValidationError(f"completion artifact is missing: {path.name}")
    try:
        relative = path.relative_to(archive_dir).as_posix()
    except ValueError as exc:
        raise EpochCompletionValidationError(
            f"completion artifact is outside archive: {path}"
        ) from exc
    return {"path": relative, "sha256": _sha256_file(path)}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EpochCompletionValidationError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EpochCompletionValidationError(f"{label} must be a JSON object")
    return payload


def _emit_phase(phase_hook: Callable[[str], None] | None, phase: str) -> None:
    if phase_hook is not None:
        phase_hook(phase)
