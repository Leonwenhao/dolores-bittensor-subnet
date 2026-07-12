from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _unit(name: str) -> str:
    return (ROOT / "deploy" / "systemd" / name).read_text(encoding="utf-8")


def test_miner_unit_is_non_root_supervised_and_never_republishes() -> None:
    unit = _unit("dolores-miner.service")
    start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
    post = next(line for line in unit.splitlines() if line.startswith("ExecStartPost="))

    assert "User=dolores-miner" in unit
    assert "Group=dolores-miner" in unit
    assert "EnvironmentFile=/etc/dolores/miner.env" in unit
    assert "Restart=on-failure" in unit
    assert "StandardOutput=journal" in unit
    assert "NoNewPrivileges=true" in unit
    assert "dolores-miner serve" in start
    assert "--network test --netuid 523" in start
    assert "--publish" not in start
    assert "--allow-any-signed-validator" not in start
    assert "dolores-miner doctor" in post
    assert "--network test --netuid 523" in post


def test_validator_unit_is_serialized_dry_run_with_explicit_health() -> None:
    unit = _unit("dolores-validator.service")
    start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
    post = next(line for line in unit.splitlines() if line.startswith("ExecStartPost="))

    assert "Type=oneshot" in unit
    assert "User=dolores-validator" in unit
    assert "EnvironmentFile=/etc/dolores/validator.env" in unit
    assert "dolores-validator tick" in start
    assert "--network test --netuid 523" in start
    assert "--chain dry-run" in start
    assert "--panel-mode mock" in start
    for forbidden in (
        "--miner-endpoints",
        "--chain live",
        "--allow-extrinsics",
        "--allow-provider-spend",
        "--allow-commit-reveal",
    ):
        assert forbidden not in start
    assert "dolores-validator health" in post
    assert "--network test --netuid 523" in post


def test_validator_timer_waits_after_completion_and_persists() -> None:
    timer = _unit("dolores-validator.timer")

    assert "Unit=dolores-validator.service" in timer
    assert "OnUnitInactiveSec=" in timer
    assert "Persistent=true" in timer
    assert "OnUnitActiveSec=" not in timer
