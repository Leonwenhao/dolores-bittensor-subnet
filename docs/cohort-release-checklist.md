# Controlled HackerQuest Cohort Release Checklist

This checklist is the evidence gate for a controlled external-miner cohort on
Bittensor public testnet. It implements
[`ADR-001`](decisions/ADR-001-controlled-cohort-boundaries.md). It does not
authorize a permissionless launch, mainnet use, paid inference, publication,
chain writes, or participant contact.

The fixed scope is:

- network: `test`
- netuid: `523`
- cohort: one to three known HackerQuest participants with operator support
- supported task family: the exact `parser_roundtrip` subset accepted by the
  versioned validator-owned holdout policy
- release candidates: engine and subnet `0.2.0rc1`

Use `PASS`, `FAIL`, `PENDING-HUMAN`, or `N/A` for every row. A gate is `PASS`
only when the evidence named in the row exists and was inspected. A missing or
indirect artifact is `FAIL`, not an inferred pass. Record the exact command that
was actually implemented and run; do not substitute proposed CLI syntax.

## Release decision record

| Field | Value |
|---|---|
| Review timestamp (UTC) | |
| Engine immutable revision | |
| Engine wheel filename and SHA-256 | |
| Subnet immutable revision | |
| Subnet wheel filename and SHA-256 | |
| Verifier image tag and immutable digest | |
| Local gate result | `PASS` / `FAIL` |
| Security disclosure gate | `PASS` / `PENDING-HUMAN` / `FAIL` |
| Public artifact gate | `PASS` / `PENDING-HUMAN` / `FAIL` |
| External cohort proof | `PASS` / `PENDING-HUMAN` / `FAIL` |
| Final outcome | `cohort-ready` / `conditionally ready` / `blocked` |

## 0. Invariants

| Status | Gate | Required evidence |
|---|---|---|
| | Every chain command and receipt identifies `network=test`. | Command transcript and receipt fields; no implicit network default. |
| | Every subnet command and receipt identifies `netuid=523`. | Command transcript and receipt fields. |
| | No mainnet, `finney`, or other public network appears in executable cohort instructions. | Targeted repository search result. Localnet fixtures may remain clearly labeled as local-only. |
| | No mnemonic, seed, private key, wallet password, provider credential, `.env` content, or operator secret appears in source, logs, evidence, or release artifacts. | Release-content inspection and secret-scan result. Do not print secret-bearing environment variables to prove this gate. |
| | Paid provider execution is off. | Evidence that the mock panel is selected and neither the provider-spend CLI opt-in nor `DOLORES_ALLOW_PROVIDER_SPEND=1` was used. Do not record provider credentials. |
| | Generated or external task execution remains Docker-only and fail-closed. | Test proving Docker unavailability does not fall back to host execution. |
| | The controlled-cohort claim is used; no permissionless, production, training-value, or mainnet-readiness claim is made. | Final status and public copy review. |

## 1. Local release-candidate gates

These gates are local and may be completed without publishing, contacting a
participant, signing a chain action, or spending provider funds.

### Engine and dependency boundary

| Status | Gate | Required evidence |
|---|---|---|
| | The engine builds wheel and source distribution for `0.2.0rc1`. | Exact build command, exit code, filenames, and SHA-256 values. |
| | Package contents exclude work databases, generated datasets, provider material, internal reports, local paths, caches, and credentials. | Complete wheel and sdist file listings plus targeted content scan. |
| | The base engine install contains the authoritative task schema, loading, canonical serialization, and stable hash without validator-only dependencies. | Clean base-only install and import/hash smoke output. |
| | Validator-only dependencies are isolated behind the pinned engine extra selected by ADR-001. | Built metadata and clean validator install. |
| | The verifier Dockerfile or equivalent required runtime asset resolves from the installed distribution, not a source checkout. | Clean-directory asset-resolution and image-build evidence. |
| | Golden task and wire fixtures produce the same stable hash in engine-base, subnet-miner, and subnet-validator environments. | Exact fixture digest and three matching results. |

### Subnet installation and miner surface

| Status | Gate | Required evidence |
|---|---|---|
| | The subnet builds installable `0.2.0rc1` artifacts and pins the exact compatible engine release. | Built metadata, filenames, SHA-256 values, and dependency inspection. |
| | A fresh environment outside both source trees installs from the two local release artifacts. | Temporary-environment path, exact install command, and `pip check` result. |
| | The clean install works without `DOLORES_REPO`, editable installs, `PYTHONPATH`, adjacent checkouts, or source-tree current working directory. | Sanitized command transcript and imported module locations. |
| | Installed miner entry points expose the implemented doctor/init/validate/serve journey. | Installed command discovery and help output. Record only syntax that exists in the release candidate. |
| | Curated mutation assets resolve from the installed package. | Init/asset smoke from a clean directory. |
| | Miner install does not require Docker, DuckDB, PyArrow, Streamlit, Fireworks credentials, a solver panel, or validator internals. | Installed dependency inventory and miner doctor result. |
| | Miner doctor checks supported Python, pinned versions, Bittensor SDK, `btcli`, wallet/hotkey existence without reading them, public testnet balance, netuid-523 registration, port availability, public-address validity, engine import, task loading, and published-axon reachability. | Redacted doctor output. Public addresses and balances may be recorded; wallet paths and key material may not. |

