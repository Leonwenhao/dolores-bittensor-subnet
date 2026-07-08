# Dolores Autocurricula Bittensor Testnet Runbook

Status: M4 wire-mode rehearsal and release-readiness hardening completed on
2026-07-08. H2 wallet creation is complete, and the `dolores-test` coldkey now
has 10.0 test TAO on `--network test`. No public subnet is registered yet. M6
chain-readiness now has a tested read-only and dry-run `SubtensorChain` path.
M6 public testnet remains blocked on netuid creation, registration, validator
permit, and Leon-approved signing/spend extrinsics.
Public subnet registration can proceed once Leon approves the
create/start/register/stake sequence. Public live weights require either
verified `commit_reveal_enabled=false` or an explicit validator
`--allow-commit-reveal` opt-in; commit-reveal submissions are not immediate
metagraph read-back evidence.

This runbook uses Dolores branding on-chain where a subnet identity/name is
needed. It never uses mainnet. Every command that signs or spends test TAO is
marked `LEON ONLY`.

## Safety Rules

- Never run a command that omits `--network test` or the explicit localnet URL.
- Never run a command containing `finney` for this plan.
- Do not paste mnemonics, private keys, provider keys, or wallet files into chat.
- Agents may run read-only diagnostics with explicit test/localnet network flags.
- Leon must run every create/register/stake/set-weights/signing command himself.
- `btcli` has no weights command in this installed version; live `set_weights`
  uses the SDK through the gated `SubtensorChain` client and is **LEON ONLY**.

## Current Gate

M4 preflight no longer stops at H2. The `dolores-test` wallet and three hotkeys
exist locally under `~/.bittensor/wallets/`, and `configs/testnet.json` contains
only public fields. M4 wire mode has run locally via Bittensor Axon/Dendrite.
The coldkey has 10.0 test TAO free and 0.0 staked, but M6 public testnet
registration is still blocked on STOP-LEON H4/H6 approval for every extrinsic,
public netuid creation, neuron registration, stake, validator permit, and a
live weight receipt. The chain client can now do read-only checks and dry-run
payload receipts, but defaults to `--chain off`.

```bash
.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey validator
# PASS wallet existence: wallet dolores-test/validator exists (not read)
```

## H2 - Wallets

Completed on 2026-07-07 as a testnet-only local wallet. The wallet was created
non-interactively for speed at the hackerhouse, with no secrets printed or
stored in the repo. Do not reuse these keys for mainnet, production funds, or
Dolores company custody.

Public fields currently recorded in `configs/testnet.json`:

- Coldkey: `5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG`
- Testnet balance: 10.0 free TAO, 0.0 staked TAO, 10.0 total TAO.
- Validator hotkey: `5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm`
- Miner 0 hotkey: `5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA`
- Miner 1 hotkey: `5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg`

Equivalent manual commands for a fresh machine:

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

## M4 - Wire Mode

Completed commands:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona honest --quota 2 \
  --seed 201 --port 8091 --wallet.name dolores-test --wallet.hotkey miner-0

.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer \
  --quota 2 --seed 202 --port 8092 \
  --wallet.name dolores-test --wallet.hotkey miner-1

.venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/m4_wire \
  --wallet.name dolores-test --wallet.hotkey validator \
  --timeout 45

.venv/bin/python scripts/report.py --work work/m4_wire --epoch 1
.venv/bin/python scripts/report.py --work work/m4_wire --epoch 1 --replay-check 1
```

M4 completion evidence:

- Both miners were reached over axon/dendrite.
- Honest miner received weight `1.0`; duplicate-spammer received `0.0`.
- Docker-backed Dolores verification ran with `containerized=true`.
- Replay check passed.
- Kill test stopped miner 1, recorded it as terminal `unreachable` with no
  package hash, did not mark the epoch degraded, and did not abort.
- Miner-supplied reserved control keys such as `wire_error` are rejected as
  `invalid`; they cannot self-declare `infra_error`.
- Aggregate wire responses above `MAX_RESPONSE_BYTES` are terminal `invalid`
  outcomes before task validation.

Artifacts:

- `work/m4_hardening_wire/subnet_archive/epochs/epoch_1/report_epoch_1.md`
- `work/m4_hardening_kill/subnet_archive/epochs/epoch_1/report_epoch_1.md`
- `work/m4_wire/subnet_archive/epochs/epoch_1/report_epoch_1.md`
- `work/m4_wire_kill/subnet_archive/epochs/epoch_1/report_epoch_1.md`
- `docs/diary/2026-07-08-m4-wire.md`
- `docs/diary/2026-07-08-m4-hardening.md`

## M5 - Localnet Rehearsal

Agent may start the local subtensor container:

```bash
docker run -d --name dolores_localnet -p 9944:9944 -p 9945:9945 \
  ghcr.io/opentensor/subtensor-localnet:devnet-ready

