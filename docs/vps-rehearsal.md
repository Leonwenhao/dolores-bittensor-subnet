# Chain-neutral clean-VPS release rehearsal

This is an operator-only rehearsal profile for one disposable Ubuntu 24.04 LTS
AMD64 host. It validates the public `0.2.0rc1` release under real systemd,
Docker, `PrivateTmp`, restart, journal, state, replay, and cross-host network
conditions without registering, publishing an axon, discovering a metagraph,
setting weights, or making any other chain write.

It is not the participant topology. The disposable host temporarily contains a
miner account and a validator account so both service paths can be tested. A
participant miner does not need Docker, a holdout input, validator packages, or
provider credentials. Manual endpoints and ephemeral first-party wallets are
rehearsal evidence only; they are never external-miner or cohort evidence.

Do not start this runbook without a separate exact VPS `STOP-LEON` approval
naming the provider resource, image ID, architecture, size, region, hourly and
maximum cost, inbound rules, SSH method, sudo actions, wallet boundary,
duration, evidence schema, and teardown. The approval must explicitly say no chain write is authorized.

## 1. Immutable public inputs and clean-host record

The approved packet must pin both final source SHAs, both hosted-CI runs, every
primary asset and checksum/provenance digest, and the already-public engine
release manifest. The final subnet manifest, external checklist, VPS receipt,
and HackerQuest handoff do not exist yet; that planned difference from the
participant trust path must be recorded in the VPS receipt.

On the clean host, record only public-safe output:

```bash
date --utc --iso-8601=seconds
cat /etc/os-release
dpkg --print-architecture
uname -a
nproc
free -h
df -h /
dpkg-query -W -f='${binary:Package}\t${Version}\n' \
  ca-certificates curl jq python3 docker.io 2>/dev/null || true
systemctl list-unit-files 'dolores-*' --no-pager
```

Require Ubuntu `24.04`, architecture `amd64`, no pre-existing Dolores unit,
checkout, virtual environment, or release directory, and the exact approved
resource identity. Stop on drift.

Install the CPython 3.11.15 and base prerequisites exactly as documented in
[`hackerquest-miner-quickstart.md`](hackerquest-miner-quickstart.md), section 1.
The base apt list for this combined rehearsal additionally includes `jq` and
`docker.io`:

```bash
sudo apt-get update
sudo apt-get install -y jq docker.io
sudo systemctl enable --now docker.service
/opt/python/3.11.15/bin/python3.11 --version
sudo docker version
```

Expected interpreter output is exactly `Python 3.11.15`.

## 2. Public HTTPS trust bootstrap

Run outside a checkout. Copy the four public digest values from the approved
VPS packet into the public shell variables below. They are release metadata,
not secrets. Do not substitute a chat value or a hash from this source file.

