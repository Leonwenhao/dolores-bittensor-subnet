# M5 - Full Localnet Rehearsal

Date: 2026-07-08

## Scope

Ran the M5 full localnet rehearsal against `ws://127.0.0.1:9944` only, using
localnet `netuid=2` and the active `dolores-test` wallet inventory.

No public testnet write, mainnet/finney command, public transfer, public stake,
public registration, public `set_weights`, paid provider call, GitHub push,
`.env` read, wallet key-file inspection, mnemonic inspection, seed phrase
inspection, or private credential inspection was performed.

Leon authorized the agent to run localnet-only signing/extrinsic commands for
this running container and `netuid=2`, provided every command used
`--network ws://127.0.0.1:9944`. That authorization was not used for any public
network.

## Outcome

M5 is **partial**, not complete.

What passed:

- Localnet container `dolores_localnet` ran from
  `ghcr.io/opentensor/subtensor-localnet:devnet-ready`.
- `dolores-test` was funded on localnet.
- Dolores localnet subnet was created as `netuid=2`.
- Subnet emission schedule was started; start extrinsic was `4221-2`.
- Validator hotkey was registered as uid 0.
- Miner-0 hotkey was registered as uid 1; registration extrinsic was `4837-2`.
- Miner-1 hotkey was registered as uid 2; registration extrinsic was `5355-3`.
- Validator permit was true.
- Dry-run epoch scoring produced a deterministic weights artifact and replayed.
- A pre-fix live localnet SDK submission returned receipt
  `mode=submitted`, `reason=submitted_ok`, `submission.success=true`.
- Post-fix dry-run/live rehearsal correctly skipped with
  `reason=commit_reveal_enabled`.
- Miners and localnet container were stopped and ports 8091/8092/9944/9945
  were clear after cleanup.

What blocked full acceptance:

- Localnet `netuid=2` had `commit_reveal_enabled=true`.
- The pre-fix live receipt submitted payload `uids_emitted=[1]`,
  `weights_u16=[65535]`, but manual metagraph read-back stayed
  `weights row: [0.0, 0.0, 0.0]`.
- After the chain seam was corrected to detect the SDK's
  `commit_reveal_enabled(netuid=...)` method, both dry-run and live-localnet
  rehearsals skipped with `mode=skipped`, `reason=commit_reveal_enabled`, and
  no submission.
- Attempts to disable commit-reveal did not flip the flag:
  - `btcli sudo set ... --param commit_reveal_weights_enabled --value false`
    failed with `Unable to reconnect because there are currently open
    subscriptions`.
  - direct SDK owner attempt failed with
    `AdminActionProhibitedDuringWeightsWindow`.
  - root-sudo localnet attempt returned outer success, but events showed
    `Sudo.Sudid` with an inner module error and the flag stayed true.

## Key Evidence

Localnet setup and chain state:

```bash
docker run -d --name dolores_localnet -p 9944:9944 -p 9945:9945 \
  ghcr.io/opentensor/subtensor-localnet:devnet-ready

.venv/bin/python scripts/preflight.py --mode localnet \
  --wallet.name dolores-test --wallet.hotkey validator \
  --network ws://127.0.0.1:9944 --netuid 2
# PASS chain reachability
# PASS chain readiness with validator_uid=0, validator_permit=true,
# commit_reveal_enabled=true
```

Observed localnet costs and permit:

- subnet creation burn: `1000.0` localnet TAO
  (`work/m5_full/02_burncost.json`)
- registration cost snapshots:
  - before miner registration: `0.07935363`
    (`work/m5_full/04_show_before_miners.json`)
  - after miner-0: `0.050670989`
    (`work/m5_full/04_show_after_miner_0.json`)
  - after miner-1: `0.023413629`
    (`work/m5_full/04_show_after_miner_1.json`)
- permit threshold: `0.0` additional localnet TAO after registration; permit
  was already true at first Phase 5 poll.

Dry-run and live receipts:

```bash
jq '{mode, reason, payload, submission}' \
  work/m5_full/dry_run/subnet_archive/epochs/epoch_1/chain_receipt_epoch_1.json
# mode=dry_run, reason=dry_run_ok, uids_emitted=[1], weights_u16=[65535],
# submission=null

jq '{mode, reason, payload, submission}' \
  work/m5_full/live/subnet_archive/epochs/epoch_2/chain_receipt_epoch_2.json
# mode=submitted, reason=submitted_ok, submission.success=true

cat work/m5_full/09_read_back.txt
# expected_u16: [(1, 65535)]
# weights row: [0.0, 0.0, 0.0]
# uid=1 expected_u16=65535 actual=0.0
```

Post-fix commit-reveal handling:

```bash
jq '{mode, reason, payload, submission}' \
  work/m5_full/postfix_dry_run/subnet_archive/epochs/epoch_3/chain_receipt_epoch_3.json
# mode=skipped, reason=commit_reveal_enabled, payload=null, submission=null

env DOLORES_ALLOW_EXTRINSICS=1 .venv/bin/python neurons/validator.py --mode localnet \
  --network ws://127.0.0.1:9944 --netuid 2 --chain live \
  --allow-extrinsics --confirm-live I-AM-LEON-AND-I-APPROVE \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 4 --quota 2 --work work/m5_full/postfix_live \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45

jq '{mode, reason, payload, submission}' \
  work/m5_full/postfix_live/subnet_archive/epochs/epoch_4/chain_receipt_epoch_4.json
# mode=skipped, reason=commit_reveal_enabled, payload=null, submission=null

env | rg '^DOLORES'
# no output; DOLORES_ALLOW_EXTRINSICS was not left set
```

Replay and verification:

```bash
.venv/bin/python scripts/report.py --work work/m5_full/dry_run --epoch 1 --replay-check 1
# REPLAY OK

.venv/bin/python scripts/report.py --work work/m5_full/live --epoch 2 --replay-check 2
# REPLAY OK

.venv/bin/python scripts/report.py --work work/m5_full/postfix_dry_run --epoch 3 --replay-check 3
# REPLAY OK

.venv/bin/python scripts/report.py --work work/m5_full/postfix_live --epoch 4 --replay-check 4
# REPLAY OK

.venv/bin/ruff check .
# All checks passed!

.venv/bin/python -m pytest -q
# 62 passed in 6.66s

.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey validator
.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey miner-0
.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey miner-1
# all PASS for required wire checks; chain checks skipped in wire mode
```

Cleanup:

```bash
docker stop dolores_localnet
docker rm dolores_localnet
lsof -nP -iTCP:8091 -iTCP:8092 -iTCP:9944 -iTCP:9945 -sTCP:LISTEN
# no output
```

## Artifacts

- `work/m5_full/netuid.txt`
- `work/m5_full/02_burncost.json`
- `work/m5_full/02_subnet_show.json`
- `work/m5_full/03_start_subnet.txt`
- `work/m5_full/04_register_miner_0.json`
- `work/m5_full/04_register_miner_1.json`
- `work/m5_full/04_uid_map.txt`
- `work/m5_full/05_permit_threshold.txt`
- `work/m5_full/dry_run/subnet_archive/epochs/epoch_1/`
- `work/m5_full/live/subnet_archive/epochs/epoch_2/`
- `work/m5_full/postfix_dry_run/subnet_archive/epochs/epoch_3/`
- `work/m5_full/postfix_live/subnet_archive/epochs/epoch_4/`
- `work/m5_full/09_read_back.txt`
- `work/m5_full/13_current_chain_status.txt`
- `work/m5_full/14_localnet_preflight_final.txt`
- `work/m5_full/14_ports_after_cleanup.txt`
- `work/m5_full/14_wire_preflight_validator.txt`
- `work/m5_full/14_wire_preflight_miner_0.txt`
- `work/m5_full/14_wire_preflight_miner_1.txt`

## Remaining Work

M5 full sign-off requires one of:

1. A fresh localnet subnet or corrected localnet hyperparameter path with
   `commit_reveal_enabled=false`, followed by live `set_weights` and metagraph
   read-back showing the submitted nonzero vector.
2. A deliberate commit-reveal implementation/rehearsal that records commit,
   reveal, and post-reveal metagraph read-back as the acceptance evidence.

M6 public testnet remains STOP-LEON for subnet creation, registration, staking,
validator permit, any live public `set_weights`, and any spend/signing action.
