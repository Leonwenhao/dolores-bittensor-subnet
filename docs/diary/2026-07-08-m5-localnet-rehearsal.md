# M5 - Localnet Rehearsal

Date: 2026-07-08

## Scope

Ran the M5 localnet rehearsal as far as possible without public testnet access,
mainnet access, paid provider calls, secret inspection, or any public-chain
extrinsic.

No public testnet command, mainnet/finney command, subnet create, public
registration, stake, transfer, live `set_weights`, paid provider call, GitHub
push, `.env` read, wallet key-file inspection, mnemonic inspection, or
private-key inspection was performed.

## Commands And Results

Preflight state:

```bash
git status --short
# clean at start

docker version --format '{{.Server.Version}}'
# 28.3.0

python3 - <<'PY'
import socket
for port in (9944, 9945):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as exc:
        print(f"PORT {port} BUSY {exc}")
    else:
        print(f"PORT {port} FREE")
    finally:
        sock.close()
PY
# PORT 9944 FREE
# PORT 9945 FREE
```

Localnet image and container:

```bash
docker pull ghcr.io/opentensor/subtensor-localnet:devnet-ready
# Downloaded newer image
# Digest: sha256:592aa28d528ebadba5f83807d0d38e29fa954dd91ac3e180b48259d64a654e8f

docker run -d --name dolores_localnet -p 9944:9944 -p 9945:9945 \
  ghcr.io/opentensor/subtensor-localnet:devnet-ready
# 8aca40e282f25b004f616d5fbed3c446e2742981a387502c483b2b6864a7f588

docker image inspect --format '{{.Id}} {{.Architecture}}' \
  ghcr.io/opentensor/subtensor-localnet:devnet-ready
# sha256:592aa28d528ebadba5f83807d0d38e29fa954dd91ac3e180b48259d64a654e8f arm64
```

Read-only localnet preflight:

```bash
.venv/bin/python scripts/preflight.py --mode localnet \
  --wallet.name dolores-test --wallet.hotkey validator \
  --network ws://127.0.0.1:9944
# PASS chain reachability: ws://127.0.0.1:9944 block=487
# SKIP chain readiness: netuid unset; subnet readiness checks skipped
```

Read-only localnet discovery:

```bash
.venv/bin/btcli subnets list --network ws://127.0.0.1:9944 --json-output
# total_netuids: 2
# subnets: 0 root, 1 apex

.venv/bin/btcli subnets show --netuid 1 --mechid 0 \
  --network ws://127.0.0.1:9944 --no-prompt --json-output
# netuid: 1
# name: apex
# owner/hotkey/coldkey: 5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM
# uids: only uid 0; no Dolores hotkeys registered
```

Netuid-aware preflight failed closed as expected:

```bash
.venv/bin/python scripts/preflight.py --mode localnet \
  --wallet.name dolores-test --wallet.hotkey validator \
  --network ws://127.0.0.1:9944 --netuid 1
# FAIL chain readiness: reason validator_unregistered
# validator_hotkey: 5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm
# validator_uid: null
```

Static-endpoint localnet-mode dry-run rehearsal:

```bash
.venv/bin/python neurons/miner.py --mode wire --persona honest --quota 2 \
  --seed 501 --port 8091 --wallet.name dolores-test --wallet.hotkey miner-0

.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer \
  --quota 2 --seed 502 --port 8092 \
  --wallet.name dolores-test --wallet.hotkey miner-1

.venv/bin/python neurons/validator.py --mode localnet \
  --network ws://127.0.0.1:9944 --netuid 1 --chain dry-run \
  --miner-endpoints 127.0.0.1:8091:5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA,127.0.0.1:8092:5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg \
  --epoch 1 --quota 2 --work work/m5_localnet_20260708T022211/static_dry_run \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
# weights_artifact=.../weights_epoch_1.json
# miner-1 weight=0.511635 epoch_score=0.896332
# miner-0 weight=0.488365 epoch_score=0.855567
```

The chain receipt was produced but did not reach `dry_run_ok` because the
validator hotkey is not registered on the local subnet:

