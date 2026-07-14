from __future__ import annotations

import re
from pathlib import Path

from dolores_subnet.config import MAX_SIGNED_REQUEST_TIMEOUT_SECONDS

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


def test_packaged_checklist_uses_external_exact_release_assets() -> None:
    checklist = _text("docs/cohort-release-checklist.md")
    manifest = _text("docs/release-manifest-0.2.0rc2.md")
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

    expected_assets = (
        "dolores-autocurricula-0.2.0rc2-release-manifest.md",
        "dolores-autocurricula-0.2.0rc2-SHA256SUMS",
        "dolores-bittensor-subnet-0.2.0rc2-release-manifest.md",
        "dolores-bittensor-subnet-0.2.0rc2-SHA256SUMS",
        "dolores-bittensor-subnet-0.2.0rc2-provenance.json",
        "dolores-bittensor-subnet-0.2.0rc2-cohort-checklist.md",
        "hackerquest-handoff-0.2.0rc2.md",
    )
    for asset in expected_assets:
        assert asset in checklist or asset in manifest

    assert "external manifest" in subnet_wheel
    assert re.search(r"`[0-9a-f]{40}`", subnet_revision) is None
    assert re.search(r"`[0-9a-f]{64}`", subnet_wheel) is None
    assert "releases/download/v0.2.0-rc.2/" in manifest

    stale_values = (
        "814d9bcc451a36db1b341c2ddd6f27d1aaed565b",
        "30475e724a1e04ed34c8640a02be655b41794d35",
        "a6cc2ce41c867e221e2ecbe44a9168d8235a609c81a487b18d055946c3d35078",
        "3da6ce1d8ecdad28b0cf17a99e3d8fac0fccdf2b046485b0d360283823492541",
        "600570d150f870033d806665f16b73df8c3092b5949a9881e857bed5621af14a",
        "8c2c1b427ee4a07be932835d9488cdf5416110e5eec860eb34b0e83ec5f173f9",
        "sha256:ac7a99b6f218563c6ea2f701e0ae4727854d998220fa6bfa5a90b78af4dec4e5",
    )
    tracked_release_prose = checklist + manifest + _text(
        "docs/hackerquest-miner-quickstart.md"
    )
    for stale in stale_values:
        assert stale not in tracked_release_prose


def test_rc2_manifest_freezes_engine_input_without_inventing_subnet_output() -> None:
    manifest = _text("docs/release-manifest-0.2.0rc2.md")

    for exact_engine_input in (
        "7998603deac3b18d8c2ee5ef7f2756f6b1a38972",
        "dolores_autocurricula-0.2.0rc2-py3-none-any.whl",
        "`99934` bytes",
        "8991fae7ad8ffce29391bd4c3bd48927a9a962e832104b019f28890799ff356c",
        "dolores_autocurricula-0.2.0rc2.tar.gz",
        "`111467` bytes",
        "c9088a30e53a39e85c096968de1d1db1380c57009670ad7bce1e6661c4ca5475",
        "4e860cc6717adf8b00af863a3fc2441d13fcc6369ae359b3644388258482d377",
        "`1783968000`",
        "sha256:908267dba8c87033821f2e4c89788fbf9e3ea8c3d2e7498094201ec2a399336a",
    ):
        assert exact_engine_input in manifest

    assert "Engine RC2 hosted CI and release | `PENDING-STOP`" in manifest
    assert (
        "Subnet RC2 hosted CI, tag, release, and public asset verification "
        "| `PENDING-STOP`"
    ) in manifest
    assert "Private report receipt | `PENDING-HUMAN`" in manifest
    assert "Private report triage | `PENDING-HUMAN`" in manifest
    assert "RC1 diagnostic clean-VPS rehearsal | `FAIL`" in manifest
    assert (
        "teardown/read-back completed; historical diagnostic only, not RC2 evidence"
        in manifest
    )
    assert "RC2 external miner traction | None claimed" in manifest
    assert "RC2 registration or axon publication | Not executed" in manifest
    assert "RC2 live weights | Not executed" in manifest
    assert "final subnet source identity" in manifest


