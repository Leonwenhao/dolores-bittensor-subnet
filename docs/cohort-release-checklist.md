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
| Review timestamp (UTC) | `2026-07-12T16:25:12Z` |
| Engine immutable revision | artifact `7be1167ee0afad8857c2b3fb435dc14ad476e2a0`; manifest `8c096196ceccd02906f21b2476c0b82737c01516` |
| Engine wheel filename and SHA-256 | `dolores_autocurricula-0.2.0rc1-py3-none-any.whl`; `6cc5a5e91c4fee73aa34f7d16d5905cb21366439fea8b4188f2c3db9978954fc` |
| Subnet immutable revision | artifact `c699a3e0b58c0b08c5c1e82b673d7c8caa6d7118` |
| Subnet wheel filename and SHA-256 | `dolores_bittensor_subnet-0.2.0rc1-py3-none-any.whl`; `e87c0b0e5625585665f2b6449543b66a7b8d88175cbd4bb7cf2f1ce7c196c888` |
| Verifier image tag and immutable digest | `dolores-verifier-pytest:0.2.0rc1`; `sha256:a9a963be4c32c57f2af3ac927fe92f45068869c9a3ea617e58df5cd81fd045c4` |
| Local gate result | `PASS` — see [`release-manifest-0.2.0rc1.md`](release-manifest-0.2.0rc1.md) |
| Security disclosure gate | `PENDING-HUMAN` |
| Public artifact gate | `PENDING-HUMAN` |
| External cohort proof | `PENDING-HUMAN` |
| Final outcome | `conditionally ready` |

## 0. Invariants

| Status | Gate | Required evidence |
|---|---|---|
| PASS | Every chain command and receipt identifies `network=test`. | Command transcript and receipt fields; no implicit network default. |
| PASS | Every subnet command and receipt identifies `netuid=523`. | Command transcript and receipt fields. |
| PASS | No mainnet, `finney`, or other public network appears in executable cohort instructions. | Targeted repository search result. Localnet fixtures may remain clearly labeled as local-only. |
| PASS | No mnemonic, seed, private key, wallet password, provider credential, `.env` content, or operator secret appears in source, logs, evidence, or release artifacts. | Release-content inspection and secret-scan result. Do not print secret-bearing environment variables to prove this gate. |
| PASS | Paid provider execution is off. | Evidence that the mock panel is selected and neither the provider-spend CLI opt-in nor `DOLORES_ALLOW_PROVIDER_SPEND=1` was used. Do not record provider credentials. |
| PASS | Generated or external task execution remains Docker-only and fail-closed. | Test proving Docker unavailability does not fall back to host execution. |
| PASS | The controlled-cohort claim is used; no permissionless, production, training-value, or mainnet-readiness claim is made. | Final status and public copy review. |

## 1. Local release-candidate gates

These gates are local and may be completed without publishing, contacting a
participant, signing a chain action, or spending provider funds.

### Engine and dependency boundary

| Status | Gate | Required evidence |
|---|---|---|
| PASS | The engine builds wheel and source distribution for `0.2.0rc1`. | Exact build command, exit code, filenames, and SHA-256 values. |
| PASS | Package contents exclude work databases, generated datasets, provider material, internal reports, local paths, caches, and credentials. | Complete wheel and sdist file listings plus targeted content scan. |
| PASS | The base engine install contains the authoritative task schema, loading, canonical serialization, and stable hash without validator-only dependencies. | Clean base-only install and import/hash smoke output. |
| PASS | Validator-only dependencies are isolated behind the pinned engine extra selected by ADR-001. | Built metadata and clean validator install. |
| PASS | The verifier Dockerfile or equivalent required runtime asset resolves from the installed distribution, not a source checkout. | Clean-directory asset-resolution and image-build evidence. |
| PASS | Golden task and wire fixtures produce the same stable hash in engine-base, subnet-miner, and subnet-validator environments. | Exact fixture digest and three matching results. |

### Subnet installation and miner surface

