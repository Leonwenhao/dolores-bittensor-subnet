"""Thin bridge to the existing Dolores Autocurricula repo.

The subnet should not re-implement task generation or verification. For the
testnet MVP, this module imports Dolores from a local checkout when available.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dolores_subnet.config import SubnetConfig


def add_dolores_to_path(config: SubnetConfig | None = None) -> Path:
    config = config or SubnetConfig.from_env()
    src_path = config.dolores_repo / "src"
    if not src_path.exists():
        raise FileNotFoundError(f"Dolores src path not found: {src_path}")
    src_text = str(src_path)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)
    return src_path


def propose_v3_family(
    family: str = "parser_roundtrip",
    count: int = 1,
    seed: int = 0,
    band: str | None = None,
    config: SubnetConfig | None = None,
) -> list[Any]:
    """Generate Dolores v3 task packages from the local Dolores checkout."""

    add_dolores_to_path(config)
    try:
        from dolores.proposer.families import propose_family
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown"
        raise RuntimeError(
            "Dolores backend dependency is missing: "
            f"{missing}. Run this command with the Dolores .venv, for example: "
            'PYTHONPATH=src "/Users/leonliu/Desktop/Dolores Autocurricula/.venv/bin/python" '
            "scripts/local_loop.py --family parser_roundtrip --count 1"
        ) from exc

    return propose_family(family=family, count=count, seed=seed, band=band)
