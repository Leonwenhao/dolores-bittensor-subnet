#!/usr/bin/env python3
"""Rewrite a source distribution with deterministic, safe tar metadata."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import stat
import tarfile
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class _Member:
    name: str
    is_directory: bool
    executable: bool
    data: bytes


def _safe_name(name: str) -> str:
    has_control_character = any(
        ord(character) < 32 or ord(character) == 127 for character in name
    )
    if not name or "\\" in name or has_control_character:
        raise ValueError(f"unsafe source-distribution member: {name!r}")
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in name.split("/"))
        or name != path.as_posix()
    ):
        raise ValueError(f"unsafe source-distribution member: {name!r}")
    return path.as_posix()


def _read_members(source: Path) -> list[_Member]:
    try:
        source_stat = source.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"source distribution does not exist: {source}") from exc
    if source.is_symlink() or not stat.S_ISREG(source_stat.st_mode):
        raise ValueError("source distribution must be a regular file, not a symlink")

    try:
        with tarfile.open(source, "r:gz") as archive:
            raw_members = archive.getmembers()
            names = [_safe_name(member.name) for member in raw_members]
            if not names:
                raise ValueError("source distribution is empty")
            if len(names) != len(set(names)):
                raise ValueError("source distribution contains duplicate members")
            roots = {PurePosixPath(name).parts[0] for name in names}
            if len(roots) != 1:
                raise ValueError("source distribution must have exactly one top-level root")

            members: list[_Member] = []
            for member, name in zip(raw_members, names, strict=True):
                if not (member.isdir() or member.isfile()):
                    raise ValueError("source distribution contains a link or special member")
                handle = archive.extractfile(member) if member.isfile() else None
                if member.isfile() and handle is None:
                    raise ValueError(f"could not read source-distribution member: {name!r}")
                members.append(
                    _Member(
                        name=name,
                        is_directory=member.isdir(),
                        executable=bool(member.mode & 0o111),
                        data=handle.read() if handle is not None else b"",
                    )
                )
    except (OSError, tarfile.TarError) as exc:
        raise ValueError(f"invalid source distribution: {exc}") from exc
    return sorted(members, key=lambda member: member.name)


def normalize_sdist(path: Path, *, epoch: int) -> str:
    """Normalize one gzip-compressed tar archive in place and return SHA-256."""

    if (
        isinstance(epoch, bool)
        or not isinstance(epoch, int)
        or not 315_532_800 <= epoch <= 2**31 - 1
    ):
        raise ValueError("epoch must be an integer from 1980-01-01 through 2038-01-19")
    members = _read_members(path)
    source = path.resolve(strict=True)

    handle, temporary_name = tempfile.mkstemp(prefix=f".{source.name}.", dir=source.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw,
                compresslevel=9,
                mtime=epoch,
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w",
                    format=tarfile.PAX_FORMAT,
                ) as output:
                    for member in members:
                        info = tarfile.TarInfo(member.name)
                        info.type = tarfile.DIRTYPE if member.is_directory else tarfile.REGTYPE
                        info.mode = 0o755 if member.is_directory or member.executable else 0o644
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        info.mtime = epoch
                        info.size = 0 if member.is_directory else len(member.data)
                        output.addfile(
                            info,
                            None if member.is_directory else BytesIO(member.data),
                        )
            raw.flush()
            os.fsync(raw.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, source)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(source.read_bytes()).hexdigest()


def _epoch_argument(value: str) -> int:
    try:
        epoch = int(value)
        if not 315_532_800 <= epoch <= 2**31 - 1:
            raise ValueError
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "epoch must be an integer from 1980-01-01 through 2038-01-19"
        ) from exc
    return epoch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--epoch", type=_epoch_argument, required=True)
    args = parser.parse_args()
    try:
        digest = normalize_sdist(args.path, epoch=args.epoch)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"sha256={digest} path={args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
