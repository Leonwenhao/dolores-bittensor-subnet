# ADR-001: Controlled cohort release boundaries

- Status: accepted for implementation
- Date: 2026-07-12
- Scope: public-testnet cohort on `network=test`, `netuid=523`

## Decision

Use one authoritative `dolores-autocurricula` distribution with a lightweight
base install and a pinned `validator` extra. The subnet consumes one immutable
engine release; it does not copy the task schema or stable-hash algorithm.

Operate validation as an operator-supervised, serialized recurring tick under
`systemd`. Do not build a second long-running validator daemon. The tick reuses
the existing one-epoch validator, holds an exclusive process lock, allocates a
monotonic epoch ID, persists atomic phase state, discovers miner axons from the
testnet metagraph, and exposes a separate health command.

The first cohort protocol supports only the core `parser_roundtrip` family.
Miner-supplied tests are **author tests**. After the normal author checks pass,
the validator derives a private deterministic holdout from an operator secret,
the task hash, and a versioned policy. Active cases are never returned on the
wire or written to public evidence. Unsupported families and parser archetypes
fail closed with an explicit protocol reason.

Transport has two authenticated layers:

1. A cohort verifier calls Bittensor's default Axon signature/body verifier and
   adds a fixed freshness window, minimum authenticated version, replay cache,
   and authenticated-hotkey rate limit. A bounded pre-parser admission layer
   rejects oversize or source-IP-rate-excess requests. Protocol version,
   request ID, `epoch_id`, `quota`, and timeout are required body-hash fields;
   no custom no-op verifier is permitted.
2. The miner signs the response payload, binding its canonical submissions
   digest to the request nonce/UUID, epoch, quota, protocol version, and miner
   hotkey. A bounded Dendrite caps decompressed response bytes before parsing,
   and the validator verifies the signature before scoring because the
   installed Bittensor SDK does not authenticate the JSON response body.

Public cohort serving requires a globally routable IPv4 address, fixed port,
successful testnet publication, and exact metagraph read-back. Private,
loopback, link-local, multicast, unspecified, and reserved addresses are local
rehearsal only and cannot enter the public publish path.

The release-candidate version is `0.2.0rc1` for both distributions. The subnet
pins `dolores-autocurricula==0.2.0rc1`; a clean two-wheel install is the local
release gate. Publishing the engine repository/artifacts, creating the remote,
pushing commits, and creating tag `v0.2.0-rc.1` remain explicit human gates.

## Dependency alternatives considered

### A. Publish the existing full engine unchanged

This is mechanically fast and preserves one implementation, but it forces
DuckDB, PyArrow, pytest, and Hypothesis onto every miner. The current wheel also
omits the verifier Dockerfile and resolves it through a source-checkout path, so
publication alone would not produce a clean validator install. Rejected as the
primary design; retained only as a time-boxed emergency fallback.

### B. Split the boundary into a lightweight package

A second schema/hash distribution would reduce miner weight but create two
release trains and a consensus-critical drift risk. The accepted variant keeps
the useful boundary without a second implementation: one distribution has a
small base (`pydantic`, `PyYAML`) plus `validator`, `dashboard`, and `dev` extras.
This is the selected approach.

### C. Vendor or reimplement the protocol in the subnet

This makes the subnet superficially self-contained, but the validator still
needs the engine and two implementations could compute different task
identities from the same datetime/JSON payload. It also makes future schema
migrations consensus changes in two repositories. Rejected.

## Operating alternatives considered

### Operator-supervised recurring tick

Selected. It is small enough to audit and preserves the already-tested
one-epoch path. `systemd` supplies restart policy and logs; the application
supplies locking, phase state, retry boundaries, health, and monotonic IDs.

### Bespoke long-running validator service

A daemon could own scheduling, backoff, metrics, and lifecycle internally, but
would duplicate process supervision, enlarge the crash-state surface, and delay
the cohort without improving its proof. Rejected for this release. Reconsider
after external-miner evidence exposes an operational need.

## Failure and restart semantics

The recurring state machine is:

`allocated -> querying -> evaluating -> weights_submitting -> committed`

- A whole tick owns an exclusive OS lock.
- Discovery/RPC failures before evaluation may retry the same allocation.
- Once durable evaluation writes begin, a failed attempt is terminal and the
  next run advances to a new epoch rather than duplicating audit rows.
- A canonical completion marker hashes all epoch-scoped state and definite
  chain evidence before commit. Marker recovery is explicit and path-fixed.
- A live attempt without a verified completion marker is ambiguous and fails
  closed for operator reconciliation; it never auto-resubmits.
- The existing four live-weight gates and commit-reveal fail-closed behavior
  remain unchanged.

## Release gates and consequences

The cohort release is not public-launch ready until all of these are true:

- the engine and subnet install from immutable public releases without a local
  checkout, `DOLORES_REPO`, a LAN path, or a manual miner endpoint;
- clean-install, full-suite, Docker, signed-wire, invalid-signature, stale
  nonce, replay, response-tamper, restart, holdout, and docs-command tests pass;
- the pending private security disclosure is received and triaged;
- one non-first-party HackerQuest miner publishes a stable public axon and
  earns nonzero weight in two successful epochs.

The first three groups can be completed locally up to their publication or
external-input gates. The final two are explicitly conditional and must remain
reported as unpassed until the human/external actions occur.
