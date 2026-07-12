"""Validator-owned holdout policy for the controlled miner cohort.

The active cases produced here are validator-private runtime material. Public
evidence contains only policy and digest metadata, never the case values or test
source.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from dolores.verifier.docker_runner import DockerRunner
from dolores.verifier.runner import VerifierRunner

POLICY_VERSION = "parser-core-v1"
SUPPORTED_FAMILY = "parser_roundtrip"
SUPPORTED_ARCHETYPES = frozenset({"escape_delim", "error_contract", "quoted_fields"})
PROBE_DROP_MARKER = "# PROBE-DROP"


class HoldoutPolicyError(ValueError):
    """Raised when a task is outside the deliberately narrow cohort policy."""


@dataclass(frozen=True)
class HoldoutPlan:
    """Private execution plan. Do not serialize this object into public evidence."""

    task: Any = field(repr=False)
    policy_version: str
    family: str
    archetype: str
    case_count: int
    case_digest: str
    seed_digest: str = field(repr=False)


@dataclass(frozen=True)
class HoldoutEvidence:
    passed: bool
    status: str
    reason: str
    policy_version: str
    family: str
    archetype: str
    base_package_hash: str
    case_count: int
    case_digest: str
    reference_passed: bool
    containerized: bool
    executed: bool
    logs_hash: str | None
    probes_caught: dict[str, bool]

    def to_record(self) -> dict[str, Any]:
        """Return the intentionally source-free audit representation."""

        return {
            "passed": self.passed,
            "status": self.status,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "family": self.family,
            "archetype": self.archetype,
            "base_package_hash": self.base_package_hash,
            "case_count": self.case_count,
            "case_digest": self.case_digest,
            "reference_passed": self.reference_passed,
            "containerized": self.containerized,
            "executed": self.executed,
            "logs_hash": self.logs_hash,
            "probes_caught": dict(sorted(self.probes_caught.items())),
        }


def build_holdout_plan(task: Any, *, package_hash: str, secret: str) -> HoldoutPlan:
    """Build a deterministic private holdout for one supported task."""

    if not secret:
        raise HoldoutPolicyError("validator holdout secret is required")
    if task.stable_hash() != package_hash:
        raise HoldoutPolicyError("base package hash does not match task content")

    family, archetype, concepts, module_name = validate_holdout_support(task)
    delimiter = _symbol_for("delimiter", concepts.get("delim", ""))
    special_kind = "quote" if archetype == "quoted_fields" else "escape"
    special = _symbol_for(special_kind, concepts.get("special", ""))
    seed = hmac.new(
        secret.encode("utf-8"),
        f"{POLICY_VERSION}:{package_hash}".encode(),
        hashlib.sha256,
    ).digest()
    seed_digest = hashlib.sha256(seed).hexdigest()
    cases = _private_cases(random.Random(int.from_bytes(seed, "big")), delimiter, special)
    test_source = _render_test_source(
        module_name=module_name,
        archetype=archetype,
        delimiter=delimiter,
        special=special,
        cases=cases,
    )
    case_digest = hashlib.sha256(test_source.encode("utf-8")).hexdigest()
    holdout_task = task.model_copy(
        update={
            # Miner-supplied public/hidden tests are author tests. The private
            # pass evaluates only this validator-owned test source.
            "public_tests": {},
            "hidden_tests": {f"test_validator_holdout_{case_digest[:12]}.py": test_source},
        }
    )
    return HoldoutPlan(
        task=holdout_task,
        policy_version=POLICY_VERSION,
        family=family,
        archetype=archetype,
        case_count=len(cases),
        case_digest=case_digest,
        seed_digest=seed_digest,
    )


def validate_holdout_support(task: Any) -> tuple[str, str, dict[str, str], str]:
    """Validate the public, non-secret portion of the cohort holdout policy."""

    concepts = _concept_map(task.descriptors.concepts)
    family = str(task.descriptors.task_type)
    archetype = concepts.get("archetype", "")
    band = concepts.get("target_band", "")
    if family != SUPPORTED_FAMILY:
        raise HoldoutPolicyError(f"unsupported family for cohort: {family or 'missing'}")
    if archetype not in SUPPORTED_ARCHETYPES or band != "core":
        raise HoldoutPolicyError(
            f"unsupported parser policy: archetype={archetype or 'missing'} "
            f"band={band or 'missing'}"
        )
    module_name = _reference_module(task.reference_files)
    _symbol_for("delimiter", concepts.get("delim", ""))
    special_kind = "quote" if archetype == "quoted_fields" else "escape"
    _symbol_for(special_kind, concepts.get("special", ""))
    return family, archetype, concepts, module_name


def evaluate_holdout(
    task: Any,
    *,
    package_hash: str,
    secret: str,
    runner: VerifierRunner | None = None,
    require_containerized: bool = True,
) -> HoldoutEvidence:
    """Run the reference and known-wrong probes against private holdout cases."""

    try:
        plan = build_holdout_plan(task, package_hash=package_hash, secret=secret)
    except HoldoutPolicyError as exc:
        status = "infra_error" if not secret else "unsupported"
        return HoldoutEvidence(
            passed=False,
            status=status,
            reason=str(exc),
            policy_version=POLICY_VERSION,
            family=str(getattr(task.descriptors, "task_type", "")),
            archetype=_concept_map(getattr(task.descriptors, "concepts", [])).get(
                "archetype", ""
            ),
            base_package_hash=package_hash,
            case_count=0,
            case_digest="",
            reference_passed=False,
            containerized=False,
            executed=False,
            logs_hash=None,
            probes_caught={},
        )

    active_runner = runner or DockerRunner(allow_fallback=False)
    reference = active_runner.verify(plan.task)
    reference_ok = reference.status == "passed"
    isolation_ok = (
        reference.containerized and reference.executed
        if require_containerized
        else reference.executed
    )
    probes_caught: dict[str, bool] = {}
    if reference_ok and isolation_ok:
        for probe_id, candidate in _probe_candidates(task).items():
            result = active_runner.verify(plan.task, candidate)
            probe_isolated = (
                result.containerized and result.executed
                if require_containerized
                else result.executed
            )
            probes_caught[probe_id] = result.status != "passed" and probe_isolated

    passed = reference_ok and isolation_ok and bool(probes_caught) and all(probes_caught.values())
    if not reference.executed:
        status = "infra_error"
        reason = reference.fallback_reason or "validator holdout did not execute"
    elif require_containerized and not reference.containerized:
        status = "infra_error"
        reason = "validator holdout was not containerized"
    elif not reference_ok:
        status = "failed"
        reason = "reference failed validator-owned holdout"
    elif not probes_caught:
        status = "failed"
        reason = "no validator holdout probe was available"
    elif not all(probes_caught.values()):
        status = "failed"
        reason = "validator-owned holdout missed a known-wrong probe"
    else:
        status = "passed"
        reason = ""
    return HoldoutEvidence(
        passed=passed,
        status=status,
        reason=reason,
        policy_version=plan.policy_version,
        family=plan.family,
        archetype=plan.archetype,
        base_package_hash=package_hash,
        case_count=plan.case_count,
        case_digest=plan.case_digest,
        reference_passed=reference_ok,
        containerized=bool(reference.containerized),
        executed=bool(reference.executed),
        logs_hash=reference.logs_hash,
        probes_caught=probes_caught,
    )


def _concept_map(values: list[str]) -> dict[str, str]:
    concepts: dict[str, str] = {}
    for value in values:
        if ":" not in value:
            continue
        key, item = value.split(":", 1)
        if key in concepts and concepts[key] != item:
            raise HoldoutPolicyError(f"ambiguous concept: {key}")
        concepts[key] = item
    return concepts


def _reference_module(reference_files: dict[str, str]) -> str:
    if len(reference_files) != 1:
        raise HoldoutPolicyError("supported parser task must have exactly one reference file")
    path = PurePosixPath(next(iter(reference_files)))
    if len(path.parts) != 1 or path.suffix != ".py" or not path.stem.isidentifier():
        raise HoldoutPolicyError("supported parser reference must be one root Python module")
    return path.stem


def _symbol_for(kind: str, slug: str) -> str:
    from dolores.proposer.families.parser import DELIM_BY_SLUG, ESC_BY_SLUG, QUOTE_BY_SLUG

    tables = {
        "delimiter": DELIM_BY_SLUG,
        "escape": ESC_BY_SLUG,
        "quote": QUOTE_BY_SLUG,
    }
    row = tables[kind].get(slug)
    if row is None:
        raise HoldoutPolicyError(f"unknown parser {kind}: {slug or 'missing'}")
    return str(row["char"])


def _private_cases(rng: random.Random, delimiter: str, special: str) -> list[list[str]]:
    alphabet = "abcdefghijkmnpqrstuvwxyz23456789"

    def token() -> str:
        size = rng.randint(2, 10)
        value = "".join(rng.choice(alphabet) for _ in range(size))
        insertions = [delimiter, special, delimiter + special, special + special]
        marker = rng.choice(insertions)
        offset = rng.randint(0, len(value))
        return value[:offset] + marker + value[offset:]

    cases: list[list[str]] = [
        [""],
        ["", delimiter, special, ""],
        [delimiter + special + delimiter],
        [special + special, delimiter + delimiter],
    ]
    for _ in range(20):
        cases.append([token() for _ in range(rng.randint(1, 6))])
    rng.shuffle(cases)
    return cases


def _render_test_source(
    *,
    module_name: str,
    archetype: str,
    delimiter: str,
    special: str,
    cases: list[list[str]],
) -> str:
    cases_json = json.dumps(cases, ensure_ascii=True, separators=(",", ":"))
    lines = [
        f"from {module_name} import format_record, parse_record",
        "",
        f"DELIMITER = {delimiter!r}",
        f"SPECIAL = {special!r}",
        f"CASES = {cases_json}",
        "",
    ]
    if archetype == "quoted_fields":
        lines.extend(
            [
                "def _expected_format(fields):",
                "    parts = []",
                "    for field in fields:",
                "        if DELIMITER in field or SPECIAL in field:",
                "            body = field.replace(SPECIAL, SPECIAL + SPECIAL)",
                "            parts.append(SPECIAL + body + SPECIAL)",
                "        else:",
                "            parts.append(field)",
                "    return DELIMITER.join(parts)",
            ]
        )
    else:
        lines.extend(
            [
                "def _expected_format(fields):",
                "    parts = []",
                "    for field in fields:",
                "        encoded = []",
                "        for character in field:",
                "            if character == SPECIAL or character == DELIMITER:",
                "                encoded.append(SPECIAL)",
                "            encoded.append(character)",
                "        parts.append(''.join(encoded))",
                "    return DELIMITER.join(parts)",
            ]
        )
    lines.extend(
        [
            "",
            "def test_validator_private_round_trips():",
            "    for fields in CASES:",
            "        expected = _expected_format(fields)",
            "        assert format_record(fields) == expected",
            "        assert parse_record(expected) == fields",
        ]
    )
    if archetype == "error_contract":
        lines.extend(
            [
                "",
                "def test_validator_private_dangling_escape_contract():",
                f"    marker = {special!r}",
                "    try:",
                "        parse_record('private' + marker)",
                "    except ValueError:",
                "        return",
                "    raise AssertionError('dangling escape must raise ValueError')",
            ]
        )
    return "\n".join(lines) + "\n"


def _probe_candidates(task: Any) -> dict[str, dict[str, str]]:
    probes: dict[str, dict[str, str]] = {}
    if task.starter_files:
        probes["starter_files"] = dict(task.starter_files)
    stripped = {
        path: _strip_probe_drop_lines(content)
        for path, content in task.reference_files.items()
    }
    if stripped != task.reference_files:
        probes["family_edge_removed"] = stripped
    return probes


def _strip_probe_drop_lines(content: str) -> str:
    lines = [line for line in content.splitlines() if PROBE_DROP_MARKER not in line]
    stripped = "\n".join(lines)
    if content.endswith("\n") and not stripped.endswith("\n"):
        stripped += "\n"
    return stripped


def evidence_contains_active_material(record: dict[str, Any]) -> bool:
    """Defensive assertion helper used by tests and public-export callers."""

    serialized = json.dumps(record, sort_keys=True).lower()
    forbidden = ("cases", "test_source", "holdout_task", "secret")
    return any(re.search(rf'"[^"\\]*{name}[^"\\]*"\s*:', serialized) for name in forbidden)