.venv/bin/python scripts/preflight.py --mode localnet \
  --wallet.name dolores-test --wallet.hotkey validator \
  --network ws://127.0.0.1:9944
```

The 2026-07-08 M5 rehearsals confirmed this image runs on arm64 and exposes a
preseeded local subnet `netuid=1` named `apex`. A full localnet rehearsal then
created Dolores `netuid=2`, registered validator/miner-0/miner-1, and obtained
validator permit. Read-only discovery commands:

```bash
btcli subnets list --network ws://127.0.0.1:9944 --json-output
btcli subnets show --netuid 1 --mechid 0 \
  --network ws://127.0.0.1:9944 --no-prompt --json-output
```

That preseeded subnet does not register the Dolores hotkeys by default. A
netuid-aware preflight may therefore fail closed with
`reason: "validator_unregistered"` until the localnet registration steps below
are completed.

Important correction from the netuid=2 rehearsal: the created localnet subnet
had `commit_reveal_enabled=true`. Immediate metagraph weight read-back stayed
zero after a successful commit-style SDK submission. Full M5 sign-off still
requires either commit-reveal disabled before phase 7 or a separately designed
commit-reveal reveal/read-back path. With the current chain client, preflight
will report commit-reveal status and the epoch receipt will skip with
`reason: "commit_reveal_enabled"` instead of submitting.

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
st = bt.Subtensor(network="ws://127.0.0.1:9944")
m = st.metagraph(netuid=<N>, lite=True)
print(dict(zip([str(h) for h in m.hotkeys], [bool(p) for p in m.validator_permit])))
PY
```

After the localnet miners are registered and serving axons, the agent may run a
non-signing dry-run epoch:

```bash
.venv/bin/python neurons/validator.py --mode localnet \
  --network ws://127.0.0.1:9944 --netuid <N> \
  --chain dry-run --epoch 1 --quota 2 --work work/m5 \
  --wallet.name dolores-test --wallet.hotkey validator
```

This writes `chain_receipt_epoch_1.json` with `submission: null`. A live localnet
`--chain live` run is still **LEON ONLY** because it signs `set_weights`.
Before claiming M5 complete, inspect the receipt and then run manual metagraph
read-back. `submitted_ok` alone is insufficient when commit-reveal is enabled.

If registration is not yet approved, a static-endpoint localnet rehearsal can
still validate miner payloads and prove the chain client fails closed:

```bash
.venv/bin/python neurons/validator.py --mode localnet \
  --network ws://127.0.0.1:9944 --netuid 1 \
  --chain dry-run \
  --miner-endpoints 127.0.0.1:8091:<miner-0-hotkey>,127.0.0.1:8092:<miner-1-hotkey> \
  --epoch 1 --quota 2 --work work/m5_static \
  --wallet.name dolores-test --wallet.hotkey validator
```

This fallback is not full M5 sign-off because miner discovery is not from the
metagraph and no localnet `set_weights` extrinsic is submitted.

## M6 - Public Testnet

Preconditions:

- H2 wallets exist.
- H3 is satisfied: 10.0 test TAO is present on the `dolores-test` coldkey.
- Real `SubtensorChain`/`set_weights` code has been implemented and tested
  without signing.
- H4 Leon approves the live testnet subnet burn/spend after seeing a fresh burn
  cost.
- H6 Leon is at the keyboard for every extrinsic.

Registration can proceed before the live-weight commit-reveal decision is
closed. Do not run a public live-weight epoch until either read-only
preflight/hyperparameters show `commit_reveal_enabled=false`, or Leon
explicitly chooses the commit-reveal path and the validator command includes
`--allow-commit-reveal`.

Read-only diagnostics the agent may run:

```bash
btcli subnet burn-cost --network test
btcli subnets check-start --network test --netuid <N>
.venv/bin/python scripts/preflight.py --mode testnet \
  --wallet.name dolores-test --wallet.hotkey validator --netuid <N>
```

When `configs/testnet.json.netuid` is still `null`, testnet preflight can only
check network reachability. Once a netuid exists, preflight adds read-only
subnet readiness: subnet existence, validator registration, permit, rate-limit,
and commit-reveal status. It never constructs a live-publish client.

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

Before `btcli subnet create`, re-query `btcli subnet burn-cost --network test`.
The burn cost is dynamic. A read-only M7 check observed `1.0000 τ`, but that
number is point-in-time only. Subnet creation also has a 14,400-block
(approximately 2-day) per-account reuse/rate-limit window, so a mistaken create
can cost both the burn and two days of calendar time.

