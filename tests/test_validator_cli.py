from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dolores_subnet import validator_cli
from dolores_subnet.atomic import atomic_write_json
from dolores_subnet.chain import ChainWeightResult, NullChain
from dolores_subnet.config import (
    DEFAULT_QUOTA,
    LOCALNET_ALT_NETWORK,
    LOCALNET_NETWORK,
    Mode,
)
from dolores_subnet.epoch import EpochResult, write_epoch_completion_marker


def test_tick_defaults_are_dry_and_auto_numbered() -> None:
    args = validator_cli.build_parser().parse_args(
        [
            "tick",
            "--work",
            "/tmp/work",
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
        ]
    )

    assert args.quota == DEFAULT_QUOTA
    assert args.chain == "dry-run"
    assert not hasattr(args, "epoch")
    assert args.allow_extrinsics is False
    assert args.allow_commit_reveal is False
    assert args.confirm_live == ""


def test_testnet_tick_requires_explicit_fixed_target(capsys) -> None:
    result = validator_cli.main(
        [
            "tick",
            "--work",
            "/tmp/work",
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
        ]
    )

    assert result == 2
    assert "explicit --network test --netuid 523" in capsys.readouterr().err


def test_testnet_tick_forbids_manual_endpoints(capsys) -> None:
    result = validator_cli.main(
        [
            "tick",
            "--work",
            "/tmp/work",
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--network",
            "test",
            "--netuid",
            "523",
            "--miner-endpoints",
            "127.0.0.1:8091:hotkey",
        ]
    )

    assert result == 2
    assert "manual endpoints forbidden" in capsys.readouterr().err


def test_localnet_tick_rejects_public_test_network_before_any_chain_call(
    tmp_path,
    capsys,
) -> None:
    result = validator_cli.main(
        [
            "tick",
            "--mode",
            "localnet",
            "--work",
            str(tmp_path),
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--network",
            "test",
            "--netuid",
            "523",
            "--chain",
            "dry-run",
        ]
    )

    assert result == 2
    assert "public network test is forbidden" in capsys.readouterr().err


@pytest.mark.parametrize("network", [LOCALNET_NETWORK, LOCALNET_ALT_NETWORK])
def test_localnet_tick_allows_only_explicit_loopback_targets(network: str) -> None:
    validator_cli._validate_tick_target(
        SimpleNamespace(
            network=network,
            netuid=2,
            chain="dry-run",
            miner_endpoints="",
        ),
        Mode.LOCALNET,
    )


@pytest.mark.parametrize(
    ("network", "netuid"),
    [(None, 2), (LOCALNET_NETWORK, None)],
)
def test_localnet_tick_requires_explicit_network_and_netuid(network, netuid) -> None:  # noqa: ANN001
    with pytest.raises(ValueError, match="requires explicit"):
        validator_cli._validate_tick_target(
            SimpleNamespace(
                network=network,
                netuid=netuid,
                chain="dry-run",
                miner_endpoints="",
            ),
            Mode.LOCALNET,
        )


