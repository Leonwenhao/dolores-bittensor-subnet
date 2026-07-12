from __future__ import annotations

import builtins
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bittensor as bt
import pytest

from dolores_subnet import miner_cli

COLDKEY_SS58 = "5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG"
HOTKEY_SS58 = "5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA"
PUBLIC_IP = "8.8.8.8"
PUBLIC_PORT = 8091


def _wallet_tree(tmp_path: Path) -> Path:
    root = tmp_path / "wallets"
    wallet = root / "cohort-wallet"
    (wallet / "hotkeys").mkdir(parents=True)
    (wallet / "coldkeypub.txt").touch()
    (wallet / "hotkeys" / "cohort-miner").touch()
    return root


def _doctor_argv(wallet_root: Path, *, task_dir: Path | None = None) -> list[str]:
    argv = [
        "doctor",
        "--network",
        "test",
        "--netuid",
        "523",
        "--wallet.name",
        "cohort-wallet",
        "--wallet.hotkey",
        "cohort-miner",
        "--wallet.path",
        str(wallet_root),
        "--coldkey-ss58",
        COLDKEY_SS58,
        "--hotkey-ss58",
        HOTKEY_SS58,
        "--external-ip",
        PUBLIC_IP,
        "--port",
        str(PUBLIC_PORT),
        "--timeout",
        "0.25",
    ]
    if task_dir is not None:
        argv.extend(["--task-dir", str(task_dir)])
    return argv


def _snapshot(
    *,
    registered: bool = True,
    ip: str = PUBLIC_IP,
    port: int = PUBLIC_PORT,
    coldkey: str = COLDKEY_SS58,
    balance_rao: int = 1_000_000_000,
) -> miner_cli.DoctorChainSnapshot:
    hotkeys = [HOTKEY_SS58] if registered else []
    uids = [7] if registered else []
    axons = [SimpleNamespace(ip=ip, port=port, coldkey=coldkey)] if registered else []
    return miner_cli.DoctorChainSnapshot(
        balance_rao=balance_rao,
        metagraph=SimpleNamespace(hotkeys=hotkeys, uids=uids, axons=axons),
    )


def _patch_doctor_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    snapshot: miner_cli.DoctorChainSnapshot | None = None,
    public_tcp: bool = True,
    local_port_state: str = "free",
    engine_smoke: bool = True,
    versions: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    installed = dict(miner_cli.EXPECTED_DISTRIBUTIONS)
    if versions:
        installed.update(versions)
    monkeypatch.setattr(miner_cli.importlib.metadata, "version", installed.__getitem__)
    monkeypatch.setattr(
        miner_cli.shutil,
        "which",
        lambda executable: "/usr/bin/btcli" if executable == "btcli" else None,
    )
    monkeypatch.setattr(
        miner_cli.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="BTCLI version: 9.23.1",
            stderr="",
        ),
    )
    monkeypatch.setattr(miner_cli, "_public_ss58_is_valid", lambda address: bool(address))
    monkeypatch.setattr(miner_cli, "_local_port_state", lambda port, timeout: local_port_state)
    monkeypatch.setattr(miner_cli, "_tcp_reachable", lambda host, port, timeout: public_tcp)
    if engine_smoke:
        monkeypatch.setattr(
            miner_cli,
            "_engine_smoke_check",
            lambda: {
                "ok": True,
                "generated": 1,
                "family": "parser_roundtrip",
                "archetype": "escape_delim",
                "stable_hash_matches_wire": True,
                "wire_bytes": 1024,
            },
        )

    calls: list[dict[str, Any]] = []

    def fake_read_chain(**kwargs: Any) -> miner_cli.DoctorChainSnapshot:
        calls.append(kwargs)
        return snapshot or _snapshot()

    monkeypatch.setattr(miner_cli, "_read_doctor_chain", fake_read_chain)
    return calls


def test_miner_bounded_call_preserves_results_and_exceptions() -> None:
    assert miner_cli._bounded_call(lambda value: value * 2, 21, timeout=1.0) == 42
    with pytest.raises(ValueError, match="boom"):
        miner_cli._bounded_call(
            lambda: (_ for _ in ()).throw(ValueError("boom")),
            timeout=1.0,
        )