```bash
export TAG='v0.2.0-rc.1'
export ENGINE_BASE="https://github.com/Leonwenhao/dolores-autocurricula/releases/download/$TAG"
export SUBNET_BASE="https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/download/$TAG"
export ENGINE_API="https://api.github.com/repos/Leonwenhao/dolores-autocurricula/releases/tags/$TAG"
export SUBNET_API="https://api.github.com/repos/Leonwenhao/dolores-bittensor-subnet/releases/tags/$TAG"
export DOWNLOAD_DIR='/var/tmp/dolores-0.2.0rc1'

export ENGINE_WHEEL='dolores_autocurricula-0.2.0rc1-py3-none-any.whl'
export ENGINE_SDIST='dolores_autocurricula-0.2.0rc1.tar.gz'
export ENGINE_MANIFEST='dolores-autocurricula-0.2.0rc1-release-manifest.md'
export ENGINE_SUMS='dolores-autocurricula-0.2.0rc1-SHA256SUMS'
export SUBNET_WHEEL='dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl'
export SUBNET_SDIST='dolores_bittensor_subnet-0.2.0rc1.tar.gz'
export SUBNET_BUNDLE='dolores-bittensor-subnet-0.2.0rc1-release-bundle.tar.gz'
export SUBNET_SUMS='dolores-bittensor-subnet-0.2.0rc1-SHA256SUMS'
export SUBNET_PROVENANCE='dolores-bittensor-subnet-0.2.0rc1-provenance.json'

export APPROVED_ENGINE_SUMS_SHA256='<EXACT_PACKET_VALUE>'
export APPROVED_ENGINE_MANIFEST_SHA256='<EXACT_PACKET_VALUE>'
export APPROVED_SUBNET_SUMS_SHA256='<EXACT_PACKET_VALUE>'
export APPROVED_SUBNET_PROVENANCE_SHA256='<EXACT_PACKET_VALUE>'

test ! -e "$DOWNLOAD_DIR"
install -d -m 0755 "$DOWNLOAD_DIR"
cd "$DOWNLOAD_DIR"
curl --fail --location --retry 3 --output engine-release.json "$ENGINE_API"
curl --fail --location --retry 3 --output subnet-release.json "$SUBNET_API"

for asset in \
  "$ENGINE_WHEEL" "$ENGINE_SDIST" "$ENGINE_MANIFEST" "$ENGINE_SUMS"; do
  curl --fail --location --retry 3 --output "$asset" "$ENGINE_BASE/$asset"
done
for asset in \
  "$SUBNET_WHEEL" "$SUBNET_SDIST" "$SUBNET_BUNDLE" \
  "$SUBNET_SUMS" "$SUBNET_PROVENANCE"; do
  curl --fail --location --retry 3 --output "$asset" "$SUBNET_BASE/$asset"
done

printf '%s  %s\n' "$APPROVED_ENGINE_SUMS_SHA256" "$ENGINE_SUMS" | \
  sha256sum --check --strict
printf '%s  %s\n' "$APPROVED_ENGINE_MANIFEST_SHA256" "$ENGINE_MANIFEST" | \
  sha256sum --check --strict
printf '%s  %s\n' "$APPROVED_SUBNET_SUMS_SHA256" "$SUBNET_SUMS" | \
  sha256sum --check --strict
printf '%s  %s\n' "$APPROVED_SUBNET_PROVENANCE_SHA256" "$SUBNET_PROVENANCE" | \
  sha256sum --check --strict
sha256sum --check --strict --ignore-missing "$ENGINE_SUMS"
sha256sum --check --strict --ignore-missing "$SUBNET_SUMS"
```

Require each GitHub API asset digest to equal the corresponding approved
`sha256:` digest before install. A packet-specific command sheet supplies the
exact immutable comparisons; retain the sanitized `jq` pass/fail output and API
asset IDs. Stop if `digest` is missing, any hash differs, or either release is
not a prerelease at the approved tag and source.

Prove that no private input entered the host:

```bash
test ! -d .git
test -z "${DOLORES_REPO-}"
test -z "${PYTHONPATH-}"
find "$DOWNLOAD_DIR" -maxdepth 1 -type f -printf '%f\n' | sort
```

No `scp`, mounted host directory, Git clone/archive, editable install, private
index, private URL, or unpublished file is permitted.

## 3. Install isolated miner and validator environments

Create locked service accounts and root-owned virtual environments:

