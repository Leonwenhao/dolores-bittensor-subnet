# Local Demo

Run the full validator loop on your own machine — no public chain, no
emissions, no secrets. The demo shows an honest miner earning all the weight
while a duplicate-spammer and an invalid miner collapse to zero, and it proves
every epoch replays deterministically.

## Prerequisites

- Python 3.11 with the repo installed (`pip install -e ".[dev]"`).
- Docker running (the verifier executes each task in a container).
- The Dolores verifier image built locally:

  ```bash
  docker image inspect dolores-verifier-pytest:0.1.0 >/dev/null || \
    (cd "$DOLORES_REPO" && docker build -f docker/verifier/Dockerfile \
       -t dolores-verifier-pytest:0.1.0 .)
  ```

- The Dolores engine on the path:

  ```bash
  export DOLORES_REPO="<path-to-dolores-autocurricula>"
  ```

Sanity-check the environment first:

```bash
python scripts/preflight.py --mode offline
```

Expect `PASS` for Python, Dolores import, solver panel, Docker daemon, and the
verifier image. The `solver panel` check reports the **mock** panel — the demo
always runs mock; real calibration mode is operator-only and not exercised
here. Chain and wallet checks are skipped in offline mode.

## 1. Offline epoch — honest vs. duplicate-spammer vs. invalid

One command runs a full epoch against three miner personas:

```bash
python scripts/local_epoch.py --mode offline \
  --miners honest,duplicate_spammer,invalid --quota 1 --epoch 1 \
  --work work/demo/offline
```

Expected core output:

```text
offline-0-honest             weight=1.000000 epoch_score=0.893963
offline-1-duplicate_spammer  weight=0.000000 epoch_score=0.000000
offline-2-invalid            weight=0.000000 epoch_score=0.000000
```

The honest task passes every gate and takes all the weight; the duplicate and
invalid tasks fail a hard gate and score zero. Inspect the report and confirm
the epoch replays:

```bash
python scripts/report.py --work work/demo/offline --epoch 1
python scripts/report.py --work work/demo/offline --epoch 1 --replay-check 1
```

The report shows honest accepted `1/1`, the two adversaries `0/1`,
`degraded: False`, and `weight_result: fallback` (no chain in offline mode). The
replay check prints:

```text
REPLAY OK
```

## 2. Wire mode — two miners over Bittensor transport

This runs the same loop but over signed axon/dendrite transport between separate
processes. The wallet flags select **local keypairs used only to sign transport**
— no chain calls are made.

Start two miner axons in the background:

```bash
python neurons/miner.py --mode wire --persona honest --quota 2 \
  --seed 201 --port 8091 --wallet.name dolores-test --wallet.hotkey miner-0 \
  > work/demo/miner-0.log 2>&1 &

python neurons/miner.py --mode wire --persona duplicate_spammer --quota 2 \
  --seed 202 --port 8092 --wallet.name dolores-test --wallet.hotkey miner-1 \
  > work/demo/miner-1.log 2>&1 &
```

Each log should report `wire_miner_started` with its endpoint. Run the
validator against both:

```bash
python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/demo/wire_happy \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
```

Expected core output — the honest miner wins, the spammer is zeroed:

```text
5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg weight=0.000000 epoch_score=0.000000
5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA weight=1.000000 epoch_score=1.707393
```

```bash
python scripts/report.py --work work/demo/wire_happy --epoch 1 --replay-check 1
# REPLAY OK
```

## 3. Kill test — a miner going down is not a crash

Stop one miner mid-flight and confirm the validator records it cleanly rather
than failing. Kill the spammer's process, then re-run with a short timeout:

```bash
python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/demo/wire_kill \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 8
```

The report marks the downed miner `unreachable` with `weight_result: fallback`
and `degraded: False` — a first-class transport failure, not a pipeline error —
and the epoch still replays `REPLAY OK`. When done, stop the remaining miner and
confirm no axon listeners are left behind:

```bash
lsof -nP -iTCP:8091 -sTCP:LISTEN || true
lsof -nP -iTCP:8092 -sTCP:LISTEN || true
```

Both should print nothing.

## Expected outputs at a glance

| Check | Expected |
|---|---|
| Honest miner weight | `1.000000` |
| Duplicate-spammer / invalid weight | `0.000000` |
| Replay check | `REPLAY OK` |
| `degraded` | `False` |
| `weight_result` (no chain) | `fallback` |
| Downed miner status | `unreachable` |

## Troubleshooting

- **`docker` errors / verifier image missing** — confirm the daemon is running
  and rebuild `dolores-verifier-pytest:0.1.0` (see prerequisites).
- **Dolores import fails in preflight** — check `DOLORES_REPO` points at the
  engine checkout and the engine is installed in the active environment.
- **Ports 8091/8092 already in use** — a previous miner is still listening; kill
  it (`lsof -nP -iTCP:8091 -sTCP:LISTEN`) before restarting.
- **Wire validator times out** — make sure both miner logs show
  `wire_miner_started` before starting the validator, and raise `--timeout`.
