from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import Path, PurePosixPath
from typing import Any

BUNDLE_ROOT = PurePosixPath("release-bundle")
PROVENANCE_PATH = PurePosixPath("provenance.json")
CHECKSUMS_PATH = PurePosixPath("SHA256SUMS")
PROVENANCE_SCHEMA = "dolores-release-bundle-provenance-v1"
BUILDER_ID = "scripts/build_release_bundle.py"
FIXTURE_NAMES = ("task.yaml", "wire.json")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
MAX_BUNDLE_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 512 * 1024 * 1024


class BundleError(ValueError):
    """Raised when a release-bundle input or archive violates the contract."""


@dataclass(frozen=True)
class Payload:
    path: PurePosixPath
    role: str
    data: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True)
class BundleVerification:
    bundle_sha256: str
    member_count: int
    payload_count: int
    provenance: dict[str, Any]


def build_release_bundle(
    *,
    engine_wheel: Path,
    subnet_wheel: Path,
    subnet_sdist: Path,
    fixture_dir: Path,
    output: Path,
    version: str,
    source_date_epoch: int,
    engine_source_commit: str,
    subnet_source_commit: str,
) -> BundleVerification:
    """Build and independently verify a deterministic controlled-cohort bundle."""

    _validate_version(version)
    _validate_source_date_epoch(source_date_epoch)
    _validate_commit(engine_source_commit, "engine source commit")
    _validate_commit(subnet_source_commit, "subnet source commit")

    expected_artifacts = {
        "engine wheel": (
            engine_wheel,
            f"dolores_autocurricula-{version}-py3-none-any.whl",
            "engine_wheel",
        ),
        "subnet wheel": (
            subnet_wheel,
            f"dolores_bittensor_subnet-{version}-py3-none-any.whl",
            "subnet_wheel",
        ),
        "subnet source distribution": (
            subnet_sdist,
            f"dolores_bittensor_subnet-{version}.tar.gz",
            "subnet_sdist",
        ),
    }

    payloads: list[Payload] = []
    for label, (path, expected_name, role) in expected_artifacts.items():
        _require_regular_file(path, label)
        if path.name != expected_name:
            raise BundleError(f"{label} must be named {expected_name!r}, received {path.name!r}")
        data = path.read_bytes()
        payloads.append(Payload(PurePosixPath("artifacts") / expected_name, role, data))

    payload_by_role = {payload.role: payload for payload in payloads}
    _validate_wheel_bytes(
        payload_by_role["engine_wheel"].data,
        label=engine_wheel.name,
        expected_distribution="dolores-autocurricula",
        expected_version=version,
    )
    _validate_wheel_bytes(
        payload_by_role["subnet_wheel"].data,
        label=subnet_wheel.name,
        expected_distribution="dolores-bittensor-subnet",
        expected_version=version,
    )
    _validate_sdist_bytes(
        payload_by_role["subnet_sdist"].data,
        label=subnet_sdist.name,
        expected_distribution="dolores-bittensor-subnet",
        expected_version=version,
        expected_source_date_epoch=source_date_epoch,
    )

    fixture_payloads = _load_fixture_payloads(fixture_dir)
    _validate_output_location(
        output,
        protected_files=[engine_wheel, subnet_wheel, subnet_sdist],
        fixture_dir=fixture_dir,
    )
    payloads.extend(fixture_payloads)
    payloads.sort(key=lambda payload: payload.path.as_posix())

    provenance = _provenance_bytes(
        payloads=payloads,
        version=version,
        source_date_epoch=source_date_epoch,
        engine_source_commit=engine_source_commit,
        subnet_source_commit=subnet_source_commit,
    )
    checksummed = [
        *payloads,
        Payload(PROVENANCE_PATH, "provenance", provenance),
    ]
    checksums = _checksums_bytes(checksummed)

    members = {
        **{(BUNDLE_ROOT / payload.path).as_posix(): payload.data for payload in payloads},
        (BUNDLE_ROOT / PROVENANCE_PATH).as_posix(): provenance,
        (BUNDLE_ROOT / CHECKSUMS_PATH).as_posix(): checksums,
    }
    archive = _render_tar_gz(members, source_date_epoch=source_date_epoch)
    return _write_verified_atomic(
        output,
        archive,
        version=version,
        source_date_epoch=source_date_epoch,
        engine_source_commit=engine_source_commit,
        subnet_source_commit=subnet_source_commit,
    )


