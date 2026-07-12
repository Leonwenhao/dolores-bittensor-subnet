# Dolores Bittensor Subnet 0.2.0rc1 local release manifest

- Review timestamp: `2026-07-12T16:25:12Z`
- Intended tag: `v0.2.0-rc.1`
- Subnet artifact source commit:
  `c699a3e0b58c0b08c5c1e82b673d7c8caa6d7118`
- Engine artifact source commit:
  `7be1167ee0afad8857c2b3fb435dc14ad476e2a0`
- Engine evidence-manifest commit:
  `8c096196ceccd02906f21b2476c0b82737c01516`
- Local artifacts remain under each repository's ignored
  `work/releases/0.2.0rc1-final/` directory.

## Immutable artifact digests

| Distribution | Artifact | SHA-256 |
|---|---|---|
| Engine | `dolores_autocurricula-0.2.0rc1-py3-none-any.whl` | `6cc5a5e91c4fee73aa34f7d16d5905cb21366439fea8b4188f2c3db9978954fc` |
| Engine | `dolores_autocurricula-0.2.0rc1.tar.gz` | `0b552fe5c7502ab7a586622952ffac4165b1c017a449aa89149274090e852bca` |
| Subnet | `dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl` | `e87c0b0e5625585665f2b6449543b66a7b8d88175cbd4bb7cf2f1ce7c196c888` |
| Subnet | `dolores_bittensor_subnet-0.2.0rc1.tar.gz` | `8efd264de2c0b01af721993dcd1cacf8391696cedb7520b0e47ed06483a75d9e` |
| Cohort bundle | `dolores-bittensor-subnet-0.2.0rc1-release-bundle.tar.gz` | `b67691a137cabbd5ee954eea7f4076a2e8006df097c81b5fc8a45801b37c99d0` |

The subnet wheel metadata pins `bittensor==10.5.0`,
`bittensor-cli==9.23.1`, `async-substrate-interface==2.2.1`,
`websockets==16.0`, and `dolores-autocurricula==0.2.0rc1`. The supported
cohort runtime is CPython `>=3.11,<3.12`.

## Verifier image

- Default tag: `dolores-verifier-pytest:0.2.0rc1`
- Local immutable image/repository digest:
  `sha256:a9a963be4c32c57f2af3ac927fe92f45068869c9a3ea617e58df5cd81fd045c4`
- Packaged Dockerfile SHA-256:
  `dbe4e9382809e00a5805ab19310c4e7462707d3d27765445feb9654855fc973b`
- A distinct image built from the installed engine wheel verified two real
  fixtures with `executed=true` and `containerized=true`.

## Local verification receipts

| Gate | Result | Evidence |
|---|---|---|
| Engine lint and full suite | PASS | `ruff check --no-cache .`; `202 passed in 166.40s` |
| Subnet lint and full suite | PASS | Exact engine wheel installed normally; `ruff check --no-cache .`; `251 passed, 31 SDK deprecation warnings in 16.32s` |
| Engine base install | PASS | Installed canonical wheel outside the checkout; `pip check`; packaged Dockerfile resolved; DuckDB, Streamlit, PyArrow, Hypothesis, and pytest absent |
| Miner artifact boundary | PASS | Fresh `python:3.11-slim` Linux container resolved the public dependency graph and installed only the two canonical wheels; `pip check`; installed `dolores-miner` init/validate; `btcli 9.23.1`; validator-only dependencies absent |
| Validator artifact execution | PASS | Fresh `python:3.11-slim` Linux container resolved the public validator dependency graph, installed the two canonical wheels, passed `pip check`, exposed the installed CLI and panel asset, and reproduced the golden digest; a separate installed `/tmp` venv accepted the honest fixture with Docker `executed=true`, `containerized=true` |
| Golden identity | PASS | Engine-base, installed miner, installed validator, wire conversion, and extracted-sdist smokes all returned `fbf1ca8f3b9cad51370332bb1329d03b16306d4828bed9674e1a3d2a2f80a249` |
| Extracted sdist | PASS | Installed from the extracted final sdist outside the checkout with no dependencies or build isolation; import and panel asset resolved under `/tmp/dolores-final-sdist-target-c699a3e` |
| Extracted release bundle | PASS | Bundle contains only the three approved install artifacts and honest public fixture; installed miner validate and installed Docker validator `once` both passed from the extracted `/tmp` bundle |
| Ubuntu supervisor syntax | PASS | Ubuntu 24.04, systemd 255, `systemd-analyze verify` on the three units from the extracted final sdist exited zero |
| Artifact content scan | PASS | Wheel and sdist contain no work DB, generated output, internal diary/review/imported/runbook tree, credential file, private key, local user path, or active holdout material |
| Signed transport and holdout | PASS | Full suite covers installed-SDK default verification, valid/tampered signatures, stale/future nonce, replay, auth rate, request/response caps, signed HTTP smoke, semantic holdout bypass, wrong probes, and Docker holdout |
| Recurring process restart | PASS | Two fresh worker processes completed dry-run epochs 1 and 2 with canonical markers, monotonic next epoch 3, and no duplicate JSONL rows |
| Online clean Linux dependency resolution | PASS | Fresh container resolved and installed `async-substrate-interface==2.2.1` plus `websockets==16.0` from the final wheel metadata; `pip check` and imported-version assertions passed |

No provider call, provider spend, wallet file read, chain write, registration,
axon publication, live weight submission, public push, release, tag, repository
setting change, issue reply, or participant message occurred during these gates.

## Current external and human gates

| Gate | Status | Reason |
|---|---|---|
| GitHub private vulnerability reporting | `PENDING-HUMAN` | Read-back at review time remained `{"enabled":false}`; public issue #4 remained open with no comments |
| Private report receipt and triage | `PENDING-HUMAN` | The pending finding has not been received through a private channel |
| Public engine and subnet artifacts | `PENDING-HUMAN` | Engine has no remote and the subnet has unpublished local commits; publishing/tagging require approval |
| Installed CI checks | `PENDING-HUMAN` | The workflow points to the future public engine release and cannot pass until that exact asset is published |
| External HackerQuest miner | `PENDING-HUMAN` | No non-first-party participant has installed or served this RC |
| Public reachable axon and supervised restart | `PENDING-HUMAN` | Existing first-party processes still run pre-RC code and advertise stale RFC1918 endpoints |
| Two consecutive nonzero external weights | `PENDING-HUMAN` | Requires separate participant, publication, and per-epoch live-weight approvals |

## Release decision

The source and local artifacts are **conditionally ready for operator review**.
They are **not authorized for publication or participant onboarding** and are
not public-launch ready. Security intake/triage, public artifact publication,
successful public CI, RC redeployment, and external cohort proof remain explicit
gates. Controlled-cohort readiness does not imply permissionless, production,
mainnet, or training-value readiness.
