# Dolores Bittensor Subnet 0.2.0rc1 source release record

- Release candidate: `0.2.0rc1`
- Intended tag: `v0.2.0-rc.1`
- Engine repository: `https://github.com/Leonwenhao/dolores-autocurricula`
- Subnet repository: `https://github.com/Leonwenhao/dolores-bittensor-subnet`
- Engine release: `https://github.com/Leonwenhao/dolores-autocurricula/releases/tag/v0.2.0-rc.1`
- Subnet release: `https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/tag/v0.2.0-rc.1`

This tracked document defines the release contract without pretending that a
pre-freeze local build is the public release. The final source SHAs, artifact
sizes, SHA-256 values, hosted-CI URLs, public-download receipts, and
platform-scoped verifier image identity belong in the immutable external asset
`dolores-bittensor-subnet-0.2.0rc1-release-manifest.md`. The tracked checklist
and quickstart point to that asset and the checksum sidecars.

The older local subnet artifacts built from `30475e7` are superseded candidates:
their packaged security/checklist prose predates the current source. They must
not be tagged, uploaded, or described as final.

## Immutable publication contract

Every URL below is deterministic and versioned. A missing URL, mutable branch
archive, local wheel, private attachment, or digest mismatch is a hard stop.

### Engine assets

Base URL:
`https://github.com/Leonwenhao/dolores-autocurricula/releases/download/v0.2.0-rc.1/`

| Role | Immutable asset name |
|---|---|
| Engine wheel | `dolores_autocurricula-0.2.0rc1-py3-none-any.whl` |
| Engine source distribution | `dolores_autocurricula-0.2.0rc1.tar.gz` |
| External release manifest | `dolores-autocurricula-0.2.0rc1-release-manifest.md` |
| Checksum sidecar | `dolores-autocurricula-0.2.0rc1-SHA256SUMS` |

### Subnet assets

Base URL:
`https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/download/v0.2.0-rc.1/`

| Role | Immutable asset name |
|---|---|
| Subnet wheel | `dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl` |
| Normalized subnet source distribution | `dolores_bittensor_subnet-0.2.0rc1.tar.gz` |
| Deterministic release bundle | `dolores-bittensor-subnet-0.2.0rc1-release-bundle.tar.gz` |
| External release manifest | `dolores-bittensor-subnet-0.2.0rc1-release-manifest.md` |
| Checksum sidecar | `dolores-bittensor-subnet-0.2.0rc1-SHA256SUMS` |
| External provenance | `dolores-bittensor-subnet-0.2.0rc1-provenance.json` |
| Clean-VPS rehearsal receipt | `dolores-bittensor-subnet-0.2.0rc1-vps-rehearsal.md` |
| Exact external checklist | `dolores-bittensor-subnet-0.2.0rc1-cohort-checklist.md` |
| Participant handoff | `hackerquest-handoff-0.2.0rc1.md` |

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
- `dolores-autocurricula==0.2.0rc1`
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
| Accepted-risk publication decision | `PENDING-HUMAN` | Publishing while the two rows above remain pending requires one explicit `STOP-LEON` decision naming the unknown risk, exact release objects, and rollback/deprecation path. |

An accepted-risk publication decision does not change either pending security
row to `PASS`, does not imply that no finding exists, and does not make the
release `cohort-ready`. Participant contact, registration, axon publication,
live weights, and amplification remain separate approvals.

## Current release gates

| Gate | Status |
|---|---|
| Final engine source, hosted CI, tag, release, and public asset verification | `PENDING-HUMAN` |
| Final subnet source, reproducible rebuild, hosted CI, tag, release, and public asset verification | `PENDING-HUMAN` |
| Accepted-risk publication decision while security receipt/triage remain pending | `PENDING-HUMAN` |
| Clean Ubuntu 24.04 AMD64 VPS rehearsal from public assets | `PENDING-HUMAN` |
| External HackerQuest miner, public axon, and supervised restart | `PENDING-HUMAN` |
| Two consecutive nonzero external-miner epochs | `PENDING-HUMAN` and outside handoff-release completion |

The selected mechanism is a same-version RC1 rebuild because no public RC1 tag
or release exists. If an immutable RC1 collision appears or a defect is found
after publication, do not replace assets: deprecate RC1, bump both dependent
surfaces consistently, and rebuild the complete release chain.

Nothing in this tracked record authorizes repository creation, push, tag,
release publication, VPS provisioning, participant contact, wallet action, axon
publication, or live weights.
