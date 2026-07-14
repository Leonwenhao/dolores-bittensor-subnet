# Architecture

Dolores `0.2.0rc2` is a controlled-cohort protocol for authenticated,
verifiable task supply on Bittensor public testnet netuid `523`.

## Release boundary

The subnet depends on one authoritative engine distribution:

- miner base: `dolores-autocurricula==0.2.0rc2`
- validator extra: `dolores-autocurricula[validator]==0.2.0rc2`
- subnet: `dolores-bittensor-subnet==0.2.0rc2`

The lightweight engine base owns task schema, canonical serialization, stable
hashing, loading, and deterministic task generation. Validator-only DuckDB,
pytest, and Hypothesis dependencies live behind the extra. The subnet neither
vendors nor reimplements consensus-critical schema/hash logic.

Immutable public engine and subnet artifacts are still a release gate. Runtime
paths do not accept source-path overrides, adjacent checkouts, or private
filesystem dependencies.

## Protocol boundary

The public submission schema is `dolores-subnet-v1`; transport envelopes use
`dolores-wire-v1`.

```text
miner Axon
  -> SDK request authentication and replay checks
  -> validator-hotkey authorization
  -> signed response bound to request and payload digest
  -> schema / size / stable-hash / quota gates
  -> safety and author checks in Docker
  -> validator-private holdout and known-wrong probes
  -> archive deduplication and scoring
  -> EMA and normalized weights
  -> deterministic weights artifact + volatile chain receipt
```

Miner-supplied tests are **author tests**. On the wire they appear only as
`author_tests`; the engine's internal on-disk field name is mapped at the
package boundary. Active validator holdout cases never appear in the request,
response, task archive, or public evidence.

The cohort accepts only core `parser_roundtrip` tasks with archetype
`escape_delim`, `error_contract`, or `quoted_fields`. A versioned holdout policy
derives deterministic cases from an operator secret and package hash. Public
evidence records digests and outcomes, not cases or secret material.

## Authenticated transport

The miner's cohort verifier invokes Bittensor's default Axon verifier, then
enforces a fixed nonce-age window, minimum authenticated SDK version, its own
replay cache, and an authenticated-hotkey token bucket. A bounded ASGI admission
layer caps request bytes and source-IP frequency before SDK parsing. Required
body-hash fields cover protocol version, request ID, epoch ID, quota, and
timeout. A blacklist callback restricts callers to configured validator
hotkeys; permissive signed-caller mode is local-only and cannot be published.

Because the SDK does not authenticate the returned JSON body, the miner adds an
application signature over the canonical submissions digest and binds it to the
request nonce/UUID, validator and miner hotkeys, epoch, quota, request ID, and
protocol version. A bounded Dendrite caps the decompressed response before JSON
materialization, and the validator verifies all bindings before scoring.
Missing signatures, tampering, identity mismatch, stale requests, replay, rate
excess, and oversize bodies fail closed.

## Public endpoint policy

Public serving requires a literal globally routable IPv4 address, fixed port,
`--network test --netuid 523`, and exact metagraph read-back for the miner
hotkey. Private, loopback, link-local, multicast, unspecified, and reserved
addresses are rejected. Testnet validator ticks discover axons from the
metagraph; manual endpoints are forbidden in that mode.

Loopback endpoints remain available only inside explicitly local wire tests and
are never described as public cohort evidence.

## Isolated verification

The validator uses `dolores-verifier-pytest:0.2.0rc2`. The Dockerfile ships as
an engine package resource, so image construction works from an installed wheel.
Execution is fail-closed and uses:

- no network;
- non-root UID/GID `65532:65532`;
- read-only root and task bind mount;
- all capabilities dropped and `no-new-privileges`;
- PID, CPU, memory, swap, and tmpfs limits.

The reference must pass author checks and the private holdout. Known-wrong
probes must fail. A hard-gate failure produces zero task value.

## Recurring validator

`dolores-validator tick` is one supervised unit of work, not a hidden daemon.
One exclusive OS lock spans the whole tick. Epoch IDs are automatically
allocated and monotonic. Atomic durable state follows:

```text
allocated -> querying -> evaluating -> weights_submitting -> committed
```

Discovery failures before durable evaluation may retry the same epoch.
Evaluation failure advances safely. Before commit, a canonical completion
marker hashes the epoch-scoped miner state, weights, panel sidecar, and definite
chain evidence. A marker can be recovered explicitly. A live attempt without a
verified marker remains ambiguous and blocks automatic recovery or resubmission.

`dolores-validator health` combines runtime state, Docker/image readiness,
read-only chain preflight, public metagraph discovery, and a signed wire probe
enabled by default. Disabling that probe deliberately makes health unhealthy.
A system supervisor supplies schedule, restart, and logging.

## Determinism and chain safety

Each epoch separates a reproducible weights artifact from its volatile chain
receipt. Archive writes and runtime state use atomic replacement; replay checks
do not depend on RPC conditions.

Live weights remain behind four independent gates: explicit live mode,
allow-extrinsics CLI opt-in, an environment guard supplied only for that run,
and an exact typed confirmation. Commit-reveal uncertainty blocks submission.
The cohort target is fixed to public testnet netuid `523`.

Solver-panel calibration is mock by default. Paid provider execution requires
separate explicit spend gates and is not part of the controlled-cohort proof.
