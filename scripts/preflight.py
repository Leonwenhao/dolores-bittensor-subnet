#!/usr/bin/env python3
"""Mode-aware readiness checks for the Dolores subnet."""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.config import (  # noqa: E402
    DEFAULT_AXON_PORTS,
    LOCALNET_ALT_NETWORK,
    LOCALNET_NETWORK,
    Mode,
    NetworkSafetyError,
    SubnetConfig,
    assert_safe_network,
    parse_mode,
)
from dolores_subnet.endpoints import require_cohort_target  # noqa: E402

CheckFn = Callable[[], tuple[str, str]]


@dataclass(frozen=True)
class Check:
    name: str
    fn: CheckFn
    required: bool = True


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def result(status: str, detail: str) -> tuple[str, str]:
    return status, detail


def python_version_check() -> tuple[str, str]:
    version = sys.version_info
    detail = f"{version.major}.{version.minor}.{version.micro}"
    if (version.major, version.minor) != (3, 11):
        return result("FAIL", f"{detail}; expected Python 3.11.x")
    return result("PASS", detail)


def import_dolores_check() -> tuple[str, str]:
    try:
        dolores = importlib.import_module("dolores")
    except Exception as exc:  # noqa: BLE001
        return result("FAIL", f"{exc}; install dolores-autocurricula[validator]==0.2.0rc1")
    version = getattr(dolores, "__version__", "unknown")
    if version != "0.2.0rc1":
        return result("FAIL", f"dolores {version}; expected pinned 0.2.0rc1")
    return result("PASS", f"dolores {version}")


def import_bittensor_check() -> tuple[str, str]:
    try:
        bittensor = importlib.import_module("bittensor")
    except Exception as exc:  # noqa: BLE001
        return result(
            "FAIL",
            f"{exc}; install project deps with: .venv/bin/pip install -e \".[dev]\"",
        )
    version = getattr(bittensor, "__version__", "unknown")
    if str(version) != "10.5.0":
        return result("FAIL", f"bittensor {version}; expected pinned 10.5.0")
    return result("PASS", f"bittensor {version}")


def pip_check() -> tuple[str, str]:
    completed = run_command([sys.executable, "-m", "pip", "check"], timeout=120)
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        return result("FAIL", output)
    return result("PASS", output or "No broken requirements found.")


def panel_check(cfg: SubnetConfig) -> tuple[str, str]:
    if not cfg.panel_path.exists():
        return result("FAIL", f"missing {cfg.panel_path}")
    try:
        from dolores.solvers.base import load_panel

        panel_id, solvers = load_panel(cfg.panel_path)
    except Exception as exc:  # noqa: BLE001
        return result("FAIL", f"{cfg.panel_path}: {exc}")
    if not solvers:
        return result("FAIL", f"{cfg.panel_path}: no solvers configured")
    return result("PASS", f"{panel_id}; {len(solvers)} solvers")


def jq_check(required: bool) -> tuple[str, str]:
    path = shutil.which("jq")
    if path is None:
        status = "FAIL" if required else "SKIP"
        return result(status, "jq not found; install with: brew install jq")
    completed = run_command([path, "--version"])
    version = completed.stdout.strip()
    if completed.returncode != 0:
        return result("FAIL", (completed.stderr or "jq failed").strip())
    return result("PASS", version)


def docker_daemon_check() -> tuple[str, str]:
    docker = shutil.which("docker")
    if docker is None:
        return result("FAIL", "docker CLI not found; install/start Docker Desktop")
    completed = run_command([docker, "version", "--format", "{{.Server.Version}}"], timeout=30)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        return result("FAIL", f"Docker daemon unavailable: {detail}; operator action required")
    return result("PASS", f"server {completed.stdout.strip()}")


