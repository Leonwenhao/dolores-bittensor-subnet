# RC Demo and Smoke Checks

These checks exercise `0.2.0rc2` without registration, axon publication, live
weights, paid inference, or participant contact.

## Prerequisites

- Python 3.11
- Docker daemon for validator checks
- the frozen engine input `0.2.0rc2`
- this subnet `0.2.0rc2`

The engine RC2 hosted CI and public release remain `PENDING-STOP`; the subnet
RC2 hosted CI and public release remain `PENDING-STOP`. In a release
environment, use only the immutable public URLs and hashes published in
[`hackerquest-miner-quickstart.md`](hackerquest-miner-quickstart.md). Do not set
a source-path override or install an adjacent/private engine checkout.

For development after that artifact exists, a subnet checkout may be installed
with:

```bash
python -m pip install -e ".[dev]"
python -m pip check
dolores-miner --help
dolores-validator --help
```

## 1. Miner-only authoring smoke

This path needs no Docker, wallet, chain connection, or provider credential:

```bash
TASK_DIR="$(dolores-miner init \
  --output work/demo-author \
  --archetype quoted_fields \
  --seed 17 | awk -F= '/^task_dir=/{print $2}')"
dolores-miner validate --task-dir "$TASK_DIR"
```

Expected: validation prints `VALID`, `family=parser_roundtrip`, an archetype,
package hash, and `author_tests=...`. The complete doctor deliberately requires
metadata for an existing wallet plus live read-only registration, publication,
and public-reachability checks, so it belongs after the approved publication
step in the external-miner quickstart and is not part of this walletless smoke.

## 2. Auth, holdout, Docker, and restart smoke

Run the focused integration checks from the subnet checkout:

```bash
python -m pytest -q \
  tests/test_bittensor_default_verify.py \
  tests/test_wire_auth.py \
  tests/test_wire_http_smoke.py \
  tests/test_holdout_docker.py \
  tests/test_validator_state.py \
  tests/test_release_packaging.py
```

The Docker runner auto-builds `dolores-verifier-pytest:0.2.0rc2` from the
resource packaged inside the installed engine. No engine source path or manual
Dockerfile command is needed. The smoke covers valid signed transport, bad
signatures, stale/replayed requests, response tampering, private holdout
execution, non-root isolated Docker, lock/state behavior, and release metadata.

Run the full local gate before treating an RC as publishable:

```bash
ruff check .
python -m pytest -q
```

## 3. Read-only operator health

The operator configures `DOLORES_HOLDOUT_SECRET` outside source control and
selects an existing validator wallet without displaying wallet or secret
material. Health reads chain/metagraph state and may perform a signed wire probe;
it does not submit weights:

```bash
dolores-validator health \
  --mode testnet \
  --work /var/lib/dolores-validator \
  --wallet.name <VALIDATOR_WALLET> \
  --wallet.hotkey <VALIDATOR_HOTKEY> \
  --network test \
  --netuid 523 \
  --probe-wire
```

Healthy output requires the verifier image, configured holdout secret,
read-only chain preflight, at least one globally routable metagraph axon, no
ambiguous weight-submission state, and signed reachability when requested.

## 4. Supervised dry-run tick

This command automatically allocates a locked epoch and discovers miners from
the metagraph. It constructs the weight payload and receipt but does not submit
an extrinsic:

```bash
dolores-validator tick \
  --mode testnet \
  --work /var/lib/dolores-validator \
  --wallet.name <VALIDATOR_WALLET> \
  --wallet.hotkey <VALIDATOR_HOTKEY> \
  --network test \
  --netuid 523 \
  --chain dry-run \
  --panel-mode mock
```

Do not add manual miner endpoints in testnet mode. Do not add provider-spend or
live-weight flags to this demo. A successful run prints the allocated epoch,
deterministic weights artifact, dry-run chain reason, and per-hotkey weights.

## Troubleshooting

- `verifier_image_missing`: start Docker and run the focused Docker test once;
  the installed engine should auto-build the packaged image.
- `DOLORES_HOLDOUT_SECRET is required`: configure it through the operator's
  protected service environment; never print or commit its value.
- `no eligible miner axons discovered`: the current July 12 chain state is
  stale/offline. Do not substitute a LAN address or manual testnet endpoint.
- `weights_submitting` with a verified completion marker: stop scheduling and
  use canonical marker recovery. A started/ambiguous live-attempt artifact
  requires operator reconciliation and must never be auto-resubmitted.
