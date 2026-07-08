# M5 Full Localnet Rehearsal — LEON-ONLY Command Sheet

Date prepared: 2026-07-08 (Fable). Every flag below was verified against the
installed btcli 9.23.1 help and, where marked "verified live", against a
read-only query of a freshly started localnet container during preparation.
No signing command was executed during preparation.

Purpose: complete full M5 per
`docs/reviews/2026-07-08-fable-m5-m6-readiness-review.md` §4 — rehearse the
exact create → start → register ×3 → stake → permit → dry-run → live
`set_weights` sequence at zero real-TAO cost, measure permit behavior, and
exercise the three never-tested real-substrate seams before the one-shot
public testnet create.

## Ground rules

- **Everything here is localnet-only** (`--network ws://127.0.0.1:9944`).
  No command in this sheet touches `--network test`, finney, or mainnet.
- Steps marked **LEON** sign extrinsics and are yours alone. Steps marked
  **AGENT** are read-only (or local file writes) and Codex/Fable may run them.
- The Alice key used for funding is the **public, well-known Substrate dev
  account** baked into every localnet chain. It is not a secret. Never use it,
  or the throwaway `alice-localnet` wallet, on any real network.
- **The whole rehearsal must happen in one container session.** Stopping the
  container resets the chain — the subnet, registrations, and stake vanish.
