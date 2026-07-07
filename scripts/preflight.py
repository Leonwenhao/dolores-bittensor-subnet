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
    DEFAULT_VERIFIER_IMAGE,
    Mode,
    NetworkSafetyError,
    SubnetConfig,
    assert_safe_network,
    parse_mode,
)

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
        return result("FAIL", f"{detail}; expected Python 3.11")
    return result("PASS", detail)


def import_dolores_check() -> tuple[str, str]:
    try:
        dolores = importlib.import_module("dolores")
    except Exception as exc:  # noqa: BLE001
        return result("FAIL", f"{exc}; install with: .venv/bin/pip install \"$DOLORES\"")
    version = getattr(dolores, "__version__", "unknown")
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
    if not str(version).startswith("10."):
        return result("FAIL", f"bittensor {version}; expected 10.x")
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
        return result("FAIL", f"Docker daemon unavailable: {detail}; STOP-LEON H1")
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
        build = (
            "cd \"$DOLORES\" && docker build -f docker/verifier/Dockerfile "
            f"-t {DEFAULT_VERIFIER_IMAGE} ."
        )
        return result("FAIL", f"image {image} missing; build with: {build}")
    image_id = completed.stdout.strip()
    return result("PASS", f"{image} {image_id[:19]}")


def dolores_install_freshness_check(cfg: SubnetConfig) -> tuple[str, str]:
    try:
        dolores = importlib.import_module("dolores")
        installed_at = Path(dolores.__file__ or "").stat().st_mtime
    except Exception as exc:  # noqa: BLE001
        return result("FAIL", f"cannot inspect installed dolores: {exc}")

    completed = run_command(["git", "-C", str(cfg.dolores_repo), "log", "-1", "--format=%ct"])
    if completed.returncode != 0:
        return result("PASS", "Dolores install present; source git timestamp unavailable")
    source_at = float(completed.stdout.strip())
    if installed_at + 1 < source_at:
        reinstall = (
            ".venv/bin/pip install --no-deps --force-reinstall "
            f"{json.dumps(str(cfg.dolores_repo))}"
        )
        return result("PASS", f"WARNING installed package may be stale; run: {reinstall}")
    return result("PASS", "installed package is not older than source HEAD")


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
        "NOTE first axon bind may trigger macOS firewall prompt (STOP-LEON H1)",
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
            "wallet files missing; STOP-LEON H2 create testnet-only wallet/hotkeys. "
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

        subtensor = bt.subtensor(network=cfg.network)
        block = subtensor.block
    except Exception as exc:  # noqa: BLE001
        return result("FAIL", f"{cfg.network}: {exc}")
    return result("PASS", f"{cfg.network} block={block}")


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
    checks.append(Check("dolores install freshness", lambda: dolores_install_freshness_check(cfg)))
    if cfg.mode in {Mode.WIRE, Mode.LOCALNET, Mode.TESTNET}:
        checks.append(Check("axon ports", ports_check))
        checks.append(Check("wallet existence", lambda: wallet_exists_check(cfg)))
    else:
        checks.append(Check("axon ports", lambda: result("SKIP", f"{cfg.mode.value} mode")))
        checks.append(Check("wallet existence", lambda: result("SKIP", f"{cfg.mode.value} mode")))
    checks.append(Check("network allowlist", lambda: network_allowlist_check(cfg)))
    if cfg.mode.requires_chain:
        checks.append(Check("chain reachability", lambda: chain_reachability_check(cfg)))
    else:
        checks.append(Check("chain reachability", lambda: result("SKIP", f"{cfg.mode.value} mode")))
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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    wallet_name = args.wallet_name or args.wallet_name_alias
    wallet_hotkey = args.wallet_hotkey or args.wallet_hotkey_alias
    cfg = SubnetConfig.from_env(
        mode=parse_mode(args.mode),
        work_dir=args.work,
        wallet_name=wallet_name,
        wallet_hotkey=wallet_hotkey,
        network=args.network,
    )
    return run_preflight(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