```bash
getent passwd dolores-miner >/dev/null || \
  sudo useradd --system --create-home --home-dir /home/dolores-miner \
    --shell /usr/sbin/nologin dolores-miner
getent passwd dolores-validator >/dev/null || \
  sudo useradd --system --create-home --home-dir /home/dolores-validator \
    --shell /usr/sbin/nologin dolores-validator
getent group dolores-config >/dev/null || sudo groupadd --system dolores-config
sudo usermod -aG dolores-config dolores-miner
sudo usermod -aG dolores-config,docker dolores-validator

sudo install -d -m 0755 -o root -g root /opt/dolores-miner /opt/dolores-validator
sudo /opt/python/3.11.15/bin/python3.11 -m venv /opt/dolores-miner/venv
sudo /opt/python/3.11.15/bin/python3.11 -m venv /opt/dolores-validator/venv
sudo /opt/dolores-miner/venv/bin/python -m pip install --upgrade pip
sudo /opt/dolores-validator/venv/bin/python -m pip install --upgrade pip

sudo /opt/dolores-miner/venv/bin/python -m pip install \
  "dolores-autocurricula @ file://$DOWNLOAD_DIR/$ENGINE_WHEEL" \
  "dolores-bittensor-subnet @ file://$DOWNLOAD_DIR/$SUBNET_WHEEL"
sudo /opt/dolores-validator/venv/bin/python -m pip install \
  "dolores-autocurricula[validator] @ file://$DOWNLOAD_DIR/$ENGINE_WHEEL" \
  "dolores-bittensor-subnet[validator] @ file://$DOWNLOAD_DIR/$SUBNET_WHEEL"
sudo /opt/dolores-miner/venv/bin/python -m pip check
sudo /opt/dolores-validator/venv/bin/python -m pip check

cd "$DOWNLOAD_DIR"
test ! -e dolores_bittensor_subnet-0.2.0rc1
tar --extract --gzip --file "$SUBNET_SDIST"
export RELEASE_SOURCE="$DOWNLOAD_DIR/dolores_bittensor_subnet-0.2.0rc1"
test -f "$RELEASE_SOURCE/docs/vps-rehearsal.md"
```

Run the exact import/version/dependency-boundary checks from the miner
quickstart and validator configuration packet. Record versions and import paths
under `/opt/dolores-miner/venv` and `/opt/dolores-validator/venv`; do not record
wallet paths or environment contents. Require validator-only packages to be
absent from the miner environment.

Use the build and inspection commands from
[`validator-configuration-packet.md`](validator-configuration-packet.md),
section 3, but do not follow its normal participant instruction to compare with
the not-yet-rendered subnet manifest. For this pre-manifest rehearsal, the
already-public engine manifest and exact approved VPS packet are the sole
identity anchors. Require `linux/amd64` plus their exact Dockerfile SHA-256,
base-image digest, and hosted AMD64 image ID. Stop if those public anchors omit
or disagree on any value.

## 4. Human-only ephemeral wallets and protected input

The VPS packet must explicitly authorize human creation of two disposable,
unfunded, unregistered, test-only wallets. The human runs the pinned `btcli`
interactively under each service account and privately handles every mnemonic,
password, and secret. Agents receive only wallet selector names and public SS58
addresses. Never copy a funded or production wallet to the rehearsal host.

In a private terminal, the human runs the pinned binaries directly. The exact
wallet names may differ only if the approved packet names them:

```bash
sudo -H -u dolores-miner /opt/dolores-miner/venv/bin/btcli wallet new-coldkey \
  --wallet-name dolores-rehearsal-miner \
  --wallet-path /home/dolores-miner/.bittensor/wallets \
  --use-password
sudo -H -u dolores-miner /opt/dolores-miner/venv/bin/btcli wallet new-hotkey \
  --wallet-name dolores-rehearsal-miner \
  --hotkey miner \
  --wallet-path /home/dolores-miner/.bittensor/wallets \
  --no-use-password
sudo -H -u dolores-validator \
  /opt/dolores-validator/venv/bin/btcli wallet new-coldkey \
  --wallet-name dolores-rehearsal-validator \
  --wallet-path /home/dolores-validator/.bittensor/wallets \
  --use-password
sudo -H -u dolores-validator \
  /opt/dolores-validator/venv/bin/btcli wallet new-hotkey \
  --wallet-name dolores-rehearsal-validator \
  --hotkey validator \
  --wallet-path /home/dolores-validator/.bittensor/wallets \
  --no-use-password
```

The unencrypted hotkey is necessary for unattended systemd signing on this
disposable host. Both wallets remain unfunded, unregistered, test-only, and are
destroyed with the VPS; the coldkeys remain password protected.

