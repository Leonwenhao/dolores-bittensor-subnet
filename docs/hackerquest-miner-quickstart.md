# HackerQuest Controlled-Cohort Miner Quickstart

This is the zero-context Ubuntu VPS path for one known HackerQuest engineer to
prepare a Dolores miner from immutable public artifacts. It is fixed to
`network=test`, `netuid=523`, engine `0.2.0rc1`, subnet `0.2.0rc1`, and tag
`v0.2.0-rc.1`. It is not a permissionless, production, or mainnet launch guide.

The two immutable release pages are:

- engine: `https://github.com/Leonwenhao/dolores-autocurricula/releases/tag/v0.2.0-rc.1`;
- subnet: `https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/tag/v0.2.0-rc.1`.

Their immutable asset bases are:

- `https://github.com/Leonwenhao/dolores-autocurricula/releases/download/v0.2.0-rc.1/`;
- `https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/download/v0.2.0-rc.1/`.

If either page, the exact tag, the checksum sidecars, or
`hackerquest-handoff-0.2.0rc1.md` is missing, stop. Never substitute a local
wheel, branch archive, editable checkout, private attachment, mutable `latest`
URL, `DOLORES_REPO`, or `PYTHONPATH` override.

Registration and axon publication are signed human actions. Complete download,
verification, installation, task validation, and local serving first. Then stop
at each separate `STOP-LEON` gate.

## 0. Machine and participant prerequisites

Use a fresh Ubuntu `24.04 LTS` `amd64` VPS with at least:

- 2 vCPU;
- 4 GB RAM;
- 25 GB disk;
- one stable, literal, globally routable IPv4 address;
- one fixed inbound TCP port, normally `8091`, open in both the provider
  firewall/security group and the host firewall.

The participant must control:

- a Bittensor coldkey and miner hotkey stored only under the non-root
  `dolores-miner` service account;
- enough public-testnet TAO to cover the current netuid-523 registration recycle
  fee; testnet TAO has no monetary value, but registration still spends it;
- the exact public validator SS58 hotkey supplied by the cohort operator.

The miner does **not** need Docker, DuckDB, PyArrow, Streamlit, Fireworks or
other provider credentials, a solver panel, or validator internals. Docker and
the secret-keyed private holdout run on the validator. Ubuntu `docker.io` belongs
only on the validator host; do not install it for the miner.

Never send or paste a mnemonic, seed phrase, private key, wallet password,
wallet file, provider credential, `.env` content, SSH private key, or validator
holdout secret to the operator, an agent, an issue, or a log. Wallet creation,
restore, and password entry happen only in the participant's own terminal.

## 1. Install the supported CPython 3.11.15 runtime

Ubuntu 24.04 does not provide the supported interpreter as its default Python.
Build the reviewed CPython source to `/opt/python/3.11.15` and use
`make altinstall` so the operating-system Python remains untouched.

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential ca-certificates curl xz-utils \
  libbz2-dev libffi-dev libgdbm-dev liblzma-dev libncurses-dev \
  libreadline-dev libsqlite3-dev libssl-dev tk-dev uuid-dev zlib1g-dev

cd /var/tmp
curl --fail --location --retry 3 \
  --output Python-3.11.15.tar.xz \
  https://www.python.org/ftp/python/3.11.15/Python-3.11.15.tar.xz
printf '%s  %s\n' \
  272179ddd9a2e41a0fc8e42e33dfbdca0b3711aa5abf372d3f2d51543d09b625 \
  Python-3.11.15.tar.xz | sha256sum --check --strict
tar --extract --file Python-3.11.15.tar.xz
cd Python-3.11.15
./configure --prefix=/opt/python/3.11.15 --with-ensurepip=install
make -j"$(nproc)"
sudo make altinstall
/opt/python/3.11.15/bin/python3.11 --version
```

Expected output includes:

```text
Python-3.11.15.tar.xz: OK
Python 3.11.15
```

Any other interpreter version is unsupported for this release.

## 2. Download and verify the immutable RC1 assets

Run this as the VPS administrator, not as root and not inside a checkout:

```bash
export TAG="v0.2.0-rc.1"
export ENGINE_BASE="https://github.com/Leonwenhao/dolores-autocurricula/releases/download/$TAG"
export SUBNET_BASE="https://github.com/Leonwenhao/dolores-bittensor-subnet/releases/download/$TAG"
export DOWNLOAD_DIR="/var/tmp/dolores-0.2.0rc1"