def test_miner_bounded_call_timeout_does_not_delay_cli_process_exit() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    code = """
import time
from dolores_subnet.miner_cli import _bounded_call
try:
    _bounded_call(time.sleep, 30, timeout=0.05)
except TimeoutError:
    print("timed_out")
"""
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )

    assert completed.stdout.strip() == "timed_out"
    assert time.monotonic() - started < 3


def test_miner_bounded_call_nested_alarm_fails_closed_and_restores_signal() -> None:
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer[0] > 0 or previous_timer[1] > 0:
        pytest.skip("test runner already owns ITIMER_REAL")

    def prior_handler(signum, frame):  # noqa: ANN001
        del signum, frame

    signal.signal(signal.SIGALRM, prior_handler)
    try:
        with pytest.raises(TimeoutError, match="active SIGALRM"):
            miner_cli._bounded_call(
                lambda: miner_cli._bounded_call(lambda: None, timeout=0.5),
                timeout=1.0,
            )
        assert signal.getsignal(signal.SIGALRM) is prior_handler
        assert signal.getitimer(signal.ITIMER_REAL) == pytest.approx((0.0, 0.0))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_miner_bounded_call_non_main_thread_fails_without_calling_target() -> None:
    called = False
    errors: list[BaseException] = []

    def target() -> None:
        nonlocal called
        called = True

    def worker() -> None:
        try:
            miner_cli._bounded_call(target, timeout=1.0)
        except BaseException as exc:  # noqa: BLE001 - capture thread assertion evidence.
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert called is False
    assert len(errors) == 1
    assert isinstance(errors[0], TimeoutError)
    assert "main thread" in str(errors[0])


def test_init_then_validate_supported_task_without_docker(tmp_path, capsys) -> None:
    output = tmp_path / "tasks"
    assert miner_cli.main(["init", "--output", str(output), "--seed", "17"]) == 0
    created = capsys.readouterr().out
    task_dir = next(
        line.split("=", 1)[1] for line in created.splitlines() if line.startswith("task_dir=")
    )

    assert miner_cli.main(["validate", "--task-dir", task_dir]) == 0
    validated = capsys.readouterr().out
    assert "VALID task_id=" in validated
    assert "family=parser_roundtrip" in validated
    assert "author_tests=" in validated


def test_doctor_full_success_is_read_only_structured_and_path_free(
    tmp_path, monkeypatch, capsys
) -> None:
    wallet_root = _wallet_tree(tmp_path)
    calls = _patch_doctor_dependencies(monkeypatch)

    result = miner_cli.main(_doctor_argv(wallet_root))
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert result == 0
    assert payload["ok"] is True
    assert payload["checks"]["target"] == {"ok": True, "network": "test", "netuid": 523}
    assert payload["checks"]["registration"] == {
        "ok": True,
        "registered": True,
        "uid": 7,
    }
    assert payload["checks"]["balance"]["balance_rao"] == 1_000_000_000
    assert payload["checks"]["published_axon"] == {
        "ok": True,
        "exact": True,
        "owner_matches": True,
        "endpoint_matches": True,
    }
    assert payload["attempts"] == {"configured": 1, "used": 1}
    assert payload["checks"]["public_tcp"] == {
        "ok": True,
        "reachable": True,
        "scope": "same_host_hairpin",
        "external_reachability_proof": False,
    }
    assert payload["checks"]["local_port"] == {"ok": True, "state": "free"}
    assert payload["checks"]["wallet_metadata"]["inspection"] == "metadata_only"
    assert payload["checks"]["miner_boundary"] == {
        "ok": True,
        "docker_required": False,
        "duckdb_required": False,
        "fireworks_required": False,
        "streamlit_required": False,
    }
    assert calls == [
        {
            "network": "test",
            "netuid": 523,
            "coldkey_ss58": COLDKEY_SS58,
            "timeout": 0.25,
        }
    ]
    for private_value in (
        str(wallet_root),
        "cohort-wallet",
        "cohort-miner",
        COLDKEY_SS58,
        HOTKEY_SS58,
    ):
        assert private_value not in output


def test_doctor_uses_wallet_filesystem_metadata_without_opening_files(
    tmp_path, monkeypatch, capsys
) -> None:
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("doctor must not open or read wallet files")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)

    assert miner_cli.main(_doctor_argv(wallet_root)) == 0
    assert json.loads(capsys.readouterr().out)["checks"]["wallet_metadata"]["ok"] is True


