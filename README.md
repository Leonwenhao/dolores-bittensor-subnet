# Dolores Autocurricula

**The open proving ground for AI's training curriculum.**

A Bittensor subnet that pays for *verified task supply*. Miners produce
software tasks with hidden tests; the validator proves each task is real,
deduplicated, and hard — then rewards the tasks worth keeping.

- Network: Bittensor public **testnet**, netuid **523**
- Status: registered, started, validator staked (validator permit pending)
- Tests: 68 passing locally with the Dolores engine, public CI smoke enabled,
  `ruff` clean
- Repo: https://github.com/Leonwenhao/dolores-bittensor-subnet
- Canonical status & on-chain evidence: [`docs/testnet-status.md`](docs/testnet-status.md)

---

## Why this exists

Reinforcement-learning *environments* are abundant. What is scarce is the thing
labs actually pay for: **verified, deduplicated, frontier-calibrated tasks** —
problems with trustworthy graders, no contamination, and difficulty that tracks
the model frontier. Frontier labs spend on the order of a billion dollars a year
sourcing and cleaning RL environments, and most of that spend goes to
*verification and curation*, not to generating more raw problems.

Solver subnets reward agents for **solving** benchmarks. Dolores rewards the
opposite side of the market: **producing** the benchmarks. A miner's job is to
supply a task package — a coding problem with public and hidden tests, a
reference solution, and metadata — that survives an adversarial verification
gauntlet. Volume alone earns nothing; a miner who spams duplicates or ships
tasks with broken graders scores zero.

The incentive structure doubles as free red-teaming. Duplicate-spam pressure,
contamination pressure, and wrong-solution probes are exactly the attacks a
curriculum pipeline must survive to be trustworthy — so the network's
adversaries continuously harden the curation logic instead of degrading it.

Dolores Autocurricula is the open, public supply side of Dolores Research's
broader curriculum layer. It complements solver subnets (which reward solving
benchmarks) by rewarding the creation of the benchmarks those solvers need, and
the durable output — a verified, deduplicated task archive — is useful well
outside crypto.

## Current status

Honest snapshot. Full evidence in [`docs/testnet-status.md`](docs/testnet-status.md).

| Milestone | State |
|---|---|
| Subnet created on testnet (netuid 523) | done |
| Emission schedule started | done |
| Miners registered (uid 1, uid 2) | done |
| Validator staked (uid 0) | done |
| Commit-reveal verified off | done |
| Validator permit granted | pending (expected at a tempo boundary) |
| First public live weights | pending (blocked on permit) |

There are **no live public weights yet**. The chain-write path has been fully
rehearsed on a local substrate node — including a live `set_weights` accepted by
the node and a deterministic replay — but nothing has been written to the public
metagraph. See the rehearsal appendix in the status doc.

## How it works

Two roles talk over signed Bittensor axon/dendrite transport.

- **Miner** supplies a Dolores task package: an RL coding-agent task with public
  tests, hidden tests, a reference solution, and metadata.
- **Validator** runs each package through a verification pipeline and turns the
  results into on-chain weights.

```
 miner task package
        │
        ▼
 ┌──────────────────────────────────────────────────────────┐
 │ VALIDATION PIPELINE                                        │
 │                                                            │
 │  safety screen  →  deterministic Docker verification       │
 │       │                    │                               │
 │   (reject unsafe)     (reference must pass public+hidden)  │
 │                            │                               │
 │            wrong-solution probes (bad code must FAIL)       │
 │                            │                               │
 │                     duplicate / dedup gate                 │
 │                            │                               │
 │                          scoring                           │
 │                            │                               │
 │                    EMA  →  normalized weights              │
 └──────────────────────────────────────────────────────────┘
        │                             │
        ▼                             ▼
 deterministic weights file    volatile chain receipt
 (replayable)                  (extrinsic / read-back)
```

A task that passes every gate scores toward `1.0`; a duplicate or an invalid
task collapses to `0.0`. Scores feed an exponential moving average, which is
normalized into the weight vector. Task difficulty is measured by a solver
panel — a **pinned mock panel by default**, with an **optional calibration
mode** that measures gauntlet-surviving tasks against named frontier/open
models instead. The default loop needs no paid inference. Every epoch writes
two separate artifacts:
a **deterministic weights file** (byte-reproducible, replayable) and a
**volatile chain receipt** (the extrinsic outcome). Splitting them keeps the
scoring provable independent of chain conditions.

