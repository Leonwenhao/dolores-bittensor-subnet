# Dolores Bittensor Subnet 0.2.0rc2 source release record

- Release candidate: `0.2.0rc2`
- Intended tag: `v0.2.0-rc.2`
- Engine repository: `https://github.com/Leonwenhao/dolores-autocurricula`
- Subnet repository: `https://github.com/Leonwenhao/dolores-bittensor-subnet`
- Intended engine release: `https://github.com/Leonwenhao/dolores-autocurricula/releases/tag/v0.2.0-rc.2`
- Intended subnet release: `https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/tag/v0.2.0-rc.2`

This tracked document defines the RC2 release contract without pretending that
local build evidence is hosted release evidence. The engine RC2 input is frozen
below. The final subnet source SHA, artifact sizes, SHA-256 values, hosted-CI
URLs, public-download receipts, and platform-scoped hosted verifier image
identity remain unresolved until the immutable RC2 source and release objects
exist. Those final values belong in the external asset
`dolores-bittensor-subnet-0.2.0rc2-release-manifest.md`.

## Frozen engine RC2 input

| Field | Exact input |
|---|---|
| Engine source SHA | `7998603deac3b18d8c2ee5ef7f2756f6b1a38972` |
| Intended engine tag | `v0.2.0-rc.2` |
| Engine wheel | `dolores_autocurricula-0.2.0rc2-py3-none-any.whl` |
| Engine wheel size | `99934` bytes |
| Engine wheel SHA-256 | `8991fae7ad8ffce29391bd4c3bd48927a9a962e832104b019f28890799ff356c` |
| Engine source distribution | `dolores_autocurricula-0.2.0rc2.tar.gz` |
| Engine source distribution size | `111467` bytes |
| Engine source distribution SHA-256 | `c9088a30e53a39e85c096968de1d1db1380c57009670ad7bce1e6661c4ca5475` |
| Packaged engine Dockerfile SHA-256 | `4e860cc6717adf8b00af863a3fc2441d13fcc6369ae359b3644388258482d377` |
| Engine `SOURCE_DATE_EPOCH` | `1783968000` |
| Local three-build Linux/AMD64 image ID | `sha256:908267dba8c87033821f2e4c89788fbf9e3ea8c3d2e7498094201ec2a399336a` |
| Engine RC2 hosted CI and release | `PENDING-STOP` |

The local image ID is a reproducibility receipt for the stated Linux/AMD64
build only. It is not a hosted image identity, a public-download receipt, or a
subnet release hash. Engine RC2 publication and public read-back remain
`PENDING-STOP`.

## Immutable publication contract

Every URL below is deterministic and versioned. A missing URL, mutable branch
archive, local wheel, private attachment, or digest mismatch is a hard stop.

### Engine assets

Intended base URL:
`https://github.com/Leonwenhao/dolores-autocurricula/releases/download/v0.2.0-rc.2/`

| Role | Immutable asset name |
|---|---|
| Engine wheel | `dolores_autocurricula-0.2.0rc2-py3-none-any.whl` |
| Engine source distribution | `dolores_autocurricula-0.2.0rc2.tar.gz` |
| External release manifest | `dolores-autocurricula-0.2.0rc2-release-manifest.md` |
| Checksum sidecar | `dolores-autocurricula-0.2.0rc2-SHA256SUMS` |

### Subnet assets

Intended base URL:
`https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/download/v0.2.0-rc.2/`

| Role | Immutable asset name |
|---|---|
| Subnet wheel | `dolores_bittensor_subnet-0.2.0rc2-py3-none-any.whl` |
| Normalized subnet source distribution | `dolores_bittensor_subnet-0.2.0rc2.tar.gz` |
| Deterministic release bundle | `dolores-bittensor-subnet-0.2.0rc2-release-bundle.tar.gz` |
| External release manifest | `dolores-bittensor-subnet-0.2.0rc2-release-manifest.md` |
| Checksum sidecar | `dolores-bittensor-subnet-0.2.0rc2-SHA256SUMS` |
| External provenance | `dolores-bittensor-subnet-0.2.0rc2-provenance.json` |
| Clean-VPS rehearsal receipt | `dolores-bittensor-subnet-0.2.0rc2-vps-rehearsal.md` |
| Exact external checklist | `dolores-bittensor-subnet-0.2.0rc2-cohort-checklist.md` |
| Participant handoff | `hackerquest-handoff-0.2.0rc2.md` |

