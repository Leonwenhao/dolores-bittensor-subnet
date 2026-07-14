from __future__ import annotations

import gzip
import io
import stat
import tarfile
from pathlib import Path

import pytest

from scripts.normalize_sdist import normalize_sdist

EPOCH = 1_783_869_698


def _write_archive(
    path: Path,
    *,
    reverse: bool = False,
    metadata_offset: int = 0,
    unsafe_name: str | None = None,
    link: bool = False,
    duplicate: bool = False,
    second_root: bool = False,
) -> None:
    entries = [
        ("package-0.2.0rc2", None, 0o755),
        ("package-0.2.0rc2/PKG-INFO", b"Name: package\nVersion: 0.2.0rc2\n", 0o644),
        ("package-0.2.0rc2/scripts/run.py", b"#!/usr/bin/env python3\n", 0o755),
    ]
    if unsafe_name is not None:
        entries.append((unsafe_name, b"unsafe\n", 0o644))
    if duplicate:
        entries.append(("package-0.2.0rc2/PKG-INFO", b"duplicate\n", 0o644))
    if second_root:
        entries.append(("other-package/PKG-INFO", b"Name: other-package\n", 0o644))
    if reverse:
        entries.reverse()

    target = io.BytesIO()
    with gzip.GzipFile(
        fileobj=target,
        mode="wb",
        filename="variable-name.tar",
        mtime=1_600_000_000 + metadata_offset,
    ) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for index, (name, data, mode) in enumerate(entries):
                info = tarfile.TarInfo(name)
                info.mode = mode
                info.uid = 1000 + metadata_offset
                info.gid = 2000 + metadata_offset
                info.uname = "builder"
                info.gname = "builders"
                info.mtime = 1_600_000_000 + metadata_offset + index
                if data is None:
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                else:
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
            if link:
                info = tarfile.TarInfo("package-0.2.0rc2/unsafe-link")
                info.type = tarfile.SYMTYPE
                info.linkname = "PKG-INFO"
                archive.addfile(info)
    path.write_bytes(target.getvalue())


def test_normalization_is_byte_identical_across_input_metadata_and_order(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    _write_archive(first)
    _write_archive(second, reverse=True, metadata_offset=73)

    first_digest = normalize_sdist(first, epoch=EPOCH)
    second_digest = normalize_sdist(second, epoch=EPOCH)

    assert first_digest == second_digest
    assert first.read_bytes() == second.read_bytes()
    assert stat.S_IMODE(first.stat().st_mode) == 0o644
    normalized_bytes = first.read_bytes()
    assert normalize_sdist(first, epoch=EPOCH) == first_digest
    assert first.read_bytes() == normalized_bytes
    with tarfile.open(first, mode="r:gz") as archive:
        members = archive.getmembers()
        assert [member.name for member in members] == sorted(member.name for member in members)
        assert all(member.mtime == EPOCH for member in members)
        assert all(member.uid == member.gid == 0 for member in members)
        assert all(member.uname == member.gname == "" for member in members)
        assert next(member for member in members if member.isdir()).mode == 0o755
        executable = next(member for member in members if member.name.endswith("run.py"))
        assert executable.mode == 0o755
        regular = next(member for member in members if member.name.endswith("PKG-INFO"))
        assert regular.mode == 0o644


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "../escape",
        "/absolute",
        "root\\windows",
        "package-0.2.0rc2/a//b",
        "package-0.2.0rc2/a/./b",
        "package-0.2.0rc2/control\nname",
    ],
)
def test_normalization_rejects_unsafe_paths(tmp_path: Path, unsafe_name: str) -> None:
    archive = tmp_path / "unsafe.tar.gz"
    _write_archive(archive, unsafe_name=unsafe_name)

    with pytest.raises(ValueError, match="unsafe source-distribution member"):
        normalize_sdist(archive, epoch=EPOCH)


def test_normalization_rejects_duplicate_members_and_multiple_roots(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.tar.gz"
    _write_archive(duplicate, duplicate=True)
    with pytest.raises(ValueError, match="duplicate members"):
        normalize_sdist(duplicate, epoch=EPOCH)

    multiple_roots = tmp_path / "multiple-roots.tar.gz"
    _write_archive(multiple_roots, second_root=True)
    with pytest.raises(ValueError, match="exactly one top-level root"):
        normalize_sdist(multiple_roots, epoch=EPOCH)


def test_normalization_rejects_links_and_nonregular_input(tmp_path: Path) -> None:
    archive = tmp_path / "linked-member.tar.gz"
    _write_archive(archive, link=True)
    with pytest.raises(ValueError, match="link or special member"):
        normalize_sdist(archive, epoch=EPOCH)

    real = tmp_path / "real.tar.gz"
    alias = tmp_path / "alias.tar.gz"
    _write_archive(real)
    alias.symlink_to(real)
    with pytest.raises(ValueError, match="regular file, not a symlink"):
        normalize_sdist(alias, epoch=EPOCH)

    with pytest.raises(ValueError, match="regular file, not a symlink"):
        normalize_sdist(tmp_path, epoch=EPOCH)


@pytest.mark.parametrize("epoch", [True, 315_532_799, 2**31])
def test_normalization_rejects_non_release_epoch(tmp_path: Path, epoch: object) -> None:
    archive = tmp_path / "epoch.tar.gz"
    _write_archive(archive)

    with pytest.raises(ValueError, match="1980-01-01"):
        normalize_sdist(archive, epoch=epoch)  # type: ignore[arg-type]