export ENGINE_WHEEL="dolores_autocurricula-0.2.0rc1-py3-none-any.whl"
export ENGINE_SDIST="dolores_autocurricula-0.2.0rc1.tar.gz"
export ENGINE_MANIFEST="dolores-autocurricula-0.2.0rc1-release-manifest.md"
export ENGINE_SUMS="dolores-autocurricula-0.2.0rc1-SHA256SUMS"

export SUBNET_WHEEL="dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl"
export SUBNET_SDIST="dolores_bittensor_subnet-0.2.0rc1.tar.gz"
export SUBNET_BUNDLE="dolores-bittensor-subnet-0.2.0rc1-release-bundle.tar.gz"
export SUBNET_MANIFEST="dolores-bittensor-subnet-0.2.0rc1-release-manifest.md"
export SUBNET_SUMS="dolores-bittensor-subnet-0.2.0rc1-SHA256SUMS"
export SUBNET_PROVENANCE="dolores-bittensor-subnet-0.2.0rc1-provenance.json"
export SUBNET_CHECKLIST="dolores-bittensor-subnet-0.2.0rc1-cohort-checklist.md"
export HANDOFF="hackerquest-handoff-0.2.0rc1.md"

install -d -m 0755 "$DOWNLOAD_DIR"
cd "$DOWNLOAD_DIR"

for asset in \
  "$ENGINE_WHEEL" "$ENGINE_SDIST" "$ENGINE_MANIFEST" "$ENGINE_SUMS"; do
  curl --fail --location --retry 3 --output "$asset" "$ENGINE_BASE/$asset"
done

for asset in \
  "$SUBNET_WHEEL" "$SUBNET_SDIST" "$SUBNET_BUNDLE" \
  "$SUBNET_MANIFEST" "$SUBNET_SUMS" "$SUBNET_PROVENANCE" \
  "$SUBNET_CHECKLIST" "$HANDOFF"; do
  curl --fail --location --retry 3 --output "$asset" "$SUBNET_BASE/$asset"
done
```

Open the immutable subnet release page above. Compare the release page's
`sha256:` digest for `hackerquest-handoff-0.2.0rc1.md` with:

```bash
cd "$DOWNLOAD_DIR"
sha256sum "$HANDOFF"
```

The verified handoff contains the final SHA-256 trust anchors for both checksum
sidecars. Compare them with:

```bash
sha256sum "$ENGINE_SUMS" "$SUBNET_SUMS"
```

Stop on any mismatch. After both sidecars match the exact values in the verified
handoff, verify every downloaded payload they list:

```bash
cd "$DOWNLOAD_DIR"
sha256sum --check --strict --ignore-missing "$ENGINE_SUMS"
sha256sum --check --strict --ignore-missing "$SUBNET_SUMS"
test -s "$ENGINE_MANIFEST"
test -s "$SUBNET_MANIFEST"
test -s "$SUBNET_PROVENANCE"
test -s "$SUBNET_CHECKLIST"
test -s "$HANDOFF"
```

Run the additional exact `printf ... | sha256sum --check --strict` commands in
the verified handoff for both external manifests, subnet provenance, and the
exact checklist. Expected output names every downloaded payload/evidence file
followed by `OK`. A checksum sidecar is not trusted merely because it was
downloaded beside a wheel; its own digest must first match the verified handoff
and GitHub release metadata.

Extract only the verified subnet source distribution, which carries the reviewed
systemd unit and public runbooks:

```bash
cd "$DOWNLOAD_DIR"
test ! -e dolores_bittensor_subnet-0.2.0rc1
tar --extract --gzip --file "$SUBNET_SDIST"
export RELEASE_SOURCE="$DOWNLOAD_DIR/dolores_bittensor_subnet-0.2.0rc1"
test -f "$RELEASE_SOURCE/deploy/systemd/dolores-miner.service"
```

## 3. Create the service account and install the two wheels

Keep the virtual environment root-owned and executable, but not writable, by the
service account:

```bash
getent passwd dolores-miner >/dev/null || \
  sudo useradd --system --create-home --home-dir /home/dolores-miner \
    --shell /usr/sbin/nologin dolores-miner
