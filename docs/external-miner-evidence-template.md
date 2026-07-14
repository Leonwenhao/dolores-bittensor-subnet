# External Miner Cohort Evidence Template

Use one copy of this template for the first non-first-party HackerQuest miner
proof on Bittensor public testnet. It is deliberately limited to public identity,
immutable release evidence, authenticated reachability, holdout digest metadata,
epoch receipts, weights, and timestamps.

Do not record or request a mnemonic, seed phrase, private key, wallet password,
wallet file, wallet path, `.env` content, provider credential, operator holdout
secret, secret-derived seed, active holdout case, raw signed payload, or raw
signature. A public SS58 hotkey, UID, axon address, chain receipt, and artifact
digest are sufficient.

Do not use this template for a fixture, local persona, first-party miner, or
manually injected endpoint.

## Proof status

| Field | Value |
|---|---|
| Evidence created at (UTC) | |
| Evidence last verified at (UTC) | |
| Network | `test` |
| Netuid | `523` |
| Result | `PASS` / `FAIL` / `PENDING-HUMAN` |
| Nonclaim | Controlled cohort only; not permissionless, production, mainnet, or training-value proof |

## Immutable release identity

| Artifact | Version | Immutable revision | Artifact filename or image reference | SHA-256 or immutable digest | Verified at (UTC) |
|---|---|---|---|---|---|
| Dolores engine | `0.2.0rc2` | | | | |
| Dolores subnet | `0.2.0rc2` | | | | |
| Verifier image | | | | | |

## External miner public identity

| Field | Value |
|---|---|
| Miner hotkey SS58 (public) | |
| Miner UID on netuid 523 | |
| Published axon IPv4 (public) | |
| Published axon port | |
| First metagraph observation block | |
| First metagraph observation time (UTC) | |
| Post-restart metagraph observation block | |
| Post-restart metagraph observation time (UTC) | |

Do not add participant personal information or coldkey material. Confirm
non-first-party status outside this public-safe artifact using the operator's
cohort roster.

## Metagraph discovery

| Observation | Result | Evidence locator or digest | Timestamp (UTC) |
|---|---|---|---|
| Netuid-523 metagraph maps the public hotkey to the recorded UID | | | |
| Metagraph axon exactly matches the recorded public IPv4 and port | | | |
| Validator discovers the axon without a manual endpoint | | | |
| Same public axon is observed after supervised miner restart | | | |

Evidence locators should be a public URL or repository-relative artifact path;
avoid machine-specific absolute paths.

## Signed reachability

| Check | Result | Evidence digest or test identifier | Timestamp (UTC) |
|---|---|---|---|
| Valid Bittensor-signed request accepted | | | |
| Invalid signature rejected | | | |
| Stale nonce rejected | | | |
| Replayed request rejected | | | |
| Valid miner response signature accepted | | | |
| Response-body tamper rejected | | | |
| Validator reaches the public axon after miner restart | | | |

Record a digest or test/evidence identifier, not the raw request, response,
signature, nonce, UUID, wallet configuration, or headers.

## Validator-owned holdout metadata

Do not include active cases, expected outputs, the operator secret, or any
secret-derived seed.

| Field | Value |
|---|---|
| Holdout policy version | |
| Supported family/archetype | |
| Case-set digest | |
| Case count | |
| Reference result | `PASS` / `FAIL` |
| Known-wrong-solution result | `PASS` / `FAIL` |
| Public-safe holdout evidence digest | |
| Evaluation timestamp (UTC) | |

## Consecutive external epochs

Both rows must describe consecutive successful committed validator epochs for
the same external miner. Neither row may use a manually supplied endpoint.

| Field | First successful epoch | Immediately following successful epoch |
|---|---|---|
| Epoch ID | | |
| Tick allocated at (UTC) | | |
| Tick committed at (UTC) | | |
| Miner hotkey SS58 | | |
| Miner UID | | |
| Discovered axon IPv4:port | | |
| Metagraph discovery block | | |
| Signed reachability result | `PASS` / `FAIL` | `PASS` / `FAIL` |
| Holdout policy version | | |
| Holdout case-set digest | | |
| Holdout result | `PASS` / `FAIL` | `PASS` / `FAIL` |
| Epoch receipt locator | | |
| Epoch receipt SHA-256 | | |
| Weight payload digest | | |
| Public extrinsic identifier | | |
| Public inclusion/read-back timestamp (UTC) | | |
| Recorded miner weight | | |
| Weight is nonzero | `PASS` / `FAIL` | `PASS` / `FAIL` |
| Replay result | `PASS` / `FAIL` | `PASS` / `FAIL` |

## Completion checks

| Status | Check |
|---|---|
| | Network is exactly `test`; netuid is exactly `523`. |
| | Engine, subnet, and verifier identities match the immutable release table. |
| | Public hotkey, UID, and axon match every metagraph and epoch record. |
| | Discovery used the metagraph, not a manual endpoint. |
| | Signed request/response reachability passed after a supervised restart. |
| | Holdout evidence exposes only policy version, digest metadata, count, and result. |
| | Both committed epochs recorded nonzero weight for the same external miner. |
| | The epochs are consecutive successful committed epochs. |
| | Both epoch receipts and public read-backs have timestamps and immutable digests. |
| | No wallet secret, provider credential, operator secret, raw signature, active holdout case, or participant personal information appears in this artifact. |

If any required row is blank, indirect, or unverifiable, the external cohort
proof remains `FAIL` or `PENDING-HUMAN`; it is not replaced by a local rehearsal.
