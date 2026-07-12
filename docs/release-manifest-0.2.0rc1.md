# Dolores Bittensor Subnet 0.2.0rc1 local release manifest

- Review timestamp: `2026-07-12T19:34:46Z`
- Intended tag: `v0.2.0-rc.1`
- Current canonical subnet artifact source commit:
  `30475e724a1e04ed34c8640a02be655b41794d35`
- Intended tag target: pending private report receipt, triage, and any required
  rebuild; no tag is currently authorized.
- Engine public artifact source commit:
  `814d9bcc451a36db1b341c2ddd6f27d1aaed565b`
- Fixed build epoch: `SOURCE_DATE_EPOCH=1783869698`
- Canonical local artifacts:
  `work/releases/0.2.0rc1-final/`

This manifest is intentionally outside the subnet source distribution. It can
record the exact source commit and artifact digests without making the packaged
checklist self-referential. The canonical artifacts remain a pre-triage local
candidate. If private triage changes source or public evidence, rebuild and
rehash them before selecting a tag target.

## Immutable artifact digests

| Distribution | Artifact | SHA-256 |
|---|---|---|
| Engine | `dolores_autocurricula-0.2.0rc1-py3-none-any.whl` | `a6cc2ce41c867e221e2ecbe44a9168d8235a609c81a487b18d055946c3d35078` |
| Engine | `dolores_autocurricula-0.2.0rc1.tar.gz` | `9d1c48174ed19600774b0c85cc8f34f9e9fa6035f28334172e3a5b491d99e12a` |
| Subnet | `dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl` | `3da6ce1d8ecdad28b0cf17a99e3d8fac0fccdf2b046485b0d360283823492541` |
| Subnet | `dolores_bittensor_subnet-0.2.0rc1.tar.gz` | `600570d150f870033d806665f16b73df8c3092b5949a9881e857bed5621af14a` |
| Cohort bundle | `dolores-bittensor-subnet-0.2.0rc1-release-bundle.tar.gz` | `8c2c1b427ee4a07be932835d9488cdf5416110e5eec860eb34b0e83ec5f173f9` |

The bundle's published SHA-256 is the authenticity trust anchor. Verify that
external digest before extraction. Its embedded `SHA256SUMS` and
`provenance.json` then provide corruption detection and exact nested provenance;
they do not independently authenticate an untrusted download.

The subnet wheel metadata pins `bittensor==10.5.0`,
`bittensor-cli==9.23.1`, `async-substrate-interface==2.2.1`,
`websockets==16.0`, and `dolores-autocurricula==0.2.0rc1`. The supported cohort
runtime is CPython `>=3.11,<3.12`.

## Verifier image

- Default tag: `dolores-verifier-pytest:0.2.0rc1`
- Reproducible image ID:
  `sha256:ac7a99b6f218563c6ea2f701e0ae4727854d998220fa6bfa5a90b78af4dec4e5`
- Packaged Dockerfile SHA-256:
  `219605da24bf86862b20802f07315ab5869ca402e0810e5c12e4e8aeb1e017a0`
- Base image:
  `python:3.11-slim@sha256:e031123e3d85762b141ad1cbc56452ba69c6e722ebf2f042cc0dc86c47c0d8b3`

Two different tags built from the installed public engine wheel produced the
same image ID. A fresh validator installation then accepted the honest fixture
with this exact image and `executed=true`, `containerized=true`.

## Local verification receipts