### Full local verification

| Status | Gate | Required evidence |
|---|---|---|
| | Engine lint and full tests pass. | Exact command, exit code, and test count. |
| | Subnet lint and full tests pass with the pinned engine installed normally. | Exact command, exit code, and test count. |
| | Docker reference verification passes with `executed=true` and `containerized=true`. | Verification artifact and immutable image digest. |
| | Documentation commands execute from a clean directory or installed release bundle. | Command transcript and exit codes. |
| | CI installs the pinned engine and covers full subnet tests, clean package installation, Docker smoke, authenticated wire, rejection cases, holdout, and recurring restart behavior. | Workflow revision and successful check URLs. |

## 2. Authenticated transport gates

| Status | Gate | Required evidence |
|---|---|---|
| | No custom no-op Axon verifier remains in the cohort serve path. | Code review and regression test. |
| | A valid Bittensor-signed Dendrite request succeeds through the installed SDK version. | Signed integration test result with SDK version. |
| | Invalid request signature is rejected before task handling. | Negative integration test and observed unauthorized status. |
| | Missing or stale nonce is rejected. | Negative integration tests. |
| | Replaying an already accepted request is rejected. | Replay test using the same authenticated request identity. |
| | The miner response signature binds the canonical submissions digest to request nonce/UUID, epoch, quota, protocol version, and miner hotkey. | Valid response-signature integration test and binding-field audit. |
| | Response-body tampering is rejected by the validator. | Negative integration test. |
| | Caller authorization policy is documented and tested. | Policy text plus authorized/unauthorized cases. |
| | Package, response-size, quota, and request-frequency limits remain enforced. | Boundary and rejection tests. |

## 3. Public endpoint and supervised miner gates

These are local/configuration gates until publication is explicitly approved.

| Status | Gate | Required evidence |
|---|---|---|
| | Public mode requires a globally routable IPv4 address and fixed external port. | Address-classification tests and configuration validation. |
| | Public mode rejects private, loopback, link-local, multicast, unspecified, and reserved addresses. | Positive and negative tests covering the rejected classes. |
| | Local rehearsal mode remains clearly separate and may use loopback/private addresses without being called public. | CLI/help and documentation review. |
| | Supported Ubuntu VPS deployment instructions use an installed release, not a private checkout. | Clean VPS rehearsal transcript or equivalent clean-machine evidence. |
| | Supervisor configuration restarts the miner and preserves logs. | Supervisor validation and controlled restart evidence. |
| | Health evidence covers process state, local listener, exact metagraph publication, and reachability from the validator side. | Health output and observation timestamp. |

## 4. Validator-owned holdout gates

| Status | Gate | Required evidence |
|---|---|---|
| | Miner-supplied hidden tests are labeled author tests, not independent ground truth. | Protocol and evidence wording review. |
| | Only the supported `parser_roundtrip` subset reaches cohort evaluation; unsupported families/archetypes fail closed. | Allow/reject tests with explicit reason codes. |
| | The reference must pass author tests and the validator-owned holdout. | Positive integration fixture. |
| | Known wrong solutions fail the validator-owned holdout. | Negative integration fixtures. |
| | Holdout cases derive deterministically from the versioned policy, task hash, and operator-controlled secret. | Reproducibility test using a test-only secret. Never record the live secret. |
| | Active holdout cases and secret-derived seed material never cross the miner wire response or enter public evidence. | Wire/evidence serialization tests and content scan. |
| | Audit evidence records policy version, case-set digest, case count, and pass/fail only. | Example private and public-safe records. |

## 5. Recurring validator gates