def docker_image_check(image: str) -> tuple[str, str]:
    docker = shutil.which("docker")
    if docker is None:
        return result("FAIL", "docker CLI not found")
    completed = run_command([docker, "image", "inspect", "--format", "{{.Id}}", image], timeout=30)
    if completed.returncode != 0:
        listed = run_command(
            [docker, "image", "ls", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"],
            timeout=30,
        )
        for line in listed.stdout.splitlines():
            tag, _, image_id = line.partition(" ")
            if tag == image and image_id:
                return result("PASS", f"{image} {image_id} (listed; inspect-by-tag unavailable)")
        build = "rerun the validator; the pinned engine auto-builds its packaged verifier image"
        return result("FAIL", f"image {image} missing; build with: {build}")
    image_id = completed.stdout.strip()
    return result("PASS", f"{image} {image_id[:19]}")


def dolores_release_asset_check() -> tuple[str, str]:
    try:
        from dolores.verifier.docker_runner import _dockerfile_path

        dockerfile = _dockerfile_path()
    except Exception as exc:  # noqa: BLE001
        return result("FAIL", f"cannot resolve packaged verifier asset: {exc}")
    if not dockerfile.is_file():
        return result("FAIL", f"packaged verifier Dockerfile missing: {dockerfile}")
    return result("PASS", f"packaged verifier asset={dockerfile}")


def holdout_secret_check(cfg: SubnetConfig) -> tuple[str, str]:
    if not cfg.holdout_required:
        return result("SKIP", f"{cfg.mode.value} mode does not require cohort holdout")
    if not cfg.holdout_secret:
        return result("FAIL", "DOLORES_HOLDOUT_SECRET is required (value not displayed)")
    return result("PASS", "validator holdout secret is configured (value not displayed)")


def ports_check(ports: tuple[int, ...] = DEFAULT_AXON_PORTS) -> tuple[str, str]:
    bound: list[int] = []
    sockets: list[socket.socket] = []
    try:
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sockets.append(sock)
            bound.append(port)
    except OSError as exc:
        return result("FAIL", f"port bind failed after {bound}: {exc}")
    finally:
        for sock in sockets:
            sock.close()
    return result(
        "PASS",
        f"ports {','.join(str(port) for port in ports)} bindable; "
        "NOTE first axon bind may trigger a macOS firewall prompt",
    )


def wallet_paths(wallet_name: str, wallet_hotkey: str) -> tuple[Path, Path]:
    root = Path.home() / ".bittensor" / "wallets" / wallet_name
    return root, root / "hotkeys" / wallet_hotkey


def wallet_exists_check(cfg: SubnetConfig) -> tuple[str, str]:
    wallet_dir, hotkey_path = wallet_paths(cfg.wallet_name, cfg.wallet_hotkey)
    missing = [str(path) for path in (wallet_dir, hotkey_path) if not path.exists()]
    if missing:
        return result(
            "FAIL",
            "wallet files missing; create testnet-only wallet/hotkeys before chain mode. "
            f"Missing: {', '.join(missing)}",
        )
    return result("PASS", f"wallet {cfg.wallet_name}/{cfg.wallet_hotkey} exists (not read)")


def network_allowlist_check(cfg: SubnetConfig) -> tuple[str, str]:
    if not cfg.mode.requires_chain:
        return result("SKIP", f"{cfg.mode.value} mode has no chain network")
    try:
        network = assert_safe_network(cfg.network)
    except NetworkSafetyError as exc:
        return result("FAIL", str(exc))
    return result("PASS", network)


def chain_reachability_check(cfg: SubnetConfig) -> tuple[str, str]:
    if cfg.network is None:
        return result("FAIL", "chain mode has no network")
    try:
        import bittensor as bt

        factory = getattr(bt, "Subtensor", None)
        if factory is None:
            factory = getattr(bt, "subtensor", None)
        if factory is None:
            return result("FAIL", "bittensor has no Subtensor constructor")
        subtensor = factory(network=cfg.network)
        block = subtensor.block
    except Exception as exc:  # noqa: BLE001
        return result("FAIL", f"{cfg.network}: {exc}")
    return result("PASS", f"{cfg.network} block={block}")


def chain_readiness_check(cfg: SubnetConfig, *, substrate: object | None = None) -> tuple[str, str]:
    if not cfg.mode.requires_chain:
        return result("SKIP", f"{cfg.mode.value} mode has no chain readiness")
    if cfg.netuid is None:
        return result("SKIP", "netuid unset; subnet readiness checks skipped")
    if cfg.network is None:
        return result("FAIL", "chain mode has no network")
    try:
        from dolores_subnet.chain import SubtensorChain

        chain = SubtensorChain(
            network=cfg.network,
            netuid=cfg.netuid,
            wallet_name=cfg.wallet_name,
            wallet_hotkey=cfg.wallet_hotkey,
            publish="dry-run",
            substrate=substrate,
        )
        state = chain.preflight()
    except Exception as exc:  # noqa: BLE001
        return result("FAIL", f"{cfg.network} netuid={cfg.netuid}: {exc}")
    detail = json.dumps(state, sort_keys=True, default=str)
    if state.get("mode") == "error":
        return result("FAIL", detail)
    return result("PASS", detail)


def build_checks(cfg: SubnetConfig) -> list[Check]:
    checks = [
        Check("python", python_version_check),
        Check("dolores import", import_dolores_check),
    ]
    if cfg.mode.requires_bittensor:
        checks.append(Check("bittensor import", import_bittensor_check))
    else:
        checks.append(Check("bittensor import", lambda: result("SKIP", f"{cfg.mode.value} mode")))
    checks.extend(
        [
            Check("pip check", pip_check),
            Check("solver panel", lambda: panel_check(cfg)),
            Check("jq", lambda: jq_check(required=cfg.mode is not Mode.MOCK)),
        ]
    )
    if cfg.mode.requires_docker:
        checks.extend(
            [
                Check("docker daemon", docker_daemon_check),
                Check("verifier image", lambda: docker_image_check(cfg.verifier_image)),
            ]
        )
    else:
        checks.extend(
            [
                Check("docker daemon", lambda: result("SKIP", "mock mode")),
                Check("verifier image", lambda: result("SKIP", "mock mode")),
            ]
        )
    checks.append(Check("dolores release asset", dolores_release_asset_check))
    checks.append(Check("validator holdout secret", lambda: holdout_secret_check(cfg)))
    if cfg.mode in {Mode.WIRE, Mode.LOCALNET, Mode.TESTNET}:
        checks.append(Check("axon ports", ports_check))
        checks.append(Check("wallet existence", lambda: wallet_exists_check(cfg)))
    else:
        checks.append(Check("axon ports", lambda: result("SKIP", f"{cfg.mode.value} mode")))
        checks.append(Check("wallet existence", lambda: result("SKIP", f"{cfg.mode.value} mode")))
    checks.append(Check("network allowlist", lambda: network_allowlist_check(cfg)))
    if cfg.mode.requires_chain:
        checks.append(Check("chain reachability", lambda: chain_reachability_check(cfg)))
        checks.append(Check("chain readiness", lambda: chain_readiness_check(cfg)))
    else:
        checks.append(Check("chain reachability", lambda: result("SKIP", f"{cfg.mode.value} mode")))
        checks.append(Check("chain readiness", lambda: result("SKIP", f"{cfg.mode.value} mode")))
    return checks


def print_check(status: str, name: str, detail: str) -> None:
    print(f"{status} {name}: {detail}")


def run_preflight(cfg: SubnetConfig) -> int:
    failed = False
    for check in build_checks(cfg):
        try:
            status, detail = check.fn()
        except Exception as exc:  # noqa: BLE001
            status, detail = "FAIL", str(exc)
        print_check(status, check.name, detail)
        if status == "FAIL" and check.required:
            failed = True
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Dolores subnet preflight checks.")
    parser.add_argument("--mode", choices=[mode.value for mode in Mode], default=None)
    parser.add_argument("--work", type=Path, default=None)
    parser.add_argument("--wallet.name", dest="wallet_name", default=None)
    parser.add_argument("--wallet.hotkey", dest="wallet_hotkey", default=None)
    parser.add_argument("--wallet-name", dest="wallet_name_alias", default=None)
    parser.add_argument("--wallet-hotkey", dest="wallet_hotkey_alias", default=None)
    parser.add_argument("--network", default=None)
    parser.add_argument("--netuid", type=int, default=None)
    return parser


def validate_explicit_chain_target(
    mode: Mode,
    *,
    network: str | None,
    netuid: int | None,
) -> None:
    """Reject implicit or mode-mismatched targets before config or SDK work."""

    if mode is Mode.TESTNET:
        if network is None or netuid is None:
            raise ValueError(
                "testnet preflight requires explicit --network test --netuid 523"
            )
        require_cohort_target(network, netuid)
        return
    if mode is not Mode.LOCALNET:
        return
    if network is None or netuid is None:
        raise ValueError("localnet preflight requires explicit --network and --netuid")
    allowed = {LOCALNET_NETWORK, LOCALNET_ALT_NETWORK}
    if network not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(
            f"localnet preflight requires a loopback Subtensor network ({choices}); "
            "public network test is forbidden"
        )
    if netuid < 0:
        raise ValueError("localnet preflight netuid must be non-negative")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mode = parse_mode(args.mode)
    validate_explicit_chain_target(mode, network=args.network, netuid=args.netuid)
    wallet_name = args.wallet_name or args.wallet_name_alias
    wallet_hotkey = args.wallet_hotkey or args.wallet_hotkey_alias
    cfg = SubnetConfig.from_env(
        mode=mode,
        work_dir=args.work,
        wallet_name=wallet_name,
        wallet_hotkey=wallet_hotkey,
        network=args.network,
        netuid=args.netuid,
    )
    return run_preflight(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
