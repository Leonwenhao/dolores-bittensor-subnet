# Dolores Autocurricula Subnet

Dolores is a market for **verified curriculum supply**. Miners author software
tasks; a validator authenticates the submission, runs isolated verification,
checks novelty, applies a validator-private holdout, and converts accepted value
into Bittensor weights.

- Network: Bittensor public testnet
- Netuid: `523`
- Release candidate: subnet `0.2.0rc1`, pinned engine `0.2.0rc1`
- Cohort: one to three known HackerQuest miners, not a permissionless launch
- Canonical status: [`docs/testnet-status.md`](docs/testnet-status.md)

## Release state

The protocol and operator surface are implemented locally, but the controlled
handoff is not live until immutable engine and subnet releases exist and hosted
CI is green on their exact source commits. GitHub private vulnerability
reporting is enabled; report receipt and triage remain explicitly pending. A
release while that risk remains pending requires a separate `STOP-LEON`
accepted-risk decision and does not make the security gate or cohort proof pass.
Do not onboard a participant from a local path, editable engine checkout,
private archive, or unpublished wheel.

Historical public-testnet proof remains valid: netuid 523 accepted weights,
processed a Yuma incentive pass, and later discovered two first-party axons from
the metagraph. The current chain snapshot is stale/offline, and the historical
axon addresses are private RFC1918 addresses that the RC public endpoint policy
now rejects. See the status document for the exact separation between historical
evidence and current readiness.

Unsigned handoff preparation can begin only after immutable public artifacts
exist. The exact install commands and immutable release/checksum locations live in
[`docs/hackerquest-miner-quickstart.md`](docs/hackerquest-miner-quickstart.md).
The subnet package already pins `dolores-autocurricula==0.2.0rc1`; miners never
set a source-path override, install an adjacent checkout, or receive a private path.

## Cohort protocol

The first cohort deliberately supports one narrow family:

- family: `parser_roundtrip`
- band: `core`
- archetypes: `escape_delim`, `error_contract`, `quoted_fields`
- wire schema: `dolores-subnet-v1`

Miner-supplied tests are **author tests**. They are useful evidence, but they are
not independent ground truth. After a task clears its author checks, the
validator derives a secret-keyed, versioned holdout from the package hash and
runs it in Docker. Active holdout cases never cross the wire or enter public
evidence. Unsupported families fail closed for this release.

```text
authentic miner request/response
             |
             v
schema + size + stable-hash gates
             |
             v
safety + author checks in hardened Docker
             |
             v
validator-private holdout + wrong-solution probes
             |
             v
deduplication + scoring + EMA -> weights
             |
             v
deterministic artifact + separate chain receipt
```

Transport invokes Bittensor's default Axon signature/body verifier inside a
stricter cohort verifier that fixes request age and SDK-version policy, adds a
replay cache and authenticated-hotkey rate limit, and cannot be relaxed through
the request timeout. A pre-parser middleware caps and source-IP-rate-limits the
HTTP body. Required request body-hash fields bind protocol version, request ID,
epoch, quota, and timeout. The validator caps the decompressed HTTP response
before JSON parsing, then verifies the miner's response signature and payload
digest before scoring.

## Installed commands

The public packages expose two entry points:

```bash
dolores-miner --help
dolores-validator --help
```

The miner journey is `doctor -> init -> validate -> register -> serve`, with
`dolores-miner health` available as a local-listener diagnostic. A miner needs
Python, the pinned lightweight engine, Bittensor, a wallet/hotkey, authored
tasks, and a stable globally routable IPv4 endpoint. A miner does **not** need
Docker, DuckDB, Streamlit, Fireworks, solver-panel credentials, or validator
internals.

The supported public serve path requires an exact public IPv4/port, an
allowlisted validator hotkey, `--network test --netuid 523`, and exact metagraph
read-back. Testnet validator ticks discover miners from the metagraph; manual
endpoint injection is rejected in that mode.

The separately packaged `probe-wire` and wire-mode health surfaces accept only
explicit manual endpoints with chain mode off. They exist for signed,
first-party release rehearsals and are not testnet discovery or cohort evidence.

The validator installs the `validator` extra, builds
`dolores-verifier-pytest:0.2.0rc1` from a resource packaged inside the engine,
and runs it as a non-root user with no network, a read-only root and task mount,
dropped capabilities, no-new-privileges, and CPU, memory, PID, and tmpfs limits.

## Recurring validation

`dolores-validator tick` runs one operator-supervised epoch. It holds an
exclusive OS lock, allocates epoch IDs monotonically, persists atomic phase
state, discovers public axons, and fails closed on ambiguous weight submission.
`dolores-validator health` is the authoritative cohort endpoint health command.
It reports local runtime, Docker, read-only chain state, metagraph discovery,
and signed reachability enabled by default. A successful signed quota-zero
request/reply proves that the miner process is alive at the metagraph-discovered
endpoint and can answer the validator's authenticated wire protocol. It
complements `dolores-miner doctor`, which covers the service-account metadata,
local listener, inbound public TCP, and exact published-axon read-back. A system
supervisor may schedule ticks; the application does not hide lifecycle or retry
state inside a second daemon.

`dolores-validator replay` deterministically rechecks archived score and weight
derivation against stored receipts. It does not rerun task verification or the
private holdout; the VPS runbook checks those receipt fields separately. The
exact disposable Ubuntu/systemd proof, including removable chain-neutral
drop-ins, is documented in `docs/vps-rehearsal.md`.

Live weights remain protected by four independent gates and commit-reveal
uncertainty remains fail-closed. Paid solver-panel calibration is off by default
and is not required for the controlled cohort.

## Repository map

- `src/dolores_subnet/` — protocol, authentication, holdout, scoring, archive,
  recurring state, endpoint policy, and chain integration
- `tests/` — full local, Docker, signed-wire, replay, packaging, and restart gates
- `docs/architecture.md` — implemented design and security boundaries
- `docs/demo.md` — local RC smoke checks and operator dry-run commands
- `docs/cohort-release-checklist.md` — release and external-proof gates
- `docs/vps-rehearsal.md` — public-asset-only chain-neutral systemd proof
- `docs/testnet-status.md` — historical receipts and current chain snapshot

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for code and task contributions. Report
security-sensitive findings through the private channel described in
[`SECURITY.md`](SECURITY.md); do not post exploit details in a public issue.

This release is testnet-only and makes no claim that its score predicts
downstream training value. It proves authenticated, isolated, replayable task
evaluation and weight formation for a controlled cohort.
