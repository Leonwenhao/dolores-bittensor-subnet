# Controlled-Cohort Validator Operations

This runbook operates the serialized validator on Bittensor public testnet,
fixed to `network=test`, `netuid=523`. The supervised timer is dry-run by
default. Live weights remain a separately approved, four-gate operator action.

The validator machine requires the approved subnet `validator` extra, Docker,
the immutable verifier image, a validator hotkey, and a private holdout secret.
The default mock panel makes no paid provider calls.

Use the sanitized
[`validator configuration packet`](validator-configuration-packet.md) as the
copy-ready release, environment, service, and evidence worksheet. Keep all
wallet and holdout values in the operator's terminal and protected environment
file.

For the separately approved, disposable, first-party release rehearsal before a
public cohort miner exists, use
[`vps-rehearsal.md`](vps-rehearsal.md). Its temporary manual-wire drop-in is not
the production testnet path and must be removed after the clean-host proof.

## 1. Install and isolate the service

Use a dedicated Ubuntu 24.04 LTS amd64 host and non-root `dolores-validator`
account. Install CPython 3.11.15 from the exact source URL and SHA-256 in
[`hackerquest-miner-quickstart.md`](hackerquest-miner-quickstart.md), producing
`/opt/python/3.11.15/bin/python3.11`; do not replace Ubuntu's system Python.
Ubuntu `docker.io` is installed only on this validator host. Membership in the
Docker group permits control of the daemon and is security-sensitive; do not
give this account interactive or unrelated workload access.

Download and verify the immutable engine/subnet `v0.2.0-rc.1` assets exactly as
specified in quickstart section 2. The fixed download directory and filenames
are:

```bash
export DOWNLOAD_DIR="/var/tmp/dolores-0.2.0rc1"
export ENGINE_WHEEL="dolores_autocurricula-0.2.0rc1-py3-none-any.whl"
export SUBNET_WHEEL="dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl"
export SUBNET_SDIST="dolores_bittensor_subnet-0.2.0rc1.tar.gz"
```

Do not continue unless the release-page handoff digest, both checksum sidecars,
and all downloaded payloads pass. Then install Docker and the validator extras
in a root-owned virtual environment:

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl enable --now docker.service
sudo docker version
getent passwd dolores-validator >/dev/null || \
  sudo useradd --system --create-home --home-dir /home/dolores-validator \
    --shell /usr/sbin/nologin dolores-validator
sudo usermod -aG docker dolores-validator
sudo install -d -m 0755 -o root -g root /opt/dolores-validator
/opt/python/3.11.15/bin/python3.11 --version
sudo /opt/python/3.11.15/bin/python3.11 -m venv /opt/dolores-validator/venv
sudo /opt/dolores-validator/venv/bin/python -m pip install --upgrade pip
sudo /opt/dolores-validator/venv/bin/python -m pip install \
  'dolores-autocurricula[validator] @ file:///var/tmp/dolores-0.2.0rc1/dolores_autocurricula-0.2.0rc1-py3-none-any.whl' \
  'dolores-bittensor-subnet[validator] @ file:///var/tmp/dolores-0.2.0rc1/dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl'
sudo /opt/dolores-validator/venv/bin/python -m pip check
```

Do not use `DOLORES_REPO`, editable installs, adjacent checkouts, unpinned
branches, or another artifact directory.

Provision the validator wallet under `/home/dolores-validator/.bittensor/wallets`
by running the approved Bittensor wallet command directly as that account in the
operator's terminal. Do not copy, print, or automate private wallet material.

Extract the already verified subnet source distribution and set the fixed
release source:

```bash
cd "$DOWNLOAD_DIR"
test ! -e dolores_bittensor_subnet-0.2.0rc1
tar --extract --gzip --file "$SUBNET_SDIST"
export RELEASE_SOURCE="$DOWNLOAD_DIR/dolores_bittensor_subnet-0.2.0rc1"
test -f "$RELEASE_SOURCE/deploy/systemd/dolores-validator.service"
test -f "$RELEASE_SOURCE/deploy/systemd/dolores-validator.timer"
```

The reviewed units below come from that immutable archive, not an unpinned
checkout.

Build or pull the verifier image only through the approved release procedure,
then verify its immutable digest. `dolores-validator health` fails if Docker or
the configured verifier image is unavailable.

## 2. Configure the holdout secret without exposing it

`DOLORES_HOLDOUT_SECRET` is required in wire, localnet, and testnet validator
modes. It derives deterministic private holdout cases together with the task hash
and policy version. The live value must never appear in a command line, shell
history, chat, issue, commit, log, status document, or public evidence.

Create `/etc/dolores/validator.env` as a root-owned file readable only by the
service group:

```bash
sudo install -d -m 0750 -o root -g dolores-validator /etc/dolores
sudo test -e /etc/dolores/validator.env || \
  sudo install -m 0640 -o root -g dolores-validator /dev/null \
    /etc/dolores/validator.env