def test_doctor_requires_all_explicit_public_identity_arguments() -> None:
    with pytest.raises(SystemExit) as error:
        miner_cli.main(["doctor"])
    assert error.value.code == 2


def test_doctor_rejects_any_target_other_than_public_testnet_523(
    tmp_path, monkeypatch, capsys
) -> None:
    wallet_root = _wallet_tree(tmp_path)
    calls = _patch_doctor_dependencies(monkeypatch)
    argv = _doctor_argv(wallet_root)
    argv[argv.index("test")] = "finney"

    assert miner_cli.main(argv) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["target"] == {
        "ok": False,
        "reason": "wrong_public_cohort_target",
    }
    assert calls == []


@pytest.mark.parametrize(
    ("version", "ok"),
    [((3, 10, 14), False), ((3, 11, 0), True), ((3, 11, 99), True), ((3, 12, 0), False)],
)
def test_doctor_enforces_supported_python_range(version, ok) -> None:
    assert miner_cli._python_check(version)["ok"] is ok


def test_doctor_fails_on_any_nonexact_distribution_version(tmp_path, monkeypatch, capsys) -> None:
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch, versions={"bittensor-cli": "9.23.0"})

    assert miner_cli.main(_doctor_argv(wallet_root)) == 1
    check = json.loads(capsys.readouterr().out)["checks"]["bittensor-cli"]
    assert check == {"ok": False, "version": "9.23.0", "expected": "9.23.1"}


def test_doctor_fails_when_btcli_executable_is_missing(tmp_path, monkeypatch, capsys) -> None:
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch)
    monkeypatch.setattr(miner_cli.shutil, "which", lambda executable: None)

    assert miner_cli.main(_doctor_argv(wallet_root)) == 1
    assert json.loads(capsys.readouterr().out)["checks"]["btcli"] == {
        "ok": False,
        "executable": False,
        "version_verified": False,
    }


def test_doctor_fails_when_btcli_binary_version_is_not_pinned(
    tmp_path, monkeypatch, capsys
) -> None:
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch)
    monkeypatch.setattr(
        miner_cli.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="BTCLI version: 9.23.0",
            stderr="",
        ),
    )

    assert miner_cli.main(_doctor_argv(wallet_root)) == 1
    assert json.loads(capsys.readouterr().out)["checks"]["btcli"] == {
        "ok": False,
        "executable": True,
        "version_verified": False,
    }


def test_doctor_fails_missing_wallet_metadata_without_exposing_path(
    tmp_path, monkeypatch, capsys
) -> None:
    wallet_root = tmp_path / "secret-wallet-root"
    _patch_doctor_dependencies(monkeypatch)

    assert miner_cli.main(_doctor_argv(wallet_root)) == 1
    output = capsys.readouterr().out
    check = json.loads(output)["checks"]["wallet_metadata"]
    assert check["ok"] is False
    assert check["coldkey_public_file"] is False
    assert str(wallet_root) not in output


def test_doctor_fails_unregistered_hotkey_and_missing_uid(tmp_path, monkeypatch, capsys) -> None:
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch, snapshot=_snapshot(registered=False))

    assert miner_cli.main(_doctor_argv(wallet_root)) == 1
    checks = json.loads(capsys.readouterr().out)["checks"]
    assert checks["registration"] == {"ok": False, "registered": False, "uid": None}
    assert checks["published_axon"]["exact"] is False


@pytest.mark.parametrize(
    ("snapshot", "failed_field"),
    [
        (_snapshot(ip="1.1.1.1"), "endpoint_matches"),
        (_snapshot(port=8092), "endpoint_matches"),
        (_snapshot(coldkey=HOTKEY_SS58), "owner_matches"),
    ],
)
def test_doctor_requires_exact_published_axon(
    tmp_path, monkeypatch, capsys, snapshot, failed_field
) -> None:
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch, snapshot=snapshot)

    assert miner_cli.main(_doctor_argv(wallet_root)) == 1
    axon = json.loads(capsys.readouterr().out)["checks"]["published_axon"]
    assert axon["exact"] is False
    assert axon[failed_field] is False