sudo install -d -m 0755 -o root -g root /opt/dolores-miner
sudo /opt/python/3.11.15/bin/python3.11 -m venv /opt/dolores-miner/venv
sudo /opt/dolores-miner/venv/bin/python -m pip install --upgrade pip
sudo /opt/dolores-miner/venv/bin/python -m pip install \
  "$DOWNLOAD_DIR/$ENGINE_WHEEL" \
  "$DOWNLOAD_DIR/$SUBNET_WHEEL"
sudo /opt/dolores-miner/venv/bin/python -m pip check
sudo -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner --help
sudo -u dolores-miner /opt/dolores-miner/venv/bin/btcli --version
sudo -u dolores-miner /opt/dolores-miner/venv/bin/python - <<'PY'
import importlib.metadata as metadata
import importlib.util
from pathlib import Path

import dolores
import dolores_subnet

assert metadata.version("dolores-autocurricula") == "0.2.0rc1"
assert metadata.version("dolores-bittensor-subnet") == "0.2.0rc1"
assert Path(dolores.__file__).resolve().is_relative_to(Path("/opt/dolores-miner/venv"))
assert Path(dolores_subnet.__file__).resolve().is_relative_to(
    Path("/opt/dolores-miner/venv")
)
for name in ("docker", "duckdb", "pyarrow", "streamlit", "fireworks", "hypothesis"):
    assert importlib.util.find_spec(name) is None, name
print(f"engine={metadata.version('dolores-autocurricula')} path={dolores.__file__}")
print(f"subnet={metadata.version('dolores-bittensor-subnet')} path={dolores_subnet.__file__}")
print("miner_dependency_boundary=ok")
PY
```

Expected results:

- `pip check` prints `No broken requirements found.`;
- both versions print `0.2.0rc1` from `/opt/dolores-miner/venv`;
- `btcli` reports `9.23.1`;
- the final line is `miner_dependency_boundary=ok`.

## 4. Put the wallet under the service account and set public values

Wallet creation or restore is a human-only terminal action. Open a service-user
shell, use the installed `btcli` wallet flow, and keep every mnemonic/password
prompt private:

```bash
sudo -u dolores-miner -H /bin/bash
source /opt/dolores-miner/venv/bin/activate
btcli wallet --help
```

Create or restore the participant-controlled coldkey and miner hotkey only in
that shell. Do not copy wallet files from a root account or another user. Then
set these local values without posting them to a public log:

```bash
export PUBLIC_IPV4="<VPS_GLOBAL_IPV4>"
export PUBLIC_PORT="8091"
export VALIDATOR_HOTKEY="<COHORT_VALIDATOR_SS58>"
export BT_WALLET_NAME="<LOCAL_COLDKEY_NAME>"
export BT_WALLET_HOTKEY="<LOCAL_MINER_HOTKEY_NAME>"
export BT_WALLET_PATH="$HOME/.bittensor/wallets"
export COLDKEY_SS58="<PUBLIC_COLDKEY_SS58>"
export HOTKEY_SS58="<PUBLIC_MINER_HOTKEY_SS58>"
```

`PUBLIC_IPV4` must be a literal global IPv4, not a hostname, loopback,
RFC1918/LAN, link-local, multicast, unspecified, reserved, or documentation
address. Open `$PUBLIC_PORT/tcp` in the provider firewall and Ubuntu firewall.
The operator must be able to test it from another machine.

Before registration, obtain enough testnet TAO through the approved public
testnet funding process. Share only the public coldkey SS58 when requesting
funding; never share its mnemonic, password, or wallet file.

## 5. Create and validate one supported task

The controlled cohort accepts only the implemented `parser_roundtrip` holdout
subset. Create the documented deterministic starter task:

```bash
dolores-miner init \
  --output "$HOME/dolores-tasks" \
  --archetype escape_delim \
  --seed 730214