sudoedit /etc/dolores/validator.env
```

Generate the secret using the operator's trusted random-secret or secret-manager
workflow and write it directly with the secure editor. Do not echo it for
verification. The file must define these variable names with local values:

- `DOLORES_HOLDOUT_SECRET`
- `BT_WALLET_NAME`
- `BT_WALLET_HOTKEY`
- `DOLORES_VALIDATOR_QUOTA` — integer from 1 through 4
- `DOLORES_VALIDATOR_TIMEOUT`

The units reference the file but contain no environment values.

## 3. Read-only health before any tick

Load the environment file securely into the service context or run through
systemd. The implemented health command is:

```bash
dolores-validator health \
  --mode testnet \
  --work /var/lib/dolores-validator \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --network test \
  --netuid 523
```

Health reports:

- Docker daemon and verifier-image availability;
- whether a holdout secret is configured, never its value;
- serialized runtime state and the last receipt;
- ambiguous `weights_submitting` state;
- read-only chain readiness;
- counts of metagraph-discovered public miners and miners that pass a signed,
  quota-zero request/response probe;
- last completed epoch, last successful weight receipt, blocks since the
  validator update, and named degraded conditions.

It returns nonzero if Docker, the secret, chain readiness, discovery, or runtime
state is unhealthy, or if any discovered miner fails the signed probe. The probe
is enabled by default; `--no-probe-wire` is a diagnostic opt-out that deliberately
makes health unhealthy and does not count as cohort evidence. Health never
accepts manual endpoints in the public testnet path.

## 4. Run one dry-run tick first

The tick owns an exclusive OS lock, allocates its epoch ID automatically, and
persists atomic state transitions:

`allocated -> querying -> evaluating -> weights_submitting -> committed`

Do not pass `--miner-endpoints` for public testnet. Do not specify an epoch ID;
the serialized state store allocates it monotonically.

```bash
dolores-validator tick \
  --mode testnet \
  --work /var/lib/dolores-validator \
  --quota 4 \
  --timeout 30 \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --network test \
  --netuid 523 \
  --chain dry-run \
  --panel-mode mock
```

The default mock panel requires no Fireworks credential and no paid call. Do not
pass `--panel-mode calibrate`, `--allow-provider-spend`, or a provider-spend
environment guard during the cohort default run.

After the tick, rerun `dolores-validator health` and inspect the printed
`epoch_id`, weights artifact, chain mode/reason, runtime state, and dry-run
receipt. A dry run is evidence, not permission for a live submission.

## 5. Install the dry-run timer

Install the service and timer supplied in `deploy/systemd/`:

```bash
sudo install -m 0644 "$RELEASE_SOURCE/deploy/systemd/dolores-validator.service" \
  /etc/systemd/system/dolores-validator.service
sudo install -m 0644 "$RELEASE_SOURCE/deploy/systemd/dolores-validator.timer" \
  /etc/systemd/system/dolores-validator.timer
