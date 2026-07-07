# M6 - Chain Readiness Layer

Date: 2026-07-08

## Scope

Implemented the M6 read-only and dry-run chain layer needed before M5 localnet
and STOP-LEON public testnet execution.

No public testnet registration, subnet creation, neuron registration, staking,
transfer, live `set_weights`, signing operation, spend operation, paid provider
call, GitHub push, `.env` read, wallet key-file inspection, mnemonic inspection,
or private-key inspection was performed.

## Changes

- Added `SubnetConfig.netuid` with explicit CLI arg, `BT_NETUID`, and
  `configs/testnet.json` resolution.
- Added `SubtensorChain` in `src/dolores_subnet/chain.py`:
  - lazy private `_Substrate` facade as the mock seam and sole Bittensor import
    boundary.
  - read-only preflight for block, subnet existence, validator uid,
    registration, permit, rate-limit, and commit-reveal status.
  - active miner hotkey-to-UID mapping with dropped-hotkey recording.
  - dry-run payload shaping and `chain_receipt_epoch_<N>.json` writing.
  - live-capable `set_weights` path gated by client flag `--allow-extrinsics`,
    `DOLORES_ALLOW_EXTRINSICS=1`, CLI `--chain live`, and confirmation
    `I-AM-LEON-AND-I-APPROVE`.
- Preserved `NullChain` fallback record shape.
- Updated `neurons/validator.py` with `--chain {off,dry-run,live}`, `--netuid`,
  `--network`, and `--confirm-live`.
- Updated `scripts/preflight.py` with netuid-aware read-only chain readiness;
  preflight never constructs a live-publish client.
- Updated runbook, README, M7 demo status, and plan deviations.

## New Failure Modes Covered

- `fallback/offline`
- `dry_run/dry_run_ok`
- `skipped/all_zero`
- `skipped/epoch_degraded_all_infra`
- `error/netuid_unset`
- `error/netuid_absent`
- `error/validator_unregistered`
- `skipped/no_permit`
- `skipped/no_registered_miners`
- `skipped/rate_limited`
- `skipped/commit_reveal_enabled`
- `error/extrinsics_not_allowed`
- `error/extrinsic_failed` via fake substrate only

## Verification

Focused tests before full-suite run:

```bash
.venv/bin/python -m pytest -q tests/test_chain_client.py tests/test_config.py \
  tests/test_import_discipline.py tests/test_validator_cli.py
# 27 passed in 0.64s

.venv/bin/ruff check src/dolores_subnet/chain.py src/dolores_subnet/config.py \
  neurons/validator.py scripts/preflight.py tests/test_chain_client.py \
  tests/test_config.py tests/test_import_discipline.py tests/test_validator_cli.py
# All checks passed!
```

Full verification commands were run after docs and code edits:

```bash
.venv/bin/ruff check .
# All checks passed!

.venv/bin/python -m pytest -q
# 60 passed in 6.37s

.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey validator
# PASS wallet existence: wallet dolores-test/validator exists (not read)
# SKIP chain readiness: wire mode

.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey miner-0
# PASS wallet existence: wallet dolores-test/miner-0 exists (not read)
# SKIP chain readiness: wire mode

.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey miner-1
# PASS wallet existence: wallet dolores-test/miner-1 exists (not read)
# SKIP chain readiness: wire mode
```

All three wire preflights also passed Python, Dolores import, Bittensor import,
`pip check`, solver panel, jq, Docker daemon, verifier image, Dolores install
freshness, and axon port bind checks.

## Remaining Blocks

- M5 localnet has not been run in this pass; Leon must approve any localnet
  create/register/stake/live-weight signing commands.
- M6 public testnet has no registered subnet; `configs/testnet.json.netuid`
  remains `null`.
- No validator permit exists.
- No live on-chain `set_weights` receipt exists.
- H4/H6 remain required for every public-chain create/register/stake/live-weight
  action.
- H8: no GitHub push was performed.