```bash
jq '{mode, reason, network, netuid, validator, active_hotkey_to_uid, dropped_hotkeys, submission, read_back}' \
  work/m5_localnet_20260708T022211/static_dry_run/subnet_archive/epochs/epoch_1/chain_receipt_epoch_1.json
# mode: error
# reason: validator_unregistered
# network: ws://127.0.0.1:9944
# netuid: 1
# validator.uid: null
# active_hotkey_to_uid: {}
# dropped_hotkeys: miner-0 and miner-1 public hotkeys
# submission: null
# read_back: null
```

Report and replay:

```bash
.venv/bin/python scripts/report.py \
  --work work/m5_localnet_20260708T022211/static_dry_run --epoch 1
# weight_result: error

.venv/bin/python scripts/report.py \
  --work work/m5_localnet_20260708T022211/static_dry_run \
  --epoch 1 --replay-check 1
# REPLAY OK
```

Final verification:

```bash
.venv/bin/ruff check .
# All checks passed!

.venv/bin/python -m pytest -q
# 61 passed in 6.97s

.venv/bin/python scripts/preflight.py --mode wire \
  --wallet.name dolores-test --wallet.hotkey validator
# PASS; chain checks skipped for wire mode

.venv/bin/python scripts/preflight.py --mode localnet \
  --wallet.name dolores-test --wallet.hotkey validator \
  --network ws://127.0.0.1:9944
# PASS chain reachability
# SKIP chain readiness: netuid unset
```

One localnet preflight attempt was intentionally rerun because it was first
started in parallel with the wire preflight and both tried to bind the same axon
test port. The sequential retry passed.

Cleanup:

```bash
docker stop dolores_localnet
docker rm dolores_localnet

python3 - <<'PY'
import socket
for port in (8091, 8092, 9944, 9945):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as exc:
        print(f"PORT {port} BUSY {exc}")
    else:
        print(f"PORT {port} FREE")
    finally:
        sock.close()
PY
# PORT 8091 FREE
# PORT 8092 FREE
# PORT 9944 FREE
# PORT 9945 FREE
```

## Artifacts

- `work/m5_localnet_20260708T022211/preflight_localnet_no_netuid.txt`
- `work/m5_localnet_20260708T022211/preflight_localnet_netuid1.txt`
- `work/m5_localnet_20260708T022211/subnets_list.json`
- `work/m5_localnet_20260708T022211/subnet_1_show.json`
- `work/m5_localnet_20260708T022211/subnet_1_metagraph.json`
- `work/m5_localnet_20260708T022211/static_dry_run/subnet_archive/epochs/epoch_1/weights_epoch_1.json`
- `work/m5_localnet_20260708T022211/static_dry_run/subnet_archive/epochs/epoch_1/chain_receipt_epoch_1.json`
- `work/m5_localnet_20260708T022211/static_dry_run/subnet_archive/epochs/epoch_1/report_epoch_1.md`
- `work/m5_localnet_20260708T022211/replay_static_dry_run.txt`
- `work/m5_localnet_20260708T022211/docker_logs_tail.txt`

## Status

M5 is partially rehearsed, not fully passed.

What passed:

- Docker localnet image pulled and ran on arm64.
- Ports 9944/9945 were mapped and RPC was reachable.
- Repo localnet preflight passes without a netuid and safely skips readiness.
- Read-only discovery found preseeded `netuid=1` (`apex`).
- Netuid-aware preflight correctly failed closed with
  `validator_unregistered` for the Dolores validator hotkey.
- A localnet-mode epoch with real axon/dendrite miner queries produced a
  deterministic weights artifact and a separate chain receipt.
- Replay passed.
- All demo/localnet ports were clear after cleanup.

What remains blocked before full M5 sign-off:

- Dolores `validator`, `miner-0`, and `miner-1` hotkeys are not registered on
  localnet `netuid=1`.
- Validator permit is not available for the Dolores validator hotkey.
- No localnet live `set_weights` submission or read-back exists.
- Full M5 still requires Leon-visible localnet create/register/stake/permit/live
  weight steps, or explicit approval that the agent may run those localnet-only
  signing commands.
- `neurons/miner.py` currently supports `offline` and `wire` modes only; full
  metagraph-discovery M5 needs miners registered and served on-chain, not the
  static endpoint fallback used here.

M6 public testnet remains STOP-LEON for subnet creation, registration, staking,
validator permit, and any live weight extrinsic.
