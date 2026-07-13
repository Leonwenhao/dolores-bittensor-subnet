from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

import yaml

from dolores_subnet import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]
RC_VERSION = "0.2.0rc1"
GOLDEN_PARSER_HASH = "fbf1ca8f3b9cad51370332bb1329d03b16306d4828bed9674e1a3d2a2f80a249"
ENGINE_SOURCE_COMMIT = "a832cfac214b946490dc4feeda40e2e4dd94e241"
ENGINE_WHEEL_SHA256 = "015f5f9cd047a4c2feabf7760ccb9d3f8ebf72aef65f658154b18ca80b72aeb1"
ENGINE_SDIST_SHA256 = "1acd013f76220e5d0c6cfbe63cf075940f03a7f2f0ece83e05837a2cccf29704"
SUBNET_WHEEL_SHA256 = "97e2dcd6592e94589b8492a1fc8ffaf449f1f11a3878cefca9059ee52cc2f665"
SUBNET_SDIST_SHA256 = "f358a8801a21beff09b8a6f3f0cf9bc2ea7c3d2fcddd64c5953844f70728bc16"


def test_release_metadata_pins_engine_sdk_and_installed_commands() -> None:
    metadata = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = metadata["project"]

    assert project["version"] == __version__ == RC_VERSION
    assert project["dependencies"] == [
        "bittensor==10.5.0",
        "bittensor-cli==9.23.1",
        "async-substrate-interface==2.2.1",
        "websockets==16.0",
        "dolores-autocurricula==0.2.0rc1",
        "pydantic>=2.7",
        "PyYAML>=6.0",
    ]
    assert project["requires-python"] == ">=3.11,<3.12"
    assert metadata["build-system"] == {
        "requires": ["setuptools==83.0.0", "wheel==0.47.0"],
        "build-backend": "setuptools.build_meta",
    }
    assert metadata["tool"]["setuptools"]["package-data"] == {
        "dolores_subnet": ["_assets/configs/*.yaml"]
    }
    assert project["scripts"] == {
        "dolores-miner": "dolores_subnet.miner_cli:main",
        "dolores-validator": "dolores_subnet.validator_cli:main",
    }


def test_golden_engine_hash_matches_subnet_wire_identity() -> None:
    from dolores.schemas.task import TaskPackage

    from dolores_subnet.packaging import from_wire, to_wire

    task = TaskPackage.load(REPO_ROOT / "examples/tasks/honest_example")
    wire = to_wire(task)

    assert task.stable_hash() == GOLDEN_PARSER_HASH
    assert wire["package_hash"] == GOLDEN_PARSER_HASH
    assert from_wire(wire).stable_hash() == GOLDEN_PARSER_HASH


