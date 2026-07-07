from __future__ import annotations

import copy

from dolores_subnet.config import SCHEMA_VERSION, SubnetConfig
from dolores_subnet.gates import GateContext, run_pre_gates
from dolores_subnet.packaging import to_wire


def _task():
    from dolores.proposer.families import propose_family

    return propose_family("parser_roundtrip", count=1, seed=0)[0]


def test_pre_gates_pass_in_plan_order() -> None:
    cfg = SubnetConfig.from_env(mode="mock")
    payload = to_wire(_task())
    decision = run_pre_gates(payload, cfg, GateContext(), miner_hotkey="miner-a")

    assert decision.passed
    assert list(decision.gates) == [
        "schema_version",
        "size",
        "parse",
        "hash_match",
        "quota",
        "epoch_duplicate",
    ]
    assert all(decision.gates.values())


def test_schema_size_parse_hash_quota_and_duplicate_failures() -> None:
    cfg = SubnetConfig.from_env(mode="mock")
    payload = to_wire(_task())

    bad_schema = dict(payload, schema_version="wrong")
    assert (
        run_pre_gates(bad_schema, cfg, GateContext(), miner_hotkey="miner").failure.reason
        == "invalid:schema_version"
    )

    oversize = copy.deepcopy(payload)
    oversize["package"]["prompt"] = "x" * (cfg.max_package_bytes + 1)
    assert (
        run_pre_gates(oversize, cfg, GateContext(), miner_hotkey="miner").failure.reason
        == "invalid:size"
    )

    bad_parse = copy.deepcopy(payload)
    bad_parse["package"]["reference_files"] = {}
    assert (
        run_pre_gates(bad_parse, cfg, GateContext(), miner_hotkey="miner").failure.reason
        == "invalid:parse"
    )

    bad_hash = dict(payload, package_hash="0" * 64)
    assert (
        run_pre_gates(bad_hash, cfg, GateContext(), miner_hotkey="miner").failure.reason
        == "invalid:hash_match"
    )

    quota_context = GateContext(quota=0)
    assert (
        run_pre_gates(payload, cfg, quota_context, miner_hotkey="miner").failure.reason
        == "invalid:quota"
    )

    duplicate_context = GateContext()
    assert run_pre_gates(payload, cfg, duplicate_context, miner_hotkey="miner").passed
    assert (
        run_pre_gates(payload, cfg, duplicate_context, miner_hotkey="miner2").failure.reason
        == "invalid:epoch_duplicate"
    )


def test_schema_version_constant_matches_wire_payload() -> None:
    assert to_wire(_task())["schema_version"] == SCHEMA_VERSION