def test_doctor_fails_when_public_tcp_is_unreachable(tmp_path, monkeypatch, capsys) -> None:
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch, public_tcp=False)

    assert miner_cli.main(_doctor_argv(wallet_root)) == 1
    assert json.loads(capsys.readouterr().out)["checks"]["public_tcp"] == {
        "ok": False,
        "reachable": False,
        "scope": "same_host_hairpin",
        "external_reachability_proof": False,
    }


def test_doctor_retries_until_full_audit_succeeds(tmp_path, monkeypatch, capsys) -> None:
    wallet_root = _wallet_tree(tmp_path)
    calls = _patch_doctor_dependencies(monkeypatch)
    reachability = iter([False, True])
    sleeps: list[float] = []
    monkeypatch.setattr(
        miner_cli,
        "_tcp_reachable",
        lambda host, port, timeout: next(reachability),
    )
    monkeypatch.setattr(miner_cli.time, "sleep", sleeps.append)
    argv = _doctor_argv(wallet_root) + ["--attempts", "3", "--retry-delay", "0.5"]

    assert miner_cli.main(argv) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["attempts"] == {"configured": 3, "used": 2}
    assert len(calls) == 2
    assert sleeps == [0.5]


def test_doctor_retry_exhaustion_emits_only_final_failure(
    tmp_path, monkeypatch, capsys
) -> None:
    wallet_root = _wallet_tree(tmp_path)
    calls = _patch_doctor_dependencies(monkeypatch, public_tcp=False)
    sleeps: list[float] = []
    monkeypatch.setattr(miner_cli.time, "sleep", sleeps.append)
    argv = _doctor_argv(wallet_root) + ["--attempts", "3", "--retry-delay", "0.25"]

    assert miner_cli.main(argv) == 1
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert output.count('"checks"') == 1
    assert payload["attempts"] == {"configured": 3, "used": 3}
    assert len(calls) == 3
    assert sleeps == [0.25, 0.25]


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--attempts", "0"),
        ("--attempts", "13"),
        ("--retry-delay", "-0.1"),
        ("--retry-delay", "30.1"),
    ],
)
def test_doctor_rejects_retry_bounds(tmp_path, capsys, flag, value) -> None:
    wallet_root = _wallet_tree(tmp_path)

    assert miner_cli.main(_doctor_argv(wallet_root) + [flag, value]) == 2
    assert "outside the supported bound" in capsys.readouterr().err


def test_doctor_chain_failure_is_fail_closed_and_does_not_leak_error(
    tmp_path, monkeypatch, capsys
) -> None:
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch)

    def fail_chain(**kwargs: Any) -> Any:
        del kwargs
        raise RuntimeError("rpc secret/path should never be displayed")

    monkeypatch.setattr(miner_cli, "_read_doctor_chain", fail_chain)

    assert miner_cli.main(_doctor_argv(wallet_root)) == 1
    output = capsys.readouterr().out
    checks = json.loads(output)["checks"]
    assert checks["balance"] == {"ok": False, "reason": "chain_read_failed"}
    assert checks["registration"]["reason"] == "chain_read_failed"
    assert "rpc secret/path" not in output


def test_doctor_runs_real_curated_and_optional_task_hash_wire_smokes(
    tmp_path, monkeypatch, capsys
) -> None:
    output = tmp_path / "tasks"
    assert miner_cli.main(["init", "--output", str(output), "--seed", "17"]) == 0
    task_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in capsys.readouterr().out.splitlines()
            if line.startswith("task_dir=")
        )
    )
    wallet_root = _wallet_tree(tmp_path)
    _patch_doctor_dependencies(monkeypatch, engine_smoke=False)

    assert miner_cli.main(_doctor_argv(wallet_root, task_dir=task_dir)) == 0
    checks = json.loads(capsys.readouterr().out)["checks"]
    assert checks["engine_smoke"]["generated"] == 1
    assert checks["engine_smoke"]["family"] == "parser_roundtrip"
    assert checks["engine_smoke"]["stable_hash_matches_wire"] is True
    assert checks["tasks"]["count"] == 1
    assert checks["tasks"]["stable_hash_matches_wire"] is True


