# Testnet Status

Canonical, evidence-backed status for the Dolores Autocurricula subnet. A
machine-readable mirror lives at [`../configs/testnet.json`](../configs/testnet.json).

## Network

| Field | Value |
|---|---|
| Subnet name | Dolores Autocurricula |
| Network | Bittensor public **testnet** |
| netuid | **523** |
| Registered / started | 2026-07-08 |
| Repo | https://github.com/Leonwenhao/dolores-bittensor-subnet |

## On-chain events

All extrinsics are on Bittensor testnet, 2026-07-08.

| Event | Extrinsic |
|---|---|
| Subnet create | `7512866-7` |
| Subnet start (emission schedule) | `7512878-7` |
| Miner-0 register | `7512886-6` |
| Miner-1 register | `7512893-7` |
| Validator stake | `7512943-6` |
| Commit-reveal disable | `7512952-7` |

## Addresses and UIDs

| Role | UID | SS58 |
|---|---|---|
| Owner coldkey | — | `5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG` |
| Validator | 0 | `5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm` |
| Miner-0 | 1 | `5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA` |
| Miner-1 | 2 | `5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg` |

## Stake and hyperparameters

- Validator stake: **22.200467971 alpha** on netuid 523 (uid 0).
- Commit-reveal: **disabled**, verified `commit_reveal_weights_enabled=false`
  on-chain after an owner toggle (extrinsic `7512952-7`).

A testnet faucet top-up of roughly 10 τ landed between miner registration and
the validator stake; balances are otherwise not load-bearing for the status
here and are omitted.

## Current gaps

State plainly: the subnet is **registered, started, and staked**, but it is not
yet emitting live weights.

1. **Validator permit not yet granted.** At the first post-stake read-back,
   `validator_permit=false`. This is expected immediately after registration and
   stake. The permit is expected to flip at a tempo boundary (tempo = 360
   blocks); the next step is to poll permit/rate readiness after that boundary.
2. **No public live weights yet.** No `set_weights` has been submitted to the
   public metagraph. The write path is implemented and rehearsed (see appendix)
   but deliberately gated until the permit is live.

When live weights are submitted, this document will record the submission
extrinsic and the metagraph read-back that confirms the nonzero vector.

## Chain-safety posture

- Live chain writes default **off**; the validator must be explicitly moved from
  `off` → `dry-run` → `live`.
- Four independent gates guard any live extrinsic.
- Commit-reveal state is detected and **fails closed**: if commit-reveal is
  enabled, live submission is skipped rather than sending a payload that would
  not read back immediately. Because netuid 523 was verified commit-reveal-off,
  the plain (Path A) weight flow applies; if the flag ever flips true, live
  weights require an explicit `--allow-commit-reveal` and the receipt is treated
  as *commit evidence*, not immediate metagraph read-back.

## Appendix: prior localnet rehearsal

Before public registration, the entire chain path was rehearsed end-to-end
against a **local substrate node** (`ws://127.0.0.1:9944`), not any public
network.

- Local subnet created as `netuid=2`; emission schedule started (start extrinsic
  `4221-2`).
- Validator registered uid 0; miner-0 registered uid 1 (extrinsic `4837-2`);
  miner-1 registered uid 2 (extrinsic `5355-3`).
- Validator permit was **true** on the local node.
- A live `set_weights` submission was **accepted by the local node**
  (`mode=submitted`, `submission.success=true`).
- Dry-run and live epochs produced deterministic weight artifacts that **replay
  OK**.
- The local `netuid=2` happened to have commit-reveal enabled, so post-fix runs
  correctly **skipped** live submission with `reason=commit_reveal_enabled` —
  demonstrating the fail-closed detection working as designed.

The rehearsal proves the archive rows, deterministic weights, replay checks, and
live submission mechanics. It is localnet evidence, not a public testnet receipt.

## Status history

- **2026-07-08** — Subnet created, started, both miners registered, validator
  staked, commit-reveal verified off on Bittensor testnet netuid 523. Validator
  permit pending; no public live weights yet.