Architecture detail: [`docs/architecture.md`](docs/architecture.md).

## Quickstart

Run the full validator loop locally — no wallet, no chain, no keys. It exercises
an honest miner, a duplicate-spammer, and an invalid miner, and shows the honest
task winning all the weight.

```bash
python scripts/local_epoch.py --mode offline \
  --miners honest,duplicate_spammer,invalid --quota 1 --epoch 1 \
  --work work/demo
python scripts/report.py --work work/demo --epoch 1
python scripts/report.py --work work/demo --epoch 1 --replay-check 1
```

Expected: the honest miner takes `weight=1.0`, both adversaries take `0.0`, and
the replay check prints `REPLAY OK`. Full walkthrough — including the two-miner
wire demo and the kill test — in [`docs/demo.md`](docs/demo.md).

## Requirements

- Python 3.11
- Docker (the verifier runs each task in a container)
- `bittensor` SDK (wallets and axon/dendrite transport)
- The Dolores Autocurricula engine, referenced via an environment variable —
  the subnet deliberately reuses that backend for task schemas, verification,
  and scoring rather than re-implementing it:

  ```bash
  export DOLORES_REPO="<path-to-dolores-autocurricula>"
  ```
- **Optional — real calibration mode.** The default panel is mock and needs no
  credentials. A real calibration pass requires `--panel-mode calibrate`, the
  provider credential (`FIREWORKS_API_KEY`) in the environment, an explicit
  spend opt-in (`--allow-provider-spend` plus `DOLORES_ALLOW_PROVIDER_SPEND=1`),
  and a per-epoch task budget. It is opt-in and off by default; run
  `--panel-dry-run` first to preview the calls without spending.

## Repository layout

- `src/dolores_subnet/` — protocol, packaging, gates, bridge to the Dolores
  engine, scoring, EMA/weights, archive, epoch driver, wire transport, chain layer.
- `neurons/` — miner and validator entrypoints.
- `scripts/` — preflight checks, local epoch driver, reporting/replay.
- `tests/` — protocol, gates, scoring, chain-client, and import-discipline tests.
- `configs/` — machine-readable network status (`testnet.json`).
- `docs/` — status, architecture, roadmap, and demo.

## Current limitations

Stated plainly:

- **Testnet only.** No mainnet registration or economics.
- **First-party miners at launch.** The two registered miners are operated by
  the project; external miners are on the roadmap.
- **Weights are not yet live on the public chain.** The write path is rehearsed
  and gated, not exercised publicly.
- **Difficulty calibration is mock by default.** The frontier-difficulty signal
  comes from a pinned mock solver panel unless calibration mode is explicitly
  enabled against named models. Real calibration is opt-in, budget-capped, and
  operator-gated — it is not on by default.
- **Scores do not yet claim training-value prediction.** The current score
  proves a task is safe, verifiable, non-duplicate, and difficulty-signaled
  (mock panel by default; measured against named models in calibration mode) —
  not that it improves downstream training. Validating score → training value
  is explicit future work.

## Roadmap

Near term: validator permit → first public live weights → published read-back
evidence. Mid term: external miners and onboarding, task-family coverage
steering, verifier-quality leaderboard. Long term: mainnet consideration,
curriculum archive exports, and downstream training ablations. Detail in
[`docs/roadmap.md`](docs/roadmap.md).

## Contributing

Task authors wanted. A good task package is **verifiable** (a reference solution
that passes public *and* hidden tests deterministically in Docker),
**adversary-resistant** (wrong solutions fail the hidden tests), **novel** (not
a duplicate of an archived task), and **frontier-relevant** (hard enough to
matter). See `CONTRIBUTING.md` for what to build and how submissions are scored.

## Chain-safety note

The chain layer is fail-closed by construction: writes default to **off**, there
is a dry-run tier, four independent gates guard any live extrinsic, and
commit-reveal state is detected in a way that fails closed. Nothing here writes
to a public chain without explicit, multi-gate authorization.
