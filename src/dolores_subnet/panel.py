"""Solver-panel calibration session for the subnet validator.

Default posture is mock: no provider, no network, byte-identical behavior to
the pre-calibration validator. Calibration mode steers gauntlet-surviving
tasks through a real solver panel, guarded by three independent spend gates
(mirroring the live-chain gate pattern):

1. explicit config/CLI opt-in (``allow_provider_spend`` / ``--allow-provider-spend``),
2. the environment keystone ``DOLORES_ALLOW_PROVIDER_SPEND=1``,
3. a positive per-epoch task budget (``panel_max_tasks > 0``).

Dry-run mode requires none of these and never constructs a provider client.
All dolores/yaml imports are lazy so module import stays dependency-free.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from dolores_subnet.config import SubnetConfig
from dolores_subnet.scoring import INFRA_ERROR_CLASSES, clean_solve_rate_from_rows

SPEND_ENV = "DOLORES_ALLOW_PROVIDER_SPEND"
CREDENTIAL_ENV_BY_PROVIDER = {"fireworks": "FIREWORKS_API_KEY"}

DETERMINISTIC_ROW_KEYS = (
    "solver_id",
    "model",
    "provider",
    "attempt_id",
    "passed",
    "error_class",
)
VOLATILE_ROW_KEYS = (
    "duration_ms",
    "token_usage",
    "prompt_tokens",
    "completion_tokens",
    "cost_estimate",
    "finish_reason",
)


class PanelSpendError(RuntimeError):
    """Raised when calibration mode is requested without the spend gates."""


def panel_config_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_solver_specs(path: Path) -> list[dict[str, Any]]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [dict(entry) for entry in data.get("solvers", [])]


class PanelSession:
    """Per-epoch calibration planner, budget tracker, cache, and evidence log."""

    def __init__(self, cfg: SubnetConfig) -> None:
        self.cfg = cfg
        self.active = cfg.panel_mode == "calibrate"
        self.dry_run = bool(cfg.panel_dry_run)
        self.budget_remaining = int(cfg.panel_max_tasks)
        self.entries: list[dict[str, Any]] = []
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._digest: str | None = None
        self._solver_specs: list[dict[str, Any]] = []
        if not self.active:
            return
        if not cfg.panel_calibrate_path.exists():
            raise PanelSpendError(
                f"panel_mode=calibrate but panel config is missing: {cfg.panel_calibrate_path}"
            )
        self._digest = panel_config_digest(cfg.panel_calibrate_path)
        self._solver_specs = _load_solver_specs(cfg.panel_calibrate_path)
        if not self.dry_run:
            self._assert_spend_gates()
            self._assert_credentials()
        self._load_cache()

    # -- gates -----------------------------------------------------------

    def _assert_spend_gates(self) -> None:
        missing: list[str] = []
        if not self.cfg.allow_provider_spend:
            missing.append("allow_provider_spend flag (--allow-provider-spend)")
        if os.environ.get(SPEND_ENV) != "1":
            missing.append(f"{SPEND_ENV}=1 environment variable")
        if self.cfg.panel_max_tasks <= 0:
            missing.append("positive panel_max_tasks budget (--panel-max-tasks)")
        if missing:
            raise PanelSpendError(
                "provider_spend_not_allowed: calibration mode with real providers "
                "requires all spend gates; missing: " + "; ".join(missing)
            )

    def _assert_credentials(self) -> None:
        for spec in self._solver_specs:
            provider = str(spec.get("provider", "")).lower()
            env_name = CREDENTIAL_ENV_BY_PROVIDER.get(provider)
            if env_name and not os.environ.get(env_name):
                raise PanelSpendError(
                    f"{env_name} is required for provider={provider} in "
                    f"{self.cfg.panel_calibrate_path.name}; set it in the validator "
                    "environment (never in a file) or use --panel-dry-run"
                )

    # -- cache -----------------------------------------------------------

    def _load_cache(self) -> None:
        path = self.cfg.panel_cache_path
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("panel_digest") != self._digest:
                continue
            self._cache[(record["task_hash"], record["panel_digest"])] = record

    def _cache_store(self, task_hash: str, clean_rate: float, rows: list[dict[str, Any]]) -> None:
        record = {
            "task_hash": task_hash,
            "panel_digest": self._digest,
            "clean_solve_rate": clean_rate,
            "rows": [
                {key: row.get(key) for key in DETERMINISTIC_ROW_KEYS}
                for row in rows
                if str(row.get("error_class")) not in INFRA_ERROR_CLASSES
            ],
        }
        self._cache[(task_hash, self._digest or "")] = record
        path = self.cfg.panel_cache_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def cached_solve_rate(self, task_hash: str | None) -> float | None:
        if not self.active or not task_hash or self._digest is None:
            return None
        record = self._cache.get((task_hash, self._digest))
        if record is None:
            return None
        return record.get("clean_solve_rate")

    # -- planning ---------------------------------------------------------

    def plan(self, task_hash: str | None) -> str:
        """Return the calibration plan for one submission.

        mock            -> session inactive; use the mock panel
        cache           -> measured evidence cached; use mock panel + override
        dry_run         -> report-only; use mock panel, record the estimate
        live            -> use the real panel (budget slot reserved)
        budget_exhausted-> budget spent; use mock panel
        """

        if not self.active:
            return "mock"
        if self.cached_solve_rate(task_hash) is not None:
            return "cache"
        if self.dry_run:
            return "dry_run"
        if self.budget_remaining <= 0:
            return "budget_exhausted"
        self.budget_remaining -= 1
        return "live"

    def refund(self) -> None:
        """Return a reserved budget slot when a live-planned task never ran."""

        self.budget_remaining += 1

    def panel_path_for(self, plan: str) -> Path:
        if plan == "live":
            return self.cfg.panel_calibrate_path
        return self.cfg.panel_path

    def planned_attempts(self) -> int:
        return sum(int(spec.get("attempts", 1)) for spec in self._solver_specs)

    # -- evidence ----------------------------------------------------------

    def record(
        self,
        *,
        plan: str,
        task_id: str,
        task_hash: str | None,
        rows: list[dict[str, Any]],
        cached_rate: float | None = None,
    ) -> None:
        if not self.active:
            return
        entry: dict[str, Any] = {
            "task_id": task_id,
            "task_hash": task_hash,
            "source": plan,
        }
        if plan == "live" and rows:
            clean_rate = clean_solve_rate_from_rows(rows)
            entry["clean_solve_rate"] = clean_rate
            entry["attempts"] = [
                {key: row.get(key) for key in DETERMINISTIC_ROW_KEYS} for row in rows
            ]
            entry["volatile"] = [
                {key: row.get(key) for key in VOLATILE_ROW_KEYS} for row in rows
            ]
            if clean_rate is not None and task_hash:
                self._cache_store(task_hash, clean_rate, rows)
        elif plan == "cache":
            entry["clean_solve_rate"] = cached_rate
        elif plan == "dry_run":
            entry["estimated_attempts"] = self.planned_attempts()
            entry["models"] = [str(spec.get("model")) for spec in self._solver_specs]
        self.entries.append(entry)

    def write_sidecar(self, epoch_id: int) -> Path | None:
        if not self.active:
            return None
        sidecar = {
            "epoch_id": epoch_id,
            "mode": "dry_run" if self.dry_run else "calibrate",
            "panel_config": str(self.cfg.panel_calibrate_path),
            "panel_digest": self._digest,
            "budget": {
                "max_tasks": self.cfg.panel_max_tasks,
                "remaining": self.budget_remaining,
            },
            "tasks": self.entries,
        }
        if self.dry_run:
            sidecar["estimated_total_attempts"] = sum(
                entry.get("estimated_attempts", 0) for entry in self.entries
            )
        path = self.cfg.solver_panel_path(epoch_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path