def test_registration_is_fixed_to_testnet_523_and_dry_by_default(capsys) -> None:
    result = miner_cli.main(
        [
            "register",
            "--wallet.name",
            "cohort-wallet",
            "--wallet.hotkey",
            "cohort-miner",
            "--network",
            "test",
            "--netuid",
            "523",
        ]
    )
    output = capsys.readouterr().out

    assert result == 0
    assert "btcli subnet register --network test --netuid 523" in output
    assert "--wallet-name cohort-wallet --hotkey cohort-miner" in output
    assert "registration=not_executed" in output


def test_registration_execute_requires_exact_confirmation(monkeypatch, capsys) -> None:
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        del args, kwargs
        called = True
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(miner_cli.subprocess, "run", forbidden)
    result = miner_cli.main(
        [
            "register",
            "--wallet.name",
            "cohort-wallet",
            "--wallet.hotkey",
            "cohort-miner",
            "--network",
            "test",
            "--netuid",
            "523",
            "--execute",
        ]
    )

    assert result == 2
    assert called is False
    assert "REGISTER-TESTNET-523" in capsys.readouterr().err


def test_public_serve_forbids_allow_any_signed_validator(tmp_path, capsys) -> None:
    output = tmp_path / "tasks"
    assert miner_cli.main(["init", "--output", str(output)]) == 0
    task_dir = next(output.iterdir())
    capsys.readouterr()

    result = miner_cli.main(
        [
            "serve",
            "--wallet.name",
            "cohort-wallet",
            "--wallet.hotkey",
            "cohort-miner",
            "--task-dir",
            str(task_dir),
            "--allow-any-signed-validator",
            "--publish",
        ]
    )

    assert result == 2
    assert "forbids --allow-any-signed-validator" in capsys.readouterr().err