| Status | Gate | Required evidence |
|---|---|---|
| PASS | The subnet builds installable `0.2.0rc1` artifacts and pins the exact compatible engine release. | Built metadata, filenames, SHA-256 values, and dependency inspection. |
| PASS | A fresh environment outside both source trees installs from the two local release artifacts. | Temporary-environment path, exact install command, and `pip check` result. |
| PASS | The clean install works without `DOLORES_REPO`, editable installs, `PYTHONPATH`, adjacent checkouts, or source-tree current working directory. | Sanitized command transcript and imported module locations. |
| PASS | Installed miner entry points expose the implemented doctor/init/validate/serve journey. | Installed command discovery and help output. Record only syntax that exists in the release candidate. |
| PASS | Curated mutation assets resolve from the installed package. | Init/asset smoke from a clean directory. |
| PASS | Miner install does not require Docker, DuckDB, PyArrow, Streamlit, Fireworks credentials, a solver panel, or validator internals. | Installed dependency inventory and miner doctor result. |
| PENDING-HUMAN | Miner doctor checks supported Python, pinned versions, Bittensor SDK, `btcli`, wallet/hotkey existence without reading them, public testnet balance, netuid-523 registration, port availability, public-address validity, engine import, task loading, and published-axon reachability. | Redacted doctor output. Public addresses and balances may be recorded; wallet paths and key material may not. |

### Full local verification

| Status | Gate | Required evidence |
|---|---|---|
| PASS | Engine lint and full tests pass. | Exact command, exit code, and test count. |
| PASS | Subnet lint and full tests pass with the pinned engine installed normally. | Exact command, exit code, and test count. |
| PASS | Docker reference verification passes with `executed=true` and `containerized=true`. | Verification artifact and immutable image digest. |
| PASS | Documentation commands execute from a clean directory or installed release bundle. | Command transcript and exit codes. |
| PENDING-HUMAN | CI installs the pinned engine and covers full subnet tests, clean package installation, Docker smoke, authenticated wire, rejection cases, holdout, and recurring restart behavior. | Workflow revision and successful check URLs. |

## 2. Authenticated transport gates

| Status | Gate | Required evidence |
|---|---|---|
| PASS | No custom no-op Axon verifier remains in the cohort serve path. | Code review and regression test. |
| PASS | A valid Bittensor-signed Dendrite request succeeds through the installed SDK version. | Signed integration test result with SDK version. |
| PASS | Invalid request signature is rejected before task handling. | Negative integration test and observed unauthorized status. |
| PASS | Missing or stale nonce is rejected. | Negative integration tests. |
| PASS | Replaying an already accepted request is rejected. | Replay test using the same authenticated request identity. |
| PASS | The miner response signature binds the canonical submissions digest to request nonce/UUID, epoch, quota, protocol version, and miner hotkey. | Valid response-signature integration test and binding-field audit. |
| PASS | Response-body tampering is rejected by the validator. | Negative integration test. |
| PASS | Caller authorization policy is documented and tested. | Policy text plus authorized/unauthorized cases. |
| PASS | Package, response-size, quota, and request-frequency limits remain enforced. | Boundary and rejection tests. |

## 3. Public endpoint and supervised miner gates

These are local/configuration gates until publication is explicitly approved.

| Status | Gate | Required evidence |
|---|---|---|
| PASS | Public mode requires a globally routable IPv4 address and fixed external port. | Address-classification tests and configuration validation. |
| PASS | Public mode rejects private, loopback, link-local, multicast, unspecified, and reserved addresses. | Positive and negative tests covering the rejected classes. |
| PASS | Local rehearsal mode remains clearly separate and may use loopback/private addresses without being called public. | CLI/help and documentation review. |
| PASS | Supported Ubuntu VPS deployment instructions use an installed release, not a private checkout. | Clean VPS rehearsal transcript or equivalent clean-machine evidence. |
| PENDING-HUMAN | Supervisor configuration restarts the miner and preserves logs. | Supervisor validation and controlled restart evidence. |
| PENDING-HUMAN | Health evidence covers process state, local listener, exact metagraph publication, and reachability from the validator side. | Health output and observation timestamp. |

## 4. Validator-owned holdout gates