def verify_release_bundle(
    bundle: Path,
    *,
    expected_version: str | None = None,
    expected_source_date_epoch: int | None = None,
    expected_engine_source_commit: str | None = None,
    expected_subnet_source_commit: str | None = None,
) -> BundleVerification:
    """Verify paths, metadata, provenance, and every nested payload digest."""

    _require_regular_file(bundle, "release bundle")
    if bundle.stat().st_size > MAX_BUNDLE_BYTES:
        raise BundleError("release bundle exceeds the compressed size limit")
    archive_bytes = bundle.read_bytes()
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if names != sorted(names):
                raise BundleError("bundle members are not lexicographically sorted")
            if len(names) != len(set(names)):
                raise BundleError("bundle contains duplicate member paths")
            total_size = 0
            for member in members:
                _validate_archive_path(member.name, "bundle member")
                if not member.isfile():
                    raise BundleError(f"bundle member must be a regular file: {member.name!r}")
                if member.size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise BundleError(f"bundle member exceeds the size limit: {member.name!r}")
                total_size += member.size
                if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                    raise BundleError("bundle exceeds the uncompressed size limit")
            contents = {member.name: _read_tar_member(archive, member) for member in members}
    except (tarfile.TarError, OSError) as exc:
        raise BundleError(f"invalid release bundle: {exc}") from exc

    provenance_name = (BUNDLE_ROOT / PROVENANCE_PATH).as_posix()
    checksums_name = (BUNDLE_ROOT / CHECKSUMS_PATH).as_posix()
    if provenance_name not in contents or checksums_name not in contents:
        raise BundleError("bundle is missing provenance.json or SHA256SUMS")

    provenance = _parse_provenance(contents[provenance_name])
    version = _require_json_string(provenance, "version")
    source_date_epoch = _require_json_integer(provenance, "source_date_epoch")
    _validate_version(version)
    _validate_source_date_epoch(source_date_epoch)

    sources = provenance.get("sources")
    if not isinstance(sources, dict) or set(sources) != {"engine", "subnet"}:
        raise BundleError("provenance sources must contain exactly engine and subnet")
    engine_commit = _parse_source(
        sources["engine"],
        label="engine",
        distribution="dolores-autocurricula",
        version=version,
    )
    subnet_commit = _parse_source(
        sources["subnet"],
        label="subnet",
        distribution="dolores-bittensor-subnet",
        version=version,
    )

    if expected_version is not None and version != expected_version:
        raise BundleError(f"bundle version {version!r} does not equal {expected_version!r}")
    if expected_source_date_epoch is not None and source_date_epoch != expected_source_date_epoch:
        raise BundleError("bundle SOURCE_DATE_EPOCH does not equal the expected value")
    if expected_engine_source_commit is not None and engine_commit != expected_engine_source_commit:
        raise BundleError("engine source commit does not equal the expected value")
    if expected_subnet_source_commit is not None and subnet_commit != expected_subnet_source_commit:
        raise BundleError("subnet source commit does not equal the expected value")

    payload_records = _parse_payload_records(provenance, version=version)
    expected_payload_names = {
        (BUNDLE_ROOT / PurePosixPath(record["path"])).as_posix() for record in payload_records
    }
    expected_members = expected_payload_names | {provenance_name, checksums_name}
    if set(contents) != expected_members:
        unexpected = sorted(set(contents) - expected_members)
        missing = sorted(expected_members - set(contents))
        raise BundleError(f"bundle member set mismatch; unexpected={unexpected}, missing={missing}")

    for member in members:
        if member.mtime != source_date_epoch:
            raise BundleError(f"unexpected mtime for {member.name!r}")
        if member.uid != 0 or member.gid != 0 or member.uname or member.gname:
            raise BundleError(f"unexpected ownership metadata for {member.name!r}")
        if member.mode != 0o644:
            raise BundleError(f"unexpected mode for {member.name!r}")

    for record in payload_records:
        member_name = (BUNDLE_ROOT / PurePosixPath(record["path"])).as_posix()
        data = contents[member_name]
        if len(data) != record["size"]:
            raise BundleError(f"payload size mismatch for {record['path']!r}")
        if _sha256(data) != record["sha256"]:
            raise BundleError(f"payload hash mismatch for {record['path']!r}")

    checksum_records = _parse_checksums(contents[checksums_name])
    expected_checksum_paths = {record["path"] for record in payload_records} | {
        PROVENANCE_PATH.as_posix()
    }
    if set(checksum_records) != expected_checksum_paths:
        raise BundleError("SHA256SUMS does not cover exactly the payloads and provenance")
    for relative_path, expected_hash in checksum_records.items():
        member_name = (BUNDLE_ROOT / PurePosixPath(relative_path)).as_posix()
        if _sha256(contents[member_name]) != expected_hash:
            raise BundleError(f"SHA256SUMS mismatch for {relative_path!r}")

    artifacts_root = BUNDLE_ROOT / "artifacts"
    engine_wheel_name = f"dolores_autocurricula-{version}-py3-none-any.whl"
    subnet_wheel_name = f"dolores_bittensor_subnet-{version}-py3-none-any.whl"
    subnet_sdist_name = f"dolores_bittensor_subnet-{version}.tar.gz"
    _validate_wheel_bytes(
        contents[(artifacts_root / engine_wheel_name).as_posix()],
        label=engine_wheel_name,
        expected_distribution="dolores-autocurricula",
        expected_version=version,
    )
    _validate_wheel_bytes(
        contents[(artifacts_root / subnet_wheel_name).as_posix()],
        label=subnet_wheel_name,
        expected_distribution="dolores-bittensor-subnet",
        expected_version=version,
    )
    _validate_sdist_bytes(
        contents[(artifacts_root / subnet_sdist_name).as_posix()],
        label=subnet_sdist_name,
        expected_distribution="dolores-bittensor-subnet",
        expected_version=version,
        expected_source_date_epoch=source_date_epoch,
    )
    fixture_root = BUNDLE_ROOT / "examples/tasks/honest_example"
    _validate_fixture_semantics(
        task_yaml=contents[(fixture_root / "task.yaml").as_posix()],
        wire_json=contents[(fixture_root / "wire.json").as_posix()],
    )

    canonical_archive = _render_tar_gz(contents, source_date_epoch=source_date_epoch)
    if archive_bytes != canonical_archive:
        raise BundleError("bundle bytes are not in the canonical release encoding")

    return BundleVerification(
        bundle_sha256=_sha256(archive_bytes),
        member_count=len(contents),
        payload_count=len(payload_records),
        provenance=provenance,
    )


