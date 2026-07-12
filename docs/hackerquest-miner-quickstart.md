# HackerQuest Controlled-Cohort Miner Quickstart

This is the supported Ubuntu VPS path for a known HackerQuest participant on
Bittensor public testnet. It is fixed to `network=test`, `netuid=523`. It is not
a permissionless or mainnet launch guide.

Registration and axon publication are signed operator actions. Complete the
unsigned preparation and local serving checks first, then stop for explicit
operator approval before either action.

## What the miner machine needs

- CPython 3.11.x, the only runtime supported and tested for this cohort;
- the approved immutable `dolores-autocurricula==0.2.0rc1` and
  `dolores-bittensor-subnet==0.2.0rc1` release artifacts;
- Bittensor SDK 10.5.0, Bittensor CLI 9.23.1, and its `btcli` executable,
  installed by the subnet package;
- a participant-controlled Bittensor wallet and hotkey under the non-root
  service account;
- a literal, globally routable IPv4 address and a fixed inbound TCP port;
- the exact public validator hotkey supplied by the cohort operator.

The miner base install does **not** require Docker, DuckDB, PyArrow, Fireworks
credentials, a solver panel, Streamlit, or validator internals. Docker execution
and the private validator-owned holdout run on the validator machine.

Never send or paste a mnemonic, seed phrase, private key, wallet password,
wallet file, or `.env` content to the operator, an agent, an issue, or a log.
Wallet creation and password entry happen only in the participant's own
terminal.

## 1. Install the approved releases

Do this only after the operator supplies the approved public artifact locations
and SHA-256 values for the engine wheel, subnet wheel, and subnet source
distribution. Verify all three before installing or extracting. Do not install
from a private checkout, `DOLORES_REPO`, an editable path, or an unpinned
branch.

Run this installation block from an administrator shell. Create the service
account first so every wallet and task created later belongs to the same
non-root identity that systemd will use. The virtual environment is deliberately
root-owned and read-only to the service account.

```bash
sudo useradd --system --create-home --home-dir /home/dolores-miner \
  --shell /usr/sbin/nologin dolores-miner
sudo install -d -m 0755 -o root -g root /opt/dolores-miner
python3.11 --version
sudo python3.11 -m venv /opt/dolores-miner/venv
sudo /opt/dolores-miner/venv/bin/python -m pip install --upgrade pip
sudo /opt/dolores-miner/venv/bin/python -m pip install \
  /path/to/dolores_autocurricula-0.2.0rc1-py3-none-any.whl \
  /path/to/dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl
sudo /opt/dolores-miner/venv/bin/python -m pip check
```

The wheel paths above are local filenames for already verified public release
artifacts. Replace them with the actual downloaded paths; do not infer or invent
a registry URL.

Also verify and extract the matching public subnet source distribution,
`dolores_bittensor_subnet-0.2.0rc1.tar.gz`, which carries the reviewed service
unit and runbooks. Set `RELEASE_SOURCE` to its extracted top-level directory.
Do not copy deployment files from an unpinned branch or private checkout.

Open a shell as the service account and keep steps 2 through 6 in that shell.
This makes `$HOME`, the Bittensor wallet root, and generated task ownership match
the eventual service. Direct `sudo -u` execution works even though interactive
login for the account is disabled.

```bash
sudo -u dolores-miner -H /bin/bash
source /opt/dolores-miner/venv/bin/activate
dolores-miner --help
```

## 2. Fix the public endpoint and validator identity

Before running the commands below, set these shell variables locally:

- `PUBLIC_IPV4`: the VPS's actual numeric, globally routable IPv4 address;
- `PUBLIC_PORT`: a fixed free inbound TCP port, normally `8091`;
- `VALIDATOR_HOTKEY`: the exact public validator SS58 hotkey supplied by the
  operator;
- `BT_WALLET_NAME` and `BT_WALLET_HOTKEY`: local wallet selectors, not key
  material;
- `BT_WALLET_PATH`: the wallet root, normally
  `$HOME/.bittensor/wallets` for the service account;
- `COLDKEY_SS58` and `HOTKEY_SS58`: the participant-supplied public addresses.
  These are public identifiers, never mnemonics, seeds, private keys, or wallet
  file contents.

Do not use a hostname, automatic address-discovery substitution, `127.0.0.1`,
RFC1918/LAN space, link-local space, or a documentation-only reserved address as
`PUBLIC_IPV4`. Public mode validates the literal address with Python's global
IPv4 policy.

Open `PUBLIC_PORT/tcp` in the VPS provider firewall and host firewall. The
validator must be able to reach it from another machine.

The full doctor is an operational audit, so it intentionally fails until the
hotkey is registered, its exact axon is published, and the public endpoint is
reachable. Run it after publication in step 6. It performs public chain reads
only and never signs or submits an extrinsic. Wallet checks use filesystem
metadata only: doctor does not open a coldkey or hotkey file, derive an address
from one, or print wallet selectors, addresses, or paths.

## 3. Create and validate one supported task

The controlled cohort accepts only the implemented `parser_roundtrip` holdout
subset. Start with one of the supported archetypes:

```bash
dolores-miner init \
  --output "$HOME/dolores-tasks" \
  --archetype escape_delim \
  --seed 730214
```

The command prints `task_dir`, `task_id`, and `package_hash`. Set `TASK_DIR` to
the printed task directory, inspect the task, and validate it:

```bash
dolores-miner validate --task-dir "$TASK_DIR"
```

`validate` proves schema, stable hash, wire size, and supported-family policy.
The tests carried by the task are author tests; they are not the private
validator-owned holdout.

## 4. Preview registration without signing

The default registration command only prints the exact `btcli` command. It does
not register or spend anything:

```bash
dolores-miner register \
  --network test \
  --netuid 523 \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY"
```

Verify that the printed command also spells `--network test --netuid 523`. Check
the current testnet registration recycle fee and public balance through the
normal Bittensor tooling before proceeding. Testnet TAO has no monetary value,
but registration still signs an extrinsic and spends the current testnet recycle
fee.

### STOP-LEON: registration

The participant or operator must explicitly approve registration. The action
signs a registration extrinsic and spends the displayed testnet recycle fee. It
must never target another network or netuid.

After approval, the implemented wrapper requires its own confirmation token:

```bash
dolores-miner register \
  --network test \
  --netuid 523 \
  --wallet.name "$BT_WALLET_NAME" \
  --wallet.hotkey "$BT_WALLET_HOTKEY" \
  --execute \
  --confirm REGISTER-TESTNET-523
```

If a wallet password prompt appears, the participant enters it directly. Stop
on any unexpected target, fee, prompt, or error. Verify the public hotkey and UID
on netuid 523 before continuing.

## 5. Prove local serving without publication

This opens the axon but does not call `serve_axon` because `--publish` is absent.
The exact validator allowlist is mandatory; never use
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

In a second terminal, check the local listener:

```bash
dolores-miner health --host 127.0.0.1 --port "$PUBLIC_PORT"
```

Then have the operator test inbound TCP reachability from the validator side.
The local `health` command checks the listener only; it does not claim metagraph
publication or remote reachability. Stop the foreground miner after these checks.

## 6. Publish the exact axon endpoint

Publishing is not part of local preparation. It signs `serve_axon` with the
miner hotkey and publishes the literal IPv4 and port on testnet. It does not move
funds, but it is a public chain metadata write.

### STOP-LEON: axon publication

Before approval, provide:

- successful `validate`, local listener, and validator-side inbound
  reachability evidence; the complete doctor runs immediately after exact
  publication because its metagraph check cannot pass beforehand;
- the public miner hotkey and netuid-523 UID;
- the exact literal IPv4 and fixed port;
- the exact validator hotkey allowlist;
- the command below and the recovery plan: stop serving, correct the endpoint,
  wait through any serving rate limit, and republish the corrected endpoint.

After explicit approval, add only `--publish` to the previously proven serve
command:

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

Success requires both `axon_publish=ok` and `readback=exact`. Stop if exact
metagraph read-back fails. Once publication succeeds, stop the foreground
process and use the supervised service below with the identical endpoint.

While that proven miner process is still running, execute the complete
read-only audit in a second terminal:

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
  --timeout 5
```

Success is JSON with top-level `"ok": true`. The required checks are: CPython
3.11.x; exact engine, subnet, SDK, and CLI versions; the `btcli`
executable; metadata-only wallet layout; literal global IPv4 and valid port;
curated and supplied-task generate/hash/wire smokes; readable public balance;
registered hotkey and UID; exact owner/hotkey/IP/port axon read-back; local port
state; and inbound public TCP reachability. Any failed required check makes the
command exit nonzero. The balance and metagraph calls are bounded, read-only
queries; doctor never performs registration, axon publication, weight setting,
or any other chain write.

## 7. Install the non-root systemd service

The service intentionally omits `--publish`: publication is the explicit action
above, while the on-chain axon record persists across process restarts.

The dedicated non-root `dolores-miner` account was created before installation.
Provision the participant wallet under that account's home in the participant's
own terminal; never send its recovery material through automation or logs. Task
paths in `DOLORES_TASK_DIR` must likewise point to files created in that account's
home, not to a root user's `$HOME`.

Exit the service-user shell, return to an administrator shell, then install the
unit and create a root-managed environment file:

```bash
exit
sudo install -d -m 0750 -o root -g dolores-miner /etc/dolores
sudo install -m 0644 "$RELEASE_SOURCE/deploy/systemd/dolores-miner.service" \
  /etc/systemd/system/dolores-miner.service
sudo test -e /etc/dolores/miner.env || \
  sudo install -m 0640 -o root -g dolores-miner /dev/null /etc/dolores/miner.env
sudoedit /etc/dolores/miner.env
```

Set these names in `/etc/dolores/miner.env` using local values; do not commit or
share the file:

- `DOLORES_TASK_DIR`
- `DOLORES_MINER_QUOTA`
- `DOLORES_MINER_PORT`
- `DOLORES_EXTERNAL_IP` — literal globally routable IPv4
- `DOLORES_VALIDATOR_HOTKEY` — exact allowlisted validator
- `BT_WALLET_NAME`
- `BT_WALLET_HOTKEY`
- `BT_WALLET_PATH` — normally
  `/home/dolores-miner/.bittensor/wallets` for the service account
- `COLDKEY_SS58` and `HOTKEY_SS58` — public addresses only

The file contains selectors, public addresses, and endpoint configuration, not
private keys. Keep it root-owned because operational configuration should still
be private. `ExecStartPost` runs the complete read-only doctor after the listener
starts; a failed exact metagraph/public-reachability audit makes the service
start fail rather than silently serving a mismatched endpoint.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dolores-miner.service
sudo systemctl status dolores-miner.service
sudo journalctl -u dolores-miner.service --no-pager -n 100
sudo -u dolores-miner /opt/dolores-miner/venv/bin/dolores-miner \
  health --host 127.0.0.1 --port "$PUBLIC_PORT"
```

Finally, verify from the validator side that:

1. the exact public axon remains in the netuid-523 metagraph;
2. signed reachability succeeds through the exact validator allowlist;
3. a controlled `systemctl restart dolores-miner` preserves the same endpoint;
4. the post-restart local health and validator-side signed reachability both pass.

Do not hand the validator a manual endpoint. Cohort evidence must use metagraph
discovery.
