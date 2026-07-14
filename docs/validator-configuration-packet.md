# Controlled-Cohort Validator Configuration Packet

Status: sanitized operator worksheet for Dolores `0.2.0rc2`. It fixes every
public target and release location while leaving wallet selectors and the private
holdout secret for the operator to enter locally.

This packet configures a validator only for `network=test`, `netuid=523`, with
`--chain dry-run --panel-mode mock`. It does not authorize a wallet action, axon
publication, live weights, provider spend, VPS access, or participant contact.

The pre-participant, chain-neutral, real-systemd validation profile is a
different surface documented in [`vps-rehearsal.md`](vps-rehearsal.md). Manual
endpoints from that disposable first-party proof never become public-testnet
metagraph or cohort evidence.

## 1. Immutable release and trust path

Use the two `v0.2.0-rc.2` GitHub Releases. Engine RC2 hosted CI/release and
subnet RC2 hosted CI/release both remain `PENDING-STOP`; do not run
these release commands until both exact public objects and the handoff exist.
Do not substitute a branch archive, editable install, local wheel transfer,
private attachment, adjacent checkout, `DOLORES_REPO`, or `PYTHONPATH`.

```bash
export TAG="v0.2.0-rc.2"
export ENGINE_RELEASE="https://github.com/Leonwenhao/dolores-autocurricula/releases/tag/$TAG"
export SUBNET_RELEASE="https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/tag/$TAG"
export ENGINE_BASE="https://github.com/Leonwenhao/dolores-autocurricula/releases/download/$TAG"
export SUBNET_BASE="https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/download/$TAG"
export DOWNLOAD_DIR="/var/tmp/dolores-0.2.0rc2"
export RELEASE_SOURCE="$DOWNLOAD_DIR/dolores_bittensor_subnet-0.2.0rc2"

export ENGINE_WHEEL="dolores_autocurricula-0.2.0rc2-py3-none-any.whl"
export ENGINE_SDIST="dolores_autocurricula-0.2.0rc2.tar.gz"
export ENGINE_MANIFEST="dolores-autocurricula-0.2.0rc2-release-manifest.md"
export ENGINE_SUMS="dolores-autocurricula-0.2.0rc2-SHA256SUMS"

export SUBNET_WHEEL="dolores_bittensor_subnet-0.2.0rc2-py3-none-any.whl"
export SUBNET_SDIST="dolores_bittensor_subnet-0.2.0rc2.tar.gz"
export SUBNET_BUNDLE="dolores-bittensor-subnet-0.2.0rc2-release-bundle.tar.gz"
export SUBNET_MANIFEST="dolores-bittensor-subnet-0.2.0rc2-release-manifest.md"
export SUBNET_SUMS="dolores-bittensor-subnet-0.2.0rc2-SHA256SUMS"
export SUBNET_PROVENANCE="dolores-bittensor-subnet-0.2.0rc2-provenance.json"
export SUBNET_CHECKLIST="dolores-bittensor-subnet-0.2.0rc2-cohort-checklist.md"
export HANDOFF="hackerquest-handoff-0.2.0rc2.md"
```

Download every named asset with the commands in
[`hackerquest-miner-quickstart.md`](hackerquest-miner-quickstart.md), section 2.
The trust order is mandatory:

1. compare the downloaded handoff's SHA-256 with GitHub's release-asset digest;
2. compare both checksum-sidecar digests with the verified handoff;
3. run `sha256sum --check --strict --ignore-missing` on both sidecars;
4. run the handoff's exact checks for both manifests, subnet provenance, and the
   external checklist;
5. compare source SHAs, Dockerfile digest, platform-scoped image identity, and
   pending gates with the verified subnet manifest.

Stop if any object, digest, final hosted-CI URL, or expected source SHA is
missing or different. A hash copied from this source document is not a release
trust anchor.

## 2. Supported validator host

- Fresh Ubuntu `24.04 LTS` `amd64`.
- CPython `3.11.15` installed at `/opt/python/3.11.15/bin/python3.11` by the
  exact source URL, hash, and `make altinstall` method in the miner quickstart.
- At least 2 vCPU, 4 GB RAM, and 25 GB disk.
- A non-root `dolores-validator` service account with no interactive workload.
- Docker installed only on the validator host. Docker-group membership is
  root-equivalent access to the daemon and must remain narrowly scoped.
- An operator-controlled validator wallet and hotkey registered on public
  Bittensor testnet for netuid 523. Wallet creation and password entry remain
  human-terminal actions.

