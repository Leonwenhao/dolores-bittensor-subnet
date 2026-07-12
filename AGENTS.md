# AGENTS.md — Dolores controlled-cohort miner

This runbook is for a known HackerQuest participant joining Dolores on
Bittensor public testnet, netuid `523`. It is not a permissionless launch guide.

## 1. Hard boundaries

- Use only `--network test --netuid 523` for every chain or subnet action.
- Stop if either flag is missing or different.
- Never inspect, print, copy, or commit a mnemonic, seed, private key, wallet
  password, provider credential, `.env` content, or validator holdout secret.
- Do not use a source-path override, an editable/private engine checkout, an
  adjacent repository, a shared filesystem, or a private wheel.
- Do not publish a loopback, LAN/RFC1918, link-local, reserved, or dynamic
  endpoint. Public cohort serving requires a stable globally routable IPv4
  address and fixed port on the supported Ubuntu 24.04 LTS amd64 VPS.
- Do not pass a miner endpoint to the public-testnet validator. It discovers
  published axons from the netuid-523 metagraph.
- Registration, axon publication, and live weights are signed actions. Stop at
  `STOP-LEON` and obtain explicit operator approval before running one.
- Paid solver-panel execution is off and irrelevant to miner onboarding.

## 2. Release gate

The release candidate is `0.2.0rc1` for both
`dolores-bittensor-subnet` and `dolores-autocurricula`. The subnet pins the exact
engine version.

Do not improvise an install from a local path. Use only the immutable
`v0.2.0-rc.1` GitHub Releases and the exact asset/checksum names in
[`docs/hackerquest-miner-quickstart.md`](docs/hackerquest-miner-quickstart.md).
If either release, its checksum sidecar, or the exact-hash handoff asset is
missing, stop; preparation is not authorized from a branch archive or local
wheel. Install only after the final published hashes verify in a fresh CPython
3.11.15 virtual environment.

After installation, these commands must resolve from the environment:

```bash
dolores-miner --help
python -c "import importlib.metadata as m; print(m.version('dolores-autocurricula')); print(m.version('dolores-bittensor-subnet'))"
```

Both versions must print `0.2.0rc1`. A miner install does not require Docker,
DuckDB, Streamlit, Fireworks, a solver panel, or validator services.

## 3. Author one supported task

The controlled cohort accepts only `parser_roundtrip` tasks in band `core` with
one of these archetypes:

- `escape_delim`
- `error_contract`
- `quoted_fields`

Create a deterministic starting package:

```bash
dolores-miner init \
  --output dolores-tasks \
  --archetype escape_delim \
  --seed 17
```

The command prints `task_dir=...`, `task_id=...`, `package_hash=...`, and
`tests=author_tests validator_holdout=private`. Work only inside the printed
task directory. Make a meaningful task change, keep execution deterministic,
and keep all paths relative.

Miner-supplied tests are **author tests**. The pinned engine's on-disk
`task.yaml` still stores that author-supplied mapping under its internal legacy
field name `hidden_tests`; it is not the validator's holdout. The active
validator-owned cases are secret-keyed, generated at evaluation time, and never
sent to the miner.

Validate the authored package without Docker or chain access:

```bash
dolores-miner validate --task-dir <TASK_DIR>
```

Validation must print `VALID`, family `parser_roundtrip`, the archetype, a
stable package hash, and an `author_tests` count. The complete doctor also
checks registration, exact metagraph publication, and public reachability, so
run its fully explicit command after approved publication as specified in the
quickstart. It must then emit JSON with every check `ok: true`.

## 4. Protocol contract

The public wire schema is `dolores-subnet-v1`. A submission contains:

- `schema_version`
- `task_id`
- `package_hash`
- `package`
- `family`
- `declared_difficulty`

The wire `package` uses `author_tests`; a wire payload containing the legacy
`hidden_tests` key is rejected. The validator recomputes the engine's canonical
stable hash and rejects schema, path, size, hash, quota, or duplicate failures.
The maximum canonical task submission is 200 KiB and the miner response is
bounded to 1 MiB.

Do not claim rewardability from author validation alone. The validator still
runs safety checks, author tests and reference execution in hardened Docker,
wrong-solution probes, a private holdout, deduplication, and scoring.

