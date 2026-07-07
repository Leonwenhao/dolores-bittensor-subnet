"""Lossless conversion between Dolores task packages and subnet wire payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from dolores_subnet.config import MAX_PACKAGE_BYTES, SCHEMA_VERSION
from dolores_subnet.protocol import WireSubmission, canonical_json


@dataclass(frozen=True)
class WireError(ValueError):
    """Machine-readable wire-format failure."""

    reason: str
    detail: str

    def __str__(self) -> str:
        return f"{self.reason}: {self.detail}"


def canonical_size(payload: dict[str, Any]) -> int:
    return len(canonical_json(payload).encode("utf-8"))


def wire_size_ok(payload: dict[str, Any], *, max_bytes: int = MAX_PACKAGE_BYTES) -> bool:
    return canonical_size(payload) <= max_bytes


def to_wire(task: Any, *, max_bytes: int = MAX_PACKAGE_BYTES) -> dict[str, Any]:
    """Convert a Dolores TaskPackage into the v0 wire-submission dict."""

    family = _family(task)
    declared_difficulty = getattr(task.descriptors, "estimated_difficulty", "")
    submission = WireSubmission(
        schema_version=SCHEMA_VERSION,
        task_id=task.task_id,
        package_hash=task.stable_hash(),
        package=task.canonical_dict(),
        family=family,
        declared_difficulty=str(declared_difficulty),
    ).to_dict()
    if not wire_size_ok(submission, max_bytes=max_bytes):
        raise WireError("size", f"wire payload is {canonical_size(submission)} bytes")
    return submission


def from_wire(payload: dict[str, Any], *, max_bytes: int = MAX_PACKAGE_BYTES) -> Any:
    """Parse and verify a wire submission as a Dolores TaskPackage."""

    if not isinstance(payload, dict):
        raise WireError("payload_type", "wire payload must be a dict")
    if not wire_size_ok(payload, max_bytes=max_bytes):
        raise WireError("size", f"wire payload is {canonical_size(payload)} bytes")

    _require(payload, "schema_version")
    _require(payload, "task_id")
    _require(payload, "package_hash")
    _require(payload, "package")

    if payload["schema_version"] != SCHEMA_VERSION:
        raise WireError("schema_version", f"expected {SCHEMA_VERSION}")
    if not isinstance(payload["package"], dict):
        raise WireError("package_type", "package must be a dict")

    try:
        from dolores.schemas.task import TaskPackage

        task = TaskPackage.model_validate(payload["package"])
    except ValidationError as exc:
        raise WireError(_validation_reason(exc), _validation_detail(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise WireError("parse", str(exc)) from exc

    if task.task_id != payload["task_id"]:
        raise WireError(
            "task_id",
            f"payload task_id {payload['task_id']!r} != package {task.task_id!r}",
        )
    stable_hash = task.stable_hash()
    if stable_hash != payload["package_hash"]:
        raise WireError(
            "hash_match",
            f"claimed {payload['package_hash']} != recomputed {stable_hash}",
        )
    return task


def materialize(task: Any, root: Path) -> Path:
    """Write `<root>/<task_id>/task.yaml` using the Dolores writer."""

    from dolores.proposer.templates import write_task_package

    return write_task_package(task, root)


def loads_wire_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise WireError("payload_type", f"{path} must contain a JSON object")
    return payload


def _require(payload: dict[str, Any], key: str) -> None:
    if key not in payload:
        raise WireError(f"missing_{key}", f"wire payload missing {key!r}")


def _family(task: Any) -> str:
    descriptors = task.descriptors
    for concept in getattr(descriptors, "concepts", []):
        if isinstance(concept, str) and concept.startswith("family:"):
            return concept.split(":", 1)[1]
    return str(getattr(descriptors, "task_type", ""))


def _validation_detail(exc: ValidationError) -> str:
    first = exc.errors()[0]
    loc = ".".join(str(part) for part in first.get("loc", ())) or "package"
    message = first.get("msg", "validation failed")
    return f"{loc}: {message}"


def _validation_reason(exc: ValidationError) -> str:
    first = exc.errors()[0]
    loc = tuple(str(part) for part in first.get("loc", ()))
    message = str(first.get("msg", "")).lower()
    if loc and loc[0] in {"starter_files", "reference_files", "public_tests", "hidden_tests"}:
        return "parse_path"
    if "reference file" in message or "public or hidden tests" in message:
        return "parse_execution_material"
    return "parse"