The human also generates at least 32 random bytes and enters its lowercase hex
encoding directly through `sudoedit /etc/dolores/validator.env`. Never put that
value on a command line, in shell history, output, chat, logs, or evidence.

Create only the protected file shells and then use `sudoedit`:

```bash
sudo install -d -m 0750 -o root -g dolores-config /etc/dolores
sudo install -m 0640 -o root -g dolores-miner /dev/null /etc/dolores/miner.env
sudo install -m 0640 -o root -g dolores-validator /dev/null \
  /etc/dolores/validator.env
sudo install -m 0640 -o root -g dolores-validator /dev/null \
  /etc/dolores/rehearsal.env
sudoedit /etc/dolores/miner.env
sudoedit /etc/dolores/validator.env
sudoedit /etc/dolores/rehearsal.env
```

The files contain these names with local values:

```dotenv
# /etc/dolores/miner.env
DOLORES_TASK_DIR=<PRINTED_TASK_DIR>
DOLORES_MINER_QUOTA=4
DOLORES_MINER_PORT=8091
DOLORES_EXTERNAL_IP=<VPS_GLOBAL_IPV4>
DOLORES_VALIDATOR_HOTKEY=<VPS_VALIDATOR_HOTKEY_SS58>
BT_WALLET_NAME=<EPHEMERAL_MINER_WALLET_NAME>
BT_WALLET_HOTKEY=<EPHEMERAL_MINER_HOTKEY_NAME>

# /etc/dolores/validator.env
DOLORES_HOLDOUT_SECRET=<HUMAN_ENTERED_64_OR_MORE_LOWERCASE_HEX>
BT_WALLET_NAME=<EPHEMERAL_VALIDATOR_WALLET_NAME>
BT_WALLET_HOTKEY=<EPHEMERAL_VALIDATOR_HOTKEY_NAME>
DOLORES_VALIDATOR_QUOTA=1
DOLORES_VALIDATOR_TIMEOUT=60

# /etc/dolores/rehearsal.env
DOLORES_REHEARSAL_MINER_ENDPOINT=127.0.0.1:8091:<MINER_HOTKEY_SS58>:<MINER_COLDKEY_SS58>
```

Confirm only ownership, mode, and field shape with non-outputting `grep --quiet`
checks. Never use `cat`, `env`, shell tracing, `systemctl show` on environment
properties, or evidence commands that reveal values. Do not define
`DOLORES_ALLOW_EXTRINSICS` or any live-extrinsic opt-in.

## 5. Unsigned task and registration preview

Create the documented task as the miner service user:

```bash
sudo install -d -m 0700 -o dolores-miner -g dolores-miner \
  /var/lib/dolores-miner/tasks
sudo -H -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner init \
  --output /var/lib/dolores-miner/tasks \
  --archetype escape_delim \
  --seed 730214
sudo -H -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner validate \
  --task-dir '<PRINTED_TASK_DIR>'
sudo -H -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner register \
  --wallet.name '<EPHEMERAL_MINER_WALLET_NAME>' \
  --wallet.hotkey '<EPHEMERAL_MINER_HOTKEY_NAME>' \
  --network test \
  --netuid 523
```

Require the approved task ID and canonical digest, `VALID`, and
`registration=not_executed`. Never add `--execute` or a registration
confirmation.

## 6. Foreground miner, cross-host TCP, and signed probe

Before systemd, the human supplies the VPS validator hotkey and a different
external test validator hotkey as public allowlist values. Start the miner in a
private operator terminal without `--publish` and require
`axon_publish=skipped reason=no_publish_flag`:

```bash
sudo -H -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner serve \
  --task-dir '<PRINTED_TASK_DIR>' \
  --quota 4 \
  --host 0.0.0.0 \
  --port 8091 \
  --external-ip '<VPS_GLOBAL_IPV4>' \
  --external-port 8091 \
  --validator-hotkey '<VPS_VALIDATOR_HOTKEY_SS58>' \
  --validator-hotkey '<EXTERNAL_PROBE_VALIDATOR_HOTKEY_SS58>' \
  --wallet.name '<EPHEMERAL_MINER_WALLET_NAME>' \
  --wallet.hotkey '<EPHEMERAL_MINER_HOTKEY_NAME>' \
  --network test \
  --netuid 523
```

From a second machine whose source CIDR is in the approved firewall rule:

```bash
nc -vz '<VPS_GLOBAL_IPV4>' 8091
dolores-validator probe-wire \
  --miner-endpoints '<VPS_GLOBAL_IPV4>:8091:<MINER_HOTKEY_SS58>:<MINER_COLDKEY_SS58>' \
  --wallet.name '<EXTERNAL_TEST_VALIDATOR_WALLET>' \
  --wallet.hotkey '<EXTERNAL_TEST_VALIDATOR_HOTKEY>' \
  --timeout 10
```

The second command must be installed from the same public release, must use a
human-controlled test-only wallet, and must return `"ok": true`,
`"chain_mode": "off"`, `"quota": 0`, and `"metagraph_discovery": false`.
It proves signed request/response transport over the public network; it does
not prove scoring, metagraph discovery, external traction, or cohort readiness.
Stop the foreground miner after capturing sanitized evidence.

## 7. Real miner systemd lifecycle

Install the unmodified base unit and the public rehearsal drop-in:

```bash
sudo install -m 0644 "$RELEASE_SOURCE/deploy/systemd/dolores-miner.service" \
  /etc/systemd/system/dolores-miner.service
sudo install -d -m 0755 /etc/systemd/system/dolores-miner.service.d
sudo install -m 0644 \
  "$RELEASE_SOURCE/deploy/systemd/dolores-miner-chain-neutral-rehearsal.conf" \
  /etc/systemd/system/dolores-miner.service.d/90-chain-neutral-rehearsal.conf
sudo systemctl daemon-reload
sudo systemd-analyze verify dolores-miner.service
sudo systemctl enable --now dolores-miner.service
sudo systemctl restart dolores-miner.service
sudo systemctl show dolores-miner.service --no-pager \
  --property=ActiveState --property=SubState --property=Result \
  --property=ExecMainStatus --property=NRestarts --property=User \
  --property=Group --property=PrivateTmp --property=FragmentPath \
  --property=DropInPaths
sudo journalctl -u dolores-miner.service --no-pager -n 150
sudo -H -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner \
  health --host 127.0.0.1 --port 8091
```

Require `active/running`, `Result=success`, `NRestarts=0`, local health after
restart, `axon_publish=skipped`, no doctor claim, no chain-write output, no
restart loop, and cross-host TCP reachability again. The drop-in replaces only
the production post-start doctor with local TCP health; the base `ExecStart`
remains unchanged and never contains `--publish`.

## 8. Real validator systemd, Docker, timer, state, and replay

Install the unmodified base service/timer and the public chain-neutral service
drop-in. Do not change the production timer cadence:

```bash
sudo install -m 0644 "$RELEASE_SOURCE/deploy/systemd/dolores-validator.service" \
  /etc/systemd/system/dolores-validator.service
sudo install -m 0644 "$RELEASE_SOURCE/deploy/systemd/dolores-validator.timer" \
  /etc/systemd/system/dolores-validator.timer
sudo install -d -m 0755 /etc/systemd/system/dolores-validator.service.d
sudo install -m 0644 \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator-chain-neutral-rehearsal.conf" \
  /etc/systemd/system/dolores-validator.service.d/90-chain-neutral-rehearsal.conf
sudo systemctl daemon-reload
sudo systemd-analyze verify \
  dolores-validator.service dolores-validator.timer
sudo systemctl enable --now dolores-validator.timer
sudo systemctl list-timers dolores-validator.timer --no-pager
```