def test_security_docs_record_pending_truth_and_accepted_risk_decision() -> None:
    readme = _text("README.md")
    security = _text("SECURITY.md")
    contributing = _text("CONTRIBUTING.md")
    checklist = _text("docs/cohort-release-checklist.md")
    packet = _text("docs/security-disclosure-packet.md")
    manifest = _text("docs/release-manifest-0.2.0rc2.md")

    assert '| PASS | A private reporting channel exists. |' in checklist
    assert '`{"enabled":true}` at `2026-07-12T19:32:08Z`' in checklist
    assert "The private-channel gate is now `PASS`" in packet
    assert "## Completed public-safe notification" in packet
    assert "issue comment `4952486451`" in packet
    assert "No duplicate comment was posted" in packet
    assert "the issue is now closed" in packet
    assert "| Private vulnerability reporting channel | `PASS` |" in manifest
    assert "| Public-safe reporter notification | `PASS` |" in manifest
    assert "| Private report receipt | `PENDING-HUMAN` |" in manifest
    assert "No private advisory identifier has been received or claimed" in manifest
    assert "| Private report triage | `PENDING-HUMAN` |" in manifest
    assert "neither has occurred or been claimed" in packet

    for document in (readme, security, contributing, checklist, packet, manifest):
        assert "accepted-risk" in document
    assert "does not make the security gate" in readme
    assert "does not mark the\nsecurity gate" in security
    assert re.search(r"does\s+not make the release `cohort-ready`", packet)
    assert "does not change either pending security\nrow to `PASS`" in manifest

    all_public_security_prose = security + contributing + packet
    assert "currently disabled" not in all_public_security_prose
    assert "remains blocked until the pending private report" not in all_public_security_prose
    assert "Do not publish the cohort release" not in packet


def test_quickstart_uses_exact_immutable_public_asset_locations() -> None:
    quickstart = _text("docs/hackerquest-miner-quickstart.md")

    assert (
        "https://github.com/Leonwenhao/dolores-autocurricula/"
        "releases/download/v0.2.0-rc.2/"
    ) in quickstart
    assert (
        "https://github.com/Leonwenhao/dolores-bittensor-subnet/"
        "releases/download/v0.2.0-rc.2/"
    ) in quickstart
    for asset in (
        "dolores_autocurricula-0.2.0rc2-py3-none-any.whl",
        "dolores-autocurricula-0.2.0rc2-release-manifest.md",
        "dolores-autocurricula-0.2.0rc2-SHA256SUMS",
        "dolores_bittensor_subnet-0.2.0rc2-py3-none-any.whl",
        "dolores_bittensor_subnet-0.2.0rc2.tar.gz",
        "dolores-bittensor-subnet-0.2.0rc2-release-manifest.md",
        "dolores-bittensor-subnet-0.2.0rc2-SHA256SUMS",
        "dolores-bittensor-subnet-0.2.0rc2-provenance.json",
        "dolores-bittensor-subnet-0.2.0rc2-cohort-checklist.md",
        "hackerquest-handoff-0.2.0rc2.md",
    ):
        assert asset in quickstart

    assert "curl --fail --location --retry 3" in quickstart
    assert "sha256sum --check --strict --ignore-missing" in quickstart
    assert "python -m pip check" in quickstart
    assert "/path/to" not in quickstart
    assert "operator supplies the approved public artifact locations" not in quickstart


def test_quickstart_pins_supported_ubuntu_python_and_minimum_vps() -> None:
    quickstart = _text("docs/hackerquest-miner-quickstart.md")

    for required in (
        "Ubuntu `24.04 LTS` `amd64`",
        "2 vCPU",
        "4 GB RAM",
        "25 GB disk",
        "https://www.python.org/ftp/python/3.11.15/Python-3.11.15.tar.xz",
        "272179ddd9a2e41a0fc8e42e33dfbdca0b3711aa5abf372d3f2d51543d09b625",
        "./configure --prefix=/opt/python/3.11.15 --with-ensurepip=install",
        "sudo make altinstall",
        "/opt/python/3.11.15/bin/python3.11 --version",
        "globally routable IPv4",
        "enough public-testnet TAO",
        "exact public validator SS58 hotkey",
    ):
        assert required in quickstart

    assert "Ubuntu `docker.io` belongs\nonly on the validator host" in quickstart
    assert "The miner does **not** need Docker" in quickstart
    assert "Docker and\nthe secret-keyed private holdout run on the validator" in quickstart


