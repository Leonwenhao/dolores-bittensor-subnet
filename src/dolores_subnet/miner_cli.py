"""Installed miner CLI for the controlled HackerQuest cohort."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Tuple  # noqa: UP035 - Bittensor 10.5 signature uses typing.Tuple.

from dolores_subnet.config import MAX_RESPONSE_BYTES
from dolores_subnet.endpoints import (
    COHORT_NETUID,
    COHORT_NETWORK,
    metagraph_has_exact_axon,
    require_cohort_target,
    require_port,
    require_public_ipv4,
)
from dolores_subnet.holdout import validate_holdout_support
from dolores_subnet.packaging import to_wire

REGISTER_CONFIRMATION = "REGISTER-TESTNET-523"
DOCTOR_TIMEOUT_MAX_SECONDS = 30.0
DOCTOR_SMOKE_SEED = 0
EXPECTED_DISTRIBUTIONS = {
    "dolores-autocurricula": "0.2.0rc1",
    "dolores-bittensor-subnet": "0.2.0rc1",
    "bittensor": "10.5.0",
    "bittensor-cli": "9.23.1",
}
MAX_REQUEST_BODY_BYTES = 64 * 1024
MAX_REQUEST_AGE_NS = 30_000_000_000
MAX_REQUEST_FUTURE_SKEW_NS = 5_000_000_000
MAX_REQUEST_TIMEOUT_SECONDS = 30.0
HTTP_RATE_BURST = 20
HTTP_RATE_PER_SECOND = 1.0
AUTH_RATE_BURST = 6
AUTH_RATE_PER_SECOND = 0.2


@dataclass
class _TokenBucket:
    tokens: float
    updated_at: float


class TokenBucketLimiter:
    """Small in-process limiter for source-IP and authenticated-hotkey admission."""

    def __init__(self, *, burst: int, rate_per_second: float) -> None:
        if burst < 1 or rate_per_second <= 0:
            raise ValueError("rate limiter bounds must be positive")
        self.burst = int(burst)
        self.rate_per_second = float(rate_per_second)
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _TokenBucket(tokens=float(self.burst), updated_at=current)
            elapsed = max(0.0, current - bucket.updated_at)
            tokens = min(
                float(self.burst),
                bucket.tokens + elapsed * self.rate_per_second,
            )
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
            self._buckets[key] = _TokenBucket(tokens=tokens, updated_at=current)
            return allowed


class RequestAdmissionMiddleware:
    """Bound and rate-limit HTTP input before the SDK reads or decodes its body."""

    def __init__(
        self,
        app: Any,
        *,
        max_bytes: int = MAX_REQUEST_BODY_BYTES,
        burst: int = HTTP_RATE_BURST,
        rate_per_second: float = HTTP_RATE_PER_SECOND,
    ) -> None:
        self.app = app
        self.max_bytes = int(max_bytes)
        self.limiter = TokenBucketLimiter(burst=burst, rate_per_second=rate_per_second)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        client = scope.get("client") or ("unknown", 0)
        source_ip = str(client[0])
        if not self.limiter.allow(source_ip):
            await _send_admission_error(send, status=429, detail="request rate exceeded")
            return
        headers = {bytes(key).lower(): bytes(value) for key, value in scope.get("headers", [])}
        declared_value = headers.get(b"content-length")
        if declared_value is not None:
            try:
                declared = int(declared_value)
            except ValueError:
                await _send_admission_error(send, status=400, detail="invalid content length")
                return
            if declared > self.max_bytes:
                await _send_admission_error(send, status=413, detail="request body too large")
                return

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message.get("type") == "http.disconnect":
                return
            if message.get("type") != "http.request":
                continue
            chunk = bytes(message.get("body", b""))
            if len(body) + len(chunk) > self.max_bytes:
                await _send_admission_error(send, status=413, detail="request body too large")
                return
            body.extend(chunk)
            more_body = bool(message.get("more_body", False))

        delivered = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)


async def _send_admission_error(send: Any, *, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}, separators=(",", ":")).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


@dataclass(frozen=True)
class DoctorChainSnapshot:
    """The two public-chain reads needed by miner doctor."""

    balance_rao: int
    metagraph: Any


@dataclass
class FileMiner:
    """Serve participant-authored task packages from one or more directories."""

    hotkey: str
    uid: int
    task_dirs: list[Path]

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del epoch_id
        return [to_wire(task) for task in load_tasks(self.task_dirs)[:quota]]


@dataclass
class OfflineMiner:
    """Deterministic local-only personas retained for regression rehearsals."""

    hotkey: str
    uid: int
    persona: str
    seed: int = 0

    def submissions(self, *, epoch_id: int, quota: int) -> list[dict[str, Any]]:
        del epoch_id
        if self.persona == "honest":
            tasks = _generated_tasks(quota, self.seed)
        elif self.persona == "duplicate_spammer":
            base = _generated_tasks(1, self.seed + 10_000)[0]
            tasks = [
                base.model_copy(update={"task_id": f"duplicate_spam_{self.seed}_{index}"})
                for index in range(quota)
            ]
        elif self.persona == "invalid":
            tasks = _invalid_tasks(max(1, quota), self.seed)
        elif self.persona == "lazy":
            tasks = _generated_tasks(1, self.seed) if quota > 0 else []
        else:
            raise ValueError(f"unknown offline miner persona: {self.persona}")
        return [to_wire(task) for task in tasks]


def _generated_tasks(count: int, seed: int) -> list[Any]:
    from dolores.proposer.families import propose_family

    tasks = propose_family("parser_roundtrip", count=count, seed=seed)
    return [
        task.model_copy(update={"task_id": f"honest_{seed}_{index}_{task.task_id}"})
        for index, task in enumerate(tasks)
    ]


def _invalid_tasks(count: int, seed: int) -> list[Any]:
    from dolores.schemas.task import TaskPackage

    fixture = Path(__file__).resolve().parents[2] / "tests/fixtures/planted/bad_reference_fails"
    base = TaskPackage.load(fixture)
    return [
        base.model_copy(update={"task_id": f"invalid_reference_{seed}_{index}"})
        for index in range(count)
    ]


def load_tasks(task_dirs: list[Path]) -> list[Any]:
    from dolores.schemas.task import TaskPackage

    tasks: list[Any] = []
    for root in task_dirs:
        source = root.expanduser().resolve()
        try:
            tasks.append(TaskPackage.load(source))
            continue
        except Exception:  # noqa: BLE001 - a parent directory is also supported.
            pass
        if not source.is_dir():
            raise ValueError(f"task path does not exist or is not a package: {source}")
        loaded = []
        for child in sorted(path for path in source.iterdir() if path.is_dir()):
            try:
                loaded.append(TaskPackage.load(child))
            except Exception:  # noqa: BLE001 - ignore unrelated child directories.
                continue
        if not loaded:
            raise ValueError(f"no task packages found under: {source}")
        tasks.extend(loaded)
    if not tasks:
        raise ValueError("at least one task package is required")
    return tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dolores-miner",
        description="Prepare and operate a Dolores controlled-cohort miner.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser(
        "doctor", help="run the read-only controlled-cohort miner audit"
    )
    _wallet_args(doctor)
    doctor.add_argument(
        "--wallet.path",
        dest="wallet_path",
        type=Path,
        default=Path("~/.bittensor/wallets"),
    )
    doctor.add_argument("--coldkey-ss58", required=True)
    doctor.add_argument("--hotkey-ss58", required=True)
    doctor.add_argument("--network", required=True)
    doctor.add_argument("--netuid", type=int, required=True)
    doctor.add_argument("--task-dir", action="append", default=[])
    doctor.add_argument("--external-ip", required=True)
    doctor.add_argument("--port", type=int, required=True)
    doctor.add_argument("--timeout", type=float, default=5.0)
    doctor.set_defaults(handler=doctor_command)

    init = subparsers.add_parser("init", help="create a supported parser task template")
    init.add_argument("--output", type=Path, default=Path("dolores-tasks"))
    init.add_argument(
        "--archetype",
        choices=["escape_delim", "error_contract", "quoted_fields"],
        default="escape_delim",
    )
    init.add_argument("--seed", type=int, default=0)
    init.set_defaults(handler=init_command)

    validate = subparsers.add_parser(
        "validate", help="validate schema, stable hash, wire size, and cohort family policy"
    )
    validate.add_argument("--task-dir", action="append", required=True)
    validate.set_defaults(handler=validate_command)

    register = subparsers.add_parser(
        "register", help="show or explicitly execute the fixed testnet registration command"
    )
    _wallet_args(register)
    register.add_argument("--network", required=True)
    register.add_argument("--netuid", type=int, required=True)
    register.add_argument("--execute", action="store_true")
    register.add_argument("--confirm", default="")
    register.set_defaults(handler=register_command)

    serve = subparsers.add_parser("serve", help="serve signed task responses from an Axon")
    _wallet_args(serve)
    serve.add_argument("--task-dir", action="append", required=True)
    serve.add_argument("--quota", type=int, default=4)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8091)
    serve.add_argument("--external-ip")
    serve.add_argument("--external-port", type=int)
    serve.add_argument("--validator-hotkey", action="append", default=[])
    serve.add_argument("--allow-any-signed-validator", action="store_true")
    serve.add_argument("--publish", action="store_true")
    serve.add_argument("--network")
    serve.add_argument("--netuid", type=int)
    serve.set_defaults(handler=serve_command)

    health = subparsers.add_parser("health", help="check the local Axon TCP listener")
    health.add_argument("--host", default="127.0.0.1")
    health.add_argument("--port", type=int, default=8091)
    health.add_argument("--timeout", type=float, default=2.0)
    health.set_defaults(handler=health_command)
    return parser


def _wallet_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--wallet.name", dest="wallet_name", required=True)
    parser.add_argument("--wallet.hotkey", dest="wallet_hotkey", required=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


def doctor_command(args: argparse.Namespace) -> int:
    checks: dict[str, dict[str, Any]] = {}
    checks["python"] = _python_check(sys.version_info)
    for distribution, expected in EXPECTED_DISTRIBUTIONS.items():
        checks[distribution] = _distribution_check(distribution, expected)
    checks["btcli"] = _btcli_check()

    target_ok = True
    try:
        require_cohort_target(args.network, args.netuid)
        checks["target"] = {
            "ok": True,
            "network": COHORT_NETWORK,
            "netuid": COHORT_NETUID,
        }
    except ValueError as exc:
        del exc
        target_ok = False
        checks["target"] = {"ok": False, "reason": "wrong_public_cohort_target"}

    endpoint_ok = True
    try:
        external_ip = require_public_ipv4(args.external_ip)
        port = require_port(args.port)
        timeout = _require_doctor_timeout(args.timeout)
        checks["endpoint"] = {"ok": True, "literal_global_ipv4": True, "port_valid": True}
    except ValueError:
        endpoint_ok = False
        external_ip = ""
        port = 0
        timeout = 5.0
        checks["endpoint"] = {"ok": False, "reason": "invalid_public_endpoint"}

    coldkey_valid = _public_ss58_is_valid(args.coldkey_ss58)
    hotkey_valid = _public_ss58_is_valid(args.hotkey_ss58)
    checks["public_addresses"] = {
        "ok": coldkey_valid and hotkey_valid,
        "coldkey_valid": coldkey_valid,
        "hotkey_valid": hotkey_valid,
    }
    checks["wallet_metadata"] = _wallet_metadata_check(
        root=args.wallet_path,
        wallet_name=args.wallet_name,
        wallet_hotkey=args.wallet_hotkey,
    )

    try:
        checks["engine_smoke"] = _engine_smoke_check()
    except Exception:  # noqa: BLE001 - doctor emits stable, path-free failure codes.
        checks["engine_smoke"] = {"ok": False, "reason": "engine_smoke_failed"}

    if args.task_dir:
        try:
            checks["tasks"] = _supplied_tasks_check([Path(item) for item in args.task_dir])
        except Exception:  # noqa: BLE001 - never emit participant filesystem paths.
            checks["tasks"] = {"ok": False, "reason": "task_validation_failed"}

    if endpoint_ok:
        local_state = _local_port_state(port, timeout)
        checks["local_port"] = {
            "ok": local_state in {"free", "listening"},
            "state": local_state,
        }
        public_reachable = _tcp_reachable(external_ip, port, timeout)
        checks["public_tcp"] = {"ok": public_reachable, "reachable": public_reachable}
    else:
        checks["local_port"] = {"ok": False, "reason": "invalid_public_endpoint"}
        checks["public_tcp"] = {"ok": False, "reason": "invalid_public_endpoint"}

    chain_prerequisites = target_ok and endpoint_ok and coldkey_valid and hotkey_valid
    if chain_prerequisites:
        try:
            snapshot = _read_doctor_chain(
                network=args.network,
                netuid=args.netuid,
                coldkey_ss58=args.coldkey_ss58,
                timeout=timeout,
            )
            _add_chain_checks(
                checks,
                snapshot=snapshot,
                coldkey_ss58=args.coldkey_ss58,
                hotkey_ss58=args.hotkey_ss58,
                external_ip=external_ip,
                port=port,
            )
        except Exception:  # noqa: BLE001 - RPC details can contain endpoints or paths.
            _add_failed_chain_checks(checks, "chain_read_failed")
    else:
        _add_failed_chain_checks(checks, "prerequisite_failed")

    checks["miner_boundary"] = {
        "ok": True,
        "docker_required": False,
        "duckdb_required": False,
        "fireworks_required": False,
        "streamlit_required": False,
    }
    ok = all(bool(item.get("ok")) for item in checks.values())
    print(json.dumps({"ok": ok, "checks": checks}, indent=2, sort_keys=True))
    return 0 if ok else 1


def _python_check(version_info: Any) -> dict[str, Any]:
    version = tuple(int(item) for item in version_info[:3])
    return {
        "ok": (3, 11) <= version < (3, 12),
        "version": ".".join(str(item) for item in version),
        "required": ">=3.11,<3.12",
    }


def _distribution_check(distribution: str, expected: str) -> dict[str, Any]:
    try:
        installed = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return {"ok": False, "expected": expected, "reason": "not_installed"}
    except Exception:  # noqa: BLE001 - metadata errors must stay path-free.
        return {"ok": False, "expected": expected, "reason": "metadata_unavailable"}
    return {"ok": installed == expected, "version": installed, "expected": expected}


def _btcli_check() -> dict[str, Any]:
    executable = shutil.which("btcli")
    if executable is None:
        return {"ok": False, "executable": False, "version_verified": False}
    try:
        completed = subprocess.run(
            [executable, "--version"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "executable": True, "version_verified": False}
    output = f"{completed.stdout}\n{completed.stderr}"
    verified = completed.returncode == 0 and EXPECTED_DISTRIBUTIONS["bittensor-cli"] in output
    return {"ok": verified, "executable": True, "version_verified": verified}


def _require_doctor_timeout(value: float) -> float:
    timeout = float(value)
    if not 0 < timeout <= DOCTOR_TIMEOUT_MAX_SECONDS:
        raise ValueError("doctor timeout is outside the supported bound")
    return timeout


def _public_ss58_is_valid(address: str) -> bool:
    try:
        import bittensor as bt

        return str(bt.Keypair(ss58_address=address).ss58_address) == address
    except Exception:  # noqa: BLE001 - invalid public input is a normal failed check.
        return False


def _safe_wallet_component(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and Path(value).name == value


def _metadata_kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return "missing"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    return "unsupported"


def _wallet_metadata_check(
    *, root: Path, wallet_name: str, wallet_hotkey: str
) -> dict[str, Any]:
    if not _safe_wallet_component(wallet_name) or not _safe_wallet_component(wallet_hotkey):
        return {"ok": False, "reason": "invalid_wallet_selector"}
    wallet_dir = root.expanduser() / wallet_name
    directory_ok = _metadata_kind(wallet_dir) == "directory"
    coldkey_ok = _metadata_kind(wallet_dir / "coldkeypub.txt") == "file"
    hotkeys_ok = _metadata_kind(wallet_dir / "hotkeys") == "directory"
    hotkey_ok = _metadata_kind(wallet_dir / "hotkeys" / wallet_hotkey) == "file"
    return {
        "ok": directory_ok and coldkey_ok and hotkeys_ok and hotkey_ok,
        "wallet_directory": directory_ok,
        "coldkey_public_file": coldkey_ok,
        "hotkeys_directory": hotkeys_ok,
        "hotkey_file": hotkey_ok,
        "inspection": "metadata_only",
    }


def _wire_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _check_task(task: Any) -> tuple[str, str, int]:
    family, archetype, _, _ = validate_holdout_support(task)
    payload = to_wire(task)
    if payload.get("package_hash") != task.stable_hash():
        raise RuntimeError("stable hash and wire hash differ")
    size = _wire_size(payload)
    if size > MAX_RESPONSE_BYTES:
        raise RuntimeError("wire payload exceeds the response bound")
    return family, archetype, size


def _engine_smoke_check() -> dict[str, Any]:
    task = _generated_tasks(1, DOCTOR_SMOKE_SEED)[0]
    family, archetype, size = _check_task(task)
    return {
        "ok": True,
        "generated": 1,
        "family": family,
        "archetype": archetype,
        "stable_hash_matches_wire": True,
        "wire_bytes": size,
    }


def _supplied_tasks_check(task_dirs: list[Path]) -> dict[str, Any]:
    tasks = load_tasks(task_dirs)
    sizes = [_check_task(task)[2] for task in tasks]
    return {
        "ok": True,
        "count": len(tasks),
        "stable_hash_matches_wire": True,
        "max_wire_bytes": max(sizes),
    }


def _bounded_call(fn: Any, *args: Any, timeout: float, **kwargs: Any) -> Any:
    """Run a read-only SDK call with a process-exitable POSIX deadline."""

    duration = float(timeout)
    if (
        os.name != "posix"
        or not hasattr(signal, "SIGALRM")
        or not hasattr(signal, "setitimer")
        or not hasattr(signal, "ITIMER_REAL")
    ):
        raise TimeoutError("read-only chain deadline requires POSIX SIGALRM")
    if threading.current_thread() is not threading.main_thread():
        raise TimeoutError("read-only chain deadline requires the POSIX main thread")
    if not math.isfinite(duration) or duration <= 0:
        raise TimeoutError("read-only chain call timed out")

    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer[0] > 0 or previous_timer[1] > 0:
        raise TimeoutError("read-only chain deadline unavailable with active SIGALRM timer")
    previous_handler = signal.getsignal(signal.SIGALRM)

    class DeadlineExpired(BaseException):
        pass

    def expire(signum: int, frame: Any) -> None:
        del signum, frame
        raise DeadlineExpired

    try:
        signal.signal(signal.SIGALRM, expire)
        signal.setitimer(signal.ITIMER_REAL, duration)
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        raise TimeoutError("read-only chain deadline could not be installed") from exc
    try:
        return fn(*args, **kwargs)
    except DeadlineExpired as exc:
        raise TimeoutError("read-only chain call timed out") from exc
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def _balance_rao(value: Any) -> int:
    if hasattr(value, "rao"):
        return int(value.rao)
    return int(value)


def _read_doctor_chain(
    *, network: str, netuid: int, coldkey_ss58: str, timeout: float
) -> DoctorChainSnapshot:
    """Read public balance and metagraph state without constructing a wallet."""

    import bittensor as bt

    subtensor = _bounded_call(bt.Subtensor, network=network, timeout=timeout)
    balance = _bounded_call(subtensor.get_balance, coldkey_ss58, timeout=timeout)
    metagraph = _bounded_call(subtensor.metagraph, netuid=netuid, lite=True, timeout=timeout)
    balance_rao = _balance_rao(balance)
    if balance_rao < 0:
        raise RuntimeError("negative public balance")
    return DoctorChainSnapshot(balance_rao=balance_rao, metagraph=metagraph)


def _local_port_state(port: int, timeout: float) -> str:
    if _tcp_reachable("127.0.0.1", port, timeout):
        return "listening"
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(timeout)
    try:
        probe.bind(("0.0.0.0", port))
    except OSError:
        return "unavailable"
    finally:
        probe.close()
    return "free"


def _tcp_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _uid_for_hotkey(metagraph: Any, hotkey: str) -> tuple[int | None, int | None]:
    hotkeys = [str(item) for item in getattr(metagraph, "hotkeys", [])]
    if hotkey not in hotkeys:
        return None, None
    index = hotkeys.index(hotkey)
    uids = list(getattr(metagraph, "uids", []))
    uid = int(uids[index]) if index < len(uids) else index
    return uid, index


def _add_chain_checks(
    checks: dict[str, dict[str, Any]],
    *,
    snapshot: DoctorChainSnapshot,
    coldkey_ss58: str,
    hotkey_ss58: str,
    external_ip: str,
    port: int,
) -> None:
    checks["balance"] = {
        "ok": snapshot.balance_rao >= 0,
        "readable": True,
        "balance_rao": snapshot.balance_rao,
        "positive": snapshot.balance_rao > 0,
    }
    uid, index = _uid_for_hotkey(snapshot.metagraph, hotkey_ss58)
    registered = uid is not None
    checks["registration"] = {"ok": registered, "registered": registered, "uid": uid}

    axons = list(getattr(snapshot.metagraph, "axons", []))
    axon = axons[index] if index is not None and index < len(axons) else None
    owner_matches = bool(axon) and str(getattr(axon, "coldkey", "") or "") == coldkey_ss58
    endpoint_matches = metagraph_has_exact_axon(
        snapshot.metagraph,
        hotkey=hotkey_ss58,
        host=external_ip,
        port=port,
    )
    exact = registered and owner_matches and endpoint_matches
    checks["published_axon"] = {
        "ok": exact,
        "exact": exact,
        "owner_matches": owner_matches,
        "endpoint_matches": endpoint_matches,
    }


def _add_failed_chain_checks(checks: dict[str, dict[str, Any]], reason: str) -> None:
    checks["balance"] = {"ok": False, "reason": reason}
    checks["registration"] = {"ok": False, "reason": reason, "registered": False, "uid": None}
    checks["published_axon"] = {"ok": False, "reason": reason, "exact": False}


def init_command(args: argparse.Namespace) -> int:
    from dolores.proposer.families import propose_family
    from dolores.proposer.templates import write_task_package

    task = None
    for offset in range(1000):
        candidate = propose_family(
            "parser_roundtrip",
            count=1,
            seed=args.seed + offset,
        )[0]
        if f"archetype:{args.archetype}" in candidate.descriptors.concepts:
            task = candidate
            break
    if task is None:
        raise RuntimeError(f"could not generate archetype: {args.archetype}")
    validate_holdout_support(task)
    destination = args.output.expanduser().resolve() / task.task_id
    if destination.exists():
        raise ValueError(f"refusing to overwrite existing task: {destination}")
    written = write_task_package(task, args.output.expanduser().resolve())
    print(f"task_dir={written}")
    print(f"task_id={task.task_id}")
    print(f"package_hash={task.stable_hash()}")
    print("tests=author_tests validator_holdout=private")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    tasks = load_tasks([Path(item) for item in args.task_dir])
    for task in tasks:
        family, archetype, _, _ = validate_holdout_support(task)
        payload = to_wire(task)
        print(
            f"VALID task_id={task.task_id} package_hash={payload['package_hash']} "
            f"family={family} archetype={archetype} "
            f"author_tests={len(task.public_tests) + len(task.hidden_tests)}"
        )
    return 0


def registration_argv(*, wallet_name: str, wallet_hotkey: str) -> list[str]:
    return [
        "btcli",
        "subnet",
        "register",
        "--network",
        COHORT_NETWORK,
        "--netuid",
        str(COHORT_NETUID),
        "--wallet-name",
        wallet_name,
        "--hotkey",
        wallet_hotkey,
    ]


def register_command(args: argparse.Namespace) -> int:
    require_cohort_target(args.network, args.netuid)
    command = registration_argv(
        wallet_name=args.wallet_name,
        wallet_hotkey=args.wallet_hotkey,
    )
    print("command=" + " ".join(command))
    if not args.execute:
        print("registration=not_executed")
        return 0
    if args.confirm != REGISTER_CONFIRMATION:
        raise ValueError(f"--execute requires --confirm {REGISTER_CONFIRMATION}")
    executable = shutil.which("btcli")
    if executable is None:
        raise RuntimeError("btcli is not installed")
    command[0] = executable
    return subprocess.run(command, check=False).returncode


def serve_command(args: argparse.Namespace) -> int:
    import bittensor as bt

    from dolores_subnet.wire import (
        DoloresTaskSynapse,
        response_payload_size,
        sign_response,
    )

    if not args.validator_hotkey and not args.allow_any_signed_validator:
        raise ValueError(
            "serve requires --validator-hotkey; --allow-any-signed-validator is local-only"
        )
    if args.publish and args.allow_any_signed_validator:
        raise ValueError("public --publish forbids --allow-any-signed-validator")
    quota = int(args.quota)
    if not 1 <= quota <= 4:
        raise ValueError("quota must be within 1..4")
    require_port(args.port)
    wallet = bt.Wallet(name=args.wallet_name, hotkey=args.wallet_hotkey)
    miner = FileMiner(
        hotkey=wallet.hotkey.ss58_address,
        uid=0,
        task_dirs=[Path(item) for item in args.task_dir],
    )
    # Validate all tasks before opening a socket or touching chain metadata.
    for task in load_tasks(miner.task_dirs):
        validate_holdout_support(task)
        to_wire(task)

    def forward(synapse: DoloresTaskSynapse) -> DoloresTaskSynapse:
        response_quota = min(quota, synapse.quota)
        submissions = miner.submissions(epoch_id=synapse.epoch_id, quota=response_quota)
        while submissions and response_payload_size(submissions) > MAX_RESPONSE_BYTES:
            submissions.pop()
        synapse.submissions = submissions
        synapse.error = ""
        return sign_response(synapse, wallet.hotkey)

    blacklist = validator_blacklist(
        allowed_hotkeys=frozenset(args.validator_hotkey),
        allow_any_signed=args.allow_any_signed_validator,
    )
    forward.__annotations__ = {
        "synapse": DoloresTaskSynapse,
        "return": DoloresTaskSynapse,
    }
    blacklist.__annotations__ = {
        "synapse": DoloresTaskSynapse,
        "return": Tuple[bool, str],  # noqa: UP006 - exact SDK signature contract.
    }
    axon = bt.Axon(
        wallet=wallet,
        port=args.port,
        ip=args.host,
        external_ip=args.external_ip or args.host,
        external_port=args.external_port or args.port,
    )
    attach_miner_axon(axon, forward=forward, blacklist=blacklist).start()
    try:
        publish_axon(args, axon=axon)
    except Exception:
        axon.stop()
        raise
    print(
        "wire_miner_started "
        f"tasks={len(load_tasks(miner.task_dirs))} "
        f"wallet={args.wallet_name}/{args.wallet_hotkey} "
        f"hotkey={wallet.hotkey.ss58_address} endpoint={args.host}:{args.port}",
        flush=True,
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        axon.stop()
        print("wire_miner_stopped", flush=True)
        return 0


def health_command(args: argparse.Namespace) -> int:
    port = require_port(args.port)
    try:
        with socket.create_connection((args.host, port), timeout=args.timeout):
            pass
    except OSError as exc:
        print(f"healthy=false endpoint={args.host}:{port} reason={exc}")
        return 1
    print(f"healthy=true endpoint={args.host}:{port}")
    return 0


def validator_blacklist(*, allowed_hotkeys: frozenset[str], allow_any_signed: bool):
    """Build the controlled-cohort caller authorization policy."""

    def blacklist(synapse: Any) -> tuple[bool, str]:
        terminal = getattr(synapse, "dendrite", None)
        hotkey = str(getattr(terminal, "hotkey", "") or "")
        if not hotkey:
            return True, "missing validator hotkey"
        if allow_any_signed or hotkey in allowed_hotkeys:
            return False, ""
        return True, "validator hotkey is not allowlisted"

    return blacklist


def build_request_verifier(axon: Any):
    """Layer fixed freshness, version, replay, and rate policy over SDK verification."""

    from bittensor.core.axon import V_7_2_0

    from dolores_subnet.wire import DoloresTaskSynapse

    limiter = TokenBucketLimiter(
        burst=AUTH_RATE_BURST,
        rate_per_second=AUTH_RATE_PER_SECOND,
    )
    accepted: dict[tuple[str, str, int], float] = {}
    accepted_lock = threading.Lock()

    async def verify(synapse: DoloresTaskSynapse) -> None:
        terminal = synapse.dendrite
        if terminal is None:
            raise ValueError("missing request terminal")
        hotkey = str(terminal.hotkey or "")
        request_uuid = str(terminal.uuid or "")
        try:
            nonce = int(terminal.nonce)
            version = int(terminal.version)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid authenticated request metadata") from exc
        if not hotkey or not request_uuid or len(request_uuid) > 128:
            raise ValueError("invalid authenticated request identity")
        if version < V_7_2_0:
            raise ValueError("unsupported authenticated request version")
        timeout = float(synapse.timeout)
        if not 0 < timeout <= MAX_REQUEST_TIMEOUT_SECONDS:
            raise ValueError("request timeout exceeds cohort policy")
        now_ns = time.time_ns()
        age_ns = now_ns - nonce
        if age_ns > MAX_REQUEST_AGE_NS:
            raise ValueError("request nonce is stale")
        if age_ns < -MAX_REQUEST_FUTURE_SKEW_NS:
            raise ValueError("request nonce is too far in the future")

        # Retain all SDK signature/body-hash checks and its nonce cache, then
        # apply cohort policy that cannot be disabled by unsigned body fields.
        await axon.default_verify(synapse)
        if not limiter.allow(hotkey):
            raise ValueError("authenticated request rate exceeded")
        identity = (hotkey, request_uuid, nonce)
        now = time.monotonic()
        with accepted_lock:
            cutoff = now - (MAX_REQUEST_AGE_NS / 1_000_000_000)
            stale = [key for key, accepted_at in accepted.items() if accepted_at < cutoff]
            for key in stale:
                accepted.pop(key, None)
            if identity in accepted:
                raise ValueError("authenticated request replayed")
            accepted[identity] = now

    verify.__annotations__ = {
        "synapse": DoloresTaskSynapse,
        "return": None,
    }
    return verify


def install_request_admission(axon: Any) -> None:
    """Install the pre-parser HTTP cap once on a concrete Bittensor Axon."""

    app = getattr(axon, "app", None)
    if app is None or getattr(axon, "_dolores_request_admission", False):
        return
    app.add_middleware(
        RequestAdmissionMiddleware,
        max_bytes=MAX_REQUEST_BODY_BYTES,
        burst=HTTP_RATE_BURST,
        rate_per_second=HTTP_RATE_PER_SECOND,
    )
    axon._dolores_request_admission = True


def attach_miner_axon(axon: Any, *, forward: Any, blacklist: Any) -> Any:
    """Attach bounded handlers plus SDK and cohort request verification."""

    install_request_admission(axon)
    verifier = build_request_verifier(axon)
    return axon.attach(
        forward_fn=forward,
        blacklist_fn=blacklist,
        verify_fn=verifier,
    )


def publish_axon(args: argparse.Namespace, *, axon: Any) -> None:
    """Publish and read back one exact public-testnet endpoint, or fail closed."""

    if not args.publish:
        print("axon_publish=skipped reason=no_publish_flag", flush=True)
        return
    from dolores_subnet.config import assert_safe_network

    if args.network is None or args.netuid is None:
        raise ValueError("public --publish requires explicit --network test --netuid 523")
    network = assert_safe_network(args.network)
    require_cohort_target(network, args.netuid)
    if args.host != "0.0.0.0":
        raise ValueError("public --publish requires --host 0.0.0.0")
    if not args.external_ip:
        raise ValueError("public --publish requires an explicit --external-ip")
    external_ip = require_public_ipv4(args.external_ip)
    external_port = require_port(args.external_port or args.port)

    import bittensor as bt

    subtensor = bt.Subtensor(network=network)
    response = subtensor.serve_axon(netuid=args.netuid, axon=axon)
    success = bool(getattr(response, "success", response))
    message = str(getattr(response, "message", "") or "")
    if not success:
        raise RuntimeError(f"testnet axon publication failed: {message or 'unknown error'}")
    readback_ok = False
    for attempt in range(6):
        metagraph = subtensor.metagraph(netuid=args.netuid, lite=True)
        readback_ok = metagraph_has_exact_axon(
            metagraph,
            hotkey=axon.wallet.hotkey.ss58_address,
            host=external_ip,
            port=external_port,
        )
        if readback_ok:
            break
        if attempt < 5:
            time.sleep(2)
    if not readback_ok:
        raise RuntimeError(
            "testnet axon publication did not read back exact "
            f"{external_ip}:{external_port} for the miner hotkey"
        )
    print(
        f"axon_publish=ok netuid={args.netuid} external={external_ip}:{external_port} "
        f"readback=exact message={message}",
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