def _load_fixture_payloads(fixture_dir: Path) -> list[Payload]:
    try:
        directory_stat = fixture_dir.lstat()
    except FileNotFoundError as exc:
        raise BundleError(f"honest fixture directory does not exist: {fixture_dir}") from exc
    if fixture_dir.is_symlink() or not stat.S_ISDIR(directory_stat.st_mode):
        raise BundleError("honest fixture path must be a real directory, not a symlink")

    entries = sorted(fixture_dir.iterdir(), key=lambda path: path.name)
    if [entry.name for entry in entries] != list(FIXTURE_NAMES):
        raise BundleError(f"honest fixture must contain exactly {list(FIXTURE_NAMES)!r}")
    payloads: list[Payload] = []
    for entry in entries:
        _require_regular_file(entry, f"honest fixture {entry.name}")
        payloads.append(
            Payload(
                PurePosixPath("examples/tasks/honest_example") / entry.name,
                "honest_fixture",
                entry.read_bytes(),
            )
        )
    fixture_by_name = {payload.path.name: payload.data for payload in payloads}
    _validate_fixture_semantics(
        task_yaml=fixture_by_name["task.yaml"],
        wire_json=fixture_by_name["wire.json"],
    )
    return payloads


def _validate_fixture_semantics(*, task_yaml: bytes, wire_json: bytes) -> None:
    try:
        from dolores.schemas.task import TaskPackage

        from dolores_subnet.packaging import to_wire
    except ImportError as exc:
        raise BundleError(
            "fixture validation requires the pinned engine and subnet distributions"
        ) from exc

    try:
        actual_wire = json.loads(wire_json.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"honest fixture wire.json is invalid: {exc}") from exc
    if not isinstance(actual_wire, dict):
        raise BundleError("honest fixture wire.json must contain a JSON object")

    try:
        with tempfile.TemporaryDirectory(prefix="dolores-release-fixture-") as temporary:
            root = Path(temporary)
            (root / "task.yaml").write_bytes(task_yaml)
            task = TaskPackage.load(root)
            expected_wire = to_wire(task)
    except Exception as exc:  # noqa: BLE001 - normalize schema errors at the release boundary.
        raise BundleError(f"honest fixture task.yaml is invalid: {exc}") from exc
    if actual_wire != expected_wire:
        raise BundleError(
            "honest fixture wire.json does not equal the pinned conversion of task.yaml"
        )


