# Roadmap

The immediate objective is a safe, controlled cohort with one to three known
HackerQuest miners on Bittensor public testnet netuid `523`.

## Implemented in `0.2.0rc2`

- Exact subnet/engine version pin with a lightweight miner dependency boundary.
- Installed `dolores-miner` and `dolores-validator` command surfaces.
- `dolores-subnet-v1` package schema and canonical stable-hash verification.
- Default Bittensor request verification, required body-hash fields, caller
  allowlisting, and miner-signed response payloads.
- Public IPv4 policy and exact metagraph publication read-back.
- Core `parser_roundtrip` policy with miner author tests and a validator-private,
  secret-keyed holdout.
- Packaged, auto-built `dolores-verifier-pytest:0.2.0rc2` with non-root,
  networkless, read-only, resource-limited execution.
- Serialized recurring ticks with automatic epoch IDs, atomic state, exclusive
  locking, crash recovery boundaries, metagraph discovery, and health output.
- Full local tests for packaging, signed wire behavior, rejection cases,
  holdout, Docker, and recurring state.

## Required before cohort launch

1. Publish immutable public engine and subnet artifacts, hashes, and tag only
   after explicit approval. No participant may depend on a local/private path.
2. Receive and privately triage the pending security review; fix any blocking
   finding and add public-safe regression tests.
3. Rehearse the Ubuntu supervisor path from a clean public install.
4. Bring up one non-first-party miner on a stable globally routable IPv4/port,
   with exact netuid-523 metagraph read-back and signed reachability.
5. Run two successful consecutive external-miner epochs with nonzero testnet
   weight and replayable evidence.

The July 12 chain snapshot is stale/offline, so historical July 9 proof does
not satisfy these launch gates.

## After cohort proof

- Expand supported task families only after each family has a validator-owned
  holdout and explicit wrong-solution coverage.
- Publish a public verifier-quality and accepted-task evidence surface.
- Export the deduplicated archive in research-friendly formats.
- Measure whether task scores predict downstream training value before making
  any training-impact claim.
- Consider broader registration only after endpoint stability, validator
  recovery, and independent-miner evidence are routine.

Paid solver-panel calibration remains optional, off by default, and separate
from cohort readiness. A future calibration must be explicitly approved,
budget-capped, dry-run previewed, and supported by public-safe receipts.
