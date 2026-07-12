#!/usr/bin/env python3
"""Build stable planted good/bad M2 fixtures."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.packaging import materialize, to_wire  # noqa: E402

CASES = {
    "good_parser",
    "bad_no_reference",
    "bad_reference_fails",
    "bad_unsafe",
    "bad_duplicate",
    "bad_hash_lie",
    "bad_oversize",
}


def build_fixtures(out: Path) -> None:
    from dolores.proposer.families import propose_family
    from dolores.schemas.task import TaskPackage
    from dolores.verifier.safety import scan_task

    out.mkdir(parents=True, exist_ok=True)
    wire_dir = out / "wire"
    wire_dir.mkdir(parents=True, exist_ok=True)

    base = propose_family("parser_roundtrip", count=1, seed=0)[0]
    good, duplicate = _good_duplicate_pair(base)
    _write_case(out, wire_dir, "good_parser", good, to_wire(good))

    no_reference = good.model_dump(mode="json")
    no_reference["task_id"] = "bad_no_reference"
    no_reference["reference_files"] = {}
    _write_raw_case(out, wire_dir, "bad_no_reference", no_reference, package_hash="invalid")

    reference_fails = _with_task_id(good, "bad_reference_fails_seed")
    first_ref = next(iter(reference_fails.reference_files))
    broken_refs = dict(reference_fails.reference_files)
    broken_refs[first_ref] = (
        "def intentionally_wrong_reference(*args, **kwargs):\n    return None\n"
    )
    reference_fails = reference_fails.model_copy(update={"reference_files": broken_refs})
    reference_fails = _after_hash(reference_fails, "bad_reference_fails", good.stable_hash())
    _write_case(out, wire_dir, "bad_reference_fails", reference_fails, to_wire(reference_fails))

    unsafe = _with_task_id(good, "bad_unsafe_seed")
    unsafe_refs = dict(unsafe.reference_files)
    first_ref = next(iter(unsafe_refs))
    unsafe_refs[first_ref] = "import subprocess\n" + unsafe_refs[first_ref]
    unsafe = unsafe.model_copy(update={"reference_files": unsafe_refs})
    unsafe = _after_hash(unsafe, "bad_unsafe", good.stable_hash())
    assert scan_task(unsafe), "bad_unsafe must trip the Dolores safety scanner"
    _write_case(out, wire_dir, "bad_unsafe", unsafe, to_wire(unsafe))

    _write_case(out, wire_dir, "bad_duplicate", duplicate, to_wire(duplicate))

    hash_lie = _with_task_id(good, "bad_hash_lie")
    hash_payload = to_wire(hash_lie)
    hash_payload["package_hash"] = "0" * 64
    _write_case(out, wire_dir, "bad_hash_lie", hash_lie, hash_payload)

    oversize = copy.deepcopy(good.model_dump(mode="json"))
    oversize["task_id"] = "bad_oversize"
    oversize["prompt"] = "x" * (220 * 1024)
    _write_raw_case(out, wire_dir, "bad_oversize", oversize, package_hash="oversize")

    for case in CASES:
        assert (out / case / "task.yaml").exists(), case
        assert (wire_dir / f"{case}.json").exists(), case

    # Ensure raw invalid packages still explain what they are intended to be.
    TaskPackage.model_validate(good.model_dump(mode="json"))


def _with_task_id(task, task_id: str):
    return task.model_copy(update={"task_id": task_id})


def _good_duplicate_pair(task):
    for good_index in range(500):
        good = _with_task_id(task, f"good_parser_{good_index:03d}")
        for duplicate_index in range(500):
            duplicate = _with_task_id(task, f"bad_duplicate_{duplicate_index:03d}")
            if good.stable_hash() < duplicate.stable_hash():
                return good, duplicate
    raise RuntimeError("could not find good/duplicate task_id pair with stable hash order")


def _after_hash(task, base: str, lower_hash: str):
    for index in range(500):
        candidate = _with_task_id(task, f"{base}_{index:03d}")
        if lower_hash < candidate.stable_hash():
            return candidate
    raise RuntimeError(f"could not find {base} task_id above lower hash")


def _write_case(out: Path, wire_dir: Path, case: str, task, payload: dict) -> None:
    materialize(task, out)
    source = out / task.task_id
    destination = out / case
    if source != destination:
        if destination.exists():
            _remove_tree(destination)
        source.rename(destination)
    _write_json(wire_dir / f"{case}.json", payload)


def _write_raw_case(
    out: Path,
    wire_dir: Path,
    case: str,
    package: dict,
    *,
    package_hash: str,
) -> None:
    case_dir = out / case
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "task.yaml").write_text(yaml.safe_dump(package, sort_keys=False), encoding="utf-8")
    wire_package = dict(package)
    wire_package["author_tests"] = wire_package.pop("hidden_tests", {})
    payload = {
        "schema_version": "dolores-subnet-v1",
        "task_id": package["task_id"],
        "package_hash": package_hash,
        "package": wire_package,
        "family": "parser_roundtrip",
        "declared_difficulty": "medium",
    }
    _write_json(wire_dir / f"{case}.json", payload)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _remove_tree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.rmdir()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed planted adversarial fixtures.")
    parser.add_argument("--out", type=Path, default=Path("tests/fixtures/planted"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    build_fixtures(args.out)
    print(f"wrote planted fixtures to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
