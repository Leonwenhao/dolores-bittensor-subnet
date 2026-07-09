from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from dolores_subnet.config import ConfigError, SubnetConfig
from dolores_subnet.panel import SPEND_ENV, PanelSession, PanelSpendError

CALIBRATE_YAML = """\
panel_id: test_calibrate
solvers:
  - id: floor
    provider: fireworks
    model: accounts/fireworks/models/gpt-oss-120b
    temperature: 0.2
    max_tokens: 1024
    attempts: 1
  - id: strong
    provider: fireworks
    model: accounts/fireworks/models/kimi-k2p6
    temperature: 0.2
    max_tokens: 1024
    attempts: 2
"""


def _cfg(tmp_path: Path, monkeypatch, **kwargs) -> SubnetConfig:
    monkeypatch.delenv("DOLORES_SUBNET_PANEL_MODE", raising=False)
    monkeypatch.delenv("DOLORES_SUBNET_PANEL_DRYRUN", raising=False)
    monkeypatch.delenv("DOLORES_SUBNET_PANEL_MAX_TASKS", raising=False)
    cfg = SubnetConfig.from_env(mode="mock", work_dir=tmp_path, **kwargs)
    return cfg


def _calibrate_cfg(tmp_path: Path, monkeypatch, **kwargs) -> SubnetConfig:
    panel_file = tmp_path / "solver_panel.calibrate.yaml"
    panel_file.write_text(CALIBRATE_YAML, encoding="utf-8")
    monkeypatch.setenv("DOLORES_SUBNET_PANEL_CALIBRATE", str(panel_file))
    return _cfg(tmp_path, monkeypatch, panel_mode="calibrate", **kwargs)


def _network_tripwire(monkeypatch) -> None:
    def _fail(*args, **kwargs):  # noqa: ANN002, ANN003
        pytest.fail("network call attempted during a test")

    monkeypatch.setattr(urllib.request, "urlopen", _fail)


def test_panel_mode_defaults_to_mock(tmp_path, monkeypatch) -> None:
    cfg = _cfg(tmp_path, monkeypatch)
    assert cfg.panel_mode == "mock"
    assert cfg.panel_path.name == "solver_panel.mock.yaml"
    session = PanelSession(cfg)
    assert session.active is False
    assert session.plan("any-hash") == "mock"
    assert session.panel_path_for("mock") == cfg.panel_path
    assert session.write_sidecar(1) is None


def test_invalid_panel_mode_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DOLORES_SUBNET_PANEL_MODE", raising=False)
    with pytest.raises(ConfigError, match="panel_mode"):
        SubnetConfig.from_env(mode="mock", work_dir=tmp_path, panel_mode="real")


def test_calibrate_refuses_without_spend_gates(tmp_path, monkeypatch) -> None:
    _network_tripwire(monkeypatch)
    monkeypatch.delenv(SPEND_ENV, raising=False)
    cfg = _calibrate_cfg(tmp_path, monkeypatch, allow_provider_spend=True)
    with pytest.raises(PanelSpendError, match="provider_spend_not_allowed"):
        PanelSession(cfg)

    monkeypatch.setenv(SPEND_ENV, "1")
    cfg = _calibrate_cfg(tmp_path, monkeypatch, allow_provider_spend=False)
    with pytest.raises(PanelSpendError, match="provider_spend_not_allowed"):
        PanelSession(cfg)

    cfg = _calibrate_cfg(
        tmp_path, monkeypatch, allow_provider_spend=True, panel_max_tasks=0
    )
    with pytest.raises(PanelSpendError, match="provider_spend_not_allowed"):
        PanelSession(cfg)


def test_calibrate_without_credentials_fails_fast(tmp_path, monkeypatch) -> None:
    _network_tripwire(monkeypatch)
    monkeypatch.setenv(SPEND_ENV, "1")
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    cfg = _calibrate_cfg(tmp_path, monkeypatch, allow_provider_spend=True)
    with pytest.raises(PanelSpendError, match="FIREWORKS_API_KEY"):
        PanelSession(cfg)


def test_calibrate_accepted_with_gates_and_credentials(tmp_path, monkeypatch) -> None:
    _network_tripwire(monkeypatch)
    monkeypatch.setenv(SPEND_ENV, "1")
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key-not-real")
    cfg = _calibrate_cfg(tmp_path, monkeypatch, allow_provider_spend=True)
    session = PanelSession(cfg)
    assert session.active is True
    assert session.plan("hash-1") == "live"
    assert session.panel_path_for("live") == cfg.panel_calibrate_path
    assert session.planned_attempts() == 3


def test_budget_cap_and_refund(tmp_path, monkeypatch) -> None:
    _network_tripwire(monkeypatch)
    monkeypatch.setenv(SPEND_ENV, "1")
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key-not-real")
    cfg = _calibrate_cfg(
        tmp_path, monkeypatch, allow_provider_spend=True, panel_max_tasks=1
    )
    session = PanelSession(cfg)
    assert session.plan("hash-1") == "live"
    assert session.plan("hash-2") == "budget_exhausted"
    assert session.panel_path_for("budget_exhausted") == cfg.panel_path
    session.refund()
    assert session.plan("hash-3") == "live"


