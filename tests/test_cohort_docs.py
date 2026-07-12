from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_cohort_docs_name_authoritative_signed_endpoint_health() -> None:
    readme = _text("README.md")
    quickstart = _text("docs/hackerquest-miner-quickstart.md")
    checklist = _text("docs/cohort-release-checklist.md")

    assert "authoritative cohort endpoint health command" in readme
    assert "signed reachability enabled by default" in readme
    assert "dolores-validator health \\\n  --mode testnet" in quickstart
    assert "--network test \\\n  --netuid 523" in quickstart
    assert "A successful signed reply\nproves that the miner process is alive" in quickstart
    assert "| PENDING-HUMAN | Health evidence covers supervised process state" in checklist
    assert "do not use `--no-probe-wire`" in checklist


def test_packaged_checklist_uses_external_subnet_provenance() -> None:
    checklist = _text("docs/cohort-release-checklist.md")
    subnet_revision = next(
        line
        for line in checklist.splitlines()
        if line.startswith("| Subnet artifact source revision |")
    )
    subnet_wheel = next(
        line
        for line in checklist.splitlines()
        if line.startswith("| Subnet wheel filename and SHA-256 |")
    )

    assert "external `release-manifest-0.2.0rc1.md`" in subnet_revision
    assert "external release manifest" in subnet_wheel
    assert re.search(r"`[0-9a-f]{40}`", subnet_revision) is None
    assert re.search(r"`[0-9a-f]{64}`", subnet_wheel) is None
    assert "814d9bcc451a36db1b341c2ddd6f27d1aaed565b" in checklist
    assert "a6cc2ce41c867e221e2ecbe44a9168d8235a609c81a487b18d055946c3d35078" in checklist
    assert "219605da24bf86862b20802f07315ab5869ca402e0810e5c12e4e8aeb1e017a0" in checklist
    assert "sha256:ac7a99b6f218563c6ea2f701e0ae4727854d998220fa6bfa5a90b78af4dec4e5" in checklist
