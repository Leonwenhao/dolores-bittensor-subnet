# Testnet Status

Canonical public-chain status for Dolores on Bittensor public testnet netuid
`523`. Historical proof and current service readiness are deliberately separate.

## Current snapshot — 2026-07-12

Read-only observation at block `7543179`:

| UID | Role | `last_update` | Current state | Axon |
|---:|---|---:|---|---|
| 0 | validator | `7521406` | `active=false`; incentive/dividends `0` | `0.0.0.0:0` |
| 1 | first-party miner | stale | public incentive/dividends `0` | `192.168.1.94:8091` |
| 2 | first-party miner | stale | public incentive/dividends `0` | `192.168.1.94:8092` |

The validator was `21773` blocks past its last update at the observed block.
The two miner endpoints are old RFC1918 addresses and are not reachable public
cohort infrastructure. The validator is not advertising an axon. Therefore the
subnet has valid historical chain receipts but is **stale/offline and not
launch-live**.

The `0.2.0rc2` endpoint policy rejects private, loopback, link-local,
reserved, and other non-global addresses for public publication. A cohort miner
must publish a stable globally routable IPv4/port and pass exact metagraph
read-back.

## Network identity

| Field | Value |
|---|---|
| Subnet | Dolores Autocurricula |
| Network | Bittensor public testnet |
| Netuid | `523` |
| Created / started | 2026-07-08 |
| Repository | https://github.com/Leonwenhao/dolores-bittensor-subnet |

| Role | UID | Public SS58 |
|---|---:|---|
| Owner coldkey | — | `5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG` |
| Validator | 0 | `5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm` |
| Miner-0 | 1 | `5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA` |
| Miner-1 | 2 | `5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg` |

## Historical on-chain events

All rows below are public-testnet events, not claims of current uptime.

| Event | Extrinsic |
|---|---|
| Subnet create | `7512866-7` |
| Start emission schedule | `7512878-7` |
| Register miner uid 1 | `7512886-6` |
| Register miner uid 2 | `7512893-7` |
| Validator stake | `7512943-6` |
| Disable commit-reveal | `7512952-7` |
| First public live weights | `7520191-8` |

At the July 8/9 proof point, validator stake was observed at
`22.200467971` alpha, validator permit was true, and
`commit_reveal_weights_enabled=false` had read back after the owner toggle.
These are dated observations; they are not substituted for a fresh preflight.

## First live-weight proof — 2026-07-09

The first public submit was extrinsic `7520191-8`. It encoded full weight for
uid `1`, and direct storage read-back returned:

```text
Weights[523,0] = [(1, 65535)]
```

Immediately before the submit, the validator artifact scored miner uid 1 at
`1.0`, uid 2 at `0.0`, and replay reported `REPLAY OK`. The first submission
used a minimal direct async-substrate fallback after the then-current SDK path
encountered websocket hangs. That caveat is historical: a later live submit ran
through the repository's gated SDK path and produced a successful receipt with
extrinsic hash beginning `0x8873244e`.

After the first Yuma tempo boundary, uid 1 was observed with incentive `1.0`
and nonzero per-uid alpha emission; uid 0 had dividends and vtrust `1.0`; uid 2
remained zero. This proved that the testnet incentive path processed the weight.
The July 12 values have since returned to zero while the services are stale, so
the historical observation must not be described as current emission.

## Historical axon discovery — later 2026-07-09

The first live-weight submit intentionally used local Axons with explicitly
supplied endpoints and made no discovery claim. Later that day, both first-party
miners signed `serve_axon` publication and the metagraph stored
`192.168.1.94:8091` and `192.168.1.94:8092`. A validator dry-run then discovered
both entries from the metagraph without supplied endpoints, mapped them to uids
1 and 2, assigned full dry-run weight to uid 1, and replayed successfully.

This is genuine historical proof that the discovery code path worked in the
operator's network context. It is **not** proof of an Internet-reachable or
stable public miner: RFC1918 addresses cannot support the external cohort and
the current RC refuses them in its public publish path.

## What remains unproved

- Immutable public `0.2.0rc2` engine and subnet release installation without a
  local checkout or private artifact.
- Private receipt and triage of the pending security report.
- A non-first-party miner with a stable public IPv4/port and signed reachability.
- Two consecutive successful epochs giving that external miner nonzero weight.
- Sustained validator operation and incentive observations after RC deployment.

Paid solver-panel calibration is off and is not a prerequisite for the cohort.

## Safety and fresh read-back

The current validator uses metagraph discovery, an exclusive recurring-tick
lock, automatic epoch IDs, atomic recovery state, four independent live-weight
gates, and fail-closed commit-reveal handling. A read-only operator health check
must spell the fixed target explicitly:

```bash
dolores-validator health \
  --mode testnet \
  --work /var/lib/dolores-validator \
  --wallet.name <VALIDATOR_WALLET> \
  --wallet.hotkey <VALIDATOR_HOTKEY> \
  --network test \
  --netuid 523
```

No historical row authorizes registration, axon publication, live weights,
artifact publication, participant contact, or paid inference.
