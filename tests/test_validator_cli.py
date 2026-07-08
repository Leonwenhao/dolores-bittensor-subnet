from __future__ import annotations

from dolores_subnet.config import DEFAULT_QUOTA
from neurons.validator import build_parser


def test_validator_quota_default_uses_configured_default() -> None:
    args = build_parser().parse_args([])

    assert args.quota == DEFAULT_QUOTA
    assert args.chain == "off"
    assert args.netuid is None
    assert args.allow_extrinsics is False
    assert args.allow_commit_reveal is False
    assert args.confirm_live == ""


def test_validator_accepts_dry_run_chain_args() -> None:
    args = build_parser().parse_args(["--mode", "testnet", "--netuid", "7", "--chain", "dry-run"])

    assert args.netuid == 7
    assert args.chain == "dry-run"
    assert args.allow_extrinsics is False


def test_validator_accepts_commit_reveal_opt_in_flag() -> None:
    args = build_parser().parse_args(["--allow-commit-reveal"])

    assert args.allow_commit_reveal is True