sudo systemctl daemon-reload
sudo systemctl enable --now dolores-validator.timer
sudo systemctl list-timers dolores-validator.timer
```

The service is `Type=oneshot`, invokes `tick` with explicit
`--network test --netuid 523`, discovers miners from the metagraph, selects
`--chain dry-run --panel-mode mock`, and uses no manual endpoint. The application
lock remains authoritative if a human and timer race.

Inspect each run:

```bash
sudo systemctl status dolores-validator.service
sudo journalctl -u dolores-validator.service --no-pager -n 200
```

The timer uses `OnUnitInactiveSec`, so a long epoch does not overlap the next
scheduled tick. Restarting the host preserves the monotonic state under
`/var/lib/dolores-validator/subnet_archive/validator_runtime/`.

## 6. Failure and restart behavior

- A failure in `allocated` or `querying` retries the same allocation and
  increments its attempt counter.
- Interruption during `evaluating` marks that epoch failed; the next tick
  allocates a new epoch instead of duplicating durable evaluation rows.
- A crash in `weights_submitting` with a live-attempt artifact is ambiguous.
  Automatic ticks fail closed and do not resubmit.
- A canonical completion marker hashes the epoch-scoped miner state, weights,
  panel sidecar, and any receipt/attempt before `committed` is allowed.
- A definite non-live receipt written before that marker is marked failed and
  advances safely on the next tick; it is never mistaken for a completed epoch.

### Recover a durable receipt

First stop the timer and inspect health:

```bash
sudo systemctl stop dolores-validator.timer
dolores-validator health \
  --mode testnet \
  --work /var/lib/dolores-validator \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --network test \
  --netuid 523
```

If state is `weights_submitting` and the exact epoch's canonical completion
marker exists, explicit recovery revalidates every canonical path, epoch, mode,
and SHA-256 before committing it:

```bash
dolores-validator recover-receipt --work /var/lib/dolores-validator
```

No alternate receipt or marker path is accepted. Never fabricate, copy, or edit
an artifact to clear state.

If a live `chain_attempt_epoch_N.json` is `started` or `ambiguous`, do **not**
retry, submit weights again, invoke recovery, or manually edit `state.json`.
Reconcile the public chain state and payload digest with the operator. This is
`STOP-LEON`; unresolved ambiguity remains fail-closed.

Restart the timer only after health no longer reports ambiguity:

```bash
sudo systemctl start dolores-validator.timer
```

## 7. Commit-reveal handling

Commit-reveal detection is fail-closed. If its state cannot be read, the tick
does not submit. If commit-reveal is enabled, a normal live submission is
skipped. Do not add `--allow-commit-reveal` to the default service or cohort
commands. Any future override requires its own reviewed protocol and explicit
operator authorization; it is not implied by a successful dry run.

## 8. Explicit live-weight action

The timer service never submits live weights. Stop the timer and obtain
`STOP-LEON` approval for one named automatically allocated epoch and reviewed
payload before a live tick.

All four existing gates remain required:

1. `--chain live`;
2. `--allow-extrinsics`;
3. `DOLORES_ALLOW_EXTRINSICS=1` for this invocation only;
4. `--confirm-live I-UNDERSTAND-THIS-WILL-SUBMIT-WEIGHTS`.

The shell or service context must already contain `DOLORES_HOLDOUT_SECRET` from
the protected environment file; never put the secret on the command line. The
explicit live command is:

```bash
DOLORES_ALLOW_EXTRINSICS=1 dolores-validator tick \
  --mode testnet \
  --work /var/lib/dolores-validator \
  --quota 4 \
  --timeout 30 \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --network test \
  --netuid 523 \
  --chain live \
  --allow-extrinsics \
  --confirm-live I-UNDERSTAND-THIS-WILL-SUBMIT-WEIGHTS \
  --panel-mode mock
```

This signs and may submit `set_weights` on public testnet netuid 523. It does not
authorize registration, stake movement, axon publication, another epoch, or any
paid panel call. If a password prompt appears, the operator enters it locally.
Stop on an unexpected network, netuid, commit-reveal state, payload, fee,
signature prompt, RPC error, or receipt mismatch.

After submission, capture the durable receipt, public inclusion/read-back,
payload digest, nonzero miner weights, and UTC timestamp. Rerun health. Two
consecutive approved successful epochs are required for external cohort proof;
one live receipt is not sufficient.

## 9. Legacy fixture command

`once` is an offline fixture validator. It does not discover miners or prove
public cohort operation:

```bash
dolores-validator once \
  --submissions /path/to/wire-fixtures \
  --work /tmp/dolores-validator-once \
  --epoch 1 \
  --quota 4
```

Never present `once`, wire mode, localnet, a manual endpoint, or a first-party
persona as external-miner evidence.