## 5. Prepare the public service

Use a host with a stable public IPv4 address. Open the chosen TCP port in the
host firewall and provider security group. Bind the process to all interfaces,
but publish only the explicit public address.

Before any chain write, rehearse the listener without `--publish`:

```bash
dolores-miner serve \
  --wallet.name <WALLET_NAME> \
  --wallet.hotkey <MINER_HOTKEY_NAME> \
  --task-dir <TASK_DIR> \
  --host 0.0.0.0 \
  --port <PORT> \
  --external-ip <PUBLIC_IPV4> \
  --external-port <PORT> \
  --validator-hotkey <COHORT_VALIDATOR_SS58> \
  --network test \
  --netuid 523
```

In another terminal:

```bash
dolores-miner health --host 127.0.0.1 --port <PORT>
```

Stop the rehearsal with Ctrl-C. `--allow-any-signed-validator` is for local
testing only and is forbidden with public publication.

## 6. Signed registration — STOP-LEON

First print the fixed registration command without executing it:

```bash
dolores-miner register \
  --wallet.name <WALLET_NAME> \
  --wallet.hotkey <MINER_HOTKEY_NAME> \
  --network test \
  --netuid 523
```

Expected: the printed command contains `btcli subnet register --network test
--netuid 523` and the final line is `registration=not_executed`.

`STOP-LEON`: registration can spend testnet funds and signs with the selected
wallet. The operator must approve the exact wallet name, hotkey name, public
hotkey/UID evidence, and command. Only after approval may the human add:

```text
--execute --confirm REGISTER-TESTNET-523
```

Do not automate wallet prompts or inspect wallet files.

## 7. Axon publication — STOP-LEON

Publication signs a `serve_axon` call. The RC rejects non-global IPv4 addresses
and fails if the exact `<PUBLIC_IPV4>:<PORT>` does not read back for the miner
hotkey from the netuid-523 metagraph.

`STOP-LEON`: obtain approval for this exact action and endpoint, then run:

```bash
dolores-miner serve \
  --wallet.name <WALLET_NAME> \
  --wallet.hotkey <MINER_HOTKEY_NAME> \
  --task-dir <TASK_DIR> \
  --host 0.0.0.0 \
  --port <PORT> \
  --external-ip <PUBLIC_IPV4> \
  --external-port <PORT> \
  --validator-hotkey <COHORT_VALIDATOR_SS58> \
  --publish \
  --network test \
  --netuid 523
```

Success requires both `wire_miner_started` and `axon_publish=ok ...
readback=exact`. Keep the process under the supplied supervisor unit and retain
its logs. If publication or read-back fails, stop the process and escalate; do
not substitute a private address or send an endpoint directly to the validator.

## 8. Authentication model

The Axon cohort verifier calls Bittensor's default verifier and adds a fixed
freshness window, minimum authenticated SDK version, replay cache, and
authenticated-hotkey rate limit. A pre-parser HTTP cap and source-IP limiter run
before SDK JSON decoding. The signed request body hash binds protocol version,
request ID, epoch ID, quota, and timeout. An allowlist restricts callers to the
cohort validator hotkey.

The miner signs the canonical response digest and binds it to the request
nonce/UUID, validator hotkey, miner hotkey, epoch, quota, and protocol version.
The validator caps decompressed response bytes before JSON parsing and rejects
missing or invalid signatures, response tampering, identity mismatches, and
oversize responses before scoring.

## 9. Final evidence checklist

- Public release URLs and SHA-256 hashes came from the approved quickstart.
- Both installed versions are `0.2.0rc1`; no local engine path is configured.
- `dolores-miner doctor` and `validate` pass.
- The task is supported core `parser_roundtrip`; tests are called author tests.
- The service uses a stable public IPv4 and fixed port.
- The validator hotkey is explicitly allowlisted.
- Registration and publication each received separate `STOP-LEON` approval.
- Publication reports exact metagraph read-back on `--network test --netuid 523`.
- The operator, not the miner, supplies private holdout, Docker, recurring
  validator, dry-run/live-weight, and chain-receipt evidence.
- Cohort success is not claimed until the external miner earns nonzero weight
  in two successful consecutive epochs.