The external assets are generated in a non-circular order after one final subnet
source commit is frozen and two independent builds match byte-for-byte. First,
primary payload/checksum/provenance material and the engine manifest become
public and are re-downloaded. A separately approved clean VPS consumes that
public trust set and produces the sanitized rehearsal receipt. Then the exact
checklist pins the receipt, the subnet manifest pins the checklist, and the
participant handoff pins both manifests, the receipt, sidecars, provenance, and
checklist. No document lists its own digest; GitHub's release-asset digest
anchors the downloaded handoff itself.

## Runtime and dependency contract

- Participant OS: Ubuntu `24.04 LTS`, `amd64`.
- Participant Python: CPython `3.11.15`.
- Package Python constraint: CPython `>=3.11,<3.12`.
- `bittensor==10.5.0`
- `bittensor-cli==9.23.1`
- `async-substrate-interface==2.2.1`
- `websockets==16.0`
- `dolores-autocurricula==0.2.0rc2`
- Subnet build epoch: `SOURCE_DATE_EPOCH=1783969800`.
- Network and subnet: `network=test`, `netuid=523`.

The miner base install does not include Docker, DuckDB, PyArrow, Streamlit,
Fireworks credentials, a solver panel, or validator-only dependencies. Docker
verification and the secret-keyed validator holdout run only on the validator.
The disposable first-party proof may temporarily colocate both service accounts
under the exact public `docs/vps-rehearsal.md` profile. Its manual endpoint,
chain-off commands, and drop-ins are not the participant topology or metagraph
cohort evidence, and their removal is part of the receipt.

Verifier image identity is platform-scoped. The external manifest must record
the packaged Dockerfile SHA-256, base-image digest, host architecture, and the
image ID observed on each rehearsed architecture. An ARM64 image ID must not be
presented as the expected AMD64 VPS identity.

## Evidence required in the external manifest

The immutable external manifest must record all of the following from the final
source commits rather than copying pre-freeze receipts:

1. exact engine and subnet source SHAs and tag targets;
2. exact artifact names, sizes, and SHA-256 values;
3. two-build byte identity for both wheels and normalized source distributions;
4. release-bundle membership, nested checksums, provenance, and golden task
   digest;
5. final engine and subnet Ruff/test results;
6. clean miner, clean validator, extracted-sdist, Docker holdout, signed HTTP,
   replay/tamper, recurring restart, and real-systemd receipts;
7. hosted GitHub Actions URLs for the exact tagged source SHAs;
8. public HTTPS re-download and checksum verification receipts;
9. Ubuntu 24.04 AMD64 VPS rehearsal identity, service lifecycle, teardown, and
   continuing-cost state;
10. every remaining human or external gate without converting it to `PASS`.

## Security truth and publication decision

| Gate | Status | Evidence or consequence |
|---|---|---|
| Private vulnerability reporting channel | `PASS` | Enabled and read back as `{"enabled":true}` at `2026-07-12T19:32:08Z`. |
| Public-safe reporter notification | `PASS` | Issue comment `4952486451` posted at `2026-07-12T19:34:46Z`; issue #4 then closed. |
| Private report receipt | `PENDING-HUMAN` | No private advisory identifier has been received or claimed. |
| Private report triage | `PENDING-HUMAN` | No finding, affected-RC decision, owner, or disposition has been received or claimed. |
| Accepted-risk RC2 publication decision | `PENDING-HUMAN` | The earlier accepted-risk publication approval does not authorize this RC2 publication. |

The accepted-risk publication decision does not change either pending security
row to `PASS`, does not imply that no finding exists, and does not make the
release `cohort-ready`. Participant contact, registration, axon publication,
live weights, and amplification remain separate approvals.

## Current release gates

| Gate | Status |
|---|---|
| Engine RC2 hosted CI, tag, release, and public asset verification | `PENDING-STOP` |
| Subnet RC2 hosted CI, tag, release, and public asset verification | `PENDING-STOP` |
| RC1 diagnostic clean-VPS rehearsal | `FAIL` — validator path failed after miner transport, signed cross-host probing, and miner systemd passed; teardown/read-back completed; historical diagnostic only, not RC2 evidence |
| RC2 external miner traction | None claimed |
| RC2 registration or axon publication | Not executed |
| RC2 live weights | Not executed |

The RC2 refreeze intentionally leaves final subnet source identity, artifact
sizes and hashes, bundle identity, provenance identity, and hosted evidence
unfilled. They must be measured from the final frozen subnet commit. If an
immutable RC2 collision appears or a defect is found after publication, do not
replace assets: deprecate RC2, bump both dependent surfaces consistently, and
rebuild the complete release chain.

Nothing in this tracked record authorizes repository creation, commit, push,
tag, release publication, VPS provisioning, participant contact, wallet action,
chain action, axon publication, live weights, provider access or spend, or
amplification.