| Gate | Result | Evidence |
|---|---|---|
| Engine history-clean boundary | PASS | Seven-commit orphan public history rooted at `6ddf86f15998768aaa55e07dabe007dc52a80897`; noreply author metadata; no reachable internal diary, Fable, local-path, credential, or internal-main ancestry |
| Engine lint and full suite | PASS | Public checkout: `ruff check --no-cache .`; `203 passed in 160.97s`; extracted canonical sdist fresh venv: `203 passed in 156.97s`; `pip check` clean |
| Subnet lint and full suite | PASS | New engine wheel installed normally from hash `a6cc2ce…`; `ruff check --no-cache .`; `285 passed, 43 SDK deprecation warnings in 38.54s` |
| Reproducible subnet build | PASS | Two independent `git archive` extracts of `30475e7…` built with CPython 3.11.15, `build==1.5.1`, `setuptools==83.0.0`, `wheel==0.47.0`, and fixed epoch; wheel and normalized sdist were byte-identical |
| Deterministic release bundle | PASS | Two builds were byte-identical; seven canonical members; exact nested artifact names and metadata; semantic `task.yaml`/`wire.json` equality; canonical outer encoding; embedded provenance and six checksum lines all verified |
| Engine base install | PASS | Installed canonical wheel outside the checkout; `pip check`; packaged Dockerfile resolved; DuckDB, Streamlit, PyArrow, Hypothesis, and pytest absent |
| Miner artifact boundary | PASS | Fresh macOS venv and fresh pinned Linux ARM64 container installed the two canonical wheels; `pip check`; installed `dolores-miner` init/validate; `btcli 9.23.1`; validator-only dependencies absent; golden digest reproduced |
| Validator artifact boundary | PASS | Fresh macOS venv and fresh pinned Linux ARM64 container installed validator extras; `pip check`; installed CLI and panel asset resolved; exact Bittensor/transport pins and golden digest reproduced |
| Validator Docker execution | PASS | Fresh installed validator accepted the honest fixture with the exact verifier image above, `executed=true`, and `containerized=true` |
| Extracted sdist | PASS | Fresh venv built and installed the normalized final sdist with its exact pinned build backend, imported from site-packages, passed `pip check`, and validated the honest fixture outside the checkout |
| Golden identity | PASS | Engine base, installed miner, installed validator, subnet wire conversion, extracted sdist, and bundle fixture returned `fbf1ca8f3b9cad51370332bb1329d03b16306d4828bed9674e1a3d2a2f80a249` |
| Ubuntu supervisor syntax | PASS | Ubuntu 24.04, systemd `255.4-1ubuntu8.16`; `systemd-analyze verify` on all three units from the extracted final sdist exited zero with expected executable placeholders |
| Artifact content and metadata | PASS | Wheel RECORD verified; sdist ownership, modes, ordering, and mtimes normalized; no work DB, generated output, internal notes, credential file, private key, local user path, active holdout material, or stale release manifest packaged |
| Signed transport and holdout | PASS | Full suite covers installed-SDK verification, real HTTP invalid signature/stale nonce/replay rejection before forwarding, signed response binding, caps, real Docker author-tests-before-private-holdout ordering, wrong probes, and semantic holdout bypass rejection |
| Axon publication behavior | PASS | Fake-chain receipts prove exact `network=test`, `netuid=523`, successful `serve_axon`, retry/read-back, and fail-closed mismatch; a separate serve-path test proves exact `bt.Axon` external-IP/port construction |
| Recurring process restart | PASS | Hard child-process exit after one fsynced evaluation row followed by a fresh process completed epoch 2; epoch 1 remained single, failed, and was not resubmitted |

No provider call, provider spend, wallet file read, chain write, registration,
axon publication, live weight submission, public push, release, tag, repository
setting change, issue reply, participant message, or existing-process stop occurred
during these gates.

## Current external and human gates

| Gate | Status | Reason |
|---|---|---|
| Private vulnerability reporting channel | `PASS` | Approved enablement followed by GitHub API read-back `{"enabled":true}` at `2026-07-12T19:32:08Z` |
| Public-safe reporter notification | `PASS` | Exact approved notice posted by `Leonwenhao` as issue comment `4952486451` at `2026-07-12T19:34:46Z`; live read-back matched and no duplicate was posted |
| Private report receipt | `PENDING-HUMAN` | Issue #4 remains open after the intake notice; no private advisory identifier has been received |
| Private report triage | `PENDING-HUMAN` | Requires the private report, affected-RC assessment, owner, disposition, and any regression evidence |
| Public engine and subnet artifacts | `PENDING-HUMAN` | Engine has no remote and both repositories have unpublished local commits; remote creation, push, release, and tag require approval |
| Hosted CI checks | `PENDING-HUMAN` | The workflow consumes the future public engine asset and cannot pass remotely until that exact asset exists |
| External HackerQuest miner | `PENDING-HUMAN` | No non-first-party participant has installed or served this RC |
| Public reachable axon and supervised restart | `PENDING-HUMAN` | Read-only block `7544717` still showed uid 1/2 inactive at `192.168.1.94:8091/8092`, with zero incentive/dividends; existing processes were not stopped or replaced |
| Authoritative health receipt | `PENDING-HUMAN` | Requires timestamped supervisor status, complete redacted miner doctor, metagraph discovery, and default signed `dolores-validator health` reachability after a controlled restart |
| Two consecutive nonzero external weights | `PENDING-HUMAN` | Requires a separate participant, publication approval, and separate per-epoch live-weight approvals |

The same read-only testnet snapshot at `2026-07-12T17:46:50Z` showed validator
uid 0 inactive with no axon, `last_update=7521406`, and raw
`Weights[523,0]=[[1,65535]]`; commit-reveal remained disabled. These public
facts preserve the historical weight receipt but do not satisfy current service
health or external-cohort proof.

## Release decision

The source and canonical local artifacts are **conditionally ready for operator
review**. They are **not authorized for publication or participant onboarding**
and are not public-launch ready. Private report receipt/triage, public artifact
publication, successful hosted CI, RC redeployment, authoritative external
health, and two consecutive nonzero external-miner epochs remain explicit gates.
Controlled-cohort readiness does not imply permissionless, production, mainnet,
or training-value readiness.