```

Expected output includes exactly these fields:

```text
task_dir=...
task_id=...
package_hash=...
tests=author_tests validator_holdout=private
```

Set `TASK_DIR` to the printed absolute `task_dir`, inspect the task, then run:

```bash
export TASK_DIR="<PRINTED_TASK_DIR>"
dolores-miner validate --task-dir "$TASK_DIR"
```

Expected output begins `VALID task_id=` and includes `family=parser_roundtrip`,
`archetype=escape_delim`, `package_hash=`, and `author_tests=`. Miner-supplied
tests are author tests, not the private validator-owned holdout.

## 6. Preview registration without signing

The default registration command prints the exact pinned `btcli` command and
does not sign, register, or spend testnet TAO:

```bash
dolores-miner register \
  --network test \
  --netuid 523 \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY"
```

Expected output contains:

```text
command=btcli subnet register --network test --netuid 523 ...
registration=not_executed
```

Confirm the current netuid-523 recycle fee and the public coldkey balance using
the normal installed Bittensor tooling before requesting approval.

### STOP-LEON: human registration action

Stop here. Registration signs an extrinsic with the participant wallet and
spends the displayed testnet recycle fee. Approval must name the exact public
coldkey/hotkey, local selectors, `network=test`, `netuid=523`, displayed fee,
command, and recovery plan. The human enters any wallet password directly.

Only after that separate approval may the participant run:

```bash
dolores-miner register \
  --network test \
  --netuid 523 \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --execute \
  --confirm REGISTER-TESTNET-523
```

Stop on any unexpected network, netuid, fee, prompt, RPC error, or receipt.
Verify the public hotkey and assigned UID on testnet netuid 523 before continuing.

## 7. Prove local serving without publication

This starts the Axon listener but does not call `serve_axon` because `--publish`
is absent. The exact validator allowlist is mandatory; never use
`--allow-any-signed-validator` on the public cohort path.

```bash
dolores-miner serve \
  --task-dir "$TASK_DIR" \
  --quota 4 \
  --host 0.0.0.0 \
  --port "$PUBLIC_PORT" \
  --external-ip "$PUBLIC_IPV4" \
  --external-port "$PUBLIC_PORT" \
  --validator-hotkey "$VALIDATOR_HOTKEY" \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --network test \
  --netuid 523
```

Expected output includes:

```text
axon_publish=skipped reason=no_publish_flag
wire_miner_started ... endpoint=0.0.0.0:8091
```

In a second participant terminal, verify the local listener:

```bash
sudo -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner \
  health --host 127.0.0.1 --port 8091
```

Expected output:

```text
healthy=true endpoint=127.0.0.1:8091 attempts_used=1
```

From a different machine, test inbound TCP reachability to the literal public
IPv4 and port. Local health alone does not prove the provider firewall is open.
Stop the foreground miner with Ctrl-C after the external reachability check.

## 8. Publish the exact axon endpoint

Publishing signs `serve_axon` with the miner hotkey and writes the literal IPv4
and port to Bittensor public testnet. It does not transfer funds, but it is a
public chain metadata write.

### STOP-LEON: human axon-publication action

Stop again. The approval packet must include successful validation/local health,
cross-host TCP reachability, public miner hotkey and UID, literal IPv4/port,
validator allowlist, exact command, and recovery plan. Registration approval is
not publication approval.

Only after separate approval, run the previously proven command with
`--publish`:

```bash
dolores-miner serve \
  --task-dir "$TASK_DIR" \
  --quota 4 \
  --host 0.0.0.0 \
  --port "$PUBLIC_PORT" \
  --external-ip "$PUBLIC_IPV4" \
  --external-port "$PUBLIC_PORT" \
  --validator-hotkey "$VALIDATOR_HOTKEY" \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --publish \
  --network test \
  --netuid 523