| Status | Gate | Required evidence |
|---|---|---|
| | A whole tick holds an exclusive OS lock for its archive/state root. | Concurrent-start test: exactly one tick proceeds. |
| | Epoch IDs are allocated automatically and monotonically. | Two-tick artifact sequence. |
| | State transitions follow `allocated -> querying -> evaluating -> weights_submitting -> committed`. | State artifacts for successful and failed ticks. |
| | Discovery/RPC failure before evaluation retries only the same safe allocation. | Failure/retry test. |
| | Failure after durable evaluation does not duplicate audit rows. | Restart test and row-count evidence. |
| | Restart in ambiguous `weights_submitting` state fails closed and never auto-resubmits. | Crash/restart test. |
| | Miner endpoints come from the netuid-523 metagraph in the supported path; no manual endpoint injection is used. | Discovery artifact and command transcript. |
| | Health reports Docker status, discovered/reachable miners, last completed epoch, last successful weight receipt, blocks since validator update, chain readiness, and degraded conditions. | Health output captured after a restart. |
| | Two consecutive dry-run epochs reproduce across a process restart. | Epoch artifacts, replay results, restart timestamp, and absence of duplicate rows. |
| | A documented supervised `systemd` method runs recurring ticks and retains logs. | Unit/timer verification and controlled restart evidence. |

## 6. Security disclosure gate

| Status | Gate | Required evidence |
|---|---|---|
| | A private reporting channel exists. | GitHub setting read-back or documented private advisory/contact channel. |
| | The pending report referenced by public issue #4 has been received privately. | Private advisory identifier only; no finding details in this checklist. |
| | Findings have been triaged against the release candidate. | Private triage record with owner and disposition. |
| | Required fixes and regression tests pass before public cohort publication. | Private advisory cross-reference plus public-safe test evidence. |

Until these rows pass, use `PENDING-HUMAN`. Follow
[`security-disclosure-packet.md`](security-disclosure-packet.md); never paste
the findings into public issues, commits, logs, or this checklist.

## 7. STOP-LEON publication and chain gates

Nothing in this section is authorized by completion of the local gates.

### Public artifacts

`STOP-LEON` is required before creating the engine remote, pushing either
repository, publishing release artifacts, or creating tag `v0.2.0-rc.1`.

Evidence required before approval:

- every local gate above passes;
- exact commits, artifact filenames, and SHA-256 values are listed;
- rollback identifies how to withdraw/deprecate the release and return cohort
  instructions to the prior known-good revision.

### Axon publication or registration

`STOP-LEON` is required before wallet registration or `serve_axon` publication.
The approval packet must state the exact implemented command, confirm
`network=test` and `netuid=523`, explain what is signed or spent, show the public
IPv4/port validation and local service health, and provide the republish/stop
recovery path.

### Live weights

All four existing gates remain mandatory and independent:

1. chain mode explicitly set to live;
2. explicit allow-extrinsics CLI flag;
3. `DOLORES_ALLOW_EXTRINSICS=1` supplied for that invocation, never stored in a
   committed environment file;
4. exact typed live-confirmation phrase
   `I-UNDERSTAND-THIS-WILL-SUBMIT-WEIGHTS`.

Commit-reveal uncertainty remains fail-closed. `STOP-LEON` approval must name
the exact epoch and payload digest before either external proof epoch submits
weights. Dry-run evidence is not authorization for a live submission.

## 8. External participant proof

This section cannot be satisfied by a fixture, first-party wallet, local persona,
or manually injected endpoint. Use
[`external-miner-evidence-template.md`](external-miner-evidence-template.md).

| Status | Gate | Required evidence |
|---|---|---|
| | A non-first-party participant installs immutable public engine and subnet releases without private files or paths. | Release hashes and participant-side clean-install result. |
| | The participant uses a non-first-party public hotkey registered only on `network=test`, `netuid=523`. | Public hotkey, UID, and metagraph observation. |
| | The axon publishes a stable globally routable IPv4/port and survives a supervised process restart. | Two timestamped metagraph read-backs and signed reachability after restart. |
| | Validator discovers the miner from the metagraph without manual endpoints. | Discovery evidence. |
| | Signed request, signed response, Docker verification, author tests, wrong-solution probes, dedup, and validator-owned holdout pass for the supported family. | Epoch audit and holdout digest metadata; never publish holdout cases. |
| | First successful external epoch commits a nonzero testnet weight. | Epoch receipt, payload digest, public chain receipt/read-back, and timestamp. |
| | The immediately following successful external epoch commits a nonzero testnet weight for the same miner. | Consecutive epoch receipt and public read-back. |
| | Both epochs pass replay and contain no manual endpoint, first-party persona, provider-spend, or hidden holdout material. | Replay/evidence audit. |

## 9. Final decision

- `cohort-ready`: every local, security, publication, and external proof gate is
  `PASS`, including two consecutive successful external epochs.
- `conditionally ready`: all authorized local gates pass, while one or more
  explicitly human/external gates remain `PENDING-HUMAN`.
- `blocked`: a required gate fails and the release candidate cannot safely enter
  the cohort.

Even `cohort-ready` does not mean permissionless, production, mainnet, or
public-launch ready.