- Verified live during preparation: on a fresh container, the `dolores-test`
  coldkey has **0 τ** and Alice (`5GrwvaEF…utQY`) has **~1,000,000 τ**; the
  localnet subnet-creation burn cost reads **1000 τ** (not testnet's 1 τ).
  That is why phase 1 transfers 5000 τ.
- Expected new netuid is **2** (the image preseeds 0 = root and 1 = `apex`).
  Confirm the actual value at phase 2 and use it everywhere `<N>` appears.
- 2026-07-08 rehearsal correction: the created localnet subnet `netuid=2`
  had `commit_reveal_weights_enabled=True`. Immediate metagraph weight
  read-back does not match a commit-reveal submission. Full M5 sign-off still
  requires `commit_reveal_enabled=False` or an explicit commit-reveal reveal
  path with read-back evidence. If the check in phase 6.5 stays true, stop and
  mark M5 partial; do not claim a live immediate `set_weights` read-back.

## Active Dolores wallet inventory

Verified against the local Bittensor CLI wallet on 2026-07-08 with:

```bash
.venv/bin/btcli wallet list --wallet-path ~/.bittensor/wallets \
  --wallet-name dolores-test
```

Use these `dolores-test` public addresses for this rehearsal. Do not substitute
the older `testnet-alice-receiver` wallet.

- Coldkey: `5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG`
- Validator hotkey: `5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm`
- Miner 0 hotkey: `5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA`
- Miner 1 hotkey: `5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg`

## Phase 0 — AGENT: container + preflight

```bash
docker run -d --name dolores_localnet -p 9944:9944 -p 9945:9945 \
  ghcr.io/opentensor/subtensor-localnet:devnet-ready

.venv/bin/python scripts/preflight.py --mode localnet \
  --wallet.name dolores-test --wallet.hotkey validator \
  --network ws://127.0.0.1:9944
# expect: PASS chain reachability; SKIP chain readiness (netuid unset)

mkdir -p work/m5_full
```

## Phase 1 — LEON: fund the dolores-test coldkey (one-time per container)

1a. Create the throwaway Alice wallet (skip if `alice-localnet` already exists
from a previous session — check with `.venv/bin/btcli wallet list | grep alice`).
This is the standard public dev seed; verified during preparation to derive
`5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY`:

```bash
.venv/bin/btcli wallet regen-coldkey --wallet-name alice-localnet \
  --seed 0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a
```

(Choose any password or none — this wallet is disposable and localnet-only.)

1b. Transfer 5000 localnet τ to the dolores-test coldkey
(covers the 1000 τ create burn + registrations + stake escalation + fees):

```bash
.venv/bin/btcli wallet transfer --wallet-name alice-localnet \
  --destination 5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG \
  --amount 5000 --network ws://127.0.0.1:9944
```

1c. **AGENT** read-back:

```bash
.venv/bin/btcli wallet balance \
  --ss58 5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG \
  --network ws://127.0.0.1:9944 | tee work/m5_full/01_balance_after_fund.txt
# expect: Free ~5000
```

## Phase 2 — LEON: create the subnet

2a. **AGENT** re-reads the localnet burn cost first (muscle memory for the
public H4 gate):

```bash
.venv/bin/btcli subnets burn-cost --network ws://127.0.0.1:9944 --json-output \
  | tee work/m5_full/02_burncost.json
# preparation read: {"burn_cost": {"tao": 1000.0}, ...}
```

2b. **LEON** creates — identity flags included deliberately, because on public
testnet they fold irreversibly into this same one-shot command (H5 rehearsal):

```bash
.venv/bin/btcli subnets create --network ws://127.0.0.1:9944 \
  --wallet-name dolores-test \
  --subnet-name "Dolores Autocurricula" \
  --github-repo "https://github.com/Leonwenhao/dolores-bittensor-subnet" \
  --subnet-contact "leonwenhao@gmail.com"
```

Record the netuid it prints — that is `<N>` (expected 2) — in
`work/m5_full/netuid.txt`.

2c. **AGENT** read-back:

```bash
.venv/bin/btcli subnets show --netuid <N> --mechid 0 \
  --network ws://127.0.0.1:9944 --no-prompt --json-output \
  | tee work/m5_full/02_subnet_show.json
# expect: owner coldkey = 5ELE5Rr…JHVG
```

## Phase 3 — start the emission schedule

3a. **AGENT** polls the read-only start check until it reports startable:

```bash
.venv/bin/btcli subnets check-start --netuid <N> --network ws://127.0.0.1:9944 \
  | tee work/m5_full/03_check_start.txt
```

3b. **LEON** when check-start is green:

```bash
.venv/bin/btcli subnets start --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet-name dolores-test
```

## Phase 4 — register the three hotkeys

4a. **AGENT** reads the per-neuron registration burn first (on public testnet
this is the STOP-LEON S3 budget re-check; rehearse the same order):

```bash
.venv/bin/btcli subnets hyperparameters --netuid <N> \
  --network ws://127.0.0.1:9944 | tee work/m5_full/04_hyperparams.txt
# note the Burn / registration-cost field
```

4b. **LEON**, validator first, then miners, one at a time:

```bash
.venv/bin/btcli subnets register --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet-name dolores-test --hotkey validator
```

**AGENT** read-back between each registration:

```bash
.venv/bin/btcli subnets show --netuid <N> --mechid 0 \
  --network ws://127.0.0.1:9944 --no-prompt --json-output \
  | tee work/m5_full/04_show_after_validator.json
```

```bash
.venv/bin/btcli subnets register --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet-name dolores-test --hotkey miner-0

.venv/bin/btcli subnets register --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet-name dolores-test --hotkey miner-1
```

**AGENT** final read-back: all three hotkeys have uids; record the uid↔hotkey
map in `work/m5_full/04_uid_map.txt`.

## Phase 5 — LEON: stake to the validator hotkey (the permit measurement)

This is the #1 measurement of the rehearsal: **the smallest stake at which
`validator_permit` flips True.** Localnet blocks are fast, so escalate in ×10
steps rather than over-asking:

```bash
.venv/bin/btcli stake add --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet-name dolores-test --hotkey validator \
  --amount 1.0 --safe --tolerance 0.05
```

After each stake, run the phase-6 permit poll. If the permit stays False after
a full localnet tempo, repeat with `--amount 10`, then `--amount 100`.
Record every (cumulative stake → permit True/False) pair in
`work/m5_full/05_permit_threshold.txt` — this is the number the public-testnet
stake decision wants.

## Phase 6 — AGENT: permit poll (read-only)

```bash
.venv/bin/python - <<'PY'
import bittensor as bt
st = bt.Subtensor(network="ws://127.0.0.1:9944")
m = st.metagraph(netuid=<N>, lite=True)
print(dict(zip([str(h) for h in m.hotkeys], [bool(p) for p in m.validator_permit])))
print("block:", st.get_current_block())
PY
```

Proceed only when `5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm: True`.

## Phase 6.5 - AGENT/LEON: commit-reveal status before weight rehearsal

**AGENT** read-only check:

```bash
.venv/bin/python scripts/preflight.py --mode localnet \
  --wallet.name dolores-test --wallet.hotkey validator \
  --network ws://127.0.0.1:9944 --netuid <N> \
  | tee work/m5_full/06_preflight_before_dry_run.txt
```

Inspect `chain readiness` for `commit_reveal_enabled`. If it is `false`,
continue to phase 7.

If it is `true`, the immediate-read-back M5 path is not ready. A localnet-only
owner attempt to disable it is a signing command and remains **LEON ONLY**
unless Leon explicitly authorizes the agent for this localnet container:

```bash
.venv/bin/btcli sudo set --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet-name dolores-test \
  --param commit_reveal_weights_enabled --value false
```

Then rerun the preflight above. If `commit_reveal_enabled` remains `true`,
stop with a partial M5 verdict. The 2026-07-08 netuid=2 rehearsal observed
`btcli` failing with an open-subscription reconnect error, direct SDK owner
attempts failing with `AdminActionProhibitedDuringWeightsWindow`, and a
root-sudo localnet attempt emitting `Sudo.Sudid` with an inner module error;
the flag stayed enabled.

## Phase 7 — AGENT: miners up + first real dry-run epoch

Use M4's known-good seeds (201/202) so the honest-wins scenario is clean —
the earlier partial-M5 seeds (501/502) produced a confusing near-tie:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona honest --quota 2 \
  --seed 201 --port 8091 --wallet.name dolores-test --wallet.hotkey miner-0 \
  > work/m5_full/miner-0.log 2>&1 &

.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer \
  --quota 2 --seed 202 --port 8092 \
  --wallet.name dolores-test --wallet.hotkey miner-1 \
  > work/m5_full/miner-1.log 2>&1 &
```

```bash
.venv/bin/python neurons/validator.py --mode localnet \
  --network ws://127.0.0.1:9944 --netuid <N> --chain dry-run \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/m5_full/dry_run \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
```

Acceptance when phase 6.5 reports `commit_reveal_enabled=false` — this is the
first `dry_run_ok` ever after a permit exists:

```bash
jq '{mode, reason, payload, submission}' \
  work/m5_full/dry_run/subnet_archive/epochs/epoch_1/chain_receipt_epoch_1.json
# expect: mode "dry_run", reason "dry_run_ok",
#         payload.uids_emitted non-empty, submission null
```

Leon reviews `payload.uids_emitted` / `weights_u16` against the uid map —
this is the exact vector phase 8 submits.

If phase 6.5 still reports `commit_reveal_enabled=true`, the corrected chain
client should write `mode "skipped"`, `reason "commit_reveal_enabled"`,
`payload null`, and `submission null`; that is an honest partial-M5 stop, not
a failure of miner scoring.

## Phase 8 — LEON: live set_weights through all four gates

> **HEAD behavior change (ba65010):** since the fresh localnet subnet is born
> `commit_reveal_enabled=true`, the validator now fail-closed **skips** this
> phase with `reason "commit_reveal_enabled"` unless you either disabled
> commit-reveal in phase 6.5 or add `--allow-commit-reveal` to the command
> below. With `--allow-commit-reveal` under commit-reveal, expect
> `reason "submitted_commit_reveal"` (not `submitted_ok`), and read-back stays
> zero until the reveal ~1 tempo later.

```bash
export DOLORES_ALLOW_EXTRINSICS=1

.venv/bin/python neurons/validator.py --mode localnet \
  --network ws://127.0.0.1:9944 --netuid <N> --chain live \
  --allow-extrinsics --confirm-live I-AM-LEON-AND-I-APPROVE \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 2 --quota 2 --work work/m5_full/live \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45

unset DOLORES_ALLOW_EXTRINSICS
```

(Epoch 2, not 1: a second submission inside the same `weights_rate_limit`
window would be `skipped/rate_limited`; if that happens, wait the rate-limit
blocks — fast on localnet — and rerun.)

Acceptance:

```bash
jq '{mode, reason, submission}' \
  work/m5_full/live/subnet_archive/epochs/epoch_2/chain_receipt_epoch_2.json
# expect (commit-reveal disabled in phase 6.5): mode "submitted",
#   reason "submitted_ok", submission.success true
# expect (commit-reveal still on + --allow-commit-reveal): mode "submitted",
#   reason "submitted_commit_reveal", submission.success true
# expect (commit-reveal still on, no --allow-commit-reveal): mode "skipped",
#   reason "commit_reveal_enabled" — rerun with the flag or disable CR first
# note: read_back will be null — known stub; phase 9 is the real read-back
```

Do not treat `submitted_ok` alone as full M5 success when commit-reveal is
enabled. In the 2026-07-08 rehearsal, a pre-fix live run returned
`submitted_ok` for payload `uid=1, weight=65535`, but phase 9 read-back stayed
`[0.0, 0.0, 0.0]` because the SDK used the commit-reveal path.

## Phase 9 — AGENT: manual read-back (the real verification)

The receipt's `read_back` field is a known stub (`chain.py:199-201`); on-chain
verification is this separate poll:

```bash
.venv/bin/python - <<'PY'
import bittensor as bt
st = bt.Subtensor(network="ws://127.0.0.1:9944")
m = st.metagraph(netuid=<N>, lite=False)
vuid = <validator-uid>
print("weights row:", list(m.weights[vuid]))
PY
```

Acceptance: the honest miner's uid carries (near-)max weight, matching
`weights_u16` from the phase-8 receipt within u16 quantization. Save the
output to `work/m5_full/09_read_back.txt`. If the row remains all-zero and
`commit_reveal_enabled=true`, mark M5 partial with the commit-reveal evidence.

## Phase 10 — wrap up

- **AGENT**: kill both miners (`kill -INT`), stop and remove the container
  (`docker stop dolores_localnet && docker rm dolores_localnet`), confirm
  ports 8091/8092/9944/9945 clear.
- **AGENT**: replay check on both epochs
  (`scripts/report.py --work work/m5_full/dry_run --epoch 1 --replay-check 1`,
  same for `live` epoch 2), then diary entry
  `docs/diary/2026-07-08-m5-full-localnet.md` recording: the measured permit
  threshold, the registration burn observed, the create burn (1000 τ localnet
  — do NOT quote this as a testnet number), both receipts, the read-back
  match if achieved, and the M5 verdict. If commit-reveal blocks read-back,
  keep the verdict partial.
- Double-check `DOLORES_ALLOW_EXTRINSICS` is unset in every shell:
  `env | grep DOLORES` should print nothing.

## Abort criteria

- RPC flaky or container unhealthy → stop, `docker logs dolores_localnet`,
  restart the rehearsal from phase 0 (chain state resets; nothing real lost).
- Any command errors "insufficient balance" → phase-1 transfer again from
  Alice; localnet funds are unlimited for our purposes.
- If the permit never flips even at 100+ τ stake → record it, stop the
  rehearsal, and bring the observation back to the review before any public
  action: that outcome would change the public-testnet stake plan.