def test_validator_install_uses_same_public_assets_and_validator_only_docker() -> None:
    quickstart = _text("docs/hackerquest-miner-quickstart.md")
    validator = _text("docs/validator-operations.md")

    assert "do not install it for the miner" in quickstart
    assert "sudo apt-get install -y docker.io docker-buildx" in validator
    assert "sudo docker buildx version" in validator
    assert "/opt/python/3.11.15/bin/python3.11" in validator
    assert "file:///var/tmp/dolores-0.2.0rc2/" in validator
    assert "dolores-autocurricula[validator]" in validator
    assert "dolores-bittensor-subnet[validator]" in validator
    assert "/usr/bin/env READ_ONLY=1 TMPDIR=/run/dolores-validator" in validator
    assert "Do not define `READ_ONLY` or `TMPDIR` in this file" in validator
    assert "ProtectHome=read-only" in validator
    assert "--timeout 30" in validator
    assert "DOLORES_VALIDATOR_TIMEOUT" not in validator
    assert "/absolute/path/to" not in validator


def test_validator_configuration_packet_is_sanitized_and_release_exact() -> None:
    packet = _text("docs/validator-configuration-packet.md")
    operations = _text("docs/validator-operations.md")
    source_manifest = _text("MANIFEST.in")

    assert "validator-configuration-packet.md" in operations
    assert "include docs/validator-configuration-packet.md" in source_manifest

    for required in (
        "https://github.com/Leonwenhao/dolores-autocurricula/releases/download/$TAG",
        "https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/download/$TAG",
        "https://github.com/Leonwenhao/dolores-autocurricula/releases/tag/$TAG",
        "https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/tag/$TAG",
        'export TAG="v0.2.0-rc.2"',
        'export RELEASE_SOURCE="$DOWNLOAD_DIR/dolores_bittensor_subnet-0.2.0rc2"',
        "hackerquest-handoff-0.2.0rc2.md",
        "sha256sum --check --strict --ignore-missing",
        "Ubuntu `24.04 LTS` `amd64`",
        "CPython `3.11.15`",
        "/opt/python/3.11.15/bin/python3.11",
        "/etc/dolores/validator.env",
        "DOLORES_HOLDOUT_SECRET=<64_OR_MORE_LOWERCASE_HEX_CHARACTERS>",
        "BT_WALLET_NAME=<VALIDATOR_WALLET_NAME>",
        "BT_WALLET_HOTKEY=<VALIDATOR_HOTKEY_NAME>",
        "/etc/systemd/system/dolores-validator.service",
        "/etc/systemd/system/dolores-validator.timer",
        "dolores-verifier-pytest:0.2.0rc2",
        "VERIFIER_SOURCE_DATE_EPOCH=1783968000",
        "docker buildx version",
        "docker buildx build",
        "--no-cache",
        'rewrite-timestamp=true',
        'docker load --input "$VERIFIER_ARCHIVE"',
        "--network test",
        "--netuid 523",
        "--chain dry-run",
        "--panel-mode mock",
        "/usr/bin/env READ_ONLY=1 TMPDIR=/run/dolores-validator",
        "'^(READ_ONLY|TMPDIR)='",
        "ProtectHome=read-only",
        "--timeout 30",
        "executed=true",
        "containerized=true",
        "Safe to share after review:",
        "Never share:",
        "real systemd behavior",
        "`PENDING-HUMAN`",
    ):
        assert required in packet

    for forbidden in (
        "DOLORES_ALLOW_EXTRINSICS",
        "--allow-extrinsics",
        "--chain live",
        "--miner-endpoints",
        "DOLORES_REPO=",
        "PYTHONPATH=",
        "DOLORES_VALIDATOR_TIMEOUT",
    ):
        assert forbidden not in packet