def test_two_wire_ticks_allocate_monotonic_epochs_under_lock(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("DOLORES_HOLDOUT_SECRET", "local-test-secret")
    seen_epochs: list[int] = []

    def fake_query(*, epoch_id, **kwargs):  # noqa: ANN001
        del kwargs
        seen_epochs.append(epoch_id)
        return [SimpleNamespace(hotkey="miner", uid=1, terminal_status=None)]

    def fake_run(cfg, miners, *, epoch_id, quota, chain_client, phase_hook):  # noqa: ANN001
        del miners, quota
        assert isinstance(chain_client, NullChain)
        phase_hook("evaluating")
        phase_hook("weights_submitting")
        artifact = cfg.weights_path(epoch_id)
        miner_state = cfg.epoch_dir(epoch_id) / f"miner_state_epoch_{epoch_id}.json"
        panel = cfg.solver_panel_path(epoch_id)
        result = ChainWeightResult(mode="fallback", reason="offline")
        atomic_write_json(cfg.archive_dir / "miner_state.json", {"miner": 1.0})
        atomic_write_json(miner_state, {"miner": 1.0})
        atomic_write_json(panel, {"epoch_id": epoch_id, "mode": "mock", "tasks": []})
        atomic_write_json(
            artifact,
            {
                "epoch_id": epoch_id,
                "weight_result": result.to_record(),
            },
        )
        marker = write_epoch_completion_marker(
            cfg,
            epoch_id=epoch_id,
            chain_result=result,
            miner_state_path=miner_state,
            weights_path=artifact,
            panel_path=panel,
        )
        phase_hook("committed")
        return EpochResult(
            artifact_path=artifact,
            report_path=artifact.parent / "report.md",
            weights={"miner": 1.0},
            epoch_scores={"miner": 1.0},
            chain_result=result,
            completion_marker_path=marker,
        )

    monkeypatch.setattr(validator_cli, "_query_miners_for_tick", fake_query)
    monkeypatch.setattr(validator_cli, "run_epoch", fake_run)
    argv = [
        "tick",
        "--mode",
        "wire",
        "--work",
        str(tmp_path),
        "--wallet.name",
        "wallet",
        "--wallet.hotkey",
        "validator",
        "--chain",
        "off",
        "--miner-endpoints",
        "127.0.0.1:8091:hotkey",
    ]

    assert validator_cli.main(argv) == 0
    assert validator_cli.main(argv) == 0
    assert seen_epochs == [1, 2]
    assert "epoch_id=2" in capsys.readouterr().out


def test_wire_tick_forbids_chain_target_before_chain_construction(
    tmp_path, monkeypatch, capsys
) -> None:
    def fail_chain(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        raise AssertionError("wire target validation must run before chain construction")

    monkeypatch.setattr(validator_cli, "build_chain_client", fail_chain)
    result = validator_cli.main(
        [
            "tick",
            "--mode",
            "wire",
            "--work",
            str(tmp_path),
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--chain",
            "off",
            "--miner-endpoints",
            "127.0.0.1:8091:hotkey",
            "--network",
            "test",
            "--netuid",
            "523",
        ]
    )

    assert result == 2
    assert "forbids --network and --netuid" in capsys.readouterr().err


@pytest.mark.parametrize(
    "authorization_args",
    [
        ["--allow-extrinsics"],
        ["--allow-commit-reveal"],
        ["--confirm-live", "LIVE-TESTNET-523"],
    ],
)
def test_wire_tick_forbids_live_chain_authorization_flags(
    tmp_path, authorization_args, capsys  # noqa: ANN001
) -> None:
    result = validator_cli.main(
        [
            "tick",
            "--mode",
            "wire",
            "--work",
            str(tmp_path),
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--chain",
            "off",
            "--miner-endpoints",
            "127.0.0.1:8091:hotkey",
            *authorization_args,
        ]
    )

    assert result == 2
    assert "forbids live-chain authorization flags" in capsys.readouterr().err


def test_recover_parser_requires_explicit_work() -> None:
    args = validator_cli.build_parser().parse_args(
        ["recover-receipt", "--work", str(Path("work/validator"))]
    )
    assert not hasattr(args, "receipt")


def test_recover_parser_rejects_arbitrary_receipt_path() -> None:
    with pytest.raises(SystemExit):
        validator_cli.build_parser().parse_args(
            [
                "recover-receipt",
                "--work",
                str(Path("work/validator")),
                "--receipt",
                "/tmp/forged.json",
            ]
        )


def test_installed_replay_command_uses_archived_epoch(
    tmp_path, monkeypatch, capsys
) -> None:
    seen: dict[str, object] = {}

    def fake_replay(cfg, *, epoch_id):  # noqa: ANN001
        seen["work_dir"] = cfg.work_dir
        seen["epoch_id"] = epoch_id

    monkeypatch.setattr(validator_cli, "assert_replay_matches", fake_replay)

    assert (
        validator_cli.main(
            ["replay", "--work", str(tmp_path), "--epoch", "2"]
        )
        == 0
    )
    assert seen == {"work_dir": tmp_path, "epoch_id": 2}
    assert "REPLAY OK epoch_id=2" in capsys.readouterr().out


def test_installed_replay_rejects_nonpositive_epoch(tmp_path, capsys) -> None:
    assert (
        validator_cli.main(
            ["replay", "--work", str(tmp_path), "--epoch", "0"]
        )
        == 2
    )
    assert "replay epoch must be positive" in capsys.readouterr().err


def test_health_is_structured_and_never_prints_holdout_secret(
    tmp_path, monkeypatch, capsys
) -> None:
    secret = "health-secret-must-not-print"
    monkeypatch.setenv("DOLORES_HOLDOUT_SECRET", secret)
    monkeypatch.setattr(
        validator_cli,
        "_docker_health",
        lambda image: {"ok": True, "reason": "ok", "image": image},
    )

    class FakeChain:
        def __init__(self, **kwargs):
            del kwargs

        def preflight(self):
            return {"mode": "read_only", "reason": "ok", "blocks_since_last_update": 1}

        def miner_endpoints(self):
            return [{"host": "8.8.8.8", "port": 8091, "hotkey": "miner", "uid": 1}]

    monkeypatch.setattr(validator_cli, "SubtensorChain", FakeChain)
    monkeypatch.setattr(
        validator_cli,
        "_signed_health_probe",
        lambda **kwargs: 1,
    )
    result = validator_cli.main(
        [
            "health",
            "--work",
            str(tmp_path),
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--network",
            "test",
            "--netuid",
            "523",
        ]
    )
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert result == 0
    assert payload["ok"] is True
    assert payload["holdout_secret_configured"] is True
    assert payload["discovered_public_miners"] == 1
    assert payload["reachable_miner_count"] == 1
    assert payload["blocks_since_validator_update"] == 1
    assert payload["degraded_conditions"] == []
    assert payload["last_completed_epoch"] is None
    assert payload["last_successful_weight_receipt"] is None
    assert secret not in output


def test_health_fails_closed_when_signed_probe_is_disabled(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("DOLORES_HOLDOUT_SECRET", "local-test-secret")
    monkeypatch.setattr(
        validator_cli,
        "_docker_health",
        lambda image: {"ok": True, "reason": "ok", "image": image},
    )

    class FakeChain:
        def __init__(self, **kwargs):
            del kwargs

        def preflight(self):
            return {"mode": "read_only", "reason": "ok"}

        def miner_endpoints(self):
            return [{"host": "8.8.8.8", "port": 8091, "hotkey": "miner", "uid": 1}]

    monkeypatch.setattr(validator_cli, "SubtensorChain", FakeChain)
    result = validator_cli.main(
        [
            "health",
            "--work",
            str(tmp_path),
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--network",
            "test",
            "--netuid",
            "523",
            "--no-probe-wire",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["reachable_miner_count"] is None
    assert "signed_reachability_probe_disabled" in payload["degraded_conditions"]


def test_wire_health_is_signed_chain_neutral_and_never_constructs_subtensor(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("DOLORES_HOLDOUT_SECRET", "local-test-secret")
    monkeypatch.setattr(
        validator_cli,
        "_docker_health",
        lambda image: {"ok": True, "reason": "ok", "image": image},
    )
    monkeypatch.setattr(
        validator_cli,
        "_manual_wire_endpoint_rows",
        lambda **kwargs: [
            {
                "host": "127.0.0.1",
                "port": 8091,
                "hotkey": "miner",
                "uid": 0,
                "coldkey": "coldkey",
            }
        ],
    )
    monkeypatch.setattr(
        validator_cli,
        "_signed_health_probe",
        lambda **kwargs: 1,
    )

    class ForbiddenChain:
        def __init__(self, **kwargs):
            del kwargs
            raise AssertionError("wire health must not construct SubtensorChain")

    monkeypatch.setattr(validator_cli, "SubtensorChain", ForbiddenChain)
    result = validator_cli.main(
        [
            "health",
            "--mode",
            "wire",
            "--work",
            str(tmp_path),
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--miner-endpoints",
            "127.0.0.1:8091:miner:coldkey",
            "--chain",
            "off",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["ok"] is True
    assert payload["chain"] == {
        "mode": "off",
        "reason": "manual_wire_chain_neutral",
    }
    assert payload["endpoint_source"] == "manual_wire"
    assert payload["manual_endpoints"] == 1
    assert payload["discovered_public_miners"] == 0
    assert payload["signed_reachable_miners"] == 1
    assert payload["degraded_conditions"] == []


def test_wire_health_requires_manual_endpoints_and_chain_off(capsys, tmp_path) -> None:
    common = [
        "health",
        "--mode",
        "wire",
        "--work",
        str(tmp_path),
        "--wallet.name",
        "wallet",
        "--wallet.hotkey",
        "validator",
    ]
    assert validator_cli.main(common) == 2
    assert "requires --miner-endpoints" in capsys.readouterr().err

    assert validator_cli.main(common + ["--miner-endpoints", "127.0.0.1:8091:miner"]) == 2
    assert "requires --chain off" in capsys.readouterr().err


def test_chain_health_forbids_manual_endpoint_injection(capsys, tmp_path) -> None:
    result = validator_cli.main(
        [
            "health",
            "--work",
            str(tmp_path),
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--network",
            "test",
            "--netuid",
            "523",
            "--miner-endpoints",
            "127.0.0.1:8091:miner",
        ]
    )

    assert result == 2
    assert "manual endpoints forbidden" in capsys.readouterr().err


def test_probe_wire_is_quota_zero_chain_off_and_sanitized(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        validator_cli,
        "_manual_wire_endpoint_rows",
        lambda **kwargs: [
            {
                "host": "203.0.113.10",
                "port": 8091,
                "hotkey": "miner",
                "uid": 0,
                "coldkey": "coldkey",
            }
        ],
    )
    monkeypatch.setattr(
        validator_cli,
        "_signed_health_probe",
        lambda **kwargs: 1,
    )

    result = validator_cli.main(
        [
            "probe-wire",
            "--miner-endpoints",
            "203.0.113.10:8091:miner:coldkey",
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
        ]
    )
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert result == 0
    assert payload == {
        "chain_mode": "off",
        "endpoint_count": 1,
        "endpoint_source": "manual",
        "metagraph_discovery": False,
        "mode": "wire",
        "ok": True,
        "quota": 0,
        "signed_reachable": 1,
    }
    assert "wallet" not in output
    assert "203.0.113.10" not in output


def test_localnet_health_rejects_public_test_network_before_any_chain_call(
    tmp_path,
    capsys,
) -> None:
    result = validator_cli.main(
        [
            "health",
            "--mode",
            "localnet",
            "--work",
            str(tmp_path),
            "--wallet.name",
            "wallet",
            "--wallet.hotkey",
            "validator",
            "--network",
            "test",
            "--netuid",
            "523",
        ]
    )

    assert result == 2
    assert "public network test is forbidden" in capsys.readouterr().err


@pytest.mark.parametrize("network", [LOCALNET_NETWORK, LOCALNET_ALT_NETWORK])
def test_localnet_health_allows_only_explicit_loopback_targets(network: str) -> None:
    validator_cli._validate_health_target(
        SimpleNamespace(network=network, netuid=2),
        Mode.LOCALNET,
    )