def _validate_wheel_bytes(
    data: bytes,
    *,
    label: str,
    expected_distribution: str,
    expected_version: str,
) -> None:
    if len(data) > MAX_ARCHIVE_MEMBER_BYTES:
        raise BundleError(f"wheel exceeds the compressed size limit: {label!r}")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise BundleError(f"wheel contains duplicate paths: {label!r}")
            total_size = 0
            for info in infos:
                _validate_archive_path(info.filename, f"wheel {label}")
                if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise BundleError(f"wheel member exceeds the size limit: {info.filename!r}")
                total_size += info.file_size
                if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                    raise BundleError(f"wheel exceeds the uncompressed size limit: {label!r}")
                file_type = stat.S_IFMT(info.external_attr >> 16)
                if file_type == stat.S_IFLNK:
                    raise BundleError(f"wheel contains a symlink: {info.filename!r}")
                if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise BundleError(
                        f"wheel contains an unsupported member type: {info.filename!r}"
                    )
            corrupt = archive.testzip()
            if corrupt is not None:
                raise BundleError(f"wheel CRC check failed for {corrupt!r}")
            metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(metadata_names) != 1:
                raise BundleError("wheel must contain exactly one dist-info/METADATA")
            metadata = archive.read(metadata_names[0])
    except (OSError, zipfile.BadZipFile) as exc:
        raise BundleError(f"invalid wheel {label!r}: {exc}") from exc
    _validate_distribution_metadata(
        metadata,
        label=label,
        expected_distribution=expected_distribution,
        expected_version=expected_version,
    )