def test_chain_neutral_vps_rehearsal_is_public_asset_only_and_bounded() -> None:
    rehearsal = _text("docs/vps-rehearsal.md")
    manifest = _text("MANIFEST.in")

    for required in (
        "Ubuntu 24.04 LTS",
        "amd64",
        "docs/vps-rehearsal.md",
        "dolores-miner-chain-neutral-rehearsal.conf",
        "dolores-validator-chain-neutral-rehearsal.conf",
        "DOLORES_REHEARSAL_MINER_ENDPOINT",
        "dolores-validator probe-wire",
        '"chain_mode": "off"',
        "dolores-validator replay",
        "PrivateTmp=true",
        "TMPDIR=/run/dolores-validator",
        "systemctl enable --now dolores-validator.timer",
        "DropInPaths",
        "registration=not_executed",
        "axon_publish=skipped reason=no_publish_flag",
        "No `scp`",
        "no chain write is authorized",
        "never external-miner or cohort evidence",
        "sudo apt-get install -y jq docker.io docker-buildx",
        "sudo docker buildx version",
        "/usr/bin/env READ_ONLY=1 TMPDIR=/run/dolores-validator",
        "'^(READ_ONLY|TMPDIR)='",
        "ProtectHome=read-only",
        "--timeout 30",
        "assert state['active_epoch_id'] == state['last_completed_epoch']",
        "assert state['phase'] == 'committed'",
        "assert state['next_epoch_id'] == state['last_completed_epoch'] + 1",
    ):
        assert required in rehearsal

    for required in (
        "include deploy/systemd/dolores-miner-chain-neutral-rehearsal.conf",
        "include deploy/systemd/dolores-validator-chain-neutral-rehearsal.conf",
        "include docs/vps-rehearsal.md",
    ):
        assert required in manifest

    for forbidden in (
        "  --execute \\",
        "  --confirm REGISTER-TESTNET-523",
        "  --publish \\",
        "--chain live",
        "--allow-extrinsics",
        "--allow-provider-spend",
        "--allow-commit-reveal",
        "DOLORES_VALIDATOR_TIMEOUT",
        "assert state['active_epoch_id'] is None",
        "assert state['phase'] is None",
    ):
        assert forbidden not in rehearsal


def test_rehearsal_timeout_never_exceeds_miner_policy() -> None:
    rehearsal = _text("docs/vps-rehearsal.md")
    timeouts = [float(value) for value in re.findall(r"--timeout ([0-9.]+)", rehearsal)]

    assert timeouts
    assert max(timeouts) <= MAX_SIGNED_REQUEST_TIMEOUT_SECONDS


def test_quickstart_contains_exact_unsigned_commands_and_expected_outputs() -> None:
    quickstart = _text("docs/hackerquest-miner-quickstart.md")

    required_commands = (
        "dolores-miner init \\",
        '--seed 730214',
        'dolores-miner validate --task-dir "$TASK_DIR"',
        "dolores-miner register \\",
        "registration=not_executed",
        "dolores-miner serve \\",
        "axon_publish=skipped reason=no_publish_flag",
        "health --host 127.0.0.1 --port 8091",
        "healthy=true endpoint=127.0.0.1:8091 attempts_used=1",
        "sudo systemctl enable --now dolores-miner.service",
        "sudo systemctl restart dolores-miner.service",
        "sudo journalctl -u dolores-miner.service --no-pager -n 100",
        "dolores-validator health \\",
    )
    for command in required_commands:
        assert command in quickstart

    assert "task_dir=..." in quickstart
    assert "tests=author_tests validator_holdout=private" in quickstart
    assert "VALID task_id=" in quickstart
    assert "family=parser_roundtrip" in quickstart


def test_quickstart_has_stop_gates_troubleshooting_and_handoff_message() -> None:
    quickstart = _text("docs/hackerquest-miner-quickstart.md")

    assert "### STOP-LEON: human registration action" in quickstart
    assert "--execute \\\n  --confirm REGISTER-TESTNET-523" in quickstart
    assert "### STOP-LEON: human axon-publication action" in quickstart
    assert "Registration approval is\nnot publication approval" in quickstart

    for heading in (
        "### Python version",
        "### Checksum mismatch",
        "### Wallet ownership",
        "### Port or firewall",
        "### Version mismatch",
        "### Registration",
        "### Axon read-back",
        "### Service restart",
        "### Validator reachability",
    ):
        assert heading in quickstart

    assert "Safe to share with the cohort operator:" in quickstart
    assert "Never share:" in quickstart
    assert "## 12. Ready-to-send HackerQuest message" in quickstart
    assert "This request is a handoff rehearsal, not a" in quickstart
    assert "successful weight epochs\n> already exist" in quickstart
