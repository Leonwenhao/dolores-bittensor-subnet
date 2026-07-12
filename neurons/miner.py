"""Compatibility wrapper for the installed ``dolores-miner`` command."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.miner_cli import (  # noqa: E402,F401
    FileMiner,
    OfflineMiner,
    attach_miner_axon,
    build_parser,
    load_tasks,
    main,
    publish_axon,
    registration_argv,
    validator_blacklist,
)

# Historical tests and local scripts import this private name.
_publish_axon = publish_axon


if __name__ == "__main__":
    raise SystemExit(main())
