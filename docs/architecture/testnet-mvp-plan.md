# Testnet MVP Plan

## North Star

Build a Bittensor testnet subnet where miners propose verifiable software-task
packages and validators score the packages for marginal value to the Dolores
archive.

The testnet MVP should prove the loop, not the economics.

## What Ports From Dolores Autocurricula

- Task package schema and canonical task hashes.
- Generator v3 task families.
- Docker/generated-mode verification.
- Safety scanner and fail-closed execution policy.
- Public/hidden test separation.
- Wrong-solution probes.
- Solver-panel scoring and clean solve-rate logic.
- DuckDB archive and lineage model.
- HF/JSONL/verifier export concepts.

## What The Subnet Adds

- Miner/validator process boundaries.
- Task submission messages and content hashes.
- Per-miner scoring aggregation.
- Weight vector generation.
- Testnet wallet/subtensor integration.
- Optional commit-reveal and held-out scoring policy later.
- Public contributor leaderboard.

## Minimal Demo Loop

1. Miner creates or selects a Dolores v3 task package.
2. Miner submits a content hash plus task payload reference.
3. Validator fetches/loads the task package.
4. Validator runs cheap gates:
   - schema valid;
   - safety clean;
   - reference passes public and hidden tests in Docker;
   - probes are caught;
   - duplicate gate passes.
5. Validator assigns a quality score.
6. Validator writes an archive row and emits a miner weight.
7. CLI/dashboard shows accepted tasks and miner ranking.

## Scoring V0

Use a simple staged score for testnet:

- Hard gate failure: `score = 0`.
- Otherwise:
  - verifier quality: 0.35;
  - novelty/diversity: 0.25;
  - frontier signal: 0.25;
  - metadata clarity: 0.15.

For the first testnet demo, frontier signal can be a mock or cached panel
result. Do not make paid inference a demo blocker.

## Fable Research Decisions To Preserve

- Reward frontier-calibrated tasks, not task volume.
- Keep one miner role in v0: task proposer.
- Validators should own held-out scoring.
- Hidden tests should not be fully controlled by miners long term.
- Archive value is the durable asset.
- Mainnet should wait until testnet proves deterministic validation and real
  contributor interest.

## Build Order

1. Offline local loop with fake miners and deterministic scoring.
2. Dolores backend bridge for generation and verification.
3. Testnet wallet/subtensor preflight.
4. Bittensor miner/validator message loop.
5. Weight setting and archive writeback.
6. Minimal dashboard or CLI report.

## Demo Definition Of Done

- Two miner submissions.
- One accepted task and one rejected or low-scored task.
- Validator records why.
- Weights/rankings reflect the score difference.
- The accepted task is visible in an archive file or DuckDB row.
- No provider keys are required for the demo.

## Local Python Environment Note

The subnet repo is intentionally thin. Bridge-backed commands should run inside
the Dolores Autocurricula `.venv` until this repo has its own locked
environment, because the Dolores backend needs dependencies such as PyYAML,
Pydantic, Hypothesis, pytest, DuckDB, and PyArrow.
