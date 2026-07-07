from __future__ import annotations

import pytest

from dolores_subnet.scoring import normalize_active_weights, top_k_epoch_scores, update_ema_scores


def test_top_k_epoch_scores_are_monotonic() -> None:
    scores = top_k_epoch_scores({"a": [0.2, 0.9, 0.1], "b": [0.5]}, top_k=2)
    assert scores["a"] == pytest.approx(1.1)
    assert scores["b"] == pytest.approx(0.5)


def test_ema_bounds_and_infra_carry_forward() -> None:
    updated = update_ema_scores(
        {"a": 0.5, "b": 0.25},
        {"a": 1.0, "b": 0.0},
        alpha=0.3,
        infra_only_miners={"b"},
    )
    assert updated["a"] == pytest.approx(0.65)
    assert updated["b"] == pytest.approx(0.25)


def test_normalize_active_weights_excludes_inactive() -> None:
    weights = normalize_active_weights({"a": 1.0, "b": 1.0, "inactive": 100.0}, ["a", "b"])
    assert weights == {"a": 0.5, "b": 0.5}


def test_normalize_active_weights_handles_all_zero() -> None:
    assert normalize_active_weights({"a": 0.0}, ["a"]) == {"a": 0.0}