The production `OnBootSec=10min` activation fires immediately if that monotonic
deadline has passed; otherwise wait for the displayed deadline. On any
validator service failure—whether from the timer activation or the controlled
restart below—run the following within the inherited 30-second restart delay,
then retain the journal. Stop both the timer and service; do not weaken a gate
or allow a restart loop:

```bash
sudo systemctl disable --now dolores-validator.timer
sudo systemctl stop dolores-validator.service
sudo systemctl show dolores-validator.service --no-pager \
  --property=ActiveState --property=SubState --property=Result \
  --property=ExecMainStatus --property=NRestarts
sudo journalctl -u dolores-validator.service --no-pager -n 300
```

If the service has already retried, record every attempt and fail the rehearsal;
do not reset the failure until evidence is captured.

After one timer-triggered epoch completes, capture that invocation and
immediately disable the timer before any evidence or debugging work can cross
the next production cadence. Keep the timer disabled for the rest of the
rehearsal, then run one controlled service restart for epoch 2:

```bash
sudo systemctl show dolores-validator.service --no-pager \
  --property=ActiveState --property=SubState --property=Result \
  --property=ExecMainStatus --property=NRestarts
sudo journalctl -u dolores-validator.service --no-pager -n 300
sudo systemctl disable --now dolores-validator.timer
sudo systemctl stop dolores-validator.service
test "$(sudo systemctl is-enabled dolores-validator.timer)" = disabled
test "$(sudo systemctl is-active dolores-validator.timer)" = inactive
sudo systemctl restart dolores-validator.service
sudo systemctl show dolores-validator.service --no-pager \
  --property=ActiveState --property=SubState --property=Result \
  --property=ExecMainStatus --property=NRestarts --property=User \
  --property=Group --property=PrivateTmp --property=RuntimeDirectory \
  --property=StateDirectory --property=ReadWritePaths \
  --property=FragmentPath --property=DropInPaths
sudo journalctl -u dolores-validator.service --no-pager -n 300
sudo -H -u dolores-validator /opt/dolores-validator/venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path('/var/lib/dolores-validator/subnet_archive/validator_runtime/state.json')
state = json.loads(path.read_text(encoding='utf-8'))
assert state['last_completed_epoch'] is not None
assert state['last_completed_epoch'] >= 2
assert state['next_epoch_id'] > state['last_completed_epoch']
assert state['active_epoch_id'] is None
assert state['phase'] is None
print('validator_state=monotonic last_completed_epoch=' + str(state['last_completed_epoch']))
PY
sudo -H -u dolores-validator \
  /opt/dolores-validator/venv/bin/dolores-validator replay \
  --work /var/lib/dolores-validator --epoch 1
sudo -H -u dolores-validator \
  /opt/dolores-validator/venv/bin/dolores-validator replay \
  --work /var/lib/dolores-validator --epoch 2
for epoch in 1 2; do
  sudo -H -u dolores-validator jq \
    '{epoch_id, degraded, weight_result}' \
    "/var/lib/dolores-validator/subnet_archive/epochs/epoch_${epoch}/weights_epoch_${epoch}.json"
  sudo -H -u dolores-validator jq --exit-status --compact-output --slurp \
    --argjson epoch "$epoch" \
    '[.[] | select(.epoch_id == $epoch)] |
     select(length > 0 and
            all(.verification.executed == true) and
            all(.verification.containerized == true) and
            all(.verification.status == "passed") and
            all(.holdout.passed == true) and
            all(.holdout.executed == true) and
            all(.holdout.containerized == true) and
            all(.holdout.status == "passed")) |
     {rows: length,
      task_ids: (map(.task_id) | unique),
      package_hashes: (map(.package_hash) | unique),
      executed: all(.verification.executed == true),
      containerized: all(.verification.containerized == true),
      verifier_statuses: (map(.verification.status) | unique),
      holdout_passed: all(.holdout.passed == true),
      holdout_executed: all(.holdout.executed == true),
      holdout_containerized: all(.holdout.containerized == true),
      holdout_statuses: (map(.holdout.status) | unique)}' \
    /var/lib/dolores-validator/subnet_archive/submissions.jsonl
done
```

