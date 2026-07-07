from __future__ import annotations

from dolores_subnet.config import DEFAULT_QUOTA
from neurons.validator import build_parser


def test_validator_quota_default_uses_configured_default() -> None:
    args = build_parser().parse_args([])

    assert args.quota == DEFAULT_QUOTA