def test_dry_run_needs_no_gates_and_reports_estimates(tmp_path, monkeypatch) -> None:
    _network_tripwire(monkeypatch)
    monkeypatch.delenv(SPEND_ENV, raising=False)
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    cfg = _calibrate_cfg(
        tmp_path, monkeypatch, allow_provider_spend=False, panel_dry_run=True
    )
    session = PanelSession(cfg)
    assert session.plan("hash-1") == "dry_run"
    assert session.panel_path_for("dry_run") == cfg.panel_path
    session.record(plan="dry_run", task_id="t1", task_hash="hash-1", rows=[])
    sidecar_path = session.write_sidecar(7)
    assert sidecar_path is not None
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["mode"] == "dry_run"
    assert sidecar["estimated_total_attempts"] == 3
    assert sidecar["tasks"][0]["models"] == [
        "accounts/fireworks/models/gpt-oss-120b",
        "accounts/fireworks/models/kimi-k2p6",
    ]


def test_cache_hit_skips_live_and_survives_reload(tmp_path, monkeypatch) -> None:
    _network_tripwire(monkeypatch)
    monkeypatch.setenv(SPEND_ENV, "1")
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key-not-real")
    cfg = _calibrate_cfg(tmp_path, monkeypatch, allow_provider_spend=True)
    session = PanelSession(cfg)
    assert session.plan("hash-1") == "live"
    rows = [
        {"solver_id": "floor", "model": "m1", "provider": "fireworks",
         "attempt_id": 1, "passed": True, "error_class": "none",
         "prompt_tokens": 10, "completion_tokens": 20},
        {"solver_id": "strong", "model": "m2", "provider": "fireworks",
         "attempt_id": 1, "passed": False, "error_class": "verification_failure"},
    ]
    session.record(plan="live", task_id="t1", task_hash="hash-1", rows=rows)
    assert session.cached_solve_rate("hash-1") == 0.5

    # A fresh session (new epoch / restart) reloads the cache from disk and
    # never plans a live call for the same task hash.
    session2 = PanelSession(cfg)
    assert session2.plan("hash-1") == "cache"
    assert session2.cached_solve_rate("hash-1") == 0.5
    assert session2.budget_remaining == cfg.panel_max_tasks


def test_all_infra_rows_are_not_cached(tmp_path, monkeypatch) -> None:
    _network_tripwire(monkeypatch)
    monkeypatch.setenv(SPEND_ENV, "1")
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key-not-real")
    cfg = _calibrate_cfg(tmp_path, monkeypatch, allow_provider_spend=True)
    session = PanelSession(cfg)
    rows = [
        {"solver_id": "floor", "model": "m1", "provider": "fireworks",
         "attempt_id": 1, "passed": False, "error_class": "provider_error"},
        {"solver_id": "strong", "model": "m2", "provider": "fireworks",
         "attempt_id": 1, "passed": False, "error_class": "timeout_error"},
    ]
    session.record(plan="live", task_id="t1", task_hash="hash-1", rows=rows)
    assert session.cached_solve_rate("hash-1") is None
    assert not cfg.panel_cache_path.exists()


def test_epoch_gate_failure_never_reaches_panel_and_refunds_budget(
    tmp_path, monkeypatch
) -> None:
    from dataclasses import dataclass
    from typing import Any

    from dolores_subnet import bridge
    from dolores_subnet.epoch import run_epoch

    _network_tripwire(monkeypatch)
    monkeypatch.setenv(SPEND_ENV, "1")
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key-not-real")
    cfg = _calibrate_cfg(
        tmp_path, monkeypatch, allow_provider_spend=True, panel_max_tasks=2
    )

    pipeline_calls: list[str] = []

    def fake_validate(payload, cfg, *, context, miner_hotkey, panel_path=None):
        del cfg, context, miner_hotkey
        pipeline_calls.append(str(panel_path))
        # Simulate a hard-gate failure: invalid outcome, no panel rows.
        return bridge.SubmissionOutcome(
            status="invalid",
            task_id=payload["task_id"],
            package_hash=payload["package_hash"],
            task_value=0.0,
            gates={"schema_version": False},
            reason="invalid:schema",
        )

    monkeypatch.setattr(bridge, "validate_submission", fake_validate)

    @dataclass
    class OneShotMiner:
        hotkey: str
        uid: int

        def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
            del epoch_id, quota
            return [
                {
                    "schema_version": "bad",
                    "task_id": "t-bad",
                    "package_hash": "hash-bad",
                    "package": {},
                }
            ]

    run_epoch(cfg, [OneShotMiner("hk", 1)], epoch_id=1, quota=1)
    sidecar = json.loads(cfg.solver_panel_path(1).read_text(encoding="utf-8"))
    # Budget slot was refunded and the sidecar records the gate failure.
    assert sidecar["budget"]["remaining"] == 2
    assert sidecar["tasks"][0]["source"] == "gate_failed"
    # The panel never produced rows and nothing was cached.
    assert not cfg.panel_cache_path.exists()


def test_cache_invalidated_by_panel_config_change(tmp_path, monkeypatch) -> None:
    _network_tripwire(monkeypatch)
    monkeypatch.setenv(SPEND_ENV, "1")
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key-not-real")
    cfg = _calibrate_cfg(tmp_path, monkeypatch, allow_provider_spend=True)
    session = PanelSession(cfg)
    rows = [
        {"solver_id": "floor", "model": "m1", "provider": "fireworks",
         "attempt_id": 1, "passed": True, "error_class": "none"},
    ]
    session.record(plan="live", task_id="t1", task_hash="hash-1", rows=rows)

    panel_file = cfg.panel_calibrate_path
    panel_file.write_text(CALIBRATE_YAML + "# changed\n", encoding="utf-8")
    session2 = PanelSession(cfg)
    assert session2.cached_solve_rate("hash-1") is None
    assert session2.plan("hash-1") == "live"