def test_serve_constructs_axon_with_exact_external_endpoint(monkeypatch, capsys) -> None:
    wallet = SimpleNamespace(hotkey=SimpleNamespace(ss58_address=HOTKEY_SS58))
    calls: dict[str, list[Any]] = {
        "wallet": [],
        "axon": [],
        "attach": [],
        "publish": [],
        "start": [],
        "stop": [],
    }

    class FakeAxon:
        def __init__(self, **kwargs: Any) -> None:
            self.wallet = kwargs["wallet"]
            self.kwargs = kwargs

        def start(self) -> FakeAxon:
            calls["start"].append(self)
            return self

        def stop(self) -> None:
            calls["stop"].append(self)

    def fake_wallet(*, name: str, hotkey: str) -> Any:
        calls["wallet"].append((name, hotkey))
        return wallet

    def fake_axon(**kwargs: Any) -> FakeAxon:
        calls["axon"].append(kwargs)
        return FakeAxon(**kwargs)

    def fake_attach(axon: FakeAxon, *, forward: Any, blacklist: Any) -> FakeAxon:
        calls["attach"].append((axon, forward, blacklist))
        return axon

    def fake_publish(args: Any, *, axon: FakeAxon) -> None:
        calls["publish"].append((args.network, args.netuid, axon))
        assert axon.kwargs == {
            "wallet": wallet,
            "port": PUBLIC_PORT,
            "ip": "0.0.0.0",
            "external_ip": PUBLIC_IP,
            "external_port": PUBLIC_PORT,
        }

    monkeypatch.setattr(bt, "Wallet", fake_wallet)
    monkeypatch.setattr(bt, "Axon", fake_axon)
    monkeypatch.setattr(miner_cli, "attach_miner_axon", fake_attach)
    monkeypatch.setattr(miner_cli, "publish_axon", fake_publish)
    monkeypatch.setattr(
        miner_cli.time,
        "sleep",
        lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    args = SimpleNamespace(
        validator_hotkey=["validator-hotkey"],
        allow_any_signed_validator=False,
        publish=True,
        quota=1,
        port=PUBLIC_PORT,
        wallet_name="cohort-wallet",
        wallet_hotkey="cohort-miner",
        task_dir=[str(Path(__file__).resolve().parents[1] / "examples/tasks/honest_example")],
        host="0.0.0.0",
        external_ip=PUBLIC_IP,
        external_port=PUBLIC_PORT,
        network="test",
        netuid=523,
    )

    assert miner_cli.serve_command(args) == 0

    assert calls["wallet"] == [("cohort-wallet", "cohort-miner")]
    assert len(calls["axon"]) == 1
    axon = calls["start"][0]
    assert calls["publish"] == [("test", 523, axon)]
    assert calls["stop"] == [axon]
    assert len(calls["attach"]) == 1
    output = capsys.readouterr().out
    assert f"endpoint=0.0.0.0:{PUBLIC_PORT}" in output
    assert "wire_miner_stopped" in output


def test_public_publish_requires_explicit_testnet_target() -> None:
    args = SimpleNamespace(publish=True, network=None, netuid=None)

    try:
        miner_cli.publish_axon(args, axon=object())
    except ValueError as exc:
        assert str(exc) == "public --publish requires explicit --network test --netuid 523"
    else:  # pragma: no cover - explicit chain targeting is a release gate.
        raise AssertionError("publication accepted an implicit chain target")


def test_public_publish_submits_exact_target_polls_readback_and_reports_success(
    monkeypatch, capsys
) -> None:
    calls: dict[str, list[Any]] = {
        "network": [],
        "serve": [],
        "metagraph": [],
        "sleep": [],
    }
    axon = SimpleNamespace(
        wallet=SimpleNamespace(
            hotkey=SimpleNamespace(ss58_address=HOTKEY_SS58),
        )
    )

    class FakeSubtensor:
        def __init__(self, *, network: str) -> None:
            calls["network"].append(network)

        def serve_axon(self, *, netuid: int, axon: Any) -> Any:
            calls["serve"].append((netuid, axon))
            return SimpleNamespace(success=True, message="accepted")

        def metagraph(self, *, netuid: int, lite: bool) -> Any:
            calls["metagraph"].append((netuid, lite))
            ip = "1.1.1.1" if len(calls["metagraph"]) == 1 else PUBLIC_IP
            return SimpleNamespace(
                hotkeys=[HOTKEY_SS58],
                axons=[SimpleNamespace(ip=ip, port=PUBLIC_PORT)],
            )

    monkeypatch.setattr(bt, "Subtensor", FakeSubtensor)
    monkeypatch.setattr(
        miner_cli.time,
        "sleep",
        lambda seconds: calls["sleep"].append(seconds),
    )
    args = SimpleNamespace(
        publish=True,
        network="test",
        netuid=523,
        host="0.0.0.0",
        port=PUBLIC_PORT,
        external_ip=PUBLIC_IP,
        external_port=PUBLIC_PORT,
    )

    miner_cli.publish_axon(args, axon=axon)

    assert calls == {
        "network": ["test"],
        "serve": [(523, axon)],
        "metagraph": [(523, True), (523, True)],
        "sleep": [2],
    }
    assert capsys.readouterr().out == (
        f"axon_publish=ok netuid=523 external={PUBLIC_IP}:{PUBLIC_PORT} "
        "readback=exact message=accepted\n"
    )


def test_public_publish_fails_after_exact_readback_never_appears(
    monkeypatch, capsys
) -> None:
    calls: dict[str, list[Any]] = {"metagraph": [], "sleep": []}
    axon = SimpleNamespace(
        wallet=SimpleNamespace(
            hotkey=SimpleNamespace(ss58_address=HOTKEY_SS58),
        )
    )

    class FakeSubtensor:
        def __init__(self, *, network: str) -> None:
            assert network == "test"

        def serve_axon(self, *, netuid: int, axon: Any) -> Any:
            assert netuid == 523
            assert axon is not None
            return SimpleNamespace(success=True, message="accepted")

        def metagraph(self, *, netuid: int, lite: bool) -> Any:
            calls["metagraph"].append((netuid, lite))
            return SimpleNamespace(
                hotkeys=[HOTKEY_SS58],
                axons=[SimpleNamespace(ip="1.1.1.1", port=PUBLIC_PORT)],
            )

    monkeypatch.setattr(bt, "Subtensor", FakeSubtensor)
    monkeypatch.setattr(
        miner_cli.time,
        "sleep",
        lambda seconds: calls["sleep"].append(seconds),
    )
    args = SimpleNamespace(
        publish=True,
        network="test",
        netuid=523,
        host="0.0.0.0",
        port=PUBLIC_PORT,
        external_ip=PUBLIC_IP,
        external_port=PUBLIC_PORT,
    )

    with pytest.raises(RuntimeError, match="did not read back exact"):
        miner_cli.publish_axon(args, axon=axon)

    assert calls == {
        "metagraph": [(523, True)] * 6,
        "sleep": [2] * 5,
    }
    assert capsys.readouterr().out == ""