```

Success requires both:

```text
axon_publish=ok netuid=523 external=<PUBLIC_IPV4>:<PUBLIC_PORT>
readback=exact
```

Stop if the exact endpoint does not read back. While that process is still
running, open a second service-user terminal, export the same public values and
wallet selectors from section 4, and execute the complete read-only audit:

```bash
dolores-miner doctor \
  --network test \
  --netuid 523 \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --wallet.path "$BT_WALLET_PATH" \
  --coldkey-ss58 "$COLDKEY_SS58" \
  --hotkey-ss58 "$HOTKEY_SS58" \
  --external-ip "$PUBLIC_IPV4" \
  --port "$PUBLIC_PORT" \
  --task-dir "$TASK_DIR" \
  --timeout 10
```

Success is JSON with top-level `"ok": true`. Doctor performs bounded read-only
balance and metagraph queries; it never registers, publishes an axon, sets
weights, reads wallet files, or prints wallet paths/selectors.

## 9. Install and verify the non-root systemd service

This section is the post-publication participant path. The separate
[`chain-neutral clean-VPS release rehearsal`](vps-rehearsal.md) uses a public,
temporary drop-in before registration; it never changes the base unit and is
not participant or cohort evidence.

After exact publication succeeds, stop the foreground miner and exit the
service-user shell. The published unit deliberately omits `--publish`; the
already-reviewed chain record persists across process restarts.

```bash
exit
sudo install -d -m 0750 -o root -g dolores-miner /etc/dolores
sudo install -m 0644 "$RELEASE_SOURCE/deploy/systemd/dolores-miner.service" \
  /etc/systemd/system/dolores-miner.service
sudo test -e /etc/dolores/miner.env || \
  sudo install -m 0640 -o root -g dolores-miner /dev/null /etc/dolores/miner.env
sudoedit /etc/dolores/miner.env
```

Set these names in `/etc/dolores/miner.env` using local values; never commit or
share the file:

```text
DOLORES_TASK_DIR=<PRINTED_TASK_DIR>
DOLORES_MINER_QUOTA=4
DOLORES_MINER_PORT=8091
DOLORES_EXTERNAL_IP=<VPS_GLOBAL_IPV4>
DOLORES_VALIDATOR_HOTKEY=<COHORT_VALIDATOR_SS58>
BT_WALLET_NAME=<LOCAL_COLDKEY_NAME>
BT_WALLET_HOTKEY=<LOCAL_MINER_HOTKEY_NAME>
BT_WALLET_PATH=/home/dolores-miner/.bittensor/wallets
COLDKEY_SS58=<PUBLIC_COLDKEY_SS58>
HOTKEY_SS58=<PUBLIC_MINER_HOTKEY_SS58>
```

Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dolores-miner.service
sudo systemctl status dolores-miner.service --no-pager
sudo journalctl -u dolores-miner.service --no-pager -n 100
sudo systemctl restart dolores-miner.service
sudo systemctl status dolores-miner.service --no-pager
sudo journalctl -u dolores-miner.service --no-pager -n 100
sudo -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner \
  health --host 127.0.0.1 --port 8091
```

Expected evidence shows `active (running)`, no restart loop, the same local
listener after restart, and no second axon-publication action.

Finally, the cohort operator runs this on the release-installed validator host:

```bash
dolores-validator health \
  --mode testnet \
  --work /var/lib/dolores-validator \
  --wallet.name "$VALIDATOR_WALLET_NAME" \
  --wallet.hotkey "$VALIDATOR_WALLET_HOTKEY" \
  --network test \
  --netuid 523
```

Do not use `--no-probe-wire`. The command must discover the published endpoint
from the netuid-523 metagraph and report all cohort miners signed-reachable with
no endpoint-related degraded condition. A successful signed reply
proves that the miner process is alive at the metagraph-discovered endpoint and
can answer the allowlisted validator. It does not replace participant-side
service status, journal, complete doctor, or cross-host TCP evidence.

## 10. Troubleshooting

### Python version

- Symptom: Python is not exactly `3.11.15`, `venv` fails, or pip selects an
  unsupported graph.
