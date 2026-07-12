from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest
import yaml

import scripts.build_release_bundle as bundle_module
from scripts.build_release_bundle import (
    BUNDLE_ROOT,
    BundleError,
    build_release_bundle,
    verify_release_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0rc1"
SOURCE_DATE_EPOCH = 1_783_869_698
ENGINE_COMMIT = "1" * 40
SUBNET_COMMIT = "2" * 40
ENGINE_NAME = f"dolores_autocurricula-{VERSION}-py3-none-any.whl"
SUBNET_WHEEL_NAME = f"dolores_bittensor_subnet-{VERSION}-py3-none-any.whl"
SUBNET_SDIST_NAME = f"dolores_bittensor_subnet-{VERSION}.tar.gz"


def _zip_file(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    archive.writestr(info, data)


def _write_wheel(path: Path, *, distribution: str, module: str) -> None:
    dist_info = distribution.replace("-", "_")
    metadata = (f"Metadata-Version: 2.4\nName: {distribution}\nVersion: {VERSION}\n\n").encode()
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        _zip_file(archive, f"{module}/__init__.py", b"__version__ = '0.2.0rc1'\n")
        _zip_file(archive, f"{dist_info}-{VERSION}.dist-info/METADATA", metadata)


def _write_sdist(path: Path, *, add_symlink: bool = False) -> None:
    root = f"dolores_bittensor_subnet-{VERSION}"
    metadata = (
        f"Metadata-Version: 2.4\nName: dolores-bittensor-subnet\nVersion: {VERSION}\n\n"
    ).encode()
    target = io.BytesIO()
    with gzip.GzipFile(
        fileobj=target,
        mode="wb",
        filename="",
        mtime=SOURCE_DATE_EPOCH,
    ) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, data in (
                (f"{root}/PKG-INFO", metadata),
                (f"{root}/src/dolores_subnet/__init__.py", b"__version__ = '0.2.0rc1'\n"),
            ):
                info = tarfile.TarInfo(name)
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = SOURCE_DATE_EPOCH
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            if add_symlink:
                link = tarfile.TarInfo(f"{root}/unsafe-link")
                link.type = tarfile.SYMTYPE
                link.linkname = "PKG-INFO"
                archive.addfile(link)
    path.write_bytes(target.getvalue())


def _inputs(tmp_path: Path) -> dict[str, Path]:
    engine = tmp_path / ENGINE_NAME
    subnet_wheel = tmp_path / SUBNET_WHEEL_NAME
    subnet_sdist = tmp_path / SUBNET_SDIST_NAME
    fixture = tmp_path / "honest_example"
    shutil.copytree(ROOT / "examples/tasks/honest_example", fixture)
    _write_wheel(engine, distribution="dolores-autocurricula", module="dolores")
    _write_wheel(
        subnet_wheel,
        distribution="dolores-bittensor-subnet",
        module="dolores_subnet",
    )
    _write_sdist(subnet_sdist)
    return {
        "engine_wheel": engine,
        "subnet_wheel": subnet_wheel,
        "subnet_sdist": subnet_sdist,
        "fixture_dir": fixture,
    }


def _build(inputs: dict[str, Path], output: Path):
    return build_release_bundle(
        **inputs,
        output=output,
        version=VERSION,
        source_date_epoch=SOURCE_DATE_EPOCH,
        engine_source_commit=ENGINE_COMMIT,
        subnet_source_commit=SUBNET_COMMIT,
    )


def _rewrite_bundle(
    path: Path,
    members: dict[str, bytes],
    *,
    gzip_mtime: int = SOURCE_DATE_EPOCH,
) -> None:
    target = io.BytesIO()
    with gzip.GzipFile(
        fileobj=target,
        mode="wb",
        filename="",
        mtime=gzip_mtime,
    ) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name in sorted(members):
                data = members[name]
                info = tarfile.TarInfo(name)
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.mtime = SOURCE_DATE_EPOCH
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    path.write_bytes(target.getvalue())


def test_bundle_is_deterministic_self_verifying_and_auditable(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"

    first_result = _build(inputs, first)
    second_result = _build(inputs, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_result.bundle_sha256 == second_result.bundle_sha256
    assert first_result.member_count == 7
    assert first_result.payload_count == 5

    verified = verify_release_bundle(
        first,
        expected_version=VERSION,
        expected_source_date_epoch=SOURCE_DATE_EPOCH,
        expected_engine_source_commit=ENGINE_COMMIT,
        expected_subnet_source_commit=SUBNET_COMMIT,
    )
    assert verified.bundle_sha256 == hashlib.sha256(first.read_bytes()).hexdigest()

    with tarfile.open(first, mode="r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        assert names == sorted(names)
        assert all(member.isfile() for member in members)
        assert all(member.mode == 0o644 for member in members)
        assert all(member.mtime == SOURCE_DATE_EPOCH for member in members)
        assert all(member.uid == member.gid == 0 for member in members)
        assert all(member.uname == member.gname == "" for member in members)
        contents = {
            member.name: archive.extractfile(member).read()  # type: ignore[union-attr]
            for member in members
        }

    provenance = json.loads(contents[f"{BUNDLE_ROOT}/provenance.json"])
    assert provenance["source_date_epoch"] == SOURCE_DATE_EPOCH
    assert provenance["sources"]["engine"]["commit"] == ENGINE_COMMIT
    assert provenance["sources"]["subnet"]["commit"] == SUBNET_COMMIT
    assert [record["path"] for record in provenance["payloads"]] == sorted(
        record["path"] for record in provenance["payloads"]
    )

    checksum_lines = contents[f"{BUNDLE_ROOT}/SHA256SUMS"].decode().splitlines()
    checksum_paths = [line.split("  ", maxsplit=1)[1] for line in checksum_lines]
    assert checksum_paths == sorted(checksum_paths)
    assert checksum_paths == [
        f"artifacts/{ENGINE_NAME}",
        f"artifacts/{SUBNET_WHEEL_NAME}",
        f"artifacts/{SUBNET_SDIST_NAME}",
        "examples/tasks/honest_example/task.yaml",
        "examples/tasks/honest_example/wire.json",
        "provenance.json",
    ]


def test_builder_rejects_unexpected_fixture_content_and_symlinks(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    fixture = inputs["fixture_dir"]
    (fixture / "unexpected.txt").write_text("not approved\n", encoding="utf-8")
    with pytest.raises(BundleError, match="must contain exactly"):
        _build(inputs, tmp_path / "unexpected.tar.gz")

    (fixture / "unexpected.txt").unlink()
    (fixture / "wire.json").unlink()
    (fixture / "wire.json").symlink_to("task.yaml")
    with pytest.raises(BundleError, match="regular file, not a symlink"):
        _build(inputs, tmp_path / "symlink.tar.gz")


def test_builder_rejects_fixture_wire_that_does_not_match_task(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    wire_path = inputs["fixture_dir"] / "wire.json"
    wire = json.loads(wire_path.read_text(encoding="utf-8"))
    wire["package_hash"] = "0" * 64
    wire_path.write_text(json.dumps(wire, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(BundleError, match="does not equal the pinned conversion"):
        _build(inputs, tmp_path / "mismatched-fixture.tar.gz")


def test_builder_rejects_link_inside_nested_source_distribution(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_sdist(inputs["subnet_sdist"], add_symlink=True)

    with pytest.raises(BundleError, match="link or special file"):
        _build(inputs, tmp_path / "unsafe-sdist.tar.gz")


def test_builder_rejects_source_distribution_without_release_epoch(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    sdist = inputs["subnet_sdist"]
    data = bytearray(sdist.read_bytes())
    data[4:8] = (SOURCE_DATE_EPOCH + 1).to_bytes(4, byteorder="little")
    sdist.write_bytes(data)

    with pytest.raises(BundleError, match="gzip mtime is not the release epoch"):
        _build(inputs, tmp_path / "unnormalized-sdist.tar.gz")


def test_builder_never_overwrites_an_input_artifact(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)

    with pytest.raises(BundleError, match="must not overwrite"):
        _build(inputs, inputs["engine_wheel"])


def test_verifier_rejects_nested_payload_tampering(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    _build(inputs, bundle)
    with tarfile.open(bundle, mode="r:gz") as archive:
        members = {
            member.name: archive.extractfile(member).read()  # type: ignore[union-attr]
            for member in archive.getmembers()
        }
    engine_name = f"{BUNDLE_ROOT}/artifacts/{ENGINE_NAME}"
    members[engine_name] += b"tampered"
    _rewrite_bundle(bundle, members)

    with pytest.raises(BundleError, match="payload (size|hash) mismatch"):
        verify_release_bundle(bundle)


def test_verifier_rejects_self_consistent_invalid_nested_artifact(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    _build(inputs, bundle)
    with tarfile.open(bundle, mode="r:gz") as archive:
        members = {
            member.name: archive.extractfile(member).read()  # type: ignore[union-attr]
            for member in archive.getmembers()
        }

    engine_member = f"{BUNDLE_ROOT}/artifacts/{ENGINE_NAME}"
    members[engine_member] = b"not-a-wheel"
    provenance_name = f"{BUNDLE_ROOT}/provenance.json"
    provenance = json.loads(members[provenance_name])
    engine_record = next(
        record
        for record in provenance["payloads"]
        if record["path"] == f"artifacts/{ENGINE_NAME}"
    )
    engine_record["size"] = len(members[engine_member])
    engine_record["sha256"] = hashlib.sha256(members[engine_member]).hexdigest()
    members[provenance_name] = (
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    ).encode()

    checksums_name = f"{BUNDLE_ROOT}/SHA256SUMS"
    checksum_members = {
        name.removeprefix(f"{BUNDLE_ROOT}/"): data
        for name, data in members.items()
        if name != checksums_name
    }
    members[checksums_name] = (
        "\n".join(
            f"{hashlib.sha256(checksum_members[name]).hexdigest()}  {name}"
            for name in sorted(checksum_members)
        )
        + "\n"
    ).encode()
    _rewrite_bundle(bundle, members)

    with pytest.raises(BundleError, match="invalid wheel"):
        verify_release_bundle(bundle)


def test_verifier_rejects_noncanonical_outer_encoding(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    _build(inputs, bundle)

    bundle.write_bytes(bundle.read_bytes() + b"trailing-junk")
    with pytest.raises(BundleError, match="canonical release encoding"):
        verify_release_bundle(bundle)

    _build(inputs, bundle)
    with tarfile.open(bundle, mode="r:gz") as archive:
        members = {
            member.name: archive.extractfile(member).read()  # type: ignore[union-attr]
            for member in archive.getmembers()
        }
    _rewrite_bundle(bundle, members, gzip_mtime=SOURCE_DATE_EPOCH + 1)
    with pytest.raises(BundleError, match="canonical release encoding"):
        verify_release_bundle(bundle)


def test_build_preserves_existing_output_when_final_verification_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path)
    output = tmp_path / "existing.tar.gz"
    output.write_bytes(b"previous-known-good")

    def reject_bundle(*args, **kwargs):  # noqa: ANN002, ANN003
        raise BundleError("injected final verification failure")

    monkeypatch.setattr(bundle_module, "verify_release_bundle", reject_bundle)
    with pytest.raises(BundleError, match="injected final verification failure"):
        _build(inputs, output)

    assert output.read_bytes() == b"previous-known-good"
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


@pytest.mark.parametrize("path", ["a/./b", "a//b", "a/../b", "a\ncontrol"])
def test_archive_path_validation_rejects_noncanonical_names(path: str) -> None:
    with pytest.raises(BundleError, match="(invalid|unsafe) test path"):
        bundle_module._validate_archive_path(path, "test")


def test_ci_uses_fixed_epoch_builder_and_independent_verification() -> None:
    workflow_path = ROOT / ".github/workflows/ci.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow_text)
    assert isinstance(parsed, dict)
    steps = parsed["jobs"]["release-artifacts"]["steps"]
    assembly = next(
        step
        for step in steps
        if step.get("name") == "Assemble and extract the checkout-independent release bundle"
    )
    assert parsed["env"]["SOURCE_DATE_EPOCH"] == str(SOURCE_DATE_EPOCH)
    assert (
        assembly["env"]["ENGINE_SOURCE_COMMIT"]
        == "814d9bcc451a36db1b341c2ddd6f27d1aaed565b"
    )
    run = assembly["run"]
    assert "scripts/build_release_bundle.py build" in run
    assert "scripts/build_release_bundle.py verify" in run
    assert '--source-date-epoch "$SOURCE_DATE_EPOCH"' in run
    assert "SHA256SUMS" in run
    assert "provenance.json" in run
    assert "tar --create" not in run
