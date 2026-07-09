"""Small scoring helpers for the testnet MVP."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_WEIGHTS = {
    "verifier_quality": 0.35,
    "novelty": 0.25,
    "frontier_signal": 0.25,
    "metadata_clarity": 0.15,
}


def weighted_score(
    components: Mapping[str, float],
    weights: Mapping[str, float] | None = None,
) -> float:
    """Return a clipped weighted score in [0, 1]."""

    weights = weights or DEFAULT_WEIGHTS
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("score weights must sum to a positive value")

    score = 0.0
    for key, weight in weights.items():
        value = max(0.0, min(1.0, float(components.get(key, 0.0))))
        score += value * weight
    return max(0.0, min(1.0, score / total_weight))


def hard_gates_pass(gates: Mapping[str, bool]) -> bool:
    return all(bool(value) for value in gates.values())


def normalize_weights(raw_scores: Mapping[str, float]) -> dict[str, float]:
    """Normalize miner score totals into a Bittensor-style weight vector."""

    clipped = {uid: max(0.0, float(score)) for uid, score in raw_scores.items()}
    total = sum(clipped.values())
    if total <= 0:
        return {uid: 0.0 for uid in clipped}
    return {uid: score / total for uid, score in clipped.items()}


def top_k_epoch_scores(
    miner_task_values: Mapping[str, list[float]],
    *,
    top_k: int,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for miner, values in miner_task_values.items():
        best = sorted((max(0.0, float(value)) for value in values), reverse=True)[:top_k]
        scores[miner] = round(sum(best), 6)
    return scores


def update_ema_scores(
    previous: Mapping[str, float],
    epoch_scores: Mapping[str, float],
    *,
    alpha: float,
    infra_only_miners: set[str] | None = None,
) -> dict[str, float]:
    infra_only_miners = infra_only_miners or set()
    miners = set(previous) | set(epoch_scores)
    updated: dict[str, float] = {}
    for miner in sorted(miners):
        if miner in infra_only_miners:
            updated[miner] = round(float(previous.get(miner, 0.0)), 6)
            continue
        prev = float(previous.get(miner, 0.0))
        current = float(epoch_scores.get(miner, 0.0))
        updated[miner] = round(alpha * current + (1.0 - alpha) * prev, 6)
    return updated


def normalize_active_weights(
    ema_state: Mapping[str, float],
    active_hotkeys: list[str],
) -> dict[str, float]:
    active = {hotkey: float(ema_state.get(hotkey, 0.0)) for hotkey in active_hotkeys}
    return normalize_weights(active)


def task_value_from_score(score: Any) -> float:
    """Return the runtime-cost-free task value used for subnet weights."""

    if score.lifecycle_status != "accepted":
        return 0.0
    runtime_cost = float(score.components.runtime_cost)
    value = (float(score.aggregate_score) - 0.05 * runtime_cost) / 0.95
    return round(max(0.0, min(1.0, value)), 6)


# Mirrors dolores.scoring.aggregate.INFRA_ERROR_CLASSES: attempts in these
# classes reflect infrastructure/provider failures, not task difficulty, and
# must never move a task's measured solve rate.
INFRA_ERROR_CLASSES = frozenset(
    {"provider_error", "parse_error", "timeout_error", "verifier_error", "truncation_error"}
)

# Mirrors the weights inside dolores.scoring.aggregate (frontier_difficulty at
# 0.25) and dolores.scoring.frontier.frontier_difficulty_score. Recalibration
# must stay bit-consistent with what a live-panel pipeline run would produce.
FRONTIER_WEIGHT = 0.25
RUNTIME_WEIGHT = 0.05


def frontier_band_score(solve_rate: float) -> float:
    """Band value peaking at ~45% solve rate (mirror of core frontier score)."""

    return max(0.0, min(1.0, 1.0 - abs(float(solve_rate) - 0.45) / 0.55))


def clean_solve_rate_from_rows(rows: list[dict[str, Any]]) -> float | None:
    """Infra-excluded solve rate over per-attempt evidence rows.

    Returns None when no genuine (non-infra) attempt exists — callers must
    treat that as "no measurement", never as difficulty 0.
    """

    genuine = [row for row in rows if str(row.get("error_class")) not in INFRA_ERROR_CLASSES]
    if not genuine:
        return None
    passed = sum(1 for row in genuine if bool(row.get("passed")))
    return passed / len(genuine)


def recalibrated_task_value(
    task_value: float,
    components: Mapping[str, float],
    measured_solve_rate: float | None,
) -> float:
    """Swap the frontier term of an accepted task's value for a measured one.

    With measured_solve_rate=None this is the identity, so mock/unsampled
    paths stay byte-identical. Zero-valued (non-accepted) tasks are never
    rescued by cached difficulty evidence — the gauntlet verdict stands.
    """

    if measured_solve_rate is None or task_value <= 0.0:
        return task_value
    baseline = max(0.0, min(1.0, float(components.get("frontier_difficulty", 0.0))))
    measured = frontier_band_score(measured_solve_rate)
    adjusted = task_value + FRONTIER_WEIGHT * (measured - baseline) / (1.0 - RUNTIME_WEIGHT)
    return round(max(0.0, min(1.0, adjusted)), 6)


VOLATILE_KEYS = {
    "timing",
    "created_at",
    "duration_ms",
    "public_stdout",
    "public_stderr",
    "hidden_stdout",
    "hidden_stderr",
    "stdout",
    "stderr",
}


def normalize_for_determinism(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: normalize_for_determinism(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [normalize_for_determinism(item) for item in value]
    return value
