# Architecture

Dolores Autocurricula proves a single loop: **miners propose verifiable task
packages, and the validator scores each package for marginal value to a
curriculum archive.** The design goal for this stage is to prove the *loop*, not
the economics.

## Components

- **Miner** — supplies a Dolores task package: an RL coding-agent task with
  public tests, hidden tests, a reference solution, and metadata. Personas
  (honest, duplicate-spammer, invalid) let the loop be tested adversarially.
- **Validator** — pulls packages over signed axon/dendrite transport, runs the
  verification pipeline, scores, updates weights, and writes evidence.
- **Verification pipeline** — the gauntlet each package must survive (below).
- **Scoring / EMA** — turns per-task results into per-miner scores, smooths them
  with an exponential moving average, and normalizes to a weight vector.
- **Archive** — durable record of tasks, verification runs, and lineage
  (JSONL submissions plus a DuckDB store).
- **Chain layer** — the gated path that turns a weight vector into an on-chain
  `set_weights` extrinsic.

The subnet deliberately **reuses the Dolores Autocurricula engine** (task
schema, canonical task hashes, Docker verification, safety scanner, hidden-test
separation, wrong-solution probes, scoring) rather than re-implementing that
logic. The subnet's own additions are the miner/validator process boundary,
task-submission messages and content hashes, per-miner aggregation, weight
generation, and the wallet/chain integration.

## Epoch flow, end to end

```
1. Miner selects/creates a Dolores task package and submits a content hash
   plus the task payload over the wire.
2. Validator loads the package.
3. Cheap gates run in order (fail-closed):
      a. schema valid
      b. safety clean
      c. reference solution passes public AND hidden tests in Docker
      d. wrong-solution probes are caught (bad code must fail hidden tests)
      e. duplicate / dedup gate passes
4. Validator assigns a quality score (0 on any hard-gate failure).
5. Scores feed the EMA; EMA is normalized into the weight vector.
6. Validator writes an archive row (task + verification run + lineage).
7. Validator emits two artifacts: deterministic weights file and chain receipt.
8. CLI report shows accepted tasks, per-miner ranking, and replay status.
```

A single hard-gate failure sets `score = 0`. Otherwise the staged score weighs
verifier quality, novelty/diversity, frontier signal, and metadata clarity.
Frontier signal can be a cached or mocked panel result at this stage — paid
inference is never required to run the loop.

## Fail-closed chain safety

The chain layer is designed so that the *default* behavior of every path is to
**not** write to a public chain.

**Gate tiers.** The validator's chain mode is one of:

- `off` — default. No extrinsic is ever constructed for submission.
- `dry-run` — the real weight payload is built and a receipt is produced, but
  nothing is submitted. Used to inspect exactly what *would* be sent.
- `live` — submission is attempted, and only after all gates pass.

**Four independent live gates.** Moving to a live submission requires all of:
an explicit chain mode of `live`, an explicit allow-extrinsics flag, an explicit
typed confirmation phrase, and a matching environment guard. Any one missing
aborts before signing. This makes an accidental live write essentially
impossible from a normal command.

**Commit-reveal handling.** Before submitting, the validator detects the
subnet's `commit_reveal_weights_enabled` state via the SDK. If commit-reveal is
enabled, live submission is **skipped** (`reason=commit_reveal_enabled`) rather
than sending a plain payload that would not read back on the metagraph
immediately. Overriding this requires an explicit `--allow-commit-reveal`, and
the resulting receipt is treated as *commit* evidence, not immediate read-back
evidence. This detection is the piece that was hardened during localnet
rehearsal after an early payload committed but did not read back.

## Determinism and replay

Scoring is byte-reproducible. Each epoch writes a **deterministic weights file**
that is independent of chain conditions, plus a separate **volatile chain
receipt** recording the extrinsic outcome. The split is deliberate: the proof
that scoring is correct must not depend on whether a chain write succeeded.

The reporting tool can `--replay-check` any epoch: it re-derives the weight
vector from the recorded inputs and confirms it matches the stored artifact,
printing `REPLAY OK`. This makes every epoch independently auditable from the
archive alone.

## What runs where

- **Docker verifier** — every task's reference solution and probes execute in a
  container (`containerized=true`, `executed=true` in the verification record),
  so verification is isolated and reproducible rather than trusting miner-side
  claims.
- **Archive** — submissions are appended as JSONL for a streaming audit trail;
  tasks, verification runs, and lineage are also written to a DuckDB store for
  queryable history.
- **Transport** — miners run Bittensor axons; the validator dendrites into them.
  Transport failures (an unreachable miner) are recorded as a first-class
  `unreachable` status with zeroed value, not as a pipeline crash.