Require two monotonic committed epochs, `chain_mode=fallback` with an offline
reason, signed manual-wire reachability, `NRestarts=0`, and `REPLAY OK` twice.
The production timer must remain disabled and inactive after its first
successful invocation; epoch 2 is the single controlled manual restart.
The archived verification receipts must show the honest task was actually
executed, containerized, and passed under the private holdout. A successful
Docker-backed tick under `User=dolores-validator`, `PrivateTmp=true`,
`TMPDIR=/run/dolores-validator`, and the explicit `/run/dolores-validator`
write path is the real bind-mount/runtime proof; static unit parsing is not.

## 9. Remove the rehearsal profile and verify production bytes

Disable all supervised work before removing the drop-ins:

```bash
sudo systemctl disable --now dolores-validator.timer dolores-miner.service
sudo systemctl stop dolores-validator.service
sudo rm -f \
  /etc/systemd/system/dolores-miner.service.d/90-chain-neutral-rehearsal.conf \
  /etc/systemd/system/dolores-validator.service.d/90-chain-neutral-rehearsal.conf \
  /etc/dolores/rehearsal.env
sudo systemctl daemon-reload
sudo systemctl reset-failed dolores-miner.service dolores-validator.service

sudo systemctl show dolores-miner.service dolores-validator.service \
  --property=DropInPaths --no-pager
sudo cmp --silent \
  "$RELEASE_SOURCE/deploy/systemd/dolores-miner.service" \
  /etc/systemd/system/dolores-miner.service
sudo cmp --silent \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator.service" \
  /etc/systemd/system/dolores-validator.service
sudo cmp --silent \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator.timer" \
  /etc/systemd/system/dolores-validator.timer
sudo systemd-analyze verify \
  "$RELEASE_SOURCE/deploy/systemd/dolores-miner.service" \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator.service" \
  "$RELEASE_SOURCE/deploy/systemd/dolores-validator.timer"
```

Require empty `DropInPaths`, byte-identical installed base units, disabled
timer/service state, and no continuing process. Leave the unmodified production
units stopped: their full doctor and metagraph health are honestly pending
until registration, axon publication, and a real public cohort miner exist.

## 10. Evidence and teardown boundary

The sanitized VPS receipt must record exact UTCs, provider/resource identity,
OS/kernel/architecture, public asset URLs/IDs/digests, installed versions and
paths, task identity, registration preview, foreground and supervised miner
results, external TCP/signed probe, Dockerfile/base/image identity, systemd
properties, timer invocation, journal outcome, state/replay receipts, exact
drop-in differences/removal, firewall cleanup, billed duration/cost, and
provider deletion read-back.

Never record wallet/environment contents, mnemonics, passwords, private keys,
wallet files, SSH private keys, provider credentials, or holdout input/cases.
Run the approved public-safe scan before freezing the receipt. Then remove host
and provider firewall rules, destroy the disposable VPS, read back the absence
of both resources, and record zero continuing ports/resources/cost. Retention or
any teardown deviation needs a new exact approval.

### What a successful rehearsal proves

- public assets can install on clean Ubuntu 24.04 AMD64;
- deterministic task generation/validation and registration preview work;
- a non-publishing miner answers signed Bittensor requests over a public port;
- the published systemd hardening works under PID 1;
- the validator's Docker holdout works through the `PrivateTmp`-safe runtime
  bind and its state survives a controlled restart;
- the production timer can invoke the chain-neutral rehearsal service; and
- the public rehearsal profile can be removed without changing base units.

It does not prove registration, axon publication, metagraph discovery, external
miner traction, independent cohort operation, training uplift, revenue,
mainnet readiness, or successful weight epochs.
