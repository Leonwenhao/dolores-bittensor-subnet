"""Configuration and safety policy for the Dolores subnet."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOLORES_REPO = Path("/Users/leonliu/Desktop/Dolores Autocurricula")

SPEC_VERSION = 1
SCHEMA_VERSION = "dolores-subnet-v0"

MAX_PACKAGE_BYTES = 200 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_QUOTA = 4
DEFAULT_TOP_K = DEFAULT_QUOTA
EMA_ALPHA = 0.3
UNSEEN_PRUNE_EPOCHS = 20
WEIGHTS_RATE_LIMIT_BLOCKS = 100
TEMPO_BLOCKS = 360

DEFAULT_VERIFIER_IMAGE = "dolores-verifier-pytest:0.1.0"
DEFAULT_WALLET_NAME = "dolores-test"
DEFAULT_WALLET_HOTKEY = "validator"
DEFAULT_AXON_PORTS = (8091, 8092)

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


@dataclass(frozen=True)
class SubnetConfig:
    """Local runtime configuration shared by scripts, neurons, and tests."""

    mode: Mode = Mode.MOCK
    repo_root: Path = REPO_ROOT
    dolores_repo: Path = DEFAULT_DOLORES_REPO
    work_dir: Path = REPO_ROOT / "work"
    archive_dir: Path = REPO_ROOT / "work" / "subnet_archive"
    archive_db: Path = REPO_ROOT / "work" / "subnet_archive" / "archive.duckdb"
    submissions_path: Path = REPO_ROOT / "work" / "subnet_archive" / "submissions.jsonl"
    panel_path: Path = REPO_ROOT / "configs" / "solver_panel.mock.yaml"
    verifier_image: str = DEFAULT_VERIFIER_IMAGE
    backend: str = "local"
    pipeline_mode: str = "fixture"
    network: str | None = None
    max_package_bytes: int = MAX_PACKAGE_BYTES
    max_response_bytes: int = MAX_RESPONSE_BYTES
    quota: int = DEFAULT_QUOTA
    top_k: int = DEFAULT_TOP_K
    ema_alpha: float = EMA_ALPHA
    spec_version: int = SPEC_VERSION
    schema_version: str = SCHEMA_VERSION
    wallet_name: str = DEFAULT_WALLET_NAME
    wallet_hotkey: str = DEFAULT_WALLET_HOTKEY

    @classmethod
    def from_env(
        cls,
        *,
        mode: str | Mode | None = None,
        work_dir: str | Path | None = None,
        wallet_name: str | None = None,
        wallet_hotkey: str | None = None,
        network: str | None = None,
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
        return cls(
            mode=parsed_mode,
            repo_root=root,
            dolores_repo=Path(
                os.environ.get("DOLORES_REPO", str(DEFAULT_DOLORES_REPO))
            ).expanduser(),
            work_dir=resolved_work,
            archive_dir=archive_dir,
            archive_db=archive_dir / "archive.duckdb",
            submissions_path=archive_dir / "submissions.jsonl",
            panel_path=Path(
                os.environ.get("DOLORES_SUBNET_PANEL", str(root / "configs/solver_panel.mock.yaml"))
            ).expanduser(),
            verifier_image=os.environ.get("DOLORES_VERIFIER_IMAGE", DEFAULT_VERIFIER_IMAGE),
            backend=backend,
            pipeline_mode=pipeline_mode,
            network=resolved_network,
            wallet_name=wallet_name
            or os.environ.get("BT_WALLET_NAME", DEFAULT_WALLET_NAME),
            wallet_hotkey=wallet_hotkey
            or os.environ.get("BT_WALLET_HOTKEY", DEFAULT_WALLET_HOTKEY),
        )

    def epoch_dir(self, epoch_id: int) -> Path:
        return self.archive_dir / "epochs" / f"epoch_{epoch_id}"

    def weights_path(self, epoch_id: int) -> Path:
        return self.epoch_dir(epoch_id) / f"weights_epoch_{epoch_id}.json"
