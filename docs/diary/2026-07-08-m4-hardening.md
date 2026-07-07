# M4 - Fable Conformance Hardening

Date: 2026-07-08

## Scope

Implemented the release-readiness fixes from Fable's conformance review so M4
wire mode can be signed off honestly.

No public testnet registration, subnet creation, staking, set-weights, signing
spend, GitHub push, paid provider call, or wallet/private-key inspection was
performed.

## Changes

- Removed synthetic `wire_error` task payloads from the wire path.
- Added validator-observed terminal wire outcomes:
  - `unreachable` for transport failure, with no package hash.
  - `invalid` for aggregate response size above `MAX_RESPONSE_BYTES`.
- Rejected miner-supplied reserved control keys such as `wire_error` as
  `invalid:reserved_key:wire_error`.
- Lowered `neurons/validator.py --quota` default to `DEFAULT_QUOTA` (`4`).
- Added `src/dolores_subnet/chain.py` with `ChainClient` and non-signing
  `NullChain`; no real `set_weights` implementation was added.
- Added containerized-or-not-accepted defense for Docker-mode outcomes.
- Made non-wire neuron imports Bittensor-free by lazy-importing wire helpers.
- Added synapse Pydantic JSON serialization and near-limit response tests.
- Updated the plan Deviations Appendix, README, runbook, and hackerhouse demo
  paths to use `work/<run>/subnet_archive/...`.
- Explicitly deferred strikes; they are not implemented in this pass and should
  not be claimed.

## Unit Verification

```bash
.venv/bin/python -m pytest -q tests/test_wire.py tests/test_bridge_mock.py \
  tests/test_epoch_offline.py tests/test_validator_cli.py \
  tests/test_import_discipline.py
# 17 passed in 6.62s

.venv/bin/python -m pytest -q
# 44 passed in 7.01s

.venv/bin/ruff check .
# All checks passed!
```

## Required Wire Preflights

The first attempt ran the three preflights in parallel and one process failed
the axon-port check because the preflight bind checks raced each other:

```bash
.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey validator
# FAIL axon ports: port bind failed after []: [Errno 48] Address already in use
```

Sequential rerun passed:

```bash
.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey validator
# PASS wallet existence: wallet dolores-test/validator exists (not read)
# PASS axon ports: ports 8091,8092 bindable

.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey miner-0
# PASS wallet existence: wallet dolores-test/miner-0 exists (not read)
# PASS axon ports: ports 8091,8092 bindable

.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey miner-1
# PASS wallet existence: wallet dolores-test/miner-1 exists (not read)
# PASS axon ports: ports 8091,8092 bindable
```

All three preflights also passed Python, Dolores import, Bittensor import,
`pip check`, solver panel, `jq`, Docker daemon, verifier image, and Dolores
install freshness checks. Wire mode skipped chain reachability by design.

## M4 Wire Rehearsal

Started two local miner axons:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona honest --quota 2 \
  --seed 201 --port 8091 --wallet.name dolores-test --wallet.hotkey miner-0

.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer \
  --quota 2 --seed 202 --port 8092 --wallet.name dolores-test \
  --wallet.hotkey miner-1
```

Ran the validator:

```bash
rm -rf work/m4_hardening_wire
.venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/m4_hardening_wire \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
```

Result:

- Honest miner weight: `1.000000`; epoch score: `1.707393`.
- Duplicate-spammer weight: `0.000000`; epoch score: `0.000000`.
- Report: `work/m4_hardening_wire/subnet_archive/epochs/epoch_1/report_epoch_1.md`.
- Replay: `.venv/bin/python scripts/report.py --work work/m4_hardening_wire --epoch 1 --replay-check 1` -> `REPLAY OK`.
- Artifact had `degraded: false` and `weight_result.mode: fallback`.

## Kill Test

Stopped miner 1, kept miner 0 running, and reran the validator:

```bash
rm -rf work/m4_hardening_kill
.venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/m4_hardening_kill \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 8
```

Result:

- Stopped miner row:
  - `status`: `unreachable`
  - `reason`: `unreachable:Service unavailable at 127.0.0.1:8092/DoloresTaskSynapse`
  - `package_hash`: `null`
  - `task_value`: `0.0`
- Artifact `degraded`: `false`.
- Reachable honest miner weight: `1.000000`; epoch score: `1.747672`.
- Report: `work/m4_hardening_kill/subnet_archive/epochs/epoch_1/report_epoch_1.md`.
- Replay: `.venv/bin/python scripts/report.py --work work/m4_hardening_kill --epoch 1 --replay-check 1` -> `REPLAY OK`.

## Remaining Blocks

M4 wire mode is sign-off ready from local evidence. M6 public testnet remains
blocked on H3 test TAO, H4 live testnet lock/spend approval, H6 Leon-at-keyboard
signing for every extrinsic, and future real chain client code beyond the
non-signing `NullChain` seam.