def _validate_sdist_bytes(
    data: bytes,
    *,
    label: str,
    expected_distribution: str,
    expected_version: str,
    expected_source_date_epoch: int,
) -> None:
    if len(data) > MAX_ARCHIVE_MEMBER_BYTES:
        raise BundleError(f"source distribution exceeds the compressed size limit: {label!r}")
    if len(data) < 10 or data[:3] != b"\x1f\x8b\x08":
        raise BundleError(f"invalid gzip header in source distribution: {label!r}")
    if int.from_bytes(data[4:8], byteorder="little") != expected_source_date_epoch:
        raise BundleError("source distribution gzip mtime is not the release epoch")
    expected_root = f"dolores_bittensor_subnet-{expected_version}"
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if names != sorted(names):
                raise BundleError("source distribution members are not sorted")
            if len(names) != len(set(names)):
                raise BundleError("source distribution contains duplicate paths")
            total_size = 0
            for member in members:
                _validate_archive_path(member.name, "source distribution member")
                if not (member.isfile() or member.isdir()):
                    raise BundleError(
                        f"source distribution contains a link or special file: {member.name!r}"
                    )
                if member.size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise BundleError(
                        f"source distribution member exceeds the size limit: {member.name!r}"
                    )
                total_size += member.size
                if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                    raise BundleError("source distribution exceeds the uncompressed size limit")
                if member.mtime != expected_source_date_epoch:
                    raise BundleError(
                        f"source distribution member has a non-release mtime: {member.name!r}"
                    )
                if member.uid != 0 or member.gid != 0 or member.uname or member.gname:
                    raise BundleError(
                        f"source distribution member has host ownership: {member.name!r}"
                    )
                expected_mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
                if member.mode != expected_mode:
                    raise BundleError(
                        f"source distribution member has a noncanonical mode: {member.name!r}"
                    )
                if PurePosixPath(member.name).parts[0] != expected_root:
                    raise BundleError(
                        f"source distribution member escapes expected root: {member.name!r}"
                    )
            metadata_name = f"{expected_root}/PKG-INFO"
            metadata_members = [member for member in members if member.name == metadata_name]
            if len(metadata_members) != 1 or not metadata_members[0].isfile():
                raise BundleError("source distribution must contain one top-level PKG-INFO")
            metadata = _read_tar_member(archive, metadata_members[0])
    except (OSError, tarfile.TarError) as exc:
        raise BundleError(f"invalid source distribution {label!r}: {exc}") from exc
    _validate_distribution_metadata(
        metadata,
        label=label,
        expected_distribution=expected_distribution,
        expected_version=expected_version,
    )


def _validate_distribution_metadata(
    metadata: bytes,
    *,
    label: str,
    expected_distribution: str,
    expected_version: str,
) -> None:
    parsed = BytesParser(policy=default).parsebytes(metadata)
    name = parsed.get("Name")
    version = parsed.get("Version")
    if not isinstance(name, str) or _canonical_distribution(name) != expected_distribution:
        raise BundleError(f"unexpected distribution name in {label!r}: {name!r}")
    if version != expected_version:
        raise BundleError(f"unexpected version in {label!r}: {version!r}")


