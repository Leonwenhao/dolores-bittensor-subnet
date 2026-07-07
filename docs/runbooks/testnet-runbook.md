# Dolores Autocurricula Bittensor Testnet Runbook

Status: draft prepared after M3. M4+ is human-blocked until H2 wallets exist.

This runbook uses Dolores branding on-chain where a subnet identity/name is
needed. It never uses mainnet. Every command that signs or spends test TAO is
marked `LEON ONLY`.

## Safety Rules

- Never run a command that omits `--network test` or the explicit localnet URL.
- Never run a command containing `finney` for this plan.
- Do not paste mnemonics, private keys, provider keys, or wallet files into chat.
- Agents may run read-only diagnostics with explicit test/localnet network flags.
- Leon must run every create/register/stake/set-weights/signing command himself.

## Current Gate

M4 preflight currently stops at H2:

```bash
.venv/bin/python scripts/preflight.py --mode wire
# FAIL wallet existence: wallet files missing; STOP-LEON H2 create testnet-only wallet/hotkeys.
```

## H2 - Wallets (LEON ONLY)

Create a brand-new testnet-only coldkey and three hotkeys. Do not reuse funded,
production, or Dolores company keys.

```bash
btcli wallet new-coldkey --wallet.name dolores-test
btcli wallet new-hotkey --wallet.name dolores-test --wallet.hotkey validator
btcli wallet new-hotkey --wallet.name dolores-test --wallet.hotkey miner-0
btcli wallet new-hotkey --wallet.name dolores-test --wallet.hotkey miner-1
btcli wallet list
```

After this, rerun:

```bash
.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey validator
```

If macOS prompts when axon ports bind later, STOP-LEON H1: click **Allow**.

## M4 - Wire Mode After H2/H1

Expected future commands once wallets exist:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona honest --port 8091 \
  --wallet.name dolores-test --wallet.hotkey miner-0

.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer --port 8092 \
  --wallet.name dolores-test --wallet.hotkey miner-1

.venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:<miner-0-ss58>,127.0.0.1:8092:<miner-1-ss58> \
  --epoch 1 --work work/m4 --wallet.name dolores-test --wallet.hotkey validator

.venv/bin/python scripts/report.py --work work/m4 --epoch 1
```

M4 is not complete until both miners are reached over axon/dendrite and the
kill test records one unreachable miner without aborting the epoch.

## M5 - Localnet Rehearsal

Agent may start the local subtensor container:

```bash
docker run -d --name local_chain -p 9944:9944 -p 9945:9945 \
  ghcr.io/opentensor/subtensor-localnet:devnet-ready

.venv/bin/python scripts/preflight.py --mode localnet \
  --wallet.name dolores-test --wallet.hotkey validator
```

The following commands sign and are **LEON ONLY**:

```bash
btcli subnet create --network ws://127.0.0.1:9944 --wallet.name dolores-test
btcli subnets start --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet.name dolores-test
btcli subnet register --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet.name dolores-test --wallet.hotkey validator
btcli subnet register --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet.name dolores-test --wallet.hotkey miner-0
btcli subnet register --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet.name dolores-test --wallet.hotkey miner-1
btcli stake add --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet.name dolores-test --wallet.hotkey validator --amount <localnet-amount>
```

Wait at least one tempo after staking, then agent may run the read-only permit
check:

```bash
.venv/bin/python - <<'PY'
import bittensor as bt
m = bt.metagraph(netuid=<N>, network='ws://127.0.0.1:9944')
print(dict(zip(m.hotkeys, m.validator_permit)))
PY
```

## M6 - Public Testnet

Preconditions:

- H2 wallets exist.
- H3 test TAO has arrived on the `dolores-test` coldkey.
- H4 Leon approves the live testnet subnet lock/spend after seeing lock cost.
- H6 Leon is at the keyboard for every extrinsic.

Read-only diagnostics the agent may run:

```bash
btcli subnet lock-cost --network test
.venv/bin/python scripts/preflight.py --mode testnet \
  --wallet.name dolores-test --wallet.hotkey validator
```

The following sign/spend and are **LEON ONLY**:

```bash
btcli subnet create --network test --wallet.name dolores-test
btcli subnets start --netuid <N> --network test --wallet.name dolores-test
btcli subnet register --netuid <N> --network test \
  --wallet.name dolores-test --wallet.hotkey validator
btcli subnet register --netuid <N> --network test \
  --wallet.name dolores-test --wallet.hotkey miner-0
btcli subnet register --netuid <N> --network test \
  --wallet.name dolores-test --wallet.hotkey miner-1
btcli stake add --netuid <N> --network test \
  --wallet.name dolores-test --wallet.hotkey validator --amount <approved-test-tao>
```

After at least one tempo (360 blocks, about 72 minutes), confirm the validator
permit with a read-only metagraph check. Do not run a weight epoch before the
validator permit reads `True`.

When M6 is ready, create `configs/testnet.json` with public-only fields:

```json
{
  "name": "Dolores Autocurricula",
  "network": "test",
  "netuid": "<N>",
  "wallet_name": "dolores-test",
  "validator_hotkey": "<validator-ss58>",
  "miner_hotkeys": ["<miner-0-ss58>", "<miner-1-ss58>"]
}
```

M6 tier (a) is complete only with a real `set_weights` receipt and metagraph
read-back under `work/m6/`. If wallet/test TAO/permit/stake blocks the chain
extrinsic, record the fallback artifact as human-blocked, not failed, and do not
tag `testnet-v0`.
