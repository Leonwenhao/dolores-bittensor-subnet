from __future__ import annotations

from dolores_subnet.scoring import (
    clean_solve_rate_from_rows,
    frontier_band_score,
    recalibrated_task_value,
)


def _rows(*specs: tuple[bool, str]) -> list[dict]:
    return [
        {"passed": passed, "error_class": error_class, "solver_id": f"s{i}",
         "model": f"m{i}", "attempt_id": 1}
        for i, (passed, error_class) in enumerate(specs)
    ]


def test_clean_solve_rate_excludes_infra_classes() -> None:
    rows = _rows(
        (True, "none"),
        (False, "verification_failure"),
        (False, "provider_error"),
        (False, "truncation_error"),
    )
    # 1 pass out of 2 genuine attempts; provider/truncation excluded.
    assert clean_solve_rate_from_rows(rows) == 0.5


def test_clean_solve_rate_none_when_all_infra() -> None:
    rows = _rows((False, "provider_error"), (False, "timeout_error"), (False, "parse_error"))
    assert clean_solve_rate_from_rows(rows) is None


def test_frontier_band_peaks_near_half() -> None:
    assert frontier_band_score(0.45) == 1.0
    assert frontier_band_score(0.5) > frontier_band_score(0.0)
    assert frontier_band_score(0.5) > frontier_band_score(1.0)
    assert frontier_band_score(1.0) == 0.0


def test_recalibrated_task_value_identity_without_measurement() -> None:
    components = {"frontier_difficulty": 0.7}
    assert recalibrated_task_value(0.5, components, None) == 0.5


def test_recalibrated_task_value_never_rescues_zero() -> None:
    assert recalibrated_task_value(0.0, {"frontier_difficulty": 0.1}, 0.5) == 0.0


def test_recalibrated_task_value_orders_measured_rates() -> None:
    components = {"frontier_difficulty": 0.5}
    base = 0.6
    mid = recalibrated_task_value(base, components, 0.5)
    easy = recalibrated_task_value(base, components, 1.0)
    hard = recalibrated_task_value(base, components, 0.0)
    assert mid > hard > easy or mid > easy  # band peak at 0.45: mid strictly highest
    assert mid > easy
    assert mid > hard
    # The adjustment is bounded and clipped to [0, 1].
    assert 0.0 <= easy <= 1.0
    assert 0.0 <= mid <= 1.0