The engine and subnet validator extras must be installed from the already
verified public wheels into the root-owned virtual environment described in
[`validator-operations.md`](validator-operations.md). Then record only the
public-safe result of these checks:

```bash
sudo /opt/dolores-validator/venv/bin/python -m pip check
sudo -u dolores-validator /opt/dolores-validator/venv/bin/python - <<'PY'
import importlib.metadata as metadata
from pathlib import Path

import dolores
import dolores_subnet

root = Path("/opt/dolores-validator/venv").resolve()
assert metadata.version("dolores-autocurricula") == "0.2.0rc2"
assert metadata.version("dolores-bittensor-subnet") == "0.2.0rc2"
assert Path(dolores.__file__).resolve().is_relative_to(root)
assert Path(dolores_subnet.__file__).resolve().is_relative_to(root)
print(f"engine=0.2.0rc2 path={dolores.__file__}")
print(f"subnet=0.2.0rc2 path={dolores_subnet.__file__}")
PY
```

Expected: `pip check` reports no broken requirements, and both import paths are
under `/opt/dolores-validator/venv` rather than a checkout.

## 3. Packaged verifier identity

Resolve the Dockerfile from the installed engine wheel, build the fixed image
with the release's timestamp-normalized Buildx recipe, and compare all printed
identity values with the immutable subnet manifest:

```bash
VERIFIER_DOCKERFILE="$(sudo -H -u dolores-validator \
  /opt/dolores-validator/venv/bin/python -c \
  'from dolores.verifier.docker_runner import _dockerfile_path; print(_dockerfile_path())')"
export VERIFIER_SOURCE_DATE_EPOCH=1783968000
export VERIFIER_ARCHIVE=/var/tmp/dolores-verifier-pytest-0.2.0rc2.tar
test -f "$VERIFIER_DOCKERFILE"
sha256sum "$VERIFIER_DOCKERFILE"
sudo -H -u dolores-validator docker buildx version
sudo -H -u dolores-validator rm -f "$VERIFIER_ARCHIVE"
sudo -H -u dolores-validator docker buildx build \
  --no-cache \
  --provenance=false \
  --platform linux/amd64 \
  --build-arg "SOURCE_DATE_EPOCH=$VERIFIER_SOURCE_DATE_EPOCH" \
  --file "$VERIFIER_DOCKERFILE" \
  --tag dolores-verifier-pytest:0.2.0rc2 \
  --output "type=docker,dest=$VERIFIER_ARCHIVE,rewrite-timestamp=true" \
  "$(dirname "$VERIFIER_DOCKERFILE")"
sudo -H -u dolores-validator docker load --input "$VERIFIER_ARCHIVE"
sudo -H -u dolores-validator docker image inspect \
  --format '{{.Os}}/{{.Architecture}} {{.Id}}' \
  dolores-verifier-pytest:0.2.0rc2
```

The refrozen engine input pins Dockerfile SHA-256
`4e860cc6717adf8b00af863a3fc2441d13fcc6369ae359b3644388258482d377`,
source epoch `1783968000`, and the successful independent local
`linux/amd64` Buildx image ID
`sha256:908267dba8c87033821f2e4c89788fbf9e3ea8c3d2e7498094201ec2a399336a`.
The hosted RC2 image identity remains `PENDING-STOP`; use the final public
engine manifest as the participant trust anchor rather than treating the local
receipt as hosted evidence.

Do not compare an ARM64 development image ID with the required AMD64 identity.
Do not set a source-tree Dockerfile override. A direct build that omits the
fixed source epoch or timestamp-rewritten Docker archive does not satisfy the
release image-identity comparison. The honest fixture must later record
`executed=true` and `containerized=true`; author-test success without the
validator-private holdout is not sufficient.

## 4. Protected service configuration

Create the environment file exactly as described in the validator operations
runbook: directory mode `0750`, file mode `0640`, owner `root`, group
`dolores-validator`. Open it with `sudoedit`; never build it with `echo`, paste it
into chat, or display it with `cat`, a bare `env`/`printenv` dump,
`systemctl show`, or a shell trace.

The following is a field template, not an executable secret. Replace every
angle-bracketed value inside the secure editor. Encode at least 32 random secret
bytes as 64 or more lowercase hexadecimal characters so the value is safe for
both systemd's environment-file parser and the read-only shell wrapper below:

```dotenv
DOLORES_HOLDOUT_SECRET=<64_OR_MORE_LOWERCASE_HEX_CHARACTERS>
BT_WALLET_NAME=<VALIDATOR_WALLET_NAME>
BT_WALLET_HOTKEY=<VALIDATOR_HOTKEY_NAME>
DOLORES_VALIDATOR_QUOTA=4
```

Wallet selector names must contain no whitespace. Confirm only ownership, mode,
and required-field presence; do not print values:

```bash
sudo stat --format='%U %G %a %n' /etc/dolores/validator.env
sudo grep --quiet --extended-regexp \
  '^DOLORES_HOLDOUT_SECRET=[0-9a-f]{64,}$' /etc/dolores/validator.env
sudo grep --quiet --extended-regexp \
  '^BT_WALLET_NAME=[A-Za-z0-9_.-]+$' /etc/dolores/validator.env
sudo grep --quiet --extended-regexp \
  '^BT_WALLET_HOTKEY=[A-Za-z0-9_.-]+$' /etc/dolores/validator.env
sudo grep --quiet --extended-regexp \
  '^DOLORES_VALIDATOR_QUOTA=[1-4]$' /etc/dolores/validator.env
if sudo grep --quiet --extended-regexp \
  '^(READ_ONLY|TMPDIR)=' /etc/dolores/validator.env; then
  echo 'forbidden validator runtime override in validator.env' >&2
  exit 1
fi
```

No live-extrinsic opt-in belongs in this file or this packet. The supplied
service is dry-run only.

Signed request timeouts are fixed at `--timeout 30` in both the base validator
unit and the chain-neutral rehearsal drop-in. Thirty seconds is the miner's
maximum cohort-policy timeout; it is not an operator environment field. The
validator CLI rejects non-positive or larger values before wallet, network, or
epoch work.

## 5. Read-only health and one dry-run tick

Run commands through the service account so the protected environment file is
read without exposing its values. Health is read-only; the tick computes a
dry-run receipt and must not submit weights.

```bash
sudo install -d -m 0700 -o dolores-validator -g dolores-validator \
  /var/lib/dolores-validator

sudo -H -u dolores-validator /bin/sh -c '
  set -eu
  set -a
  . /etc/dolores/validator.env
  set +a
  exec /opt/dolores-validator/venv/bin/dolores-validator health \
    --mode testnet \
    --work /var/lib/dolores-validator \
    --wallet.name "$BT_WALLET_NAME" \
    --wallet.hotkey "$BT_WALLET_HOTKEY" \
    --network test \
    --netuid 523
'

sudo -H -u dolores-validator /bin/sh -c '
  set -eu
  set -a
  . /etc/dolores/validator.env
  set +a
  exec /opt/dolores-validator/venv/bin/dolores-validator tick \
    --mode testnet \
    --work /var/lib/dolores-validator \
    --quota "$DOLORES_VALIDATOR_QUOTA" \
    --timeout 30 \
    --wallet.name "$BT_WALLET_NAME" \
    --wallet.hotkey "$BT_WALLET_HOTKEY" \
    --network test \
    --netuid 523 \
    --chain dry-run \
    --panel-mode mock
'
```

Do not add a manual miner endpoint to the public-testnet validator. A health
failure before a public cohort miner exists is honest pending evidence, not a
reason to disable signed reachability or fabricate a passing result.

## 6. Non-root systemd service and timer

Use only the unit files extracted from the verified public subnet sdist:

- source service: `$RELEASE_SOURCE/deploy/systemd/dolores-validator.service`;
- source timer: `$RELEASE_SOURCE/deploy/systemd/dolores-validator.timer`;
- installed service: `/etc/systemd/system/dolores-validator.service`;
- installed timer: `/etc/systemd/system/dolores-validator.timer`;
- state: `/var/lib/dolores-validator` with mode `0700`;
- runtime: `/run/dolores-validator` with mode `0700`;
- environment: `/etc/dolores/validator.env` with mode `0640`.

The service runs as `dolores-validator`; every process command begins with
`/usr/bin/env READ_ONLY=1 TMPDIR=/run/dolores-validator` after environment-file
loading. It keeps `PrivateTmp=true` and `ProtectHome=read-only`, invokes only
`--network test --netuid 523 --chain dry-run --panel-mode mock`, and writes
stdout/stderr to the journal. Verify and install the unmodified public-sdist
units, but keep the timer disabled until read-only health has a real
metagraph-discovered cohort miner to probe:

