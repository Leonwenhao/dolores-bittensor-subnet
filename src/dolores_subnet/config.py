"""Configuration and safety policy for the Dolores subnet."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGED_MOCK_PANEL_PATH = PACKAGE_ROOT / "_assets" / "configs" / "solver_panel.mock.yaml"
PACKAGED_CALIBRATE_PANEL_PATH = (
    PACKAGE_ROOT / "_assets" / "configs" / "solver_panel.calibrate.yaml"
)

SPEC_VERSION = 1
SCHEMA_VERSION = "dolores-subnet-v1"

MAX_PACKAGE_BYTES = 200 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_QUOTA = 4
DEFAULT_TOP_K = DEFAULT_QUOTA
EMA_ALPHA = 0.3
UNSEEN_PRUNE_EPOCHS = 20
WEIGHTS_RATE_LIMIT_BLOCKS = 100
TEMPO_BLOCKS = 360

DEFAULT_VERIFIER_IMAGE = "dolores-verifier-pytest:0.2.0rc1"
DEFAULT_WALLET_NAME = "dolores-test"
DEFAULT_WALLET_HOTKEY = "validator"
DEFAULT_AXON_PORTS = (8091, 8092)
TESTNET_CONFIG_PATH = REPO_ROOT / "configs" / "testnet.json"

SAFE_CHAIN_NETWORKS = frozenset(
    {
        "test",
        "ws://127.0.0.1:9944",
        "ws://127.0.0.1:9945",
    }
)
UNSAFE_CHAIN_NETWORKS = frozenset({"finney", "mainnet", "ws://entrypoint-finney.opentensor.ai:443"})
LOCALNET_NETWORK = "ws://127.0.0.1:9944"
LOCALNET_ALT_NETWORK = "ws://127.0.0.1:9945"
TESTNET_NETWORK = "test"


class ConfigError(ValueError):
    """Raised when subnet configuration is unsafe or invalid."""


class NetworkSafetyError(ConfigError):
    """Raised when a chain network could resolve to mainnet or an unknown endpoint."""


class Mode(StrEnum):
    """Execution modes supported by the staged testnet plan."""

    MOCK = "mock"
    OFFLINE = "offline"
    WIRE = "wire"
    LOCALNET = "localnet"
    TESTNET = "testnet"

    @property
    def requires_bittensor(self) -> bool:
        return self in {Mode.WIRE, Mode.LOCALNET, Mode.TESTNET}

    @property
    def requires_docker(self) -> bool:
        return self is not Mode.MOCK

    @property
    def requires_wallet(self) -> bool:
        return self in {Mode.WIRE, Mode.LOCALNET, Mode.TESTNET}

    @property
    def requires_chain(self) -> bool:
        return self in {Mode.LOCALNET, Mode.TESTNET}


def parse_mode(value: str | Mode | None) -> Mode:
    if isinstance(value, Mode):
        return value
    text = (value or "").strip().lower()
    if not text:
        return Mode.MOCK
    try:
        return Mode(text)
    except ValueError as exc:
        choices = ", ".join(mode.value for mode in Mode)
        raise ConfigError(f"unknown mode {value!r}; expected one of: {choices}") from exc


def assert_safe_network(network: str | None) -> str:
    """Return a normalized safe network or raise before any Bittensor call."""

    raw = "" if network is None else str(network).strip()
    lowered = raw.lower()
    if not raw:
        raise NetworkSafetyError("refusing to use an unset Bittensor network")
    if lowered in UNSAFE_CHAIN_NETWORKS or lowered in {"finney", "mainnet"}:
        raise NetworkSafetyError(f"refusing unsafe Bittensor network: {raw}")
    if "mainnet" in lowered:
        raise NetworkSafetyError(f"refusing unsafe Bittensor endpoint: {raw}")
    if lowered.endswith("finney.opentensor.ai:443") and "test.finney" not in lowered:
        raise NetworkSafetyError(f"refusing unsafe Bittensor endpoint: {raw}")
    if raw not in SAFE_CHAIN_NETWORKS:
        allowed = ", ".join(sorted(SAFE_CHAIN_NETWORKS))
        raise NetworkSafetyError(f"network {raw!r} is not allowlisted; allowed: {allowed}")
    return raw


def resolve_network(mode: str | Mode, requested: str | None = None) -> str | None:
    """Resolve the explicit chain network for a mode.

    Non-chain modes return ``None`` unless a caller supplies an explicit network,
    in which case the same allowlist is enforced.
    """

    parsed = parse_mode(mode)
    if requested is not None:
        return assert_safe_network(requested)
    if parsed is Mode.TESTNET:
        return assert_safe_network(TESTNET_NETWORK)
    if parsed is Mode.LOCALNET:
        return assert_safe_network(LOCALNET_NETWORK)
    return None


def verifier_defaults(mode: Mode) -> tuple[str, str]:
    if mode is Mode.MOCK:
        return "local", "fixture"
    return "docker", "generated"


def resolve_netuid(
    mode: str | Mode,
    requested: int | str | None = None,
    *,
    env_value: str | None = None,
    config_path: Path = TESTNET_CONFIG_PATH,
) -> int | None:
    """Resolve netuid from CLI/env/config without inventing a default."""

    parsed = parse_mode(mode)
    if requested is not None:
        return _parse_netuid(requested, source="argument")
    if env_value:
        return _parse_netuid(env_value, source="BT_NETUID")
    if parsed is not Mode.TESTNET or not config_path.exists():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {config_path}: {exc}") from exc
    value = data.get("netuid")
    if value is None:
        return None
    return _parse_netuid(value, source=str(config_path))


def _parse_netuid(value: int | str, *, source: str) -> int:
    try:
        netuid = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{source} netuid must be an integer: {value!r}") from exc
    if netuid < 0:
        raise ConfigError(f"{source} netuid must be non-negative: {netuid}")
    return netuid


@dataclass(frozen=True)
class SubnetConfig:
    """Local runtime configuration shared by scripts, neurons, and tests."""

    mode: Mode = Mode.MOCK
    repo_root: Path = REPO_ROOT
    work_dir: Path = REPO_ROOT / "work"
    archive_dir: Path = REPO_ROOT / "work" / "subnet_archive"
    archive_db: Path = REPO_ROOT / "work" / "subnet_archive" / "archive.duckdb"
    submissions_path: Path = REPO_ROOT / "work" / "subnet_archive" / "submissions.jsonl"
    panel_path: Path = PACKAGED_MOCK_PANEL_PATH
    verifier_image: str = DEFAULT_VERIFIER_IMAGE
    backend: str = "local"
    pipeline_mode: str = "fixture"
    network: str | None = None
    netuid: int | None = None
    max_package_bytes: int = MAX_PACKAGE_BYTES
    max_response_bytes: int = MAX_RESPONSE_BYTES
    quota: int = DEFAULT_QUOTA
    top_k: int = DEFAULT_TOP_K
    ema_alpha: float = EMA_ALPHA
    spec_version: int = SPEC_VERSION
    schema_version: str = SCHEMA_VERSION
    wallet_name: str = DEFAULT_WALLET_NAME
    wallet_hotkey: str = DEFAULT_WALLET_HOTKEY
    allow_commit_reveal: bool = False
    panel_mode: str = "mock"
    panel_calibrate_path: Path = PACKAGED_CALIBRATE_PANEL_PATH
    panel_max_tasks: int = 8
    panel_dry_run: bool = False
    allow_provider_spend: bool = False
    holdout_required: bool = False
    holdout_secret: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(
        cls,
        *,
        mode: str | Mode | None = None,
        work_dir: str | Path | None = None,
        wallet_name: str | None = None,
        wallet_hotkey: str | None = None,
        network: str | None = None,
        netuid: int | str | None = None,
        allow_commit_reveal: bool | None = None,
        panel_mode: str | None = None,
        panel_max_tasks: int | str | None = None,
        panel_dry_run: bool | None = None,
        allow_provider_spend: bool | None = None,
        holdout_required: bool | None = None,
        holdout_secret: str | None = None,
    ) -> SubnetConfig:
        parsed_mode = parse_mode(mode or os.environ.get("DOLORES_SUBNET_MODE"))
        backend, pipeline_mode = verifier_defaults(parsed_mode)
        root = REPO_ROOT
        resolved_work = Path(
            work_dir or os.environ.get("DOLORES_SUBNET_WORK_DIR", root / "work")
        ).expanduser()
        if not resolved_work.is_absolute():
            resolved_work = root / resolved_work
        archive_dir = resolved_work / "subnet_archive"
        resolved_network = resolve_network(parsed_mode, network or os.environ.get("BT_NETWORK"))
        resolved_netuid = resolve_netuid(
            parsed_mode,
            requested=netuid,
            env_value=os.environ.get("BT_NETUID"),
        )
        resolved_panel_mode = str(
            panel_mode or os.environ.get("DOLORES_SUBNET_PANEL_MODE", "mock")
        ).strip().lower()
        if resolved_panel_mode not in {"mock", "calibrate"}:
            raise ConfigError(
                f"panel_mode must be 'mock' or 'calibrate': {resolved_panel_mode!r}"
            )
        raw_max_tasks = (
            panel_max_tasks
            if panel_max_tasks is not None
            else os.environ.get("DOLORES_SUBNET_PANEL_MAX_TASKS", 8)
        )
        try:
            resolved_panel_max_tasks = int(raw_max_tasks)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"panel_max_tasks must be an integer: {raw_max_tasks!r}") from exc
        if resolved_panel_max_tasks < 0:
            raise ConfigError(f"panel_max_tasks must be non-negative: {resolved_panel_max_tasks}")
        resolved_panel_dry_run = (
            bool(panel_dry_run)
            if panel_dry_run is not None
            else os.environ.get("DOLORES_SUBNET_PANEL_DRYRUN", "") == "1"
        )
        return cls(
            mode=parsed_mode,
            repo_root=root,
            work_dir=resolved_work,
            archive_dir=archive_dir,
            archive_db=archive_dir / "archive.duckdb",
            submissions_path=archive_dir / "submissions.jsonl",
            panel_path=Path(
                os.environ.get("DOLORES_SUBNET_PANEL", str(PACKAGED_MOCK_PANEL_PATH))
            ).expanduser(),
            verifier_image=os.environ.get("DOLORES_VERIFIER_IMAGE", DEFAULT_VERIFIER_IMAGE),
            backend=backend,
            pipeline_mode=pipeline_mode,
            network=resolved_network,
            netuid=resolved_netuid,
            wallet_name=wallet_name
            or os.environ.get("BT_WALLET_NAME", DEFAULT_WALLET_NAME),
            wallet_hotkey=wallet_hotkey
            or os.environ.get("BT_WALLET_HOTKEY", DEFAULT_WALLET_HOTKEY),
            allow_commit_reveal=bool(allow_commit_reveal),
            panel_mode=resolved_panel_mode,
            panel_calibrate_path=Path(
                os.environ.get(
                    "DOLORES_SUBNET_PANEL_CALIBRATE",
                    str(PACKAGED_CALIBRATE_PANEL_PATH),
                )
            ).expanduser(),
            panel_max_tasks=resolved_panel_max_tasks,
            panel_dry_run=resolved_panel_dry_run,
            allow_provider_spend=bool(allow_provider_spend),
            holdout_required=(
                parsed_mode in {Mode.WIRE, Mode.LOCALNET, Mode.TESTNET}
                if holdout_required is None
                else bool(holdout_required)
            ),
            holdout_secret=(
                holdout_secret
                if holdout_secret is not None
                else os.environ.get("DOLORES_HOLDOUT_SECRET")
            ),
        )

    def epoch_dir(self, epoch_id: int) -> Path:
        return self.archive_dir / "epochs" / f"epoch_{epoch_id}"

    def weights_path(self, epoch_id: int) -> Path:
        return self.epoch_dir(epoch_id) / f"weights_epoch_{epoch_id}.json"

    def solver_panel_path(self, epoch_id: int) -> Path:
        return self.epoch_dir(epoch_id) / f"solver_panel_epoch_{epoch_id}.json"

    @property
    def panel_cache_path(self) -> Path:
        return self.archive_dir / "panel_cache.jsonl"
