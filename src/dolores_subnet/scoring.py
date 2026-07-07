"""Small scoring helpers for the testnet MVP."""

from __future__ import annotations

from collections.abc import Mapping

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