```bash
sudo systemd-analyze verify \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator.service" \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator.timer"
sudo install -m 0644 \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator.service" \
  /etc/systemd/system/dolores-validator.service
sudo install -m 0644 \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator.timer" \
  /etc/systemd/system/dolores-validator.timer
sudo systemctl daemon-reload
sudo systemctl disable --now dolores-validator.timer
sudo systemctl show dolores-validator.timer --no-pager \
  --property=LoadState --property=ActiveState --property=UnitFileState
```

`READ_ONLY=1` and `TMPDIR=/run/dolores-validator` are immutable process-prefix
settings, not operator secrets. They are forced after both environment files
are loaded, and the field-shape check above rejects attempts to represent either
as an operator override. Pinned Bittensor `10.5.0` otherwise attempts to create
`~/.bittensor/wallets` and `~/.bittensor/miners` while importing on a clean
host, which conflicts with `ProtectHome=read-only`. It suppresses that SDK
bootstrap write and its default file-logging directory while leaving the
pre-provisioned wallet readable and Dolores state writable only through the
declared state/runtime paths. It does not relax `PrivateTmp`, change the dry-run
chain gate, or grant any extrinsic authority.

After the external miner exists and read-only health succeeds, follow the exact
enable, status, journal, failure, and restart procedure in the validator
operations runbook. Do not weaken `ExecStartPost` to make pre-cohort testnet
health appear successful. The only pre-cohort exception is the packaged,
separately approved `vps-rehearsal.md` profile: it visibly replaces both commands
with signed manual-wire `--chain off` checks, records that this is first-party
rehearsal evidence, and proves removal before the host is destroyed.

Source review and `systemd-analyze verify` are not real-systemd proof. Keep the
following status `PENDING-HUMAN` until a genuine clean Ubuntu 24.04 AMD64 VPS
has installed public HTTPS assets and demonstrated permissions, Docker bind
mounts under `PrivateTmp`, service/timer start, journal output, controlled
restart, state persistence, and no restart loop.

## 7. Sanitized evidence record

Fill this table with public URLs, hashes, versions, public addresses, sanitized
command output, and durable report links only. Never paste environment contents
or private holdout cases.

| Gate | Status | Public-safe evidence |
|---|---|---|
| Exact engine/subnet releases, tags, SHAs, and hosted CI | `PENDING-STOP` | `<FINAL_RELEASE_AND_CI_URLS>` |
| Handoff and checksum trust chain | `PENDING-HUMAN` | `<VERIFIED_DIGEST_RECEIPT>` |
| Ubuntu 24.04 AMD64 and CPython 3.11.15 | `PENDING-HUMAN` | `<SANITIZED_ENVIRONMENT_RECEIPT>` |
| Installed versions, paths, and `pip check` | `PENDING-HUMAN` | `<SANITIZED_INSTALL_RECEIPT>` |
| Dockerfile digest and AMD64 verifier image ID | `PENDING-HUMAN` | `<MANIFEST_COMPARISON_RECEIPT>` |
| Honest fixture is executed and containerized | `PENDING-HUMAN` | `<SANITIZED_HOLDOUT_RECEIPT>` |
| Read-only testnet target and dry-run tick/replay | `PENDING-HUMAN` | `<SANITIZED_DRY_RUN_RECEIPT>` |
| Real service/timer, journal, permissions, and restart | `PENDING-HUMAN` | `<VPS_SYSTEMD_REPORT_URL>` |
| Live-weight authorization | `NOT-AUTHORIZED` | No live action is part of this packet. |

## 8. Sharing boundary

Safe to share after review: immutable public release and CI URLs, SHA-256
digests, OS/architecture, package versions, installed module paths, Dockerfile
digest, platform-scoped image ID, public validator SS58 address, public UID,
redacted dry-run receipts, unit status, and sanitized journal excerpts.

Never share: mnemonic or seed, private key, wallet password, wallet file or
path, environment-file content, holdout secret or cases, provider credential,
SSH private key, shell history containing a secret, unredacted process output,
or any live-extrinsic authorization value.

Final truth: this packet is operator-ready configuration prose, not a completed
VPS receipt. Engine and subnet RC2 hosted CI/releases remain `PENDING-STOP`;
public-asset validator installation and hosted AMD64 image identity remain
`PENDING-HUMAN`; real systemd behavior and the clean RC2 VPS rehearsal remain
`PENDING-HUMAN` until their exact external evidence exists.
