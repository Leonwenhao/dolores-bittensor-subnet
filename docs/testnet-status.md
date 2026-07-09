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
| First public live weights | `7520191-8` |

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

## Public live weights

The subnet is **registered, started, staked, permit-granted, and live-weighted**
on Bittensor public testnet.

- Validator permit: **true**, observed in `btcli wallet overview` before the
  first submit.
- First public submit: `7520191-8`, 2026-07-09, netuid 523.
- Emitted vector: uid `1` received full weight, encoded as `65535`.
- Direct storage read-back: `Weights[523,0] = [(1, 65535)]`.
- Wallet overview read-back: validator uid `0` `UPDATED` counter reset from
  roughly `7310` before submit to `3` after submit.

Operational note: the repo validator's SDK dry-run path hit intermittent
testnet websocket hangs during the first public run. The submit therefore used a
minimal direct async substrate fallback that composed the same
`SubtensorModule.set_weights` call for `dests=[1]`, `weights=[65535]`,
`version_key=1`, signed by the validator hotkey on `network=test`. The
wire-mode validator artifact immediately before the submit scored miner-0 at
`1.0` and miner-1 at `0.0`, and replay checked `REPLAY OK`.

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
  staked, commit-reveal verified off on Bittensor testnet netuid 523. At that
  time, validator permit and public live weights were still pending.
- **2026-07-09** — Validator permit observed true. First public live weights
  submitted in extrinsic `7520191-8`; direct read-back confirmed
  `Weights[523,0] = [(1, 65535)]`.
