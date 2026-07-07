# Dolores Autocurricula Demo Script

Status: offline demo floor is committed at `demo-floor-v0`; M4 wire mode is
localhost-only and chain-free. Public testnet/M6 remains blocked until test TAO,
netuid, validator permit, and Leon-approved signing actions exist.

## Offline Floor

```bash
.venv/bin/python scripts/preflight.py --mode offline

.venv/bin/python scripts/local_epoch.py --mode offline \
  --miners honest,duplicate_spammer,invalid --quota 1 --epoch 1 --work work/demo

.venv/bin/python scripts/report.py --work work/demo --epoch 1
.venv/bin/python scripts/report.py --work work/demo --epoch 1 --replay-check 1
```

Evidence paths:

```bash
.venv/bin/python -c "import duckdb; c=duckdb.connect('work/demo/subnet_archive/archive.duckdb'); print(c.sql('SELECT task_id FROM tasks')); print(c.sql('SELECT status, containerized, executed FROM verification_runs'))"
tail -3 work/demo/subnet_archive/submissions.jsonl | jq .
jq .weight_result work/demo/subnet_archive/epochs/epoch_1/weights_epoch_1.json
```

Expected claim: this is a real Docker-backed validation and scoring loop with a
fallback weight artifact. It is not a public testnet receipt.

## Wire Rehearsal

Terminal 1:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona honest --quota 2 \
  --seed 201 --port 8091 --wallet.name dolores-test --wallet.hotkey miner-0
```

Terminal 2:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer \
  --quota 2 --seed 202 --port 8092 \
  --wallet.name dolores-test --wallet.hotkey miner-1
```

Terminal 3:

```bash
.venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/m4_wire \
  --wallet.name dolores-test --wallet.hotkey validator \
  --timeout 45

.venv/bin/python scripts/report.py --work work/m4_wire --epoch 1
.venv/bin/python scripts/report.py --work work/m4_wire --epoch 1 --replay-check 1
```

Evidence paths:

```bash
tail -4 work/m4_wire/subnet_archive/submissions.jsonl | jq .
jq .weight_result work/m4_wire/subnet_archive/epochs/epoch_1/weights_epoch_1.json
```

If macOS prompts on the first axon bind, STOP-LEON H1: Leon clicks Allow.
