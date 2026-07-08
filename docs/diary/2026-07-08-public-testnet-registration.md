# Public Testnet Registration

Date: 2026-07-08

## Scope

Registered Dolores Autocurricula on Bittensor public testnet using the
`dolores-test` wallet and pushed the current GitHub repo before the on-chain
create command.

No mainnet/finney action, paid provider call, wallet-secret inspection, tag, or
public live `set_weights` run was performed.

## Outcome

Public testnet registration is complete.

- netuid: `523`
- subnet name: `Dolores Autocurricula`
- GitHub repo: `https://github.com/Leonwenhao/dolores-bittensor-subnet`
- owner coldkey: `5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG`
- validator uid 0: `5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm`
- miner-0 uid 1: `5FHE1ZpqMVWS3wyjbTmqDP4obyT1UhJ5fmzJWkf8noAVxkEA`
- miner-1 uid 2: `5DhPKfTfbN5nwTx3riEQz5TPZH94PV8GLV8oqFMyFG61ZkQg`
- validator stake: `22.200467971` alpha on netuid 523
- validator permit: `false` at first post-stake read-back
- commit-reveal weights: disabled and verified false after owner toggle

## Public Chain Events

- subnet create: `7512866-7`
- subnet start: `7512878-7`
- miner-0 register: `7512886-6`
- miner-1 register: `7512893-7`
- first validator stake attempts:
  - `1.0` TAO with 5% tolerance failed with `SlippageTooHigh`
  - `1.0` TAO with 35% tolerance failed with a btcli subscription reconnect
    error and no stake read-back
  - `0.1` TAO with MEV protection failed with shield decryption failure
- successful validator stake: `7512943-6`, using `0.1` TAO, safe staking,
  10% tolerance, and `--no-mev-protection`
- commit-reveal disable: `7512952-7`

## Evidence

- create output: path recorded in `work/testnet_create_subnet_latest_path.txt`
- start output: path recorded in `work/testnet_subnet_523_start_latest_path.txt`
- registration output:
  - `work/testnet_subnet_523_register_miner0_latest_path.txt`
  - `work/testnet_subnet_523_register_miner1_latest_path.txt`
- stake output:
  - `work/testnet_subnet_523_stake_validator_0p1_no_mev_latest_path.txt`
- final subnet read-back:
  - `work/testnet_subnet_523_show_after_stake.json`
- final wallet overview:
  - `work/testnet_wallet_overview_netuid523_after_cr_toggle.json`
- commit-reveal read-back:
  - `work/testnet_subnet_523_hyperparameters_after_cr_toggle.txt`

## Current Blocker

The validator permit had not yet flipped at first post-stake read-back:
`validator_permit=false`. This is expected immediately after registration and
stake; the next step is to poll permit/rate readiness after the tempo boundary
before running public live weights.

The public live-weight run should use the plain Path A flow because
`commit_reveal_weights_enabled=false` was verified on-chain. If the flag is
ever true again, use the explicit `--allow-commit-reveal` path and treat the
receipt as commit evidence rather than immediate metagraph read-back evidence.
