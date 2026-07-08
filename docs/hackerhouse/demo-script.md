# Dolores Autocurricula Hackerhouse Demo Script

Status: M3 offline demo floor is real, M4 localhost wire mode is sign-off ready,
and M7 is packaged to run without public testnet success. The `dolores-test`
coldkey has 10.0 test TAO on `--network test`, but no public subnet is
registered, no validator permit exists, and no on-chain weights exist. The
read-only/dry-run `SubtensorChain` path exists; live `set_weights` is still
STOP-LEON gated and has never run on any public network (one Leon-authorized
localnet-only submission was accepted on 2026-07-08; read-back was blocked by
commit-reveal).

Do not run public-chain write commands during this demo. Do not run `btcli
subnet create`, `btcli subnet register`, `btcli stake add`, `set_weights`, or
any transfer/signing command. If macOS shows a firewall prompt when the axon
ports bind, stop and have Leon click Allow.

## 0. Untimed Bootstrap

Use this only for a clean machine. The current hackerhouse laptop already has
the venv, Dolores install, and verifier image.

```bash
git clone <repo> /tmp/demo-rehearsal
cd /tmp/demo-rehearsal
python3.11 -m venv .venv
.venv/bin/pip install "$DOLORES"
.venv/bin/pip install -e ".[dev]"
docker image inspect dolores-verifier-pytest:0.1.0 >/dev/null || \
  (cd "$DOLORES" && docker build -f docker/verifier/Dockerfile -t dolores-verifier-pytest:0.1.0 .)
.venv/bin/python scripts/preflight.py --mode offline
```

Acceptance: offline preflight prints PASS for Python, Dolores import, pip
check, solver panel, jq, Docker daemon, verifier image, and Dolores install
freshness. Chain and wallet checks are skipped in offline mode.

## 1. Fast Path - Live Demo Under 8 Minutes

Use one terminal in the repo root. This path was rehearsed on 2026-07-08 in
about 2 minutes 25 seconds of epoch runtime: offline 38.72s, wire happy 70.14s,
wire kill 34.83s. Preflight and report rendering add only a few seconds on the
demo machine.

```bash
export M7_RUN=work/m7_demo_rehearsal
```

```bash
rm -rf "$M7_RUN/offline" "$M7_RUN/wire_happy" "$M7_RUN/wire_kill"
```

```bash
mkdir -p "$M7_RUN"
```

```bash
git status --short
```

Acceptance: clean tree for the locked demo commit. If local-only `work/`
artifacts exist, they should be ignored by git.

```bash
git log -1 --oneline
```

Acceptance: prints the current local demo-lock commit. The commit hash may
change after the final M7 commit, but the title should identify the M7 demo
lock/docs cleanup.

```bash
.venv/bin/python scripts/preflight.py --mode offline
```

Acceptance: PASS on required local checks; wire/chain checks skipped.

```bash
.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey validator
```

```bash
.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey miner-0
```

```bash
.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey miner-1
```

Acceptance: each wire preflight prints PASS for wallet existence without reading
wallet material, PASS for axon ports 8091/8092, and SKIP for chain reachability.

```bash
/usr/bin/time -p .venv/bin/python scripts/local_epoch.py --mode offline \
  --miners honest,duplicate_spammer,invalid --quota 1 --epoch 1 \
  --work "$M7_RUN/offline"
```

Expected core output:

```text
offline-0-honest weight=1.000000 epoch_score=0.893963
offline-1-duplicate_spammer weight=0.000000 epoch_score=0.000000
offline-2-invalid weight=0.000000 epoch_score=0.000000
```

```bash
.venv/bin/python scripts/report.py --work "$M7_RUN/offline" --epoch 1
```

Acceptance: report shows honest accepted 1/1, duplicate-spammer 0/1, invalid
0/1, `degraded: False`, and `weight_result: fallback`.

```bash
.venv/bin/python scripts/report.py --work "$M7_RUN/offline" --epoch 1 --replay-check 1
```

Expected output:

```text
REPLAY OK
```

```bash
.venv/bin/python -c "import duckdb; c=duckdb.connect('work/m7_demo_rehearsal/offline/subnet_archive/archive.duckdb'); print(c.sql('SELECT task_id, lifecycle_status FROM tasks ORDER BY task_id')); print(c.sql('SELECT status, containerized, executed FROM verification_runs ORDER BY task_id'))"
```

Acceptance: three task rows exist; verification rows show `containerized=true`
and `executed=true`.

```bash
jq .weight_result "$M7_RUN/offline/subnet_archive/epochs/epoch_1/weights_epoch_1.json"
```

Expected output:

```json
{
  "mode": "fallback",
  "reason": "offline",
  "receipt": null
}
```

Start the two local axon miners:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona honest --quota 2 \
  --seed 201 --port 8091 --wallet.name dolores-test --wallet.hotkey miner-0 \
  > "$M7_RUN/miner-0.log" 2>&1 &
```

```bash
export M7_MINER0_PID=$!
```

```bash
sleep 3
```

```bash
tail -1 "$M7_RUN/miner-0.log"
```

Expected output includes:

```text
wire_miner_started persona=honest wallet=dolores-test/miner-0 hotkey=5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA endpoint=127.0.0.1:8091
```

```bash
.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer \
  --quota 2 --seed 202 --port 8092 \
  --wallet.name dolores-test --wallet.hotkey miner-1 \
  > "$M7_RUN/miner-1.log" 2>&1 &
