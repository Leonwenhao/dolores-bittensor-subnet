from __future__ import annotations

import copy
import os
import subprocess
import sys

import pytest

from dolores_subnet.config import MAX_PACKAGE_BYTES, SCHEMA_VERSION
from dolores_subnet.packaging import WireError, from_wire, materialize, to_wire, wire_size_ok
from dolores_subnet.protocol import WireSubmission


def generated_tasks(count: int = 3):
    from dolores.proposer.families import propose_family

    return propose_family("parser_roundtrip", count=count, seed=0)


def test_generated_tasks_round_trip_through_wire() -> None:
    tasks = generated_tasks()
    for task in tasks:
        wire = to_wire(task)
        recovered = from_wire(wire)
        assert recovered.stable_hash() == task.stable_hash()
        assert "author_tests" in wire["package"]
        assert "hidden_tests" not in wire["package"]


def test_materialize_writes_dolores_task_yaml(tmp_path) -> None:
    from dolores.schemas.task import TaskPackage

    task = generated_tasks(count=1)[0]
    task_dir = materialize(task, tmp_path)

    assert task_dir == tmp_path / task.task_id
    assert (task_dir / "task.yaml").exists()
    assert TaskPackage.load(task_dir).stable_hash() == task.stable_hash()


def test_tampered_wire_hash_is_rejected() -> None:
    task = generated_tasks(count=1)[0]
    payload = to_wire(task)
    tampered = copy.deepcopy(payload)
    tampered["package"]["prompt"] = tampered["package"]["prompt"] + " changed"

    with pytest.raises(WireError) as exc_info:
        from_wire(tampered)
    assert exc_info.value.reason == "hash_match"


def test_oversize_payload_is_refused() -> None:
    task = generated_tasks(count=1)[0]
    large = task.model_copy(update={"prompt": "x" * (MAX_PACKAGE_BYTES + 1)})

    with pytest.raises(WireError) as exc_info:
        to_wire(large)
    assert exc_info.value.reason == "size"

    payload = to_wire(task)
    payload["package"]["prompt"] = "x" * (MAX_PACKAGE_BYTES + 1)
    assert not wire_size_ok(payload)


def test_malformed_payloads_have_distinct_reason_codes() -> None:
    task = generated_tasks(count=1)[0]
    payload = to_wire(task)

    missing = dict(payload)
    missing.pop("package")
    with pytest.raises(WireError) as missing_exc:
        from_wire(missing)
    assert missing_exc.value.reason == "missing_package"

    absolute_path = copy.deepcopy(payload)
    absolute_path["package"]["reference_files"] = {"/tmp/solution.py": "def f(): pass\n"}
    with pytest.raises(WireError) as path_exc:
        from_wire(absolute_path)
    assert path_exc.value.reason == "parse_path"

    empty_reference = copy.deepcopy(payload)
    empty_reference["package"]["reference_files"] = {}
    with pytest.raises(WireError) as ref_exc:
        from_wire(empty_reference)
    assert ref_exc.value.reason == "parse_execution_material"

    legacy_hidden = copy.deepcopy(payload)
    legacy_hidden["package"]["hidden_tests"] = legacy_hidden["package"].pop(
        "author_tests"
    )
    with pytest.raises(WireError) as hidden_exc:
        from_wire(legacy_hidden)
    assert hidden_exc.value.reason == "parse_execution_material"

    missing_author_tests = copy.deepcopy(payload)
    missing_author_tests["package"].pop("author_tests")
    with pytest.raises(WireError) as author_exc:
        from_wire(missing_author_tests)
    assert author_exc.value.reason == "parse_execution_material"


def test_cross_process_stable_hash_is_identical() -> None:
    code = (
        "from dolores.proposer.families import propose_family; "
        "from dolores_subnet.packaging import from_wire, to_wire; "
        "task = propose_family('parser_roundtrip', count=1, seed=0)[0]; "
        "print(from_wire(to_wire(task)).stable_hash())"
    )
    env = {**os.environ, "PYTHONPATH": "src"}
    first = subprocess.check_output([sys.executable, "-c", code], env=env, text=True).strip()
    second = subprocess.check_output([sys.executable, "-c", code], env=env, text=True).strip()

    assert first == second


def test_wire_submission_dataclass_round_trips_dict() -> None:
    task = generated_tasks(count=1)[0]
    payload = to_wire(task)
    wire = WireSubmission.from_dict(payload)

    assert wire.schema_version == SCHEMA_VERSION
    assert wire.to_dict() == payload
    assert len(wire.commitment()) == 64