def _provenance_bytes(
    *,
    payloads: list[Payload],
    version: str,
    source_date_epoch: int,
    engine_source_commit: str,
    subnet_source_commit: str,
) -> bytes:
    document = {
        "builder": BUILDER_ID,
        "payloads": [
            {
                "path": payload.path.as_posix(),
                "role": payload.role,
                "sha256": payload.sha256,
                "size": len(payload.data),
            }
            for payload in payloads
        ],
        "schema_version": PROVENANCE_SCHEMA,
        "source_date_epoch": source_date_epoch,
        "sources": {
            "engine": {
                "commit": engine_source_commit,
                "distribution": "dolores-autocurricula",
                "version": version,
            },
            "subnet": {
                "commit": subnet_source_commit,
                "distribution": "dolores-bittensor-subnet",
                "version": version,
            },
        },
        "version": version,
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _checksums_bytes(payloads: list[Payload]) -> bytes:
    lines = [
        f"{payload.sha256}  {payload.path.as_posix()}"
        for payload in sorted(payloads, key=lambda item: item.path.as_posix())
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _render_tar_gz(members: dict[str, bytes], *, source_date_epoch: int) -> bytes:
    target = io.BytesIO()
    with gzip.GzipFile(
        fileobj=target,
        mode="wb",
        filename="",
        compresslevel=9,
        mtime=source_date_epoch,
    ) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name in sorted(members):
                _validate_archive_path(name, "output bundle member")
                data = members[name]
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                info.mtime = source_date_epoch
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return target.getvalue()


def _write_verified_atomic(
    output: Path,
    data: bytes,
    *,
    version: str,
    source_date_epoch: int,
    engine_source_commit: str,
    subnet_source_commit: str,
) -> BundleVerification:
    if output.exists() or output.is_symlink():
        try:
            output_stat = output.lstat()
        except FileNotFoundError:
            output_stat = None
        if output_stat is not None and (
            output.is_symlink() or not stat.S_ISREG(output_stat.st_mode)
        ):
            raise BundleError("output path must be absent or a regular file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        verification = verify_release_bundle(
            temporary,
            expected_version=version,
            expected_source_date_epoch=source_date_epoch,
            expected_engine_source_commit=engine_source_commit,
            expected_subnet_source_commit=subnet_source_commit,
        )
        os.replace(temporary, output)
        temporary = None
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(output.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return verification
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _validate_output_location(
    output: Path,
    *,
    protected_files: list[Path],
    fixture_dir: Path,
) -> None:
    resolved_output = output.resolve(strict=False)
    if any(resolved_output == path.resolve(strict=True) for path in protected_files):
        raise BundleError("output path must not overwrite an input artifact")
    if resolved_output.is_relative_to(fixture_dir.resolve(strict=True)):
        raise BundleError("output path must not be inside the honest fixture directory")


def _parse_provenance(data: bytes) -> dict[str, Any]:
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"invalid provenance JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise BundleError("provenance JSON must be an object")
    expected_keys = {
        "builder",
        "payloads",
        "schema_version",
        "source_date_epoch",
        "sources",
        "version",
    }
    if set(document) != expected_keys:
        raise BundleError("provenance JSON has unexpected or missing fields")
    if document["schema_version"] != PROVENANCE_SCHEMA:
        raise BundleError("unsupported provenance schema")
    if document["builder"] != BUILDER_ID:
        raise BundleError("unexpected provenance builder identifier")
    return document


def _parse_source(
    value: Any,
    *,
    label: str,
    distribution: str,
    version: str,
) -> str:
    if not isinstance(value, dict) or set(value) != {"commit", "distribution", "version"}:
        raise BundleError(f"invalid {label} provenance source")
    if value["distribution"] != distribution or value["version"] != version:
        raise BundleError(f"unexpected {label} distribution provenance")
    commit = value["commit"]
    if not isinstance(commit, str):
        raise BundleError(f"invalid {label} source commit")
    _validate_commit(commit, f"{label} source commit")
    return commit


def _parse_payload_records(provenance: dict[str, Any], *, version: str) -> list[dict[str, Any]]:
    records = provenance.get("payloads")
    if not isinstance(records, list):
        raise BundleError("provenance payloads must be a list")
    expected_roles = {
        f"artifacts/dolores_autocurricula-{version}-py3-none-any.whl": "engine_wheel",
        f"artifacts/dolores_bittensor_subnet-{version}-py3-none-any.whl": "subnet_wheel",
        f"artifacts/dolores_bittensor_subnet-{version}.tar.gz": "subnet_sdist",
        "examples/tasks/honest_example/task.yaml": "honest_fixture",
        "examples/tasks/honest_example/wire.json": "honest_fixture",
    }
    normalized: list[dict[str, Any]] = []
    for value in records:
        if not isinstance(value, dict) or set(value) != {"path", "role", "sha256", "size"}:
            raise BundleError("invalid provenance payload record")
        path = value["path"]
        role = value["role"]
        digest = value["sha256"]
        size = value["size"]
        if not isinstance(path, str):
            raise BundleError("payload path must be a string")
        _validate_archive_path(path, "provenance payload")
        if path not in expected_roles or role != expected_roles[path]:
            raise BundleError(f"unexpected payload path or role: {path!r}")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise BundleError(f"invalid payload SHA-256 for {path!r}")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise BundleError(f"invalid payload size for {path!r}")
        normalized.append(value)
    paths = [record["path"] for record in normalized]
    if paths != sorted(expected_roles):
        raise BundleError("provenance payload records are not the exact sorted payload set")
    return normalized


def _parse_checksums(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BundleError("SHA256SUMS must be UTF-8") from exc
    if not text.endswith("\n"):
        raise BundleError("SHA256SUMS must end with a newline")
    records: dict[str, str] = {}
    paths: list[str] = []
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise BundleError(f"invalid SHA256SUMS line: {line!r}")
        digest, path = match.groups()
        _validate_archive_path(path, "SHA256SUMS path")
        if path in records:
            raise BundleError(f"duplicate SHA256SUMS path: {path!r}")
        records[path] = digest
        paths.append(path)
    if paths != sorted(paths):
        raise BundleError("SHA256SUMS paths are not sorted")
    return records


def _require_json_string(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise BundleError(f"provenance field {key!r} must be a string")
    return value


def _require_json_integer(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BundleError(f"provenance field {key!r} must be an integer")
    return value


def _validate_archive_path(value: str, label: str) -> None:
    has_control_character = any(
        ord(character) < 32 or ord(character) == 127 for character in value
    )
    if not value or "\\" in value or has_control_character:
        raise BundleError(f"invalid {label} path: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or value != path.as_posix()
    ):
        raise BundleError(f"unsafe {label} path: {value!r}")


def _read_tar_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    handle = archive.extractfile(member)
    if handle is None:
        raise BundleError(f"could not read tar member: {member.name!r}")
    return handle.read()


def _require_regular_file(path: Path, label: str) -> None:
    try:
        file_stat = path.lstat()
    except FileNotFoundError as exc:
        raise BundleError(f"{label} does not exist: {path}") from exc
    if path.is_symlink() or not stat.S_ISREG(file_stat.st_mode):
        raise BundleError(f"{label} must be a regular file, not a symlink: {path}")


def _validate_commit(value: str, label: str) -> None:
    if COMMIT_RE.fullmatch(value) is None:
        raise BundleError(f"{label} must be a lowercase 40-character Git object ID")


def _validate_version(value: str) -> None:
    if VERSION_RE.fullmatch(value) is None:
        raise BundleError(f"invalid release version: {value!r}")


def _validate_source_date_epoch(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2**31 - 1:
        raise BundleError("SOURCE_DATE_EPOCH must be an integer from 0 through 2147483647")


def _canonical_distribution(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _commit_argument(value: str) -> str:
    try:
        _validate_commit(value, "source commit")
    except BundleError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


def _epoch_argument(value: str) -> int:
    try:
        epoch = int(value)
        _validate_source_date_epoch(epoch)
    except (BundleError, ValueError) as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return epoch


def _add_expected_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-date-epoch", required=True, type=_epoch_argument)
    parser.add_argument("--engine-source-commit", required=True, type=_commit_argument)
    parser.add_argument("--subnet-source-commit", required=True, type=_commit_argument)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or verify a deterministic Dolores controlled-cohort bundle."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="build and verify a release bundle")
    _add_expected_arguments(build)
    build.add_argument("--engine-wheel", required=True, type=Path)
    build.add_argument("--subnet-wheel", required=True, type=Path)
    build.add_argument("--subnet-sdist", required=True, type=Path)
    build.add_argument("--fixture-dir", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)

    verify = commands.add_parser("verify", help="verify an existing release bundle")
    _add_expected_arguments(verify)
    verify.add_argument("--bundle", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_release_bundle(
                engine_wheel=args.engine_wheel,
                subnet_wheel=args.subnet_wheel,
                subnet_sdist=args.subnet_sdist,
                fixture_dir=args.fixture_dir,
                output=args.output,
                version=args.version,
                source_date_epoch=args.source_date_epoch,
                engine_source_commit=args.engine_source_commit,
                subnet_source_commit=args.subnet_source_commit,
            )
            bundle = args.output
        else:
            result = verify_release_bundle(
                args.bundle,
                expected_version=args.version,
                expected_source_date_epoch=args.source_date_epoch,
                expected_engine_source_commit=args.engine_source_commit,
                expected_subnet_source_commit=args.subnet_source_commit,
            )
            bundle = args.bundle
    except (BundleError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")

    print(f"bundle={bundle}")
    print(f"bundle_sha256={result.bundle_sha256}")
    print(f"bundle_members={result.member_count}")
    print(f"bundle_payloads={result.payload_count}")
    print("bundle_verification=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
