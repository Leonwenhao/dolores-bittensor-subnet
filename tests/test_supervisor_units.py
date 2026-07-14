from __future__ import annotations

import re
from pathlib import Path

from dolores_subnet.config import MAX_SIGNED_REQUEST_TIMEOUT_SECONDS

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PROCESS_PREFIX = (
    "/usr/bin/env READ_ONLY=1 TMPDIR=/run/dolores-validator "
    "/opt/dolores-validator/venv/bin/dolores-validator "
)


def _unit(name: str) -> str:
    return (ROOT / "deploy" / "systemd" / name).read_text(encoding="utf-8")


def _rehearsal(name: str) -> str:
    return (ROOT / "deploy" / "systemd" / name).read_text(encoding="utf-8")


def test_miner_unit_is_non_root_supervised_and_never_republishes() -> None:
    unit = _unit("dolores-miner.service")
    start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
    post = next(line for line in unit.splitlines() if line.startswith("ExecStartPost="))

    assert "User=dolores-miner" in unit
    assert "Group=dolores-miner" in unit
    assert "EnvironmentFile=/etc/dolores/miner.env" in unit
    assert "StateDirectoryMode=0700" in unit
    assert "Restart=on-failure" in unit
    assert "TimeoutStartSec=3min" in unit
    assert "StandardOutput=journal" in unit
    assert "NoNewPrivileges=true" in unit
    assert "dolores-miner serve" in start
    assert "--network test --netuid 523" in start
    assert "--publish" not in start
    assert "--allow-any-signed-validator" not in start
    assert "dolores-miner doctor" in post
    assert "--network test --netuid 523" in post
    assert "--attempts 3 --retry-delay 5" in post


def test_validator_unit_is_serialized_dry_run_with_explicit_health() -> None:
    unit = _unit("dolores-validator.service")
    start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
    post = next(line for line in unit.splitlines() if line.startswith("ExecStartPost="))

    assert "Type=oneshot" in unit
    assert "User=dolores-validator" in unit
    assert "EnvironmentFile=/etc/dolores/validator.env" in unit
    assert "StateDirectoryMode=0700" in unit
    assert "RuntimeDirectory=dolores-validator" in unit
    assert "RuntimeDirectoryMode=0700" in unit
    assert start.startswith(f"ExecStart={VALIDATOR_PROCESS_PREFIX}")
    assert post.startswith(f"ExecStartPost={VALIDATOR_PROCESS_PREFIX}")
    assert "Environment=READ_ONLY" not in unit
    assert "Environment=TMPDIR" not in unit
    assert "PrivateTmp=true" in unit
    assert "ProtectHome=read-only" in unit
    assert "ReadWritePaths=/var/lib/dolores-validator /run/dolores-validator" in unit
    assert "ReadWritePaths=/home" not in unit
    assert "dolores-validator tick" in start
    assert "--timeout 30" in start
    assert "DOLORES_VALIDATOR_TIMEOUT" not in unit
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


def test_validator_timer_waits_after_completion_without_missed_run_catch_up() -> None:
    timer = _unit("dolores-validator.timer")

    assert "Unit=dolores-validator.service" in timer
    assert "OnUnitInactiveSec=" in timer
    assert "Persistent=" not in timer
    assert "OnUnitActiveSec=" not in timer


def test_miner_rehearsal_changes_only_post_start_audit() -> None:
    drop_in = _rehearsal("dolores-miner-chain-neutral-rehearsal.conf")
    lines = drop_in.splitlines()

    assert not any(line.startswith("ExecStart=") for line in lines)
    assert sum(line.startswith("ExecStartPost=") for line in lines) == 2
    assert "dolores-miner health" in drop_in
    assert "127.0.0.1" in drop_in
    assert "--attempts 12 --retry-delay 1" in drop_in
    for forbidden in ("doctor", "--publish", "register", "serve_axon"):
        assert forbidden not in drop_in


def test_bittensor_read_only_import_mode_is_validator_only() -> None:
    validator = _unit("dolores-validator.service")
    miner = _unit("dolores-miner.service")

    assert validator.count(VALIDATOR_PROCESS_PREFIX) == 2
    assert VALIDATOR_PROCESS_PREFIX not in miner


def test_validator_rehearsal_is_signed_manual_wire_and_chain_off() -> None:
    drop_in = _rehearsal("dolores-validator-chain-neutral-rehearsal.conf")

    assert drop_in.count("ExecStart=") == 2
    assert drop_in.count("ExecStartPost=") == 2
    assert "dolores-validator tick --mode wire" in drop_in
    assert "dolores-validator health --mode wire" in drop_in
    assert "EnvironmentFile=/etc/dolores/rehearsal.env" in drop_in
    assert drop_in.count("--miner-endpoints ${DOLORES_REHEARSAL_MINER_ENDPOINT}") == 2
    assert drop_in.count("--chain off") == 2
    assert "--panel-mode mock" in drop_in
    assert drop_in.count("--timeout 30") == 2
    assert drop_in.count(VALIDATOR_PROCESS_PREFIX) == 2
    assert "DOLORES_VALIDATOR_TIMEOUT" not in drop_in
    for forbidden in (
        "--network test",
        "--netuid 523",
        "--chain dry-run",
        "--chain live",
        "--allow-extrinsics",
        "--allow-provider-spend",
    ):
        assert forbidden not in drop_in


def test_validator_process_guards_cannot_be_overridden_by_environment_files() -> None:
    commands: list[str] = []
    for content in (
        _unit("dolores-validator.service"),
        _rehearsal("dolores-validator-chain-neutral-rehearsal.conf"),
    ):
        commands.extend(
            line.partition("=")[2]
            for line in content.splitlines()
            if line.startswith(("ExecStart=", "ExecStartPost="))
            and line.partition("=")[2]
        )
        assert "Environment=READ_ONLY" not in content
        assert "Environment=TMPDIR" not in content

    assert len(commands) == 4
    assert all(command.startswith(VALIDATOR_PROCESS_PREFIX) for command in commands)


def test_supervised_validator_timeouts_do_not_exceed_miner_policy() -> None:
    configured = "\n".join(
        (
            _unit("dolores-validator.service"),
            _rehearsal("dolores-validator-chain-neutral-rehearsal.conf"),
        )
    )
    timeouts = [float(value) for value in re.findall(r"--timeout ([0-9.]+)", configured)]

    assert timeouts == [30.0, 30.0, 30.0]
    assert max(timeouts) <= MAX_SIGNED_REQUEST_TIMEOUT_SECONDS
