# M7 Demo Rehearsal Transcript

Date: 2026-07-08. Work directory:
`work/m7_demo_rehearsal/`.

This transcript summarizes verified local, non-signing commands. It is a
fallback artifact for the hackerhouse demo. It is not a public testnet receipt.

## Safety

No public testnet registration, subnet creation, staking, transfer, `set_weights`
call, signing operation, paid provider call, GitHub push, `.env` read, or wallet
material inspection was performed. Public wallet names and SS58 addresses were
used only for local wire preflight and localhost axon/dendrite signing.

## Preflight

```bash
.venv/bin/python scripts/preflight.py --mode offline
```

Result: exit 0. Required checks passed for Python 3.11.15, Dolores import,
`pip check`, solver panel, jq 1.8.1, Docker daemon 28.3.0, verifier image
`dolores-verifier-pytest:0.1.0`, and Dolores install freshness. Bittensor,
wallet, axon, network, and chain checks were skipped in offline mode.

## M3 Offline Demo Floor

```bash
/usr/bin/time -p .venv/bin/python scripts/local_epoch.py --mode offline \
  --miners honest,duplicate_spammer,invalid --quota 1 --epoch 1 \
  --work work/m7_demo_rehearsal/offline
```

Result:

```text
weights_artifact=/Users/leonliu/Desktop/dolores-bittensor-subnet/work/m7_demo_rehearsal/offline/subnet_archive/epochs/epoch_1/weights_epoch_1.json
offline-0-honest weight=1.000000 epoch_score=0.893963
offline-1-duplicate_spammer weight=0.000000 epoch_score=0.000000
offline-2-invalid weight=0.000000 epoch_score=0.000000
real 38.72
```

```bash
.venv/bin/python scripts/report.py --work work/m7_demo_rehearsal/offline --epoch 1
```

Report summary: honest accepted 1/1; duplicate-spammer accepted 0/1 with
reason `review`; invalid accepted 0/1 with reason `verification failed`;
`degraded: False`; `weight_result: fallback`.

```bash
.venv/bin/python scripts/report.py --work work/m7_demo_rehearsal/offline --epoch 1 --replay-check 1
```

Result:

```text
REPLAY OK
```

Evidence paths:

- `work/m7_demo_rehearsal/offline/subnet_archive/archive.duckdb`
- `work/m7_demo_rehearsal/offline/subnet_archive/submissions.jsonl`
- `work/m7_demo_rehearsal/offline/subnet_archive/epochs/epoch_1/report_epoch_1.md`
- `work/m7_demo_rehearsal/offline/subnet_archive/epochs/epoch_1/weights_epoch_1.json`

Archive check result: three task rows existed; verification rows showed
`containerized=true` and `executed=true`. `weight_result` was:

```json
{
  "mode": "fallback",
  "reason": "offline",
  "receipt": null
}
```

## M4 Wire Happy Path

Started local miners:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona honest --quota 2 \
  --seed 201 --port 8091 --wallet.name dolores-test --wallet.hotkey miner-0
```

```text
wire_miner_started persona=honest wallet=dolores-test/miner-0 hotkey=5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA endpoint=127.0.0.1:8091
```

```bash
.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer \
  --quota 2 --seed 202 --port 8092 \
  --wallet.name dolores-test --wallet.hotkey miner-1
```

```text
wire_miner_started persona=duplicate_spammer wallet=dolores-test/miner-1 hotkey=5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg endpoint=127.0.0.1:8092
```

Validator:

```bash
/usr/bin/time -p .venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/m7_demo_rehearsal/wire_happy \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
```

Result:

```text
weights_artifact=/Users/leonliu/Desktop/dolores-bittensor-subnet/work/m7_demo_rehearsal/wire_happy/subnet_archive/epochs/epoch_1/weights_epoch_1.json
5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg weight=0.000000 epoch_score=0.000000
5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA weight=1.000000 epoch_score=1.707393
real 70.14
```

```bash
.venv/bin/python scripts/report.py --work work/m7_demo_rehearsal/wire_happy --epoch 1 --replay-check 1
```

Result:

```text
REPLAY OK
```

Report summary: miner-0 accepted 2/2 and received weight 1.0; miner-1 accepted
0/2 and received weight 0.0; `degraded: False`; `weight_result: fallback`.

Evidence paths:

- `work/m7_demo_rehearsal/wire_happy/subnet_archive/archive.duckdb`
- `work/m7_demo_rehearsal/wire_happy/subnet_archive/submissions.jsonl`
- `work/m7_demo_rehearsal/wire_happy/subnet_archive/epochs/epoch_1/report_epoch_1.md`
- `work/m7_demo_rehearsal/wire_happy/subnet_archive/epochs/epoch_1/weights_epoch_1.json`

## M4 Kill / Unreachable Miner Test

Stopped miner-1:

```text
wire_miner_stopped
```

Validator:

```bash
/usr/bin/time -p .venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/m7_demo_rehearsal/wire_kill \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 8
```

Result:

```text
weights_artifact=/Users/leonliu/Desktop/dolores-bittensor-subnet/work/m7_demo_rehearsal/wire_kill/subnet_archive/epochs/epoch_1/weights_epoch_1.json
5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg weight=0.000000 epoch_score=0.000000
5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA weight=1.000000 epoch_score=1.747672
real 34.83
```

```bash
.venv/bin/python scripts/report.py --work work/m7_demo_rehearsal/wire_kill --epoch 1 --replay-check 1
```

Result:

```text
REPLAY OK
```

Terminal row check:

```text
status: unreachable
reason: unreachable:Service unavailable at 127.0.0.1:8092/DoloresTaskSynapse
package_hash: null
task_value: 0.0
pre_gates: {"transport": false}
degraded: false
```

Evidence paths:

- `work/m7_demo_rehearsal/wire_kill/subnet_archive/archive.duckdb`
- `work/m7_demo_rehearsal/wire_kill/subnet_archive/submissions.jsonl`
- `work/m7_demo_rehearsal/wire_kill/subnet_archive/epochs/epoch_1/report_epoch_1.md`
- `work/m7_demo_rehearsal/wire_kill/subnet_archive/epochs/epoch_1/weights_epoch_1.json`

After stopping miner-0, both port checks printed no listener rows:

```bash
lsof -nP -iTCP:8091 -sTCP:LISTEN
lsof -nP -iTCP:8092 -sTCP:LISTEN
```

## Optional Read-Only Public Testnet Note

```bash
.venv/bin/btcli subnet burn-cost --network test
```

Result:

```text
Subnet burn cost: 1.0000 tao
```

This was a read-only query. The burn cost is dynamic and must be re-queried
before any future STOP-LEON public-chain action.
