"""Mode-agnostic epoch engine for offline and future chain-backed runs."""

from __future__ import annotations

import dataclasses
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from dolores_subnet import archive, bridge
from dolores_subnet.chain import ChainClient, NullChain
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


def run_epoch(
    cfg: SubnetConfig,
    miners: list[MinerLike],
    *,
    epoch_id: int,
    quota: int,
    chain_client: ChainClient | None = None,
) -> EpochResult:
    started = time.monotonic()
    archive.init_archive(cfg)
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
        "previous_ema_state": dict(sorted(previous_ema.items())),
        "ema_state": dict(sorted(ema_state.items())),
        "infra_only": sorted(infra_only),
        "weights": dict(sorted(weights.items())),
        "degraded": degraded,
        "weight_result": chain_result.to_record(),
        "timing": {
            "created_at": datetime.now(UTC).isoformat(),
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    }
    _save_miner_state(cfg, ema_state)
    epoch_dir = cfg.epoch_dir(epoch_id)
    epoch_dir.mkdir(parents=True, exist_ok=True)
    panel_session.write_sidecar(epoch_id)
    artifact_path = cfg.weights_path(epoch_id)
    _atomic_write_text(
        artifact_path,
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
    )
    report_path = epoch_dir / f"report_epoch_{epoch_id}.md"
    return EpochResult(
        artifact_path=artifact_path,
        report_path=report_path,
        weights=weights,
        epoch_scores=epoch_scores,
    )


def replay_epoch(cfg: SubnetConfig, *, epoch_id: int) -> dict[str, Any]:
    artifact = json.loads(cfg.weights_path(epoch_id).read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in cfg.submissions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [row for row in rows if row["epoch_id"] == epoch_id]
    quota = int(artifact["config"]["quota"])
    miner_values: dict[str, list[float]] = {}
    for row in rows:
        miner_values.setdefault(row["miner_hotkey"], [])
        if row["status"] != "infra_error":
            miner_values[row["miner_hotkey"]].append(float(row["task_value"]))
    epoch_scores = top_k_epoch_scores(miner_values, top_k=quota)
    active_hotkeys = list(artifact["weights"])
    if "previous_ema_state" in artifact:
        # Re-derive the EMA chain end-to-end from the recorded prior state and this
        # epoch's scores instead of trusting the stored ema_state. This turns the
        # replay assertion into a real check that the published weights follow from
        # the submissions log, not a near-tautology over the stored value.
        previous_ema = {key: float(value) for key, value in artifact["previous_ema_state"].items()}
        infra_only = set(artifact.get("infra_only", []))
        ema_state = update_ema_scores(
            previous_ema,
            epoch_scores,
            alpha=float(artifact["config"]["ema_alpha"]),
            infra_only_miners=infra_only,
        )
    else:
        # Backward-compatible replay for artifacts written before previous_ema_state
        # was recorded: fall back to re-normalizing the stored ema_state.
        ema_state = {key: float(value) for key, value in artifact["ema_state"].items()}
    weights = normalize_active_weights(ema_state, active_hotkeys)
    return {"epoch_scores": epoch_scores, "ema_state": ema_state, "weights": weights}


def assert_replay_matches(cfg: SubnetConfig, *, epoch_id: int) -> None:
    artifact = json.loads(cfg.weights_path(epoch_id).read_text(encoding="utf-8"))
    replay = replay_epoch(cfg, epoch_id=epoch_id)
    if replay["epoch_scores"] != artifact["epoch_scores"]:
        raise AssertionError(
            f"epoch_scores mismatch: {replay['epoch_scores']} != {artifact['epoch_scores']}"
        )
    if "previous_ema_state" in artifact and replay["ema_state"] != artifact["ema_state"]:
        raise AssertionError(
            f"ema_state mismatch: {replay['ema_state']} != {artifact['ema_state']}"
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


def _save_miner_state(cfg: SubnetConfig, state: dict[str, float]) -> None:
    path = _miner_state_path(cfg)
    _atomic_write_text(
        path,
        json.dumps(dict(sorted(state.items())), indent=2, sort_keys=True) + "\n",
    )


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically via a sibling temp file + os.replace.

    A crash or a concurrent epoch can no longer leave a half-written weights
    artifact or miner_state.json behind, so the byte-reproducible-weights
    invariant holds under interruption. Callers should still serialize epoch
    execution per archive dir to avoid lost read-modify-write on miner_state.
    """

    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)
