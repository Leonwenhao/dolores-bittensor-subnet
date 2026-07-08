# Dolores Bittensor Subnet

Testnet subnet scaffold for Dolores Autocurricula.

## Thesis

Dolores is the supply side of the RL-agent economy. Solver subnets reward
agents for solving tasks; this subnet rewards miners for producing verifiable,
frontier-calibrated software tasks that can enter an open curriculum archive.

The v0 testnet goal is intentionally narrow:

1. Miner proposes a Dolores task package.
2. Validator verifies it through the Dolores backend.
3. Validator scores validity, verifier strength, novelty, and frontier value.
4. Accepted tasks are written to an archive.
5. Miner weights reflect marginal archive value, not volume.

Mainnet economics are out of scope until the testnet loop is reproducible.

## Repository Layout

- `docs/imported/` - copied source context from Dolores Autocurricula and Fable.
- `docs/architecture/` - subnet MVP plan and implementation decisions.
- `docs/hackerhouse/` - short pitch material for Bittensor conversations.
- `src/dolores_subnet/` - protocol, packaging, gates, bridge, scoring, archive, and epoch code.
- `neurons/` - miner and validator entrypoints.
- `scripts/` - local simulation utilities.
- `tests/` - lightweight tests for repo scaffolding.

## Imported Context

Start with:

- `docs/imported/fable-bittensor-subnet-research.md`
- `docs/imported/dolores-current-state.md`
- `docs/imported/dolores-business-context-2026-07-07.md`
- `docs/architecture/testnet-mvp-plan.md`
- `docs/hackerhouse/pitch.md`

## Current Status

This repo now has the offline demo-floor loop and the M4 localhost wire
rehearsal: planted fixtures, Bittensor axon/dendrite transport, Docker-backed
validation, scoring, EMA weights, archive evidence, and a replayable leaderboard.
It intentionally reuses Dolores Autocurricula as the task/verifier/scorer backend
instead of re-implementing that logic inside the subnet.

The testnet coldkey has 10.0 test TAO on `--network test`, but no public subnet
is registered yet, there is no validator permit, and there are no live on-chain
weights. The M6 chain-readiness layer now has read-only and dry-run
`SubtensorChain` support; live `set_weights` remains behind explicit
STOP-LEON gates and has never been executed on any public network. One
Leon-authorized localnet-only live submission was accepted by a local
substrate node on 2026-07-08 (read-back blocked by commit-reveal; see
`docs/diary/2026-07-08-m5-full-localnet.md`). Current local artifacts are
fallback, dry-run, or localnet artifacts, not public testnet receipts.
Public registration can proceed when Leon approves the spend/signing steps.
Public live weights require either verified commit-reveal-off state or explicit
`--allow-commit-reveal`; commit-reveal receipts are commit evidence, not
immediate metagraph read-back evidence.

Expected local dependency:

```bash
export DOLORES_REPO="/Users/leonliu/Desktop/Dolores Autocurricula"
```

## Local Smoke

```bash
.venv/bin/python scripts/preflight.py --mode offline
.venv/bin/python scripts/local_epoch.py --mode offline \
  --miners honest,honest,duplicate_spammer,invalid --quota 2 --epoch 1 --work work/m3_demo
.venv/bin/python scripts/report.py --work work/m3_demo --epoch 1
.venv/bin/python scripts/report.py --work work/m3_demo --epoch 1 --replay-check 1

tail -3 work/m3_demo/subnet_archive/submissions.jsonl | jq .
jq .weight_result work/m3_demo/subnet_archive/epochs/epoch_1/weights_epoch_1.json
```

## Immediate Build Path

1. Use `docs/hackerhouse/demo-script.md` for the locked hackerhouse path.
2. Run M5 localnet rehearsal where Leon approves signing actions at the keyboard.
3. Keep public testnet blocked at H4/H6 until netuid, registrations, permit, and receipts exist.

## Non-Goals For Testnet MVP

- No mainnet registration.
- No 2k task generation.
- No paid solver-panel dependency for the first demo.
- No complex multi-role market.
- No secret material in this repo.
