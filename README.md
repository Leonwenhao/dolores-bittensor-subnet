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

This repo now has the offline demo-floor loop: planted fixtures, Docker-backed
validation, scoring, EMA weights, archive evidence, and a replayable leaderboard.
It intentionally reuses Dolores Autocurricula as the task/verifier/scorer backend
instead of re-implementing that logic inside the subnet.

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
```

## Immediate Build Path

1. Add localhost axon/dendrite wire mode.
2. Add localnet rehearsal where Leon approves signing actions at the keyboard.
3. Prepare public testnet runbook and stop at wallet/test-TAO human gates.
4. Package the hackerhouse demo without overclaiming beyond the gates passed.

## Non-Goals For Testnet MVP

- No mainnet registration.
- No 2k task generation.
- No paid solver-panel dependency for the first demo.
- No complex multi-role market.
- No secret material in this repo.