- Action: stop. Re-run the verified CPython source build and use only
  `/opt/python/3.11.15/bin/python3.11`; do not change `/usr/bin/python3`.

### Checksum mismatch

- Symptom: the handoff, checksum sidecar, wheel, sdist, manifest, provenance, or
  checklist digest differs.
- Action: delete only the mismatched download, download it again from the exact
  versioned URL, and re-check. A second mismatch is a release incident; do not
  install, disable checking, or accept a replacement hash in chat.

### Wallet ownership

- Symptom: doctor reports missing wallet metadata, or files belong to root or a
  different user.
- Action: stop the service. The participant must create/restore the wallet in a
  `sudo -u dolores-miner -H /bin/bash` terminal. Never copy, chown blindly, open,
  or print wallet files for debugging.

### Port or firewall

- Symptom: local health passes but another machine cannot connect.
- Action: verify the literal IPv4, listener, provider security group, Ubuntu
  firewall, and inbound TCP rule for the same fixed port. Do not treat a same-host
  hairpin check as cross-host proof.

### Version mismatch

- Symptom: installed engine, subnet, SDK, or CLI differs from the release.
- Action: stop and recreate the root-owned virtual environment from the two
  verified wheels. Do not mix PyPI, branch, editable, or private-path installs.

### Registration

- Symptom: insufficient testnet TAO, unexpected fee, RPC failure, wrong target,
  or password prompt appears outside the human terminal.
- Action: do not retry automatically. Confirm `network=test`, `netuid=523`,
  public balance, current fee, and human approval before one controlled retry.

### Axon read-back

- Symptom: publication returns but `readback=exact` is absent or the metagraph
  shows another host/port.
- Action: stop serving, correct endpoint/firewalls, wait through any Bittensor
  serving rate limit, obtain a new publication approval, and republish. Never
  inject a manual endpoint into the public-testnet validator.

### Service restart

- Symptom: `systemctl` reports failure or a restart loop.
- Action: keep the service stopped while inspecting complete relevant journal
  lines, unit/environment-file permissions, task ownership, listener conflicts,
  and exact executable paths. Do not patch only the VPS; report a product defect
  against the released source.

### Validator reachability

- Symptom: public TCP works but validator health reports the miner undiscovered,
  unsigned, or unreachable.
- Action: compare public hotkey, UID, metagraph host/port, allowlisted validator
  hotkey, clock, SDK versions, and signed-probe error. Do not use
  `--no-probe-wire`, loosen the allowlist, or supply a manual public-testnet
  endpoint.

## 11. What may and may never be shared

Safe to share with the cohort operator:

- immutable repository, tag, release, asset, and CI URLs;
- SHA-256 values and `OK` checksum output;
- Ubuntu version, `amd64` architecture, installed package versions, and import
  locations;
- public coldkey/hotkey SS58 addresses, netuid-523 UID, public IPv4, and port;
- task ID, package hash, redacted validation/doctor/health output;
- redacted `systemctl status` and relevant journal lines after confirming they
  contain no environment-file contents, paths that expose private layout, or
  secrets.

Never share:

- mnemonic or seed phrase, private key, wallet password, wallet file or its
  contents, SSH private key, provider credential, `.env` or `miner.env` content;
- validator holdout secret or active holdout cases;
- unredacted logs containing any of the above.

## 12. Ready-to-send HackerQuest message

> We have prepared Dolores Autocurricula `0.2.0rc1` for one controlled Bittensor
> public-testnet setup on `network=test`, `netuid=523`. Would you be willing to
> attempt the unsigned preparation from the immutable GitHub Release assets and
> report where the guide is unclear? The supported machine is a fresh Ubuntu
> 24.04 LTS amd64 VPS with 2 vCPU, 4 GB RAM, 25 GB disk, a global IPv4, and one
> inbound TCP port. You keep all wallet secrets and password entry in your own
> terminal. Please stop before registration and again before axon publication;
> each requires separate approval. This request is a handoff rehearsal, not a
> claim that an external miner, public cohort proof, or successful weight epochs
> already exist.