```

```bash
export M7_MINER1_PID=$!
```

```bash
sleep 3
```

```bash
tail -1 "$M7_RUN/miner-1.log"
```

Expected output includes:

```text
wire_miner_started persona=duplicate_spammer wallet=dolores-test/miner-1 hotkey=5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg endpoint=127.0.0.1:8092
```

Run the wire happy path:

```bash
/usr/bin/time -p .venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work "$M7_RUN/wire_happy" \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
```

Expected core output:

```text
5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg weight=0.000000 epoch_score=0.000000
5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA weight=1.000000 epoch_score=1.707393
```

```bash
.venv/bin/python scripts/report.py --work "$M7_RUN/wire_happy" --epoch 1
```

Acceptance: honest miner accepted 2/2, duplicate-spammer accepted 0/2,
`degraded: False`, `weight_result: fallback`.

```bash
.venv/bin/python scripts/report.py --work "$M7_RUN/wire_happy" --epoch 1 --replay-check 1
```

Expected output:

```text
REPLAY OK
```

Run the kill/unreachable path:

```bash
kill -INT "$M7_MINER1_PID"
```

```bash
wait "$M7_MINER1_PID" || true
```

```bash
tail -1 "$M7_RUN/miner-1.log"
```

Expected output:

```text
wire_miner_stopped
```

```bash
/usr/bin/time -p .venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work "$M7_RUN/wire_kill" \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 8
```

Expected core output:

```text
5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg weight=0.000000 epoch_score=0.000000
5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA weight=1.000000 epoch_score=1.747672
```

```bash
.venv/bin/python scripts/report.py --work "$M7_RUN/wire_kill" --epoch 1
```

Acceptance: miner-1 appears with reason
`unreachable:Service unavailable at 127.0.0.1:8092/DoloresTaskSynapse`,
`degraded: False`, and `weight_result: fallback`.

```bash
.venv/bin/python scripts/report.py --work "$M7_RUN/wire_kill" --epoch 1 --replay-check 1
```

Expected output:

```text
REPLAY OK
```

```bash
rg -n 'unreachable|infra_error|Service unavailable' "$M7_RUN/wire_kill/subnet_archive/submissions.jsonl"
```

Acceptance: one row has `status":"unreachable"`, `package_hash":null`,
`task_value":0.0`, and `pre_gates":{"transport":false}`. There should be no
`infra_error` in the kill path.

Stop the remaining miner and confirm the demo leaves no axon listener behind:

```bash
kill -INT "$M7_MINER0_PID"
```

```bash
wait "$M7_MINER0_PID" || true
```

```bash
lsof -nP -iTCP:8091 -sTCP:LISTEN || true
```

```bash
lsof -nP -iTCP:8092 -sTCP:LISTEN || true
```

Acceptance: both `lsof` commands print no listener rows.

## 2. Fallback Path

Use this if Docker, ports, RPC, or macOS firewall timing disrupts the live demo.
Do not claim a fresh live run when using fallback artifacts.

Fresh M7 rehearsal artifacts, if present:

```bash
.venv/bin/python scripts/report.py --work work/m7_demo_rehearsal/offline --epoch 1
.venv/bin/python scripts/report.py --work work/m7_demo_rehearsal/wire_happy --epoch 1
.venv/bin/python scripts/report.py --work work/m7_demo_rehearsal/wire_kill --epoch 1
```

Committed M4 hardening artifacts, if the M7 rehearsal directory is absent:

```bash
.venv/bin/python scripts/report.py --work work/m4_hardening_wire --epoch 1
.venv/bin/python scripts/report.py --work work/m4_hardening_kill --epoch 1
```

Static fallback if local artifacts are unavailable:

```bash
sed -n '1,220p' docs/hackerhouse/m7-demo-transcript.md
```

Claim to make in fallback mode: "These are preserved local demo artifacts from
the 2026-07-08 M7 rehearsal. They prove the same archive rows, reports, replay
checks, and wire failure semantics; they are not public testnet receipts."

## 3. Release Verification Gates

Run these before tagging or presenting the locked repo state:

```bash
.venv/bin/ruff check .
```

```bash
.venv/bin/python -m pytest -q
```

```bash
.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey validator
```

```bash
.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey miner-0
```

```bash
.venv/bin/python scripts/preflight.py --mode wire --wallet.name dolores-test --wallet.hotkey miner-1
```

Acceptance: ruff clean, pytest all passed, and all three wire preflights pass.

Optional read-only public-chain note:

```bash
.venv/bin/btcli subnet burn-cost --network test
```

M7 observed:

```text
Subnet burn cost: 1.0000 tao
```

Treat this as point-in-time only. Re-query immediately before any future
STOP-LEON public-chain action.

## 4. Honest Claims

If asked "is this on testnet?":

> Not yet as a registered public subnet. We have a testnet wallet and 10.0 test
> TAO, but no netuid, no validator permit, no on-chain weights, and no public
> miners. Today is the demo-locked offline plus localhost-wire subnet loop.

If asked "what is live today?":

> The validator loop is live locally: Docker-backed Dolores verification,
> adversarial rejection gates, scoring, EMA weights, archive evidence, replay
> checks, and signed Bittensor axon/dendrite transport between local processes.
> The chain-readiness layer can produce dry-run payloads once a netuid exists;
> live chain writes are deliberately gated.

If asked "what does the subnet reward?":

> Marginal validated archive value. Miners are paid for proposing software tasks
> that pass safety, Docker reference verification, wrong-solution probes,
> duplicate checks, and frontier-value scoring. Volume alone goes to zero.

If asked "why Bittensor?":

> The market is the point. A task archive needs adversarial contributors,
> validator pressure, public scoring, and miner incentives. Bittensor gives that
> coordination layer while Dolores keeps the verifier and archive useful outside
> crypto.

Do not claim emissions, a live public subnet, validator permit, on-chain
weights, public subnet registration, public miners, mainnet readiness, or a
training-improvement result.