def test_clean_wheel_contains_both_cli_entrypoints(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(REPO_ROOT / name, source / name)
    shutil.copytree(
        REPO_ROOT / "src",
        source / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )
    wheelhouse = tmp_path / "wheelhouse"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(wheelhouse.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
        entry_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        entrypoints = archive.read(entry_name).decode("utf-8")
        assert "dolores-miner = dolores_subnet.miner_cli:main" in entrypoints
        assert "dolores-validator = dolores_subnet.validator_cli:main" in entrypoints
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
        assert metadata["Version"] == RC_VERSION
        requirements = metadata.get_all("Requires-Dist", [])
        assert any(item.startswith("dolores-autocurricula==0.2.0rc1") for item in requirements)
        assert "dolores_subnet/miner_cli.py" in names
        assert "dolores_subnet/validator_cli.py" in names
        assert "dolores_subnet/_assets/configs/solver_panel.mock.yaml" in names
        assert "dolores_subnet/_assets/configs/solver_panel.calibrate.yaml" in names

    target = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--target",
            str(target),
            str(wheels[0]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(target)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    script = (
        "from dolores_subnet.config import SubnetConfig, Mode; "
        "cfg = SubnetConfig.from_env(mode=Mode.WIRE, work_dir='/tmp/wheel-smoke'); "
        "assert cfg.panel_path.is_file(), cfg.panel_path; "
        "assert cfg.panel_calibrate_path.is_file(), cfg.panel_calibrate_path; "
        f"assert cfg.panel_path.is_relative_to({str(target)!r}); "
        "print(cfg.panel_path)"
    )
    subprocess.run(
        [sys.executable, "-P", "-c", script],
        cwd=outside,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_packaged_panel_assets_match_reviewed_source_configs() -> None:
    for name in ("solver_panel.mock.yaml", "solver_panel.calibrate.yaml"):
        source = REPO_ROOT / "configs" / name
        packaged = REPO_ROOT / "src" / "dolores_subnet" / "_assets" / "configs" / name
        assert packaged.read_bytes() == source.read_bytes()


def test_source_manifest_contains_public_ops_assets_and_excludes_internal_notes() -> None:
    lines = {
        line.strip()
        for line in (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    for required in (
        "include deploy/systemd/dolores-miner.service",
        "include deploy/systemd/dolores-validator.service",
        "include deploy/systemd/dolores-validator.timer",
        "include docs/hackerquest-miner-quickstart.md",
        "include docs/validator-operations.md",
        "include docs/cohort-release-checklist.md",
    ):
        assert required in lines
    assert "prune tests" in lines
    assert not any(
        private in line
        for line in lines
        for private in (
            "docs/diary",
            "docs/reviews",
            "docs/imported",
            "docs/strategy",
            "docs/hackerhouse",
            "docs/launch",
        )
    )


def test_ci_builds_and_smokes_checkout_independent_release_artifacts() -> None:
    workflow_text = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow_text)
    assert isinstance(parsed, dict)

    release_job = workflow_text.split("  release-artifacts:\n", maxsplit=1)[1]
    assert f"ENGINE_SOURCE_COMMIT: {ENGINE_SOURCE_COMMIT}" in workflow_text
    assert f"ENGINE_WHEEL_SHA256: {ENGINE_WHEEL_SHA256}" in workflow_text
    assert f"ENGINE_SDIST_SHA256: {ENGINE_SDIST_SHA256}" in workflow_text
    assert f"SUBNET_WHEEL_SHA256: {SUBNET_WHEEL_SHA256}" in workflow_text
    assert f"SUBNET_SDIST_SHA256: {SUBNET_SDIST_SHA256}" in workflow_text
    assert f"GOLDEN_PARSER_HASH: {GOLDEN_PARSER_HASH}" in workflow_text
    assert 'PYTHON_VERSION: "3.11.15"' in workflow_text
    assert 'BUILD_VERSION: "1.5.1"' in workflow_text
    assert 'SETUPTOOLS_VERSION: "83.0.0"' in workflow_text
    assert 'WHEEL_VERSION: "0.47.0"' in workflow_text
    assert (
        "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4"
        in workflow_text
    )
    assert (
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5"
        in workflow_text
    )
    assert "git archive \"$GITHUB_SHA\"" in release_job
    assert "python -m build --no-isolation --wheel --sdist" in release_job
    assert 'for copy in a b; do' in release_job
    assert release_job.count("cmp /tmp/subnet-dist-a/") == 2
    assert 'python "$source_dir/scripts/normalize_sdist.py" \\' in release_job
    assert '--epoch "$SOURCE_DATE_EPOCH" \\' in release_job
    assert '"$dist_dir/dolores_bittensor_subnet-0.2.0rc1.tar.gz"' in release_job
    assert 'echo "$SUBNET_WHEEL_SHA256  $SUBNET_WHEEL" | sha256sum --check --strict' in release_job
    assert 'echo "$SUBNET_SDIST_SHA256  $SUBNET_SDIST" | sha256sum --check --strict' in release_job
    assert "tar --extract --gzip --file \"$SUBNET_SDIST\"" in release_job
    assert "cd /tmp" in release_job
    assert "/tmp/miner-venv" in release_job
    assert "/tmp/validator-venv" in release_job
    assert "/tmp/sdist-venv" in release_job
    assert release_job.count('os.environ["GOLDEN_PARSER_HASH"]') == 3
    assert "clean_miner_golden_digest=" in release_job
    assert "clean_validator_golden_digest=" in release_job
    assert "clean_sdist_golden_digest=" in release_job
    assert "systemd-analyze verify" in release_job
    assert "module_path.is_relative_to(Path(\"/tmp/sdist-venv\").resolve())" in release_job
    assert "DOLORES_REPO" not in release_job
    assert "pip install -e" not in release_job