After at least one tempo (360 blocks, about 72 minutes), confirm the validator
permit with a read-only metagraph check. Do not run a weight epoch before the
validator permit reads `True`.

Dry-run the exact weight payload before any live write:

```bash
.venv/bin/python neurons/validator.py --mode testnet --netuid <N> \
  --chain dry-run --epoch 1 --quota 2 --work work/m6 \
  --wallet.name dolores-test --wallet.hotkey validator
```

If commit-reveal is enabled and Leon has chosen the commit-reveal path, add
the explicit dry-run opt-in too:

```bash
.venv/bin/python neurons/validator.py --mode testnet --netuid <N> \
  --chain dry-run --allow-commit-reveal \
  --epoch 1 --quota 2 --work work/m6 \
  --wallet.name dolores-test --wallet.hotkey validator
```

Expected artifact paths:

- `work/m6/subnet_archive/epochs/epoch_1/weights_epoch_1.json`
- `work/m6/subnet_archive/epochs/epoch_1/chain_receipt_epoch_1.json`

When the dry-run is allowed to build a payload, its receipt has
`mode: dry_run`, `reason: dry_run_ok`, the active hotkey-to-UID mapping,
dropped hotkeys, normalized weights, emitted UID/u16 payload, payload digest,
`submission: null`, and `read_back: null`. If commit-reveal is enabled and the
opt-in flag is absent, the receipt should instead be
`reason: commit_reveal_enabled` with `submission: null`.

The live SDK weight path is **LEON ONLY** and must not be run by agents:

```bash
export DOLORES_ALLOW_EXTRINSICS=1
.venv/bin/python neurons/validator.py --mode testnet --netuid <N> \
  --chain live --allow-extrinsics \
  --confirm-live I-AM-LEON-AND-I-APPROVE \
  --epoch 1 --quota 2 --work work/m6 \
  --wallet.name dolores-test --wallet.hotkey validator
unset DOLORES_ALLOW_EXTRINSICS
```

If any gate is missing, the validator records `mode: error` and
`reason: extrinsics_not_allowed` instead of calling `set_weights`.

If commit-reveal is enabled and `--allow-commit-reveal` is absent, the validator
records `mode: skipped`, `reason: commit_reveal_enabled`, `submission: null`.
If the commit-reveal probe fails or the SDK surface changes, it records
`mode: skipped`, `reason: commit_reveal_probe_failed`, `submission: null`.

If Leon explicitly chooses the commit-reveal path, add the opt-in flag while
keeping all four live gates:

```bash
export DOLORES_ALLOW_EXTRINSICS=1
.venv/bin/python neurons/validator.py --mode testnet --netuid <N> \
  --chain live --allow-extrinsics --allow-commit-reveal \
  --confirm-live I-AM-LEON-AND-I-APPROVE \
  --epoch 1 --quota 2 --work work/m6 \
  --wallet.name dolores-test --wallet.hotkey validator
unset DOLORES_ALLOW_EXTRINSICS
```

A commit-reveal live receipt should record `mode: submitted`,
`reason: submitted_commit_reveal`, and
`chain_state.commit_reveal_enabled: true`. Treat that as commit evidence only.
It is not immediate metagraph read-back evidence; poll after the reveal window
before claiming visible nonzero weights.

When M6 is ready, update the existing public-only `configs/testnet.json` with the
new `netuid` and any receipt references. Keep the nested shape already in the
file:

```json
{
  "name": "Dolores Autocurricula",
  "network": "test",
  "status": "public_subnet_registered_no_weights",
  "netuid": <N>,
  "wallet_name": "dolores-test",
  "coldkey_ss58": "5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG",
  "balance": {
    "network": "test",
    "free_tao": "<read-only balance at time of update>",
    "staked_tao": "<read-only balance at time of update>",
    "total_tao": "<read-only balance at time of update>"
  },
  "public_subnet_registered": true,
  "validator_permit": false,
  "validator": {
    "hotkey_name": "validator",
    "hotkey_ss58": "5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm"
  },
  "miners": [
    {
      "hotkey_name": "miner-0",
      "hotkey_ss58": "5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA"
    },
    {
      "hotkey_name": "miner-1",
      "hotkey_ss58": "5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg"
    }
  ]
}
```

M6 tier (a) is complete only with a real `set_weights` receipt and metagraph
read-back under `work/m6/`. If wallet/test TAO/permit/stake blocks the chain
extrinsic, record the fallback artifact as human-blocked, not failed, and do not
tag `testnet-v0`.