| Status | Gate | Required evidence |
|---|---|---|
| PASS | Miner-supplied hidden tests are labeled author tests, not independent ground truth. | Protocol and evidence wording review. |
| PASS | Only the supported `parser_roundtrip` subset reaches cohort evaluation; unsupported families/archetypes fail closed. | Allow/reject tests with explicit reason codes. |
| PASS | The reference must pass author tests and the validator-owned holdout. | Positive integration fixture. |
| PASS | Known wrong solutions fail the validator-owned holdout. | Negative integration fixtures. |
| PASS | Holdout cases derive deterministically from the versioned policy, task hash, and operator-controlled secret. | Reproducibility test using a test-only secret. Never record the live secret. |
| PASS | Active holdout cases and secret-derived seed material never cross the miner wire response or enter public evidence. | Wire/evidence serialization tests and content scan. |
| PASS | Audit evidence records policy version, case-set digest, case count, and pass/fail only. | Example private and public-safe records. |

## 5. Recurring validator gates

| Status | Gate | Required evidence |
|---|---|---|
| PASS | A whole tick holds an exclusive OS lock for its archive/state root. | Concurrent-start test: exactly one tick proceeds. |
| PASS | Epoch IDs are allocated automatically and monotonically. | Two-tick artifact sequence. |
| PASS | State transitions follow `allocated -> querying -> evaluating -> weights_submitting -> committed`. | State artifacts for successful and failed ticks. |
| PASS | Discovery/RPC failure before evaluation retries only the same safe allocation. | Failure/retry test. |
| PASS | Failure after durable evaluation does not duplicate audit rows. | Restart test and row-count evidence. |
| PASS | Restart in ambiguous `weights_submitting` state fails closed and never auto-resubmits. | Crash/restart test. |
| PASS | Miner endpoints come from the netuid-523 metagraph in the supported path; no manual endpoint injection is used. | Discovery artifact and command transcript. |
| PENDING-HUMAN | Health reports Docker status, discovered/reachable miners, last completed epoch, last successful weight receipt, blocks since validator update, chain readiness, and degraded conditions. | Health output captured after a restart. |
| PASS | Two consecutive dry-run epochs reproduce across a process restart. | Epoch artifacts, replay results, restart timestamp, and absence of duplicate rows. |
| PENDING-HUMAN | A documented supervised `systemd` method runs recurring ticks and retains logs. | Unit/timer verification and controlled restart evidence. |

## 6. Security disclosure gate

| Status | Gate | Required evidence |
|---|---|---|
| PENDING-HUMAN | A private reporting channel exists. | GitHub setting read-back or documented private advisory/contact channel. |
| PENDING-HUMAN | The pending report referenced by public issue #4 has been received privately. | Private advisory identifier only; no finding details in this checklist. |
| PENDING-HUMAN | Findings have been triaged against the release candidate. | Private triage record with owner and disposition. |
| PENDING-HUMAN | Required fixes and regression tests pass before public cohort publication. | Private advisory cross-reference plus public-safe test evidence. |

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
| PENDING-HUMAN | A non-first-party participant installs immutable public engine and subnet releases without private files or paths. | Release hashes and participant-side clean-install result. |
| PENDING-HUMAN | The participant uses a non-first-party public hotkey registered only on `network=test`, `netuid=523`. | Public hotkey, UID, and metagraph observation. |
| PENDING-HUMAN | The axon publishes a stable globally routable IPv4/port and survives a supervised process restart. | Two timestamped metagraph read-backs and signed reachability after restart. |
| PENDING-HUMAN | Validator discovers the miner from the metagraph without manual endpoints. | Discovery evidence. |
| PENDING-HUMAN | Signed request, signed response, Docker verification, author tests, wrong-solution probes, dedup, and validator-owned holdout pass for the supported family. | Epoch audit and holdout digest metadata; never publish holdout cases. |
| PENDING-HUMAN | First successful external epoch commits a nonzero testnet weight. | Epoch receipt, payload digest, public chain receipt/read-back, and timestamp. |
| PENDING-HUMAN | The immediately following successful external epoch commits a nonzero testnet weight for the same miner. | Consecutive epoch receipt and public read-back. |
| PENDING-HUMAN | Both epochs pass replay and contain no manual endpoint, first-party persona, provider-spend, or hidden holdout material. | Replay/evidence audit. |

## 9. Final decision

- `cohort-ready`: every local, security, publication, and external proof gate is
  `PASS`, including two consecutive successful external epochs.
- `conditionally ready`: all authorized local gates pass, while one or more
  explicitly human/external gates remain `PENDING-HUMAN`.
- `blocked`: a required gate fails and the release candidate cannot safely enter
  the cohort.

Even `cohort-ready` does not mean permissionless, production, mainnet, or
public-launch ready.
