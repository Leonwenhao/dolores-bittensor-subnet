"""Shared protocol records for miner submissions and validator scores."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialize payload deterministically for hash commitments."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class TaskSubmission:
    """A miner-submitted task package reference."""

    miner_uid: str
    task_id: str
    package_uri: str
    package_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_commit_payload(self) -> dict[str, Any]:
        return {
            "miner_uid": self.miner_uid,
            "task_id": self.task_id,
            "package_uri": self.package_uri,
            "package_hash": self.package_hash,
            "metadata": self.metadata,
        }

    def commitment(self) -> str:
        return sha256_text(canonical_json(self.to_commit_payload()))


@dataclass(frozen=True)
class ValidationScore:
    """Validator result for one submission."""

    task_id: str
    miner_uid: str
    valid: bool
    score: float
    gates: dict[str, bool]
    components: dict[str, float]
    reason: str = ""

    def to_weight_signal(self) -> float:
        if not self.valid:
            return 0.0
        return max(0.0, min(1.0, self.score))

