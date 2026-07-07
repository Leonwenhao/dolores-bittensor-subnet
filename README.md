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
- `src/dolores_subnet/` - shared schemas, scoring helpers, and Dolores bridge.
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

This repo is a scaffold. It intentionally reuses Dolores Autocurricula as the
task/verifier/scorer backend instead of re-implementing that logic inside the
subnet.

Expected local dependency:

```bash
export DOLORES_REPO="/Users/leonliu/Desktop/Dolores Autocurricula"
```

## Local Smoke

```bash
python3 -m unittest discover -s tests
python3 scripts/local_loop.py --dry-run
```

To call the real Dolores v3 generator, use the Dolores environment or install
the Dolores dependencies into this repo's environment:

```bash
PYTHONPATH=src "/Users/leonliu/Desktop/Dolores Autocurricula/.venv/bin/python" \
  scripts/local_loop.py --family parser_roundtrip --count 1 --seed 0
```

## Immediate Build Path

1. Make `scripts/local_loop.py` call Dolores v3 task generation.
2. Add a validator bridge that runs Docker verification and local scoring.
3. Add testnet wallet/subtensor preflight.
4. Implement minimal Bittensor miner/validator messages.
5. Demo one epoch on testnet with mock emissions if needed.

## Non-Goals For Testnet MVP

- No mainnet registration.
- No 2k task generation.
- No paid solver-panel dependency for the first demo.
- No complex multi-role market.
- No secret material in this repo.
