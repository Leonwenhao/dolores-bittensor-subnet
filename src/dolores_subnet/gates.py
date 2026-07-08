"""Deterministic subnet pre-gates for wire submissions."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from dolores_subnet.config import DEFAULT_QUOTA, SCHEMA_VERSION, SubnetConfig
from dolores_subnet.packaging import canonical_size, wire_size_ok


@dataclass(frozen=True)
class GateFailure:
    gate: str
    reason: str
    detail: str


@dataclass
class GateContext:
    quota: int = DEFAULT_QUOTA
    seen_hashes: set[str] = field(default_factory=set)
    miner_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    gates: OrderedDict[str, bool]
    task: Any | None = None
    task_hash: str | None = None
    failure: GateFailure | None = None


def run_pre_gates(
    payload: dict[str, Any],
    cfg: SubnetConfig,
    context: GateContext,
    *,
    miner_hotkey: str,
) -> GateDecision:
    gates: OrderedDict[str, bool] = OrderedDict(
        (
            ("schema_version", False),
            ("size", False),
            ("parse", False),
            ("hash_match", False),
            ("quota", False),
            ("epoch_duplicate", False),
        )
    )

    if payload.get("schema_version") != SCHEMA_VERSION:
        return _fail(
            gates,
            "schema_version",
            "invalid:schema_version",
            f"expected {SCHEMA_VERSION}",
        )
    gates["schema_version"] = True

    if not wire_size_ok(payload, max_bytes=cfg.max_package_bytes):
        return _fail(gates, "size", "invalid:size", f"{canonical_size(payload)} bytes")
    gates["size"] = True

    try:
        from dolores.schemas.task import TaskPackage

        package = payload.get("package")
        if not isinstance(package, dict):
            raise TypeError("package must be a dict")
        task = TaskPackage.model_validate(package)
    except ValidationError as exc:
        return _fail(gates, "parse", "invalid:parse", _validation_detail(exc))
    except Exception as exc:  # noqa: BLE001
        return _fail(gates, "parse", "invalid:parse", str(exc))
    gates["parse"] = True

    claimed_hash = payload.get("package_hash")
    task_hash = task.stable_hash()
    if claimed_hash != task_hash:
        return _fail(gates, "hash_match", "invalid:hash_match", f"{claimed_hash} != {task_hash}")
    gates["hash_match"] = True

    count = context.miner_counts.get(miner_hotkey, 0)
    if count >= context.quota:
        return _fail(gates, "quota", "invalid:quota", f"{miner_hotkey} quota {context.quota}")
    gates["quota"] = True
    # Charge quota as soon as the quota gate passes, before the dedup check, so a
    # submission that later fails epoch_duplicate still consumes the miner's budget.
    # Otherwise duplicate (or trivially mutated) packages never decrement quota,
    # giving a miner unlimited cheap resubmissions per epoch — a validator
    # amplification vector and a hash-probing oracle for the seen-set.
    context.miner_counts[miner_hotkey] = count + 1

    if task_hash in context.seen_hashes:
        return _fail(gates, "epoch_duplicate", "invalid:epoch_duplicate", task_hash)
    gates["epoch_duplicate"] = True

    context.seen_hashes.add(task_hash)
    return GateDecision(True, gates, task=task, task_hash=task_hash)


def _fail(
    gates: OrderedDict[str, bool],
    gate: str,
    reason: str,
    detail: str,
) -> GateDecision:
    return GateDecision(
        False,
        gates,
        failure=GateFailure(gate=gate, reason=reason, detail=detail),
    )


def _validation_detail(exc: ValidationError) -> str:
    first = exc.errors()[0]
    loc = ".".join(str(part) for part in first.get("loc", ())) or "package"
    message = first.get("msg", "validation failed")
    return f"{loc}: {message}"
