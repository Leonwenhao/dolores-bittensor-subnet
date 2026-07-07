# Fable Testnet Development Plan — Dolores Bittensor Subnet

Date: 2026-07-07. Author: Fable (lead architect), with Opus subagent verification of
the Dolores backend API surface and Bittensor testnet mechanics, and a four-reviewer
Opus panel (Bittensor mechanics, Dolores integration, architecture/gates,
demo/readiness) whose findings are reconciled into this text (all 2026-07-07).
Status: authoritative build plan. Supersedes `docs/architecture/testnet-mvp-plan.md`
(kept as historical context).

---

## Executive Summary

**Recommended target scope: Option 3 — a staged plan that starts lean and compounds
toward the ambitious testnet subnet.** Every milestone boundary leaves a demoable
product. The lean core (offline epoch with real Docker verification, real gates, real
scoring, real weights math) is the hackerhouse floor; the ambitious layers (live
axon/dendrite wire protocol, local chain rehearsal, public testnet epoch with real
`set_weights` receipts) compound on top without rework because the epoch engine is
mode-agnostic from day one.

Why staged, not lean-only or ambitious-only:

1. **The single hard external dependency — test TAO — is Discord-gated with
   unbounded latency** (the testnet faucet is disabled in mid-2026; test TAO is
   requested manually in the Bittensor Discord). A plan whose demo depends on chain
   access is a plan that can be zeroed by a faucet queue. The chain must be the
   *top* of the demo, never its foundation.
2. **The expensive, differentiated machinery already exists in Dolores
   Autocurricula** (deterministic Docker verification, safety scanner, probes,
   dedup, mock solver panel, DuckDB archive). The lean loop is therefore cheap to
   reach and already impressive — real containerized verification of adversarial
   submissions is a better demo than a toy synapse ping.
3. **The ambitious pieces are individually small once the core is right**: a
   `bt.Synapse` subclass, a metagraph sync, one `set_weights` call. The staged plan
   sequences them behind strict gates instead of betting the demo on them.

**Milestone count: 8 (M0–M7).** Two are optional-but-recommended stretch gates
(M5 localnet, commit-reveal inside M6).

**Critical path:** M0 → M1 → M2 → M3 → M4 → M6 → M7, with M5 (local chain) as a
parallel de-risking branch after M4. The demo is safe from M3 onward: M3 = offline
demo, M5 = local-chain demo, M6 = public testnet demo. Each is a strict superset.

**Human-blocking tasks (Leon):** H1 Docker Desktop running + host tooling (`jq`) +
macOS firewall approval for axon ports; H2 create testnet-only coldkey/hotkeys
(complete); H3 receive test TAO (complete: 10.0 TAO free on `--network test`,
0.0 staked); H4 approve the live testnet subnet-creation burn after a fresh
`btcli subnet burn-cost --network test` read and the 14,400-block (~2-day)
create-reuse warning; H5 decide repo/subnet public naming; H6 confirm each chain
extrinsic before it is sent; H7 (optional, default NO) any paid-panel decision;
H8 create the GitHub remote and provide authenticated push.

**Current post-M7 task discipline:** M3 offline and M4 local wire demos are the
hackerhouse floor. H3 no longer blocks M6 funding, but public testnet remains
gated on real chain-client code plus STOP-LEON approval for every create,
register, stake, and weight-setting extrinsic.

---

## 1. Product Definition

### 1.1 What the finished testnet product is

A working Bittensor **testnet** subnet implementing a *verifiable software-task
proposer market*, ported directly from the Fable subnet research (Stage 1) onto the
existing Dolores Autocurricula backend:

- **Miners** propose self-contained Dolores task packages (prompt, starter files,
  reference solution, public tests, hidden tests, constraints, descriptors,
  lineage).
- **Validators** pull submissions each epoch over the Bittensor axon/dendrite wire
  protocol, run every package through the full Dolores validation pipeline
  (safety scan → fail-closed Docker verification → wrong-solution probes → mock
  solver panel → duplicate/novelty check → staged score), write every result to a
  subnet archive (DuckDB + JSONL evidence log), and convert per-miner scores into a
  normalized weight vector.
- **Weights** are set on the Bittensor testnet chain via `subtensor.set_weights`
  (with a deterministic mock-weights fallback artifact when chain conditions block
  the extrinsic), so miner emissions-share on testnet reflects marginal validated
  archive value, not volume.

"Finished" for this plan means: a coding agent following this document produces a
repo where one command runs a full offline epoch, one command runs a live
miner+validator pair against the public Bittensor testnet on our own netuid, at
least one full testnet epoch has been executed with preserved receipts, and the
demo script in §7 runs end-to-end from a clean checkout.

### 1.2 What the miner does (v0)

One role: **task proposer**. The v0 miner:

1. Generates candidate task packages from the Dolores v3 seeded family generator
   (`dolores.proposer.families.propose_family`) — or loads pre-authored package
   directories from a local queue directory (`miner_queue/`).
2. Self-checks each package locally before offering it: schema validation plus
   `PytestRunner().verify(task)` called **directly** (the AST safety scan runs
   inside `verify`; no policy layer involved — the miner executes only its own
   generated content, so no `allow_unsafe_local` flag is needed). Never route the
   self-check through `run_task_pipeline`; if that is ever done it must use
   `mode="fixture"` — `mode="generated"` on the local backend raises unless
   `allow_unsafe_local=True`.
3. Serves a Bittensor axon. When the validator's `TaskSubmissionSynapse` request
   arrives for epoch E, it responds with up to `quota` submissions: each is the
   canonical task-package JSON inline plus its `stable_hash`.
4. In offline modes, the same miner logic runs as an in-process object (no axon).

The miner is intentionally thin. All authoring intelligence lives in Dolores;
adversarial miner variants used in testing are configuration, not new roles.

### 1.3 What the validator does (v0)

The validator is the product. Each epoch it:

1. Determines the active miner set (metagraph in chain modes; a static roster in
   offline modes).
2. Queries every miner axon with `TaskSubmissionSynapse(epoch_id, quota,
   schema_version)` and collects responses (bounded size, bounded timeout).
3. Runs **subnet pre-gates** per submission (cheap, deterministic, no execution):
   schema-version match, payload size ≤ limits, valid `TaskPackage` parse,
   recomputed `stable_hash` equals the claimed hash, per-miner quota enforcement,
   per-epoch exact-hash dedup across miners.
4. Runs the **Dolores pipeline** per surviving submission via
   `dolores.pipeline.run_task_pipeline(task_path, db_path, panel_path,
   backend="docker", mode="generated", allow_docker_fallback=False)` — safety scan,
   fail-closed Docker reference verification, wrong-solution probes, mock solver
   panel, duplicate report against the subnet archive DB, staged `TaskScore`.
5. Maps `TaskScore`s to per-miner epoch scores (top-k, gates-to-zero; §9.3), folds
   them into a persisted per-miner EMA, and normalizes into a weight vector.
6. Sets weights on chain (`subtensor.set_weights`) in chain modes, or writes the
   deterministic `weights_epoch_<E>.json` artifact in offline/fallback modes.
7. Writes everything to the subnet archive: DuckDB rows (tasks, task files,
   verification runs, solver runs, scores, lineage via `ArchiveDB`), plus an
   append-only `submissions.jsonl` evidence log (who submitted what, which gate
   failed, timing, receipts).
8. Emits a human-readable epoch report (`scripts/report.py`) — the leaderboard.

### 1.4 The task artifact

The artifact is the existing **Dolores `TaskPackage`** (pydantic `StrictModel`,
`dolores.schemas.task`), unchanged: `task_id`, `title`, `domain`, `prompt`,
`starter_files`, `reference_files`, `public_tests`, `hidden_tests`, `constraints`
(timeout/memory), `descriptors` (task_type, concepts, difficulty), `lineage`,
`metadata`. Canonical identity is `TaskPackage.stable_hash()` (sha256 over the
content dict minus `metadata.created_at`). On the wire it travels as the canonical
JSON dict inline in the synapse response; on disk it is a `<task_id>/task.yaml`
directory, exactly as Dolores writes it.

**Deliberate v0 simplification vs. the research spec:** miners submit full hidden
tests (not a hidden-test generator), and there is no environment-spec Dockerfile
per task (all tasks run in the shared pinned `dolores-verifier-pytest:0.1.0`
image). Both are recorded as post-testnet upgrades (§1.7). The research doc's
held-out discipline is partially preserved anyway: hidden tests are never included
in public exports (public-safe export policy, §8.3), and validator-side probes
(`reference_return_none`, PROBE-DROP stripping, starter probe) are evaluation
signal the miner does not control.

### 1.5 What is stored locally / in the archive

Per validator, under `work/subnet_archive/` (configurable):

- `archive.duckdb` — the Dolores `ArchiveDB` schema (tables: `tasks`, `task_files`,
  `verification_runs`, `solver_runs`, `scores`, `lineage`, `exports`, `metadata`),
  one row-set per processed submission, including rejected ones (rejection reasons
  live in `verification_runs.status` + `scores.lifecycle_status` + safety findings).
- `submissions.jsonl` — append-only evidence log: one record per received
  submission `{epoch_id, miner_hotkey, miner_uid, task_id, package_hash, pre_gate
  results, pipeline status, aggregate_score, wall_ms, mode, receipt refs}`.
- `epochs/epoch_<E>/` — `weights_epoch_<E>.json` with a **pinned schema**:
  `{epoch_id, task_values (runtime-cost-free, §2.6), epoch_scores, ema_state,
  weights, degraded: bool, weight_result: {mode: "chain"|"fallback",
  receipt: {...}|null, reason: str|null}, timing: {...}}`. The top-level `timing`
  object is the **only** place any wall-clock value (durations, timestamps, block
  times) may appear anywhere in the artifact — determinism gates compare the file
  after `del(.timing)` and a schema test enforces the invariant. Plus
  `report_epoch_<E>.md`.
- `miner_state.json` — persisted per-hotkey EMA + strike counts.
- `exports/` — Tier-0-style public-safe exports (JSONL/HF via
  `dolores.archive.export`, accepted tasks only, hidden tests stripped; §8.3).

### 1.6 What is shown in the demo

The §7 demo shows: two live miners (one honest, one adversarial) answering a real
validator query; the validator rejecting the adversarial package with a named gate
(safety finding or failed reference in Docker, `containerized=true` in the log);
the honest package accepted with a component-level score; the weight vector
shifting accordingly; the archive row and leaderboard as proof; and — if testnet is
live — the on-chain weight extrinsic and metagraph readback on our test netuid.

### 1.7 Deliberately out of scope until after testnet

- Mainnet registration, real TAO, emissions economics, dTAO strategy.
- Hidden-test **generators** / validator-synthesized held-out tests (research §3.2).
- Per-task `environment_spec` Dockerfiles; multi-language tasks.
- Real paid solver panel in the validator loop (Fireworks); frontier scores in v0
  come from the deterministic mock panel and are labeled as such.
- Commit-reveal weights as a *requirement* (off by default on new subnets; wired as
  a stretch inside M6 only if time allows — the SDK handles it transparently when
  the hyperparam is enabled, so no code depends on it).
- Multiple independent third-party validators; validator consensus tuning; Yuma
  divergence analysis (we run 1 validator + a determinism-replica check instead).
- S3/external package storage (packages travel inline; size-capped).
- Reputation-gated evaluation queues, coverage dashboards, embedding-based novelty.
- Any change to the Dolores scoring weights or family designs (the v3.1/v4
  generator pass stays in the Dolores repo's own plan; this subnet consumes
  families as-is, defaulting to `parser_roundtrip` + `multi_file_bugfix`).

---

## 2. Architecture

### 2.1 Repo layout to implement

```
dolores-bittensor-subnet/
├── pyproject.toml               # MODIFY: real deps, pytest config, py3.11 pin
├── README.md                    # MODIFY at M7
├── configs/
│   ├── solver_panel.mock.yaml   # NEW: vendored copy of Dolores local mock panel
│   └── testnet.json             # NEW at M6: netuid, network, ss58 addrs (public only)
├── src/dolores_subnet/
│   ├── __init__.py              # KEEP
│   ├── config.py                # MODIFY: mode enum, paths, chain params, limits
│   ├── protocol.py              # MODIFY: wire dataclasses + WirePackage payload
│   ├── synapse.py               # NEW: bt.Synapse subclass (only chain-importing file besides chain.py)
│   ├── packaging.py             # NEW: TaskPackage <-> wire JSON <-> disk dir; hashing; size checks
│   ├── bridge.py                # NEW (absorbs dolores_bridge.py): generation + validation entry points
│   ├── gates.py                 # NEW: subnet pre-gates (schema_version, size, hash match, quota, epoch dedup)
│   ├── scoring.py               # MODIFY: TaskScore -> epoch score -> EMA -> weight vector
│   ├── archive.py               # NEW: subnet archive layout, submissions.jsonl, epoch dirs, miner_state.json
│   ├── epoch.py                 # NEW: mode-agnostic epoch engine (the core object)
│   └── chain.py                 # NEW: subtensor/metagraph/set_weights/receipts; import-guarded
├── neurons/
│   ├── miner.py                 # REWRITE: axon miner + offline in-process mode
│   └── validator.py             # REWRITE: epoch loop driver for all modes
├── scripts/
│   ├── local_epoch.py           # NEW (replaces local_loop.py, which is DELETED)
│   ├── preflight.py             # NEW: environment/readiness checks per mode
│   ├── report.py                # NEW: leaderboard + epoch report from archive
│   └── seed_adversarial.py      # NEW: builds the planted good/bad package fixture set
├── tests/
│   ├── test_protocol.py         # MODIFY
│   ├── test_packaging.py        # NEW
│   ├── test_gates.py            # NEW
│   ├── test_scoring_weights.py  # NEW
│   ├── test_bridge_mock.py      # NEW (local backend, fixture mode — no Docker in CI)
│   ├── test_epoch_offline.py    # NEW (full mock epoch, determinism assertions)
│   └── test_synapse_roundtrip.py# NEW (serialization only; no network)
└── docs/
    ├── architecture/fable-testnet-development-plan.md   # this file
    ├── runbooks/testnet-runbook.md                      # NEW at M6
    ├── hackerhouse/demo-script.md                       # NEW at M7 (from §7)
    └── diary/                                           # NEW: build diary entries per milestone
```

Deletions: `scripts/local_loop.py`, `src/dolores_subnet/dolores_bridge.py` (logic
moves into `bridge.py`), stray `__pycache__` (add to `.gitignore`).

### 2.2 What stays in Dolores Autocurricula vs. the subnet repo

**Dolores Autocurricula owns (unchanged, consumed as a library):** task schema and
hashing; family generator; safety scanner; local/Docker verifier runners and the
fail-closed execution policy; probes; solver panel machinery + MockSolver; frontier
classification and `score_task`; `ArchiveDB` and exports. **The subnet repo must
not fork or re-implement any of this.** If a backend behavior needs changing, the
plan step says "stop and ask Leon" — Dolores changes are out of this plan's scope
except the two explicitly listed in §2.5.

**The subnet repo owns:** everything Bittensor (synapse, axon/dendrite, metagraph,
weights, wallets-by-name, receipts); the epoch engine; wire packaging and size
limits; subnet pre-gates; miner-quota/top-k/EMA aggregation; the subnet archive
layout around `ArchiveDB`; reports; runbooks; the demo.

### 2.3 How the subnet calls the Dolores backend

`bridge.py` is the only module that imports `dolores.*`. Verified entry points
(signatures confirmed against the backend on 2026-07-07):

- **Generation (miner):** `dolores.proposer.families.propose_family(family, count,
  seed, band)` → `list[TaskPackage]`; write to disk with
  `dolores.proposer.templates.write_task_package(task, out_dir)`. Note: `band`
  selects generator combo bands `"core"|"stretch"` — it is **not** a difficulty;
  passing a difficulty string selects zero combos and raises `ValueError`.
  Distinct `seed` per miner yields disjoint task sets (verified against the
  1392-combo parser pool).
- **Validation+scoring (validator):** `dolores.pipeline.run_task_pipeline(
  task_path, db_path, panel_path, backend, mode, allow_unsafe_local=False,
  allow_docker_fallback=False)` → `PipelineResult(status=score.lifecycle_status,
  verification, eval_result, score)`. This single call performs safety scan,
  verification, mock-panel evaluation, duplicate report against `db_path`, scoring,
  and archive writeback. The bridge materializes each wire package to a temp
  directory (`task.yaml`) and passes absolute `db_path` and `panel_path`
  (`configs/solver_panel.mock.yaml` — vendored because Dolores's
  `DEFAULT_PANEL_PATH` is cwd-relative to the Dolores repo).
- **Self-check (miner):** `TaskPackage.load` + `PytestRunner().verify(task)`
  called directly (no pipeline, no policy layer; `scan_task` runs inside
  `verify`). The miner checks its *own* generated package — trusted content,
  local execution acceptable; the validator never uses the local backend.
- **Archive reads (reports/exports):** `dolores.archive.db.ArchiveDB(path)` —
  `list_tasks()`, `stats()`, `show_task()`, `solver_error_breakdown()`.
  **Public exports are the subnet's responsibility to sanitize:** the Dolores
  exporters (`export_jsonl` / `export_hf_dataset`) dump `SELECT * FROM task_files`
  — including `hidden_tests` content verbatim. `archive.py` must therefore build
  every public export from a filtered **copy** of the archive DB (copy file, then
  `DELETE FROM task_files WHERE file_role='hidden_tests'`, then export the copy).
  Calling the exporters on the primary DB and publishing the result leaks the
  held-out signal — a test in M3 asserts no `hidden_tests` row exists in any
  export output.

**Execution-policy mapping (fail-closed, non-negotiable):**

| Context | backend | mode | fallback |
|---|---|---|---|
| Validator, any real epoch (offline/localnet/testnet) | `docker` | `generated` | `allow_docker_fallback=False` |
| Validator unit/CI tests on trusted fixtures | `local` | `fixture` | n/a |
| Miner self-check of own generated packages | `local` | `fixture` | n/a |

Dolores's `validate_execution_policy` enforces exactly this: untrusted/generated
content never executes on the host (verified: `backend="docker"`,
`mode="generated"`, `allow_docker_fallback=False` passes the policy without any
unsafe flag). If Docker is down, verification returns `status="rejected",
executed=False, fallback_reason=<reason>` — the epoch engine must treat that as
**infrastructure failure (submission not penalized, epoch flagged degraded)**,
not as a miner failure. The discriminator must be exact, because a safety
rejection also has `executed=False` and `PipelineResult.status` surfaces both as
`"rejected"`:

- `infra_error` ⟺ `verification.executed is False and
  verification.fallback_reason is not None and not verification.safety_findings`
- safety rejection ⟺ `verification.safety_findings` non-empty
- genuine failed reference ⟺ `status="failed", executed=True, containerized=True`

This three-way distinction is a hard gate in M2. Additionally, because
`run_task_pipeline` archives unconditionally, an infra-errored submission's rows
would poison the miner's future resubmission (the archive duplicate gate would
reject the identical resubmitted package as its own duplicate). `archive.py`
therefore provides `purge_task(task_hash)` — deleting the hash's rows from
`tasks`, `task_files`, `verification_runs`, `solver_runs`, `scores`, `lineage` —
and the bridge calls it whenever it classifies an outcome as `infra_error`, so
resubmission after infrastructure recovery is clean. Unit-tested in M2.

### 2.4 Task submission representation

Wire payload (`protocol.py::WireSubmission`, plain dict-serializable, no bittensor
import):

```json
{
  "schema_version": "dolores-subnet-v0",
  "task_id": "...",
  "package_hash": "<TaskPackage.stable_hash()>",
  "package": { /* TaskPackage.canonical_dict() */ },
  "family": "parser_roundtrip",
  "declared_difficulty": "medium"
}
```

Synapse (`synapse.py::TaskSubmissionSynapse(bt.Synapse)`): request fields filled by
validator — `epoch_id: int`, `quota: int`, `schema_version: str`; response field
filled by miner — `submissions: list[dict]` (each a `WireSubmission` dict).
Limits (enforced by `gates.py`, values in `config.py`): ≤ 200 KB canonical JSON per
package, ≤ 1 MB total response, ≤ `quota` (default 4) submissions per miner per
epoch (excess dropped deterministically: sort by `package_hash` ascending, keep
first `quota`). The validator **recomputes** `stable_hash` from the parsed package;
mismatch → invalid, zero, logged. `TaskSubmission.commitment()` (existing
`protocol.py`) is retained as the canonical hash of the submission envelope and is
what would go on chain via `subtensor.set_commitment` — wired only as a stretch
(§9.1), never a demo dependency.

### 2.5 Required Dolores-side changes (exactly two, both minimal)

1. **None to code.** The audit found no backend code change strictly required.
2. **Operational only:** (a) the verifier Docker image
   `dolores-verifier-pytest:0.1.0` **must be pre-built** from the Dolores repo:
   `cd "$DOLORES" && docker build -f docker/verifier/Dockerfile -t
   dolores-verifier-pytest:0.1.0 .` — do **not** rely on
   `DockerRunner(auto_build=True)`: under a non-editable site-packages install its
   Dockerfile discovery (`__file__`-relative and cwd-relative) cannot find the
   Dockerfile, so auto-build silently fails into the fail-closed path. Setting
   `DOLORES_VERIFIER_DOCKERFILE="$DOLORES/docker/verifier/Dockerfile"` in the
   validator environment is a belt-and-suspenders addition, not a substitute for
   pre-building. (b) After any Dolores source change, re-run `pip install
   --no-deps --force-reinstall "/Users/leonliu/Desktop/Dolores Autocurricula"` in
   the subnet venv (the Dolores repo's own diary documents that editable installs
   are unreliable on this machine). `preflight.py` checks both.

### 2.6 How validation results become miner weights

Pipeline per epoch (all pure functions in `scoring.py`, unit-tested):

1. Per submission: `lifecycle_status != "accepted"` → task value 0. Accepted →
   **task value = `round((aggregate_score − 0.05 × components.runtime_cost) /
   0.95, 6)`**. The subtraction is mandatory, not cosmetic: Dolores's
   `runtime_cost` component is a step function of wall-clock `duration_ms`
   (boundaries at 500 ms / 3000 ms), so the raw `aggregate_score` is **not**
   run-to-run deterministic — a verification straddling a boundary flips the
   score. Removing the runtime_cost term (and renormalizing by its 0.95 weight
   complement) makes task values, epoch scores, and weights a pure function of
   package content + config + archive state. All determinism gates compare these
   derived values, never the raw Dolores `aggregate_score`.
2. Per miner: epoch score = sum of top-k task values over non-`infra_error`
   submissions (k=4 = quota; with quota 4 this is a pure anti-spam cap that
   becomes binding when quota rises).
3. EMA: `ema_new = 0.3 * epoch_score + 0.7 * ema_prev` (α in config; state in
   `miner_state.json`, keyed by hotkey ss58 so UIDs can churn).
   **Infra-error semantics:** `infra_error` submissions are excluded from the
   epoch score (neither credited nor decayed); a miner whose *only* submissions
   this epoch are `infra_error` keeps its EMA unchanged (carried forward, no
   decay). An epoch containing ≥1 `infra_error` sets `degraded=true` in the
   artifact but still completes and still sets weights from the non-infra
   submissions. If *every* submission in the epoch is `infra_error`, skip both
   the EMA update and `set_weights` and write
   `weight_result.reason="epoch_degraded_all_infra"`.
4. Weight vector: normalize over exactly the hotkeys present in **both** the
   current metagraph and `miner_state.json` — deregistered hotkeys are excluded
   from numerator *and* denominator (their EMA state is retained dormant and
   pruned after K=20 epochs unseen, K in config). All-zero → skip `set_weights`,
   `weight_result.reason="all_zero"`.
5. Chain modes: map hotkeys → UIDs via metagraph, call
   `subtensor.set_weights(wallet, netuid, uids, weights,
   version_key=SPEC_VERSION)` (`SPEC_VERSION` an explicit int constant in
   `config.py`; the SDK converts weights to u16 internally and
   `wait_for_inclusion=True` is the v10 default); persist the extrinsic
   hash/block into `weight_result.receipt`. Any failure (rate limit
   `weights_rate_limit=100` blocks, permit, stake threshold) → **mock-weight
   fallback**: the identical vector plus the failure reason is written to
   `weights_epoch_<E>.json` (`weight_result.mode="fallback"`), and the epoch
   still counts as complete for every non-chain gate.

Cross-miner duplicate ordering: submissions are processed in ascending
`package_hash` order globally, so when two miners submit similar tasks the same
one wins deterministically on every validator replica. (Hash-order is arbitrary
but consensus-stable; recorded as a known v0 simplification.)

**Dedup honesty note:** `stable_hash` covers the full content dict *including
`task_id`*, so the cheap in-epoch exact-hash gate catches only byte-identical
resubmissions. A spammer who mutates only `task_id` produces distinct hashes;
those copies each consume a full Docker validation before the archive
`duplicate_report` (prompt/file-content similarity) rejects them at
`duplicate_score ≥ 0.95`. Scoring still collapses spam to ≤1 credited task, but
**validator compute is bounded only by the per-miner quota in v0**, not by
dedup. Semantic pre-gate dedup is a named post-testnet upgrade (§1.7).

### 2.7 Modes: local, mock/test, public testnet

One epoch engine (`epoch.py::run_epoch(cfg, miners, chain)`), two injected
boundaries (miner transport, chain client) plus a config-selected verifier
backend (`cfg.backend`/`cfg.pipeline_mode` strings passed through to
`run_task_pipeline` — no third injection seam exists or should be built):

| Mode (`DOLORES_SUBNET_MODE`) | Miner transport | Verification | Panel | Chain | Used for |
|---|---|---|---|---|---|
| `mock` | in-process objects | `local` + `fixture` | mock | none (weights file) | CI, unit tests, fast dev |
| `offline` | in-process objects | `docker` + `generated`, fail-closed | mock | none (weights file) | M3 gate, offline demo |
| `wire` | axon/dendrite on localhost | `docker` + `generated` | mock | none (weights file) | M4 gate |
| `localnet` | axon/dendrite | `docker` + `generated` | mock | local subtensor (`ws://127.0.0.1:9944`) | M5 rehearsal |
| `testnet` | axon/dendrite | `docker` + `generated` | mock | `--network test` (`wss://test.finney.opentensor.ai:443`) | M6 |

**Import discipline (enforced, CI-tested):** `bittensor` imports live *inside*
`SubtensorChain` methods (and `synapse.py`) only. `NullChain`, the chain
`Protocol` type, and every type hint reachable from `epoch.py` must be
importable with bittensor absent; `neurons/miner.py`/`validator.py` import
`synapse`/`SubtensorChain` lazily inside the wire/chain code paths. The §10 CI
test imports `epoch`, instantiates `NullChain`, and runs a mock epoch with
bittensor uninstalled/blocked to prove it.

**Mainnet guard (code-level, non-negotiable):** the SDK and btcli both default
to `finney` (mainnet) when no network is given. `config.py` resolves the network
strictly from `DOLORES_SUBNET_MODE` and **hard-fails if the resolved endpoint is
finney/mainnet or unset** — the allowlist is exactly `test`,
`ws://127.0.0.1:9944`, `ws://127.0.0.1:9945`. `chain.py` never calls
`bt.subtensor()` without an explicit `network=` argument, and
`preflight.py --mode localnet|testnet` re-asserts the allowlist. Human vigilance
(H6) is the second layer, not the only one.

---

## 3. Milestones

Conventions for every milestone: work happens on branch `m<N>-<slug>`; done means
all gate commands pass **from a clean shell** with only documented env vars; the
agent appends a build-diary entry `docs/diary/<date>-m<N>.md` (what changed, gate
transcript, deviations); vague statuses are prohibited — a gate either passes with
the exact expected output or the milestone is open. `$DOLORES` abbreviates
`/Users/leonliu/Desktop/Dolores Autocurricula` and `$SUBNET` this repo; commands
run from `$SUBNET`.

### M0 — Environment, dependency lock, preflight

**Objective:** a dedicated, reproducible subnet environment in which both `dolores`
and `bittensor` import cleanly, plus a preflight script that makes every later
gate checkable.

**Files:** `pyproject.toml`, `src/dolores_subnet/config.py` (MODIFY: mode enum,
network allowlist + mainnet hard-fail, paths, size/quota limits, EMA α,
`SPEC_VERSION` — the single source for every constant later gates read),
`configs/solver_panel.mock.yaml`, `scripts/preflight.py`, `.gitignore` (add
`__pycache__/`, `work/`, `.venv/`, `wallets/`), delete stray `.pyc` dirs from git.

**Implementation details:**
- Python 3.11 venv: `python3.11 -m venv .venv` (same interpreter line as Dolores).
- `pyproject.toml` dependencies: `bittensor>=10.5,<11`, `pydantic>=2.7`,
  `PyYAML>=6.0`; extras: `dev = [pytest>=8, ruff>=0.6]`. Dolores is installed as a
  local non-editable path dep, **not** listed in pyproject (machine-specific
  path): `.venv/bin/pip install "$DOLORES"` then `.venv/bin/pip install -e ".[dev]"`.
- Vendor `configs/solver_panel.mock.yaml` = copy of
  `$DOLORES/examples/configs/solver_panel.local.yaml` (3 mock solvers
  weak/mid/strong, `strategy: difficulty_profile`).
- `scripts/preflight.py --mode {mock,offline,wire,localnet,testnet}` checks, in
  order, printing `PASS/FAIL/SKIP <check>: <detail>` and exiting non-zero on any
  FAIL for the requested mode: python version; `import dolores` +
  `dolores.__version__`; `import bittensor` + version (SKIP in mock/offline);
  `pip check` clean; panel file exists and parses via
  `dolores.solvers.base.load_panel`; host tooling — `jq` present (FAIL in
  offline+ with `brew install jq` hint); docker CLI + daemon (SKIP in mock);
  image `dolores-verifier-pytest:0.1.0` present (offer the exact build command
  if not); Dolores-install freshness warning (compare `git -C $DOLORES log -1
  --format=%ct` vs. install time); ports 8091/8092 bindable + a NOTE that the
  first axon bind triggers the macOS firewall prompt (wire+); wallet files exist
  for `--wallet-name/--wallet-hotkey` (wire/localnet/testnet; existence check
  via `bittensor_wallet`, never reads key material); network allowlist assertion
  (localnet/testnet — resolved endpoint must not be finney); chain reachability
  (localnet/testnet: connect + `subtensor.block`).
- Migrate tests from `unittest` discovery to pytest (`[tool.pytest.ini_options]
  testpaths=["tests"] pythonpath=["src"]`).

**Commands / expected outputs:**
```
.venv/bin/pip check                      # -> "No broken requirements found."
.venv/bin/python -c "import dolores, bittensor; \
  assert bittensor.__version__.startswith('10.'), bittensor.__version__; \
  print(dolores.__version__, bittensor.__version__)"
                                         # -> prints versions, exit 0
.venv/bin/python scripts/preflight.py --mode mock     # -> all PASS, exit 0
.venv/bin/python scripts/preflight.py --mode offline  # -> all PASS (docker+image), exit 0
.venv/bin/pytest -q                      # -> "N passed", zero failures/errors,
                                         #    N = the pre-migration collected count
.venv/bin/ruff check .                   # -> "All checks passed!"
```

**Blockers / failure modes:** `pip check` conflicts between bittensor 10.5 and
Dolores deps (likeliest: pydantic/pyarrow pins) — resolution order: try
`bittensor>=10,<10.5`; if still conflicting, isolate by moving the miner/validator
chain layer to subprocess calls into a second venv (**stop and ask Leon before
choosing this fork**). Docker Desktop not running is H1, FAIL with instruction, not
a code problem.

**Done when:** all five commands above pass from a clean shell; diary entry exists.

### M1 — Packaging and wire format

**Objective:** lossless, size-bounded, hash-stable conversion between Dolores task
packages and the wire representation.

**Files:** `src/dolores_subnet/packaging.py`, `protocol.py`, `tests/test_packaging.py`,
`tests/test_protocol.py`.

**Implementation details:** `packaging.py` exposes
`to_wire(task: TaskPackage) -> dict` (canonical dict + hash + family from
descriptors), `from_wire(payload: dict) -> TaskPackage`
(`TaskPackage.model_validate`; raises `WireError` with a machine-readable reason
code on any failure), `materialize(task, root: Path) -> Path` (writes
`<root>/<task_id>/task.yaml` exactly like `write_task_package`),
`wire_size_ok(payload) -> bool` (≤ 200 KB canonical JSON). `protocol.py` keeps
`TaskSubmission`/`ValidationScore`/`canonical_json` and adds `WireSubmission` with
`schema_version` (`SCHEMA_VERSION = "dolores-subnet-v0"`).

**Commands / gates:**
```
.venv/bin/pytest -q tests/test_packaging.py tests/test_protocol.py
```
Tests that must exist and pass: (1) round-trip — `propose_family("parser_roundtrip",
count=3, seed=0)` → `to_wire` → `from_wire` → `stable_hash` identical to the
original for all 3; (2) disk parity — `materialize` then `TaskPackage.load` gives
the same `stable_hash`; (3) tamper detection — mutate one byte of the wire prompt →
recomputed hash ≠ claimed hash; (4) size gate — a synthetic >200 KB package is
refused; (5) malformed payloads (missing field, absolute file path, empty
reference) each raise `WireError` with distinct reason codes, never a bare
pydantic traceback.

**Failure modes that block:** any hash mismatch between subnet-side and
Dolores-side hashing (would poison every later gate); YAML/JSON canonicalization
drift (e.g., unicode ensure_ascii differences).

**Done when:** the test file passes and a 5-line determinism script (hash the same
generated task twice in two separate processes) prints identical hashes.

### M2 — Validator core: bridge, gates, real validation

**Objective:** a validator that takes wire submissions and produces fully-audited
`ValidationScore`s using the real Dolores pipeline, with the fail-closed policy and
infra-vs-miner failure distinction correct.

**Files:** `bridge.py`, `gates.py`, `scoring.py` (score extraction only),
`archive.py` (submissions.jsonl + archive dir init), `scripts/seed_adversarial.py`,
`tests/test_gates.py`, `tests/test_bridge_mock.py`.

**Implementation details:**
- `bridge.py::validate_submission(wire: dict, cfg) -> SubmissionOutcome` — runs
  `gates.py` pre-gates; on pass, materializes to a temp dir and calls
  `run_task_pipeline(task_dir, cfg.archive_db, cfg.panel_path,
  backend=cfg.backend, mode=cfg.pipeline_mode, allow_docker_fallback=False)`;
  maps `PipelineResult` → `SubmissionOutcome{status: accepted|review|rejected|
  invalid|infra_error, task_value: float, gates: dict[str,bool], components:
  dict[str,float], verification_summary, reason}`.
- **Infra-error rule (hard requirement):** classification uses the exact §2.3
  discriminator — `infra_error` ⟺ `executed is False and fallback_reason is not
  None and not safety_findings`; safety rejection ⟺ `safety_findings` non-empty
  (miner-attributable `rejected`, strike logged). On `infra_error` the bridge
  calls `archive.purge_task(task_hash)` so the archived rows cannot poison a
  future resubmission via the duplicate gate. Unit tests cover: (a) both
  classifications via monkeypatched Docker availability, (b) purge-then-resubmit
  succeeding, (c) a safety rejection NOT being purged.
- `gates.py` returns an ordered dict of named gate results:
  `schema_version, size, parse, hash_match, quota, epoch_duplicate`; first failure
  short-circuits (cheap-first ordering as in research §4).
- `scripts/seed_adversarial.py` builds `tests/fixtures/planted/` once, using real
  Dolores generation plus controlled corruption. **Each case is written to a
  stable persona-named directory** — `tests/fixtures/planted/<case>/task.yaml`
  (e.g. `planted/good_parser/task.yaml`) with wire payloads under
  `planted/wire/<case>.json` — and the script asserts those exact paths exist
  (the demo `cat`s them). The fixture set is **committed to git** so a clean
  clone can run the demo. Cases: `good_parser` (untouched v3 task),
  `bad_no_reference` (reference_files emptied → schema invalid),
  `bad_reference_fails` (reference edited to break a hidden test),
  `bad_unsafe` (inject `import subprocess` into a reference file),
  `bad_duplicate` (byte-identical copy of `good_parser` under a new task_id),
  `bad_hash_lie` (valid package, wrong claimed hash),
  `bad_oversize` (padded prompt > 200 KB).
- v0 `neurons/validator.py --mode offline --submissions <dir>` CLI: validate a
  directory of wire-submission JSON files and print one `ValidationScore` line each
  — the smallest end-to-end surface, used by the M2 gate.

**Commands / gates:**
```
.venv/bin/python scripts/seed_adversarial.py --out tests/fixtures/planted
.venv/bin/pytest -q tests/test_gates.py tests/test_bridge_mock.py   # local/fixture path
.venv/bin/python neurons/validator.py --mode offline --submissions tests/fixtures/planted/wire
```
Expected from the last command (docker/generated path, exact statuses):
`good_parser → accepted (task_value > 0)`; `bad_no_reference → invalid:parse`;
`bad_reference_fails → rejected (verification failed, containerized=true)`;
`bad_unsafe → rejected (safety finding named, executed=false)`;
`bad_duplicate → rejected` exactly (byte-identical content ⇒ `duplicate_score ≥
0.95` ⇒ unconditional reject; the `review` branch is unreachable for an exact
copy — treat a `review` here as a gate FAILURE); `bad_hash_lie →
invalid:hash_match`; `bad_oversize → invalid:size`. Determinism: running the
command twice against fresh archive DBs produces byte-identical outcome JSON
under the **canonical normalization**: compare derived `task_value` and
`components` with `runtime_cost` excluded, and strip every field under the
artifact's `timing` object plus `created_at`/`duration_ms`/`*_stdout`/`*_stderr`
raw fields — the same normalization function is used by the M3 gate
(`scoring.py::normalize_for_determinism`, unit-tested).

**Failure modes that block:** any planted-bad accepted; any planted-good rejected;
Docker fallback silently producing `containerized=false` accepted rows (must be
impossible — assert `verification.containerized or outcome.status in
{rejected, review, invalid, infra_error}` on every outcome in docker mode);
nondeterministic task_value across runs under the canonical normalization.

**Done when:** the exact expected statuses above are produced twice in a row and
`submissions.jsonl` contains one complete record per planted package.

### M3 — Offline epoch simulation (demo floor)

**Objective:** a full multi-miner epoch offline: generation → submission →
validation → scores → EMA → weight artifact → archive → leaderboard. This is the
guaranteed hackerhouse demo.

**Files:** `epoch.py`, `scoring.py` (top-k/EMA/normalize), `archive.py` (epoch
dirs, miner_state), `neurons/miner.py` (in-process `OfflineMiner` with
`honest|duplicate_spammer|invalid|lazy` personas), `scripts/local_epoch.py`,
`scripts/report.py`, `tests/test_epoch_offline.py`, `tests/test_scoring_weights.py`;
delete `scripts/local_loop.py`.

**Implementation details:** `run_epoch` steps: roster → collect (transport
injected) → global pre-gates (incl. cross-miner exact-hash dedup, ascending-hash
ordering) → validate each (bridge) → per-miner top-k epoch scores → EMA update →
weight vector → chain step (none in offline: write artifact) → archive writes →
report. Personas: `honest` submits `propose_family(seed=miner_index)` tasks;
`duplicate_spammer` submits 4 copies of one task under different task_ids;
`invalid` submits `bad_reference_fails`-style packages; `lazy` submits fewer than
quota. `scripts/local_epoch.py --mode offline --miners honest,honest,duplicate_spammer,invalid
--quota 2 --epoch 1 --work work/m3_demo` orchestrates one epoch in-process
(`--quota` overrides the config default of 4; the gate runs at quota 2 to keep
the double-run affordable, the demo runs quota 1 — see §7.2).
`scripts/report.py --work work/m3_demo --epoch 1` renders the leaderboard
(miner, submitted, accepted, rejected+why, epoch score, EMA, weight) as
markdown. `report.py --replay-check <epoch>` re-derives the weight vector from
`submissions.jsonl` + config and asserts equality. M3 also implements the
public-safe export path (§2.3) with its no-hidden-tests-in-output test.

**Timing reality (from the integration audit):** every non-pre-gated package
costs ~6 container executions (reference verify + 2–3 probes + 3 mock-panel
solvers) at ~10–30 s each — roughly 1–3 min per package. The duplicate
spammer's copies are NOT collapsed by the cheap pre-gate (distinct task_ids ⇒
distinct hashes, §2.6), so they all reach Docker. Budget accordingly: the
quota-2, 4-miner gate run (≤ 8 packages) must complete in ≤ 25 min; the quota-1
3-miner demo profile (≤ 3 packages) in ≤ 5 min. Measure both in the diary.

**Commands / gates:**
```
.venv/bin/pytest -q tests/test_epoch_offline.py tests/test_scoring_weights.py
.venv/bin/python scripts/local_epoch.py --mode offline \
  --miners honest,honest,duplicate_spammer,invalid --quota 2 --epoch 1 --work work/m3_a
.venv/bin/python scripts/local_epoch.py --mode offline \
  --miners honest,honest,duplicate_spammer,invalid --quota 2 --epoch 1 --work work/m3_b
diff <(jq -S 'del(.timing)' work/m3_a/epochs/epoch_1/weights_epoch_1.json) \
     <(jq -S 'del(.timing)' work/m3_b/epochs/epoch_1/weights_epoch_1.json)   # -> empty
# (valid because the artifact schema confines ALL volatile values to .timing — §1.5;
#  a schema test enforces this, and task_values are runtime-cost-free — §2.6)
.venv/bin/python scripts/report.py --work work/m3_a --epoch 1
.venv/bin/python scripts/report.py --work work/m3_a --epoch 1 --replay-check 1  # -> "REPLAY OK"
grep -rn 'local_loop\|dolores_bridge' README.md scripts/ src/ neurons/ ; test $? -eq 1
# -> no matches (deleted modules leave no stale references)
```
**Satisfaction requirements:** both honest miners' weights strictly greater than
spammer and invalid miner weights; spammer's duplicates collapse (≤ 1 non-rejected
duplicate-family task credited); invalid miner weight = 0; the diff gate is empty
(byte-identical weight artifacts across independent runs after `del(.timing)` —
the determinism stop/go from research Stage 0); archive DB `stats()` counts equal
`submissions.jsonl` line counts; report renders and `--replay-check` passes; the
stale-reference grep is empty; the export test proves no `hidden_tests` content
in any export output. Runtime budget: per the timing-reality note (quota-2 gate
run ≤ 25 min; measured times recorded in the diary).

**Failure modes that block:** honest ≤ adversarial in any run; weight artifacts
differ across runs; DuckDB write contention (must not parallelize pipeline calls —
sequential by design in v0).

**Done when:** all gates above pass and the diary entry includes the leaderboard
output verbatim.

### M4 — Bittensor wire integration (no chain)

**Objective:** the same epoch over real axon/dendrite transport between separate
processes on localhost, with chain absent.

**Files:** `synapse.py`, `chain.py` (wallet loading + `NullChain` stub),
`neurons/miner.py` (axon serving path), `neurons/validator.py` (dendrite collect
path), `tests/test_synapse_roundtrip.py`.

**Implementation details:** `TaskSubmissionSynapse(bt.Synapse)` with the §2.4
fields; miner `axon.attach(forward_fn=handle_submission_request,
blacklist_fn=allow_all_in_wire_mode)` (the axon's default verify is
signature+nonce only — no metagraph needed, so wire mode genuinely runs
chain-free). In `wire` mode the validator queries a static endpoint list that
**must include each miner's hotkey ss58** — dendrite targets are `AxonInfo`
objects keyed by hotkey, not bare sockets: `--miner-endpoints
127.0.0.1:8091:<miner-0 ss58>,127.0.0.1:8092:<miner-1 ss58>` → construct
`bt.AxonInfo(ip=..., port=..., hotkey=<ss58>, ...)` per entry, and
`submissions.jsonl` records the hotkey **from the constructed AxonInfo** (never
self-reported by the response). Leon supplies the two ss58s from H2 (`btcli
wallet list` prints them). Wallets: `--wallet.name dolores-test --wallet.hotkey
miner-0|validator`; dendrite timeout 120 s; response size checked before parse.
The first port bind triggers the macOS firewall prompt — Leon must approve it
(H1) or the dendrite will hang. Failure of one miner (timeout/refused) must not
abort the epoch — that miner scores 0 for the epoch with `reason="unreachable"`
(distinct from infra_error).

**Commands / gates (three terminals or `run_in_background`):**
```
.venv/bin/python neurons/miner.py --mode wire --persona honest --port 8091 \
  --wallet.name dolores-test --wallet.hotkey miner-0
.venv/bin/python neurons/miner.py --mode wire --persona duplicate_spammer --port 8092 \
  --wallet.name dolores-test --wallet.hotkey miner-1
.venv/bin/python neurons/validator.py --mode wire \
  --miner-endpoints 127.0.0.1:8091:<ss58-0>,127.0.0.1:8092:<ss58-1> \
  --epoch 1 --work work/m4 --wallet.name dolores-test --wallet.hotkey validator
.venv/bin/python scripts/report.py --work work/m4 --epoch 1
```
**Satisfaction requirements:** validator collects from both miners over HTTP;
`submissions.jsonl` records each miner's hotkey ss58 from the constructed
AxonInfo (signed transport); outcomes match the M3 offline result for identical
personas/seeds (same statuses and, under the canonical normalization, same task
values). **Kill test (exact procedure):** stop the miner-1 process entirely,
*then* run the validator — the epoch must complete with miner-1 recorded as
`reason="unreachable"`, zero submissions, distinct from `infra_error`.
`tests/test_synapse_roundtrip.py` proves synapse serialize→deserialize preserves
a max-size submission list.

**Failure modes that block:** synapse payload truncation at our 1 MB budget
(if the axon transport rejects 1 MB responses, lower the per-package cap and
document the measured ceiling — measure, don't guess); wallet-file errors
(stop and hand to Leon, never generate keys for him inside the agent run —
existence is preflight-checked).

**Done when:** the four commands above produce the described artifacts and the
mid-epoch kill test passes.

### M5 — Local chain rehearsal (recommended stretch; parallel to H3 wait)

**Objective:** rehearse every chain interaction (create subnet, register neurons,
stake, metagraph, set_weights, read-back) against a local subtensor, removing all
faucet risk from first contact with real chain mechanics.

**Files:** `chain.py` (real `SubtensorChain`: connect, metagraph sync,
hotkey→UID map, `set_weights`, receipt capture), `docs/runbooks/testnet-runbook.md`
(drafted here, finalized in M6).

**Implementation details / commands:**
```
docker run -d --name local_chain -p 9944:9944 -p 9945:9945 \
  ghcr.io/opentensor/subtensor-localnet:devnet-ready
.venv/bin/python scripts/preflight.py --mode localnet
btcli subnet create --network ws://127.0.0.1:9944 --wallet.name dolores-test   # Leon runs (H6)
btcli subnets start --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet.name dolores-test          # REQUIRED: new subnets are inactive until started
btcli subnet register --netuid <N> --network ws://127.0.0.1:9944 \
  --wallet.name dolores-test --wallet.hotkey validator                          # + miner-0, miner-1
btcli stake add --netuid <N> --network ws://127.0.0.1:9944 --wallet.name dolores-test \
  --wallet.hotkey validator --amount <enough per localnet defaults>
# WAIT ≥ 1 tempo after staking, then confirm the permit BEFORE the weight epoch:
.venv/bin/python -c "import bittensor as bt; m = bt.metagraph(netuid=<N>, \
  network='ws://127.0.0.1:9944'); print(dict(zip(m.hotkeys, m.validator_permit)))"
.venv/bin/python neurons/miner.py --mode localnet --persona honest --netuid <N> \
  --axon.external_ip 127.0.0.1 ...
.venv/bin/python neurons/validator.py --mode localnet --netuid <N> --epoch 1 --work work/m5 ...
btcli subnet metagraph --netuid <N> --network ws://127.0.0.1:9944
```
Validator permits are assigned during a subnet epoch after stake lands — a
freshly staked validator has **no permit until at least one tempo elapses**, and
`set_weights` (non-self weights) fails without one. The wait+confirm step above
is therefore mandatory, and the same sequence applies on testnet (M6).

In `localnet`/`testnet` modes the validator discovers miners from the metagraph
(axon IPs served on-chain via `axon.serve(netuid, subtensor)`) instead of a static
endpoint list — this is the new code under test here. **Same-machine note:** all
neurons run on one laptop, so the metagraph-advertised axon IP must be reachable
from the co-located validator — miners serve with `--axon.external_ip 127.0.0.1`
(localnet) and the validator additionally falls back to dialing localhost when a
metagraph IP equals its own external IP (needed on testnet, where 127.0.0.1
cannot be advertised).

**Satisfaction requirements:** one full epoch where `set_weights` succeeds; the
epoch artifact contains a real extrinsic receipt (block hash + success flag);
`btcli subnet metagraph` output (captured to `work/m5/metagraph.txt`) shows nonzero
weight from our validator UID toward the honest miner UID; miner discovery came
from the metagraph, not a static list.

**Failure modes / rollback:** localnet image fails on this arm64 machine (pull the
multi-arch tag; if it genuinely cannot run, **skip M5 entirely** — it is not on the
critical path — and note that M6 becomes the first live chain contact, raising M6's
risk but blocking nothing); fast-blocks timing differs from testnet — do not tune
any timeout against localnet block timing; localnet wallets/funds are throwaway
(chain state dies with the container unless `--rm` is dropped).

**Done when:** the receipt + metagraph artifacts exist under `work/m5/`, or the
milestone is explicitly waived with the arm64 failure documented in the diary.

### M6 — Public testnet deployment (human-gated)

**Objective:** the real thing: our own testnet subnet, registered miner+validator
hotkeys, at least one full epoch with weights on the public test chain, receipts
preserved.

**Preconditions (human-gated, see §5):** H2 wallets exist; H3 test TAO received
(current state: 10.0 test TAO free, 0.0 staked; subnet creation uses a dynamic
burn, recently observed around 1.0000 TAO, but **must** be re-queried live with
`btcli subnet burn-cost --network test`); real `SubtensorChain`/`set_weights`
code exists behind the allowlist; H4 spend approved; H6 Leon at the keyboard for
every extrinsic.

**Files:** `configs/testnet.json` (netuid, network, public ss58 addresses),
`docs/runbooks/testnet-runbook.md` (final), `chain.py` (testnet params).

**Implementation sequence (agent prepares commands + verifies results; Leon
executes anything that signs):**
1. `btcli subnet burn-cost --network test` → record cost; Leon approves (H4).
2. `btcli subnet create --network test --wallet.name dolores-test` (Leon). Record
   netuid → `configs/testnet.json`. Note the 14,400-block (~2-day) per-account
   subnet-creation rate limit: this step is one-shot; do not experiment with it.
3. **Start the subnet** (new subnets are inactive until started):
   `btcli subnets start --netuid <N> --network test --wallet.name dolores-test`
   (Leon).
4. Register: `btcli subnet register --netuid <N> --network test --wallet.name
   dolores-test --wallet.hotkey validator` and same for `miner-0`, `miner-1`
   (Leon; burns are small on quiet testnet, floor 0.0005 TAO).
5. Stake to validator hotkey: `btcli stake add --netuid <N> --network test
   --wallet.name dolores-test --wallet.hotkey validator --amount <per H3
   budget>`. Then **wait ≥ 1 tempo (360 blocks ≈ 72 min)** and confirm the
   validator permit via the metagraph (`m.validator_permit` for our UID) —
   permits are assigned at epoch boundaries after stake lands; do not attempt
   the weight epoch before this reads True. If it never becomes True with the
   H3-budget stake, the stake threshold is binding → record the observed
   requirement and proceed knowing outcome (b) is likely.
6. `.venv/bin/python scripts/preflight.py --mode testnet` → all PASS.
7. Start miners (`--mode testnet --netuid <N>`, with the same-machine
   reachability fallback from M5), then
   `.venv/bin/python neurons/validator.py --mode testnet --netuid <N> --epoch 1
   --work work/m6 ...`.
8. Wait ≥ `weights_rate_limit` (100 blocks) and run epoch 2 to prove
   repeatability.
9. Capture proof: `btcli subnet metagraph --netuid <N> --network test` output;
   extrinsic hashes; `work/m6/` epoch artifacts; screenshots for the demo.
10. Stretch (only if all above green and time remains): enable commit-reveal —
    expected spelling `btcli subnets sudo-set-hyperparameter --netuid <N>
    --network test --param commit_reveal_weights_enabled --value True` (verify
    the exact subcommand with `btcli subnets --help` first; btcli 9.x renamed
    several sudo commands) — and run one more epoch proving `set_weights` still
    succeeds through the SDK's transparent CR3 path; then a second stretch,
    `subtensor.set_commitment` of the epoch's submission-batch commitment hash
    (≤ 256 bytes).

**Satisfaction requirements (the testnet-readiness contract, §6):** one full
epoch on `--network test` with either (a) a successful `set_weights` extrinsic
receipt and metagraph read-back showing our weights, or (b) the mock-weight
fallback artifact **plus** a diagnosed, documented chain-side reason (e.g., stake
threshold) — (b) keeps the demo honest but M6 is only *fully* done under (a).
Both epochs' archives and `submissions.jsonl` intact; runbook updated to match
what actually happened.

**Failure modes / diagnosis:** no validator permit after a tempo → increase
self-stake from H3 budget and wait another tempo; check `btcli subnet
hyperparameters --netuid <N> --network test`; as subnet owner, adjust adjustable
params via the sudo-set command (verified spelling per step 10); if still
blocked, ship fallback (b) and record the exact error. Testnet resets/netuid
recycling: keep everything re-runnable from the runbook; treat the netuid as
disposable. Future test-TAO top-up delay only blocks additional public-chain
attempts; M3, M4, and M7 do not depend on public-chain success.

**Done when (two explicit tiers — an agent must not conflate them):**
- **Done, tier (a) — earns the `testnet-v0` tag:** a real `set_weights`
  extrinsic receipt AND a metagraph read-back showing our nonzero weights exist
  under `work/m6/`, plus `configs/testnet.json` committed.
- **Conditionally done, tier (b):** only the diagnosed mock-weight fallback
  artifact exists. This requires an explicit STOP-LEON acknowledgement, does
  NOT earn the `testnet-v0` tag, and must be recorded as a waived gate in the
  diary. M7 proceeds either way.

### M7 — Demo packaging, docs, claims hygiene

**Objective:** the demo runs from the script without improvisation, and the repo
tells the truth.

**Files:** `docs/hackerhouse/demo-script.md` (from §7), `README.md` (rewrite:
quickstart per mode, architecture diagram, honest status), `docs/runbooks/
testnet-runbook.md` (final), diary entries, `docs/hackerhouse/pitch.md` (refresh
numbers), archive exports for show (`exports/` via public-safe filter).

**Gates:**
```
.venv/bin/pytest -q && .venv/bin/ruff check .
# Full demo dry-run from a clean clone. demo-script.md §0 MUST contain this exact
# untimed bootstrap block (a clone has no venv, no image, no work/ state):
git clone <repo> /tmp/demo-rehearsal && cd /tmp/demo-rehearsal
python3.11 -m venv .venv
.venv/bin/pip install "$DOLORES" && .venv/bin/pip install -e ".[dev]"
docker image inspect dolores-verifier-pytest:0.1.0 >/dev/null \
  || (cd "$DOLORES" && docker build -f docker/verifier/Dockerfile \
      -t dolores-verifier-pytest:0.1.0 .)
.venv/bin/python scripts/preflight.py --mode offline
# THEN the timed part: follow demo-script.md's 5-minute path verbatim
# (tests/fixtures/planted/ is committed, so step 1's cat works from a clone)
```
**Satisfaction requirements:** the timed 5-minute technical path (demo profile,
quota 1, 3 miners — §7.2) executes verbatim (copy-paste) in ≤ 8 minutes on this
laptop after the bootstrap block; the bootstrap block itself succeeds from the
clone (untimed); the 2-minute pitch matches `claims-and-evidence.md` constraints
(no overclaims from §7.4's banned list); README quickstart reproduces M3's gate;
every milestone has a diary entry. Note the `$DOLORES` path dependency makes the
clone reproducible only on this machine — acceptable and documented. **Done
when** a timed rehearsal transcript is committed to `docs/diary/`.

---

## 4. Agent Execution Plan

Ordered task list. Execute strictly in order within a milestone; milestones may
interleave only where marked ∥. After every task: run the named verification; on
failure, follow the diagnosis note; never proceed past a red gate. "STOP-LEON"
means halt and ask; do not work around.

**M0**
0. Rewrite `config.py` first (mode enum, network allowlist with mainnet
   hard-fail, limits, α, `SPEC_VERSION`) — preflight and every later module read
   it. Verify: unit test asserting `resolve_network("testnet") == "test"` and
   that finney/unset raises.
1. `git rm -r --cached src/dolores_subnet/__pycache__ tests/__pycache__`; write
   `.gitignore`. Verify: `git status` shows no `.pyc`.
2. Create `.venv` (python3.11); install Dolores path dep, then project `[dev]`,
   then `bittensor`. Verify: the M0 import command. Diagnosis: dependency solver
   conflict → try `bittensor` first then Dolores with `--no-deps` + manual dep
   install (duckdb, hypothesis==6.155.7, pyarrow); if pydantic majors clash →
   STOP-LEON with the exact conflict.
3. Vendor `configs/solver_panel.mock.yaml`. Verify: `load_panel` parses it.
4. Build/confirm verifier image. Verify: `docker image inspect
   dolores-verifier-pytest:0.1.0` exit 0. Diagnosis: build from `$DOLORES` root
   with the exact command in §2.5; Docker down → STOP-LEON (H1).
5. Write `scripts/preflight.py`. Verify: mock+offline modes all-PASS; deliberately
   stop Docker Desktop is NOT required — simulate the failure path by pointing
   `DOCKER_HOST` at a dead socket in a unit test instead.
6. Migrate to pytest; update `pyproject.toml`. Verify: `pytest -q` green.
7. Diary entry; commit `m0-environment`.

**M1**
8. Write `packaging.py` + `WireSubmission`. Verify: new tests green.
9. Cross-process hash determinism script (two `python -c` invocations, compare).
   Diagnosis if unequal: check `ensure_ascii`/sort_keys drift — must use
   `TaskPackage.stable_hash()` on both sides, never a reimplementation.
10. Diary; commit.

**M2**
11. Write `gates.py` (+ tests with hand-built payloads). Verify: each gate fails
    exactly its planted input.
12. Write `bridge.py::validate_submission` with the exact three-way
    infra/safety/failed discriminator (§2.3) and the derived runtime-cost-free
    `task_value` (§2.6). Verify: `test_bridge_mock.py` (local/fixture) green.
13. Write `archive.py` (submissions.jsonl, archive init, `purge_task`, filtered
    public-safe export copy). Verify: rows appear; purge-then-resubmit test
    green; export output contains no `hidden_tests` row.
14. Write `scripts/seed_adversarial.py`; generate fixtures. Verify: fixture dir
    contains all 7 planted cases; `bad_unsafe` actually trips `scan_task` (assert
    in the script itself).
15. Wire v0 `neurons/validator.py --mode offline --submissions`. Verify: the M2
    expected-status table exactly (`bad_duplicate` must be `rejected`, not
    `review`). Diagnosis: `bad_duplicate` not rejected → confirm processing
    order (good must precede duplicate: ascending-hash order may need the
    fixture's hashes checked — if the duplicate's hash sorts first, regenerate
    the fixture with a different task_id so ordering demonstrates the rule);
    Docker slow → verify the image is cached and `DOLORES_VERIFIER_DOCKERFILE`
    is NOT triggering rebuilds.
16. Determinism double-run + normalization test. Diary; commit.

**M3**
17. Write `scoring.py` epoch functions (pure; property-style tests: zero-sum
    normalization over metagraph∩state, top-k monotonicity, EMA bounds,
    infra-carry-forward semantics, `normalize_for_determinism`).
18. Write `epoch.py` + `OfflineMiner` personas + `local_epoch.py` (with
    `--quota`) + `report.py` (with `--replay-check`).
19. Run the M3 gate sequence including the `diff` determinism check.
    Diagnosis: nondeterminism → first suspect is any use of raw
    `aggregate_score` (runtime_cost leak, §2.6); then wall-clock/dict-order
    leaks; scores must come only from Dolores outputs via the derived task_value
    and fixed config.
20. Delete `local_loop.py` and `dolores_bridge.py`; run the stale-reference grep
    gate (must be empty, README included). Diary; commit.
    **This is the demo floor — tag `demo-floor-v0`.**

**M4** (∥ H3 wait continues)
21. Write `synapse.py` + serialization test. 22. Extend `chain.py` with wallet
    loading + `NullChain`. Verify: preflight `--mode wire` PASS with wallets from
    H2 (if H2 not yet done → STOP-LEON, it is a 10-minute task).
23. Axon path in miner; dendrite collect in validator; unreachable-miner
    handling. Verify: M4 gate sequence including the kill test. Diagnosis:
    connection refused → port collision (change `--port`); signature errors →
    wrong hotkey names; payload too large → binary-search the real ceiling with a
    padded package, set config cap to 80 % of measured, document.
24. Diary; commit.

**M5** (∥ optional, needs H6 for btcli commands)
25. Localnet up; STOP-LEON for the btcli create/register/stake sequence (agent
    prints exact commands, Leon runs); metagraph-based discovery code; full epoch;
    capture receipts. Waive-path documented in M5 above.

**M6** (blocked on H3/H4; agent prepares, Leon executes extrinsics)
26. Write `testnet-runbook.md` draft with every command pre-filled (including
    `subnets start` and the tempo/permit wait).
27. STOP-LEON: execute runbook steps 1–5 (create/start/register/stake/permit
    wait).
28. Preflight testnet; run epoch 1; wait ≥ weights_rate_limit; epoch 2; capture
    all proof artifacts. Diagnosis per M6 failure-mode notes. 29. Stretch:
    commit-reveal epoch; set_commitment. 30. Diary; commit; tag `testnet-v0`
    ONLY under tier (a) — tier (b) requires STOP-LEON acknowledgement and a
    waived-gate diary entry instead of the tag.

**M7**
31. Write demo script (from §7, including the §0 bootstrap block) + rehearse
    from a clean clone: bootstrap untimed, 5-minute path timed.
32. Rewrite README; refresh pitch; final claims check against §7.4 banned list.
33. STOP-LEON (H8) before any push to the public remote.
34. Final full-suite run; diary; tag `hackerhouse-demo`.

**Docs/diary policy:** one diary entry per milestone minimum, plus one per
STOP-LEON resolution and one per waived gate. **Update this plan file itself** only
via a dated "Deviations" appendix — never rewrite history.

---

## 5. Human / Operator Requirements (Leon)

| ID | Task | Why | Leon provides | Blocks | Safety notes |
|---|---|---|---|---|---|
| H1 | Install/start Docker Desktop (keep running during M2+ gates); `brew install jq`; approve the macOS firewall prompt the first time Python binds an axon port (or pre-allow the venv python in System Settings → Firewall) | Fail-closed verification requires a live daemon; the M3 gate and demo use `jq`; the firewall dialog is GUI-only — an unattended agent run silently hangs on it | Confirmation `docker version` and `jq --version` work; firewall approved before M4 | M2–M6, demo (Docker/jq); M4+ (firewall) | None; no credentials involved |
| H2 | Create testnet-only wallet: coldkey `dolores-test`, hotkeys `validator`, `miner-0`, `miner-1` via `btcli wallet new-coldkey / new-hotkey` | Agents must never generate, view, or handle mnemonics/keys; synapse signing and all chain ops need them | The wallet/hotkey *names* only (defaults above fine); confirmation created | M4 (wire signing), M5, M6 | **Brand-new keys — do NOT reuse any Dolores/production/funded key.** Mnemonics written down offline, never typed into the agent chat, never committed. Wallet dir stays default `~/.bittensor/wallets/` (repo `.gitignore` also excludes `wallets/`) |
| H3 | Test TAO funding for the `dolores-test` coldkey | Needed for public testnet create/register/stake attempts | Complete as of 2026-07-08: 10.0 test TAO free, 0.0 staked, 10.0 total on `--network test` | M6 funding no longer blocks the next code/doc step; amount may still constrain stake/permit experiments | Public address only; no one legitimate will ever ask for the mnemonic |
| H4 | Approve testnet subnet creation burn/spend and the one-shot nature (14,400-block / ~2-day rate limit per account) | Irreversible externally visible chain action; burn cost is dynamic | A yes/no after seeing fresh `btcli subnet burn-cost --network test` output | M6 | Test TAO has no monetary value, but the rate limit makes mistakes costly in time; M7 observed `1.0000 τ`, but re-query immediately before any create |
| H5 | Public naming decision: GitHub repo name/visibility, subnet identity string, whether "Dolores" branding is used on-chain | Outward-facing identity; agents shouldn't publish | Repo name + public/private; subnet name string for registration metadata | M6 (registration), M7 (README/demo) | Repo must stay free of `docs/imported` items marked internal? — current imports were curated for standalone use; Leon confirms before any public push |
| H6 | Be at the keyboard for every chain extrinsic (localnet + testnet): create, register, stake, sudo hyperparam changes | Extrinsics sign with the coldkey/hotkeys; agent prepares exact commands, human executes and pastes output | Command outputs (netuid, tx hashes) back to the agent | M5, M6 | Verify `--network` flag on every command before running (test vs. finney); never run a command containing `finney` mainnet during this plan |
| H7 | (Optional, default NO) Paid-panel decision: whether any Fireworks calls happen anywhere in demo prep | Cost + the plan promises no paid calls | Explicit opt-in only | Nothing (mock panel is the plan) | If ever enabled, key stays in Dolores repo env, never in this repo |
| H8 | Create the GitHub remote and provide authenticated push (run `gh repo create` per H5's naming decision, or add the remote and confirm `gh auth status`/SSH key works) | Agents cannot authenticate as Leon to create or push a public repo; M7's clean-clone rehearsal and any public release need the remote | Repo URL + confirmation the agent may push, or Leon pushes himself at the M7 STOP-LEON | M7 (clean-clone gate, public release) | Agent never handles tokens; review the repo contents once before the first public push (imported docs are curated but deserve one human pass) |

---

## 6. Testnet Readiness (the contract for "a successful testnet run")

1. **Wallet readiness:** coldkey `dolores-test` + 3 hotkeys exist locally (H2);
   coldkey currently holds 10.0 test TAO free and 0.0 staked (H3 complete);
   a fresh `btcli subnet burn-cost --network test` plus validator-stake headroom
   check is required before any M6 public-chain action; `preflight --mode
   testnet` PASSes wallet checks without reading key material.
2. **Network/subtensor readiness:** `wss://test.finney.opentensor.ai:443`
   reachable; SDK connects and reads current block; our netuid exists
   (`configs/testnet.json` committed).
3. **Miner registration/readiness:** `miner-0` (and `miner-1` if budget allows)
   registered on our netuid (UID visible in metagraph); miner process serves an
   axon whose IP/port appear in the metagraph; **same-machine reachability
   confirmed** — all neurons run on one laptop, so the validator must reach the
   metagraph-advertised address (localhost fallback per M5) — verified by a
   manual single-synapse probe from the validator process succeeding within
   120 s.
4. **Validator registration/readiness:** `validator` hotkey registered; subnet
   **started** (`btcli subnets start`); stake added; **≥ 1 tempo elapsed since
   staking and `metagraph.validator_permit` reads True for our UID** (permits
   are epoch-assigned — never assume them on a fresh subnet);
   `weights_rate_limit=100` blocks respected by the epoch scheduler.
5. **Message/schema compatibility:** `schema_version="dolores-subnet-v0"` asserted
   on both sides; the M4 synapse round-trip test green against the *same*
   bittensor version pinned in `pyproject.toml`.
6. **One full local epoch simulation:** the M3 gate (including the byte-identical
   determinism diff) green on the demo machine within 7 days before the demo.
7. **One full testnet epoch (or equivalent):** M6's requirement — collect from ≥ 2
   registered miners over the public testnet, validate in Docker, produce weights,
   and either (a) land `set_weights` + read back nonzero weights from the
   metagraph, or (b) produce the mock-weight fallback artifact with a diagnosed
   chain-side reason. (a) is the target; (b) is the honest fallback that keeps the
   demo truthful.
8. **Weight-setting behavior:** the epoch artifact schema is identical in both
   cases (vector + EMA state + receipt-or-reason), so the demo narration does not
   change shape.
9. **Logs and artifacts preserved as proof:** `work/m6/` in full (`archive.duckdb`,
   `submissions.jsonl`, epoch dirs, metagraph dumps, extrinsic hashes, terminal
   transcripts via `script`/`tee`), plus screenshots. These are the "testnet
   receipts" deliverable and get referenced from README + pitch.

---

## 7. Demo Script (hackerhouse)

### 7.1 Two-minute pitch

> "Solver subnets like Ridges reward agents for *solving* benchmarks. Nobody on
> Bittensor rewards *making* them — and frontier task supply is the actual
> bottleneck in RL for coding agents. Dolores is the supply side: miners propose
> verifiable software tasks; validators run every package through a hardened,
> fail-closed pipeline — AST safety scan, containerized reference verification,
> known-wrong-solution probes, duplicate detection, and a solver panel — and
> weights follow *marginal validated archive value*, not volume. Everything you'll
> see is real execution evidence: `containerized=true` is an evidence claim in our
> archive, not a label. The archive exports to Hugging Face and
> verifiers-compatible formats, so accepted tasks are immediately consumable as an
> RL curriculum dataset — whether they improve training is a separate experiment
> we haven't run, and we say so. The subnet is the adversarial proving ground; the
> archive is the asset. [If M6 tier (a):] "We run the full loop on our own testnet
> netuid — miner, validator, scoring, and the weight extrinsic. Here's the
> `set_weights` receipt, read back from the metagraph." [If tier (b)/waiting:]
> "The chain call is queued behind real chain-client code and Leon-approved
> public-testnet extrinsics — today it writes the identical artifact the
> extrinsic consumes; every other layer is exactly what runs on chain." Mainnet
> economics come only after the loop survives adversarial testnet pressure."
>
> (The demo driver must know which branch is true on the day; rehearse both.)

### 7.2 Five-minute technical walkthrough (exact commands)

Terminal font large; `work/` pre-cleaned; Docker warm; testnet artifacts from M6
open in a browser tab as backup.

```bash
# 0. (before audience) sanity
.venv/bin/python scripts/preflight.py --mode offline

# 1. Show an actual task package — the artifact miners are paid for
cat tests/fixtures/planted/good_parser/task.yaml | head -40

# 2. One live epoch — DEMO PROFILE: 3 miners, quota 1, pre-warmed image (~2-4 min
#    measured at M3; the quota-4 config default would take ~20+ min and is NOT
#    what you run on stage)
.venv/bin/python scripts/local_epoch.py --mode offline \
  --miners honest,duplicate_spammer,invalid --quota 1 --epoch 1 --work work/demo

# (while it runs) narrate the pipeline stages scrolling by:
#   safety scan -> docker verify (point at containerized=true) -> probes ->
#   mock panel -> duplicate report -> score

# 3. The leaderboard: quality wins, spam collapses, invalid zeroes
.venv/bin/python scripts/report.py --work work/demo --epoch 1

# 4. The evidence trail (this is the moat) — python module, no duckdb CLI needed:
.venv/bin/python -c "import duckdb; c=duckdb.connect('work/demo/subnet_archive/archive.duckdb'); \
  print(c.sql('SELECT task_id, lifecycle_status FROM tasks')); \
  print(c.sql('SELECT status, containerized, executed FROM verification_runs'))"
tail -3 work/demo/subnet_archive/submissions.jsonl | jq .

# 5. Chain proof (if testnet live): weights on the public testnet
btcli subnet metagraph --netuid <N> --network test        # live, or:
jq .weight_result work/m6/subnet_archive/epochs/epoch_1/weights_epoch_1.json
#   -> {"mode":"chain","receipt":{...}} under tier (a),
#      {"mode":"fallback","reason":"..."} under tier (b) — narrate accordingly
```
(Step-4 names verified against the backend audit — `tasks.lifecycle_status` is
maintained by `ArchiveDB.add_score` — but re-confirm and pin into
`demo-script.md` during M3.)

### 7.3 What to show / success looks like

Screenshots/logs staged in advance: M6 metagraph output with our weights; an
extrinsic hash; a rejected `bad_unsafe` submission's safety finding; the
determinism diff (two runs, empty diff); **and a full pre-recorded fallback set
for the live epoch itself** — a terminal capture (`script`/asciinema) of a
known-good `local_epoch` demo-profile run, its rendered leaderboard, and the
step-4 evidence output (archive rows + `submissions.jsonl` tail), kept open in a
tab. Success = the audience sees a rejected malicious package with a *named
reason*, an accepted package with a component score, weights that moved, and a
chain receipt.

### 7.4 If live testnet registration/funding is delayed

Say exactly: *"We have 10.0 test TAO on the testnet coldkey, but the public
subnet is not registered yet and the real chain client is intentionally still
behind the STOP-LEON gate. Today's weights step writes the deterministic artifact
the chain call will consume; every other layer — the safety scan, Docker
verification, probes, dedup, scoring, and local axon/dendrite transport — is
running now."* If Docker, ports, RPC, or the live epoch itself fails on stage,
switch to the pre-recorded epoch capture (§7.3) and narrate from it — the archive
rows and leaderboard are the proof, not the live run. Never claim: live on
mainnet; a registered public testnet subnet; public emissions; validator permit;
live on-chain weights; public miners; 2k-task archive; 15 strong frontier tasks;
production-grade isolation; that the scorer predicts training value
(banned-claims list from `docs/imported/limitations.md` +
`claims-and-evidence.md` applies verbatim).

---

## 8. Robustness and Provenance (testnet-grade, auditable — not production security)

1. **Deterministic validation:** gates, verification pass/fail, probe outcomes,
   duplicate scores, and the derived task values/weights are deterministic given
   (package, config, archive state); enforced by the M2/M3 byte-identical
   double-run gates under the canonical normalization. The one wall-clock input
   in the Dolores scorer (the `runtime_cost` component, a step function of
   verification duration) is **excluded from weight derivation by construction**
   (§2.6); the stochastic surface otherwise is zero — deterministic MockSolver
   panel, seeded generation.
2. **Containerized verification evidence:** every scored execution row carries
   `backend/requested_backend/executed/containerized/image/logs_hash`;
   `containerized=true` only when code actually ran in the pinned
   `dolores-verifier-pytest:0.1.0` image with `--network none`, read-only mount and
   memory caps; fail-closed otherwise (Dolores `validate_execution_policy` +
   DockerRunner semantics, unchanged).
3. **Public/held-out separation:** hidden tests never leave the validator
   archive; public exports are produced only from a filtered DB copy with
   `hidden_tests` rows deleted (§2.3 — the raw Dolores exporters do NOT filter,
   so this is enforced subnet-side with a dedicated leak test); probes are
   validator-side signal miners don't control. Full held-out synthesis is an
   acknowledged post-testnet upgrade, stated as such.
4. **Task package hashes:** identity = `stable_hash()` over canonical content;
   validator recomputes, never trusts; submission envelopes have a
   `commitment()` hash; batch commitment on-chain via `set_commitment` is the M6
   stretch.
5. **Archive provenance:** per task: files with content hashes, verification runs
   with log hashes and container evidence, solver rows with error classes, score
   components, duplicate report, lineage, timestamps — the existing Dolores
   `ArchiveDB` schema, plus the subnet `submissions.jsonl` binding every row to a
   miner hotkey and epoch.
6. **Duplicate and quality gates:** exact-hash dedup in-epoch across miners;
   `duplicate_report` against the growing archive DB (reject ≥ 0.95, review ≥
   0.85); staged gates-then-score; too-easy/too-hard → review, not accepted.
7. **Miner scoring transparency:** every weight is reproducible from committed
   code + archived rows; `report.py` shows the full decomposition per miner per
   epoch; `weights_epoch_<E>.json` includes raw scores, EMA inputs, and the
   normalization.
8. **Local replayability:** any submission can be re-validated from its archived
   files (`show_task` → rematerialize → `validate_submission`), and any epoch can
   be re-run from `submissions.jsonl` + config to reproduce the weight vector.
   A `report.py --replay-check <epoch>` flag doing exactly this is part of M3.

Explicit non-claims: not production security isolation; the mock panel's frontier
signal is a stand-in; single-validator consensus proves determinism, not
Yuma-scale agreement.

---

## 9. Bittensor-Specific Design

### 9.1 Protocol message shape

One synapse type v0: `TaskSubmissionSynapse(bt.Synapse)` — request
`{epoch_id: int, quota: int, schema_version: str}`, response
`{submissions: list[WireSubmission-dict]}` (§2.4). Pull model (validator polls
miners each epoch), matching the research recommendation and the reference
subnet-template pattern. On-chain commitments (`subtensor.set_commitment`, ≤ 256
bytes) carry only the epoch batch-commitment hash and only as an M6 stretch.

### 9.2 Miner/validator responsibilities

Miner: generate/self-check/serve; sign transport with its hotkey; stay under
quota and size caps. Validator: everything else (§1.3) — the trust asymmetry is
total by design: the validator re-derives every claim (hash, verification, score)
and treats packages as hostile code (fail-closed sandbox).

### 9.3 Scores → weights

Exactly §2.6: gates-to-zero → derived runtime-cost-free task value per accepted
task → top-k(=quota) per miner over non-infra submissions → EMA(α=0.3) keyed by
hotkey → normalize over metagraph-present hotkeys → `set_weights(...,
version_key=SPEC_VERSION)` (SDK converts to u16). `weights_rate_limit`
(100 blocks) and tempo (360) drive the epoch scheduler; commit-reveal, when
enabled, is transparent to this code path.

### 9.4 Invalid submissions

Distinct terminal states, all archived with reasons: `invalid:*` (pre-gate:
schema/size/hash/quota/dup-in-epoch) — zero, cheap, no execution;
`rejected` (safety or failed verification or dup ≥ 0.95) — zero + strike;
`review` (too_easy/too_hard/dup ≥ 0.85) — zero weight in v0 but archived as
negative examples; `infra_error` — no penalty, EMA carried forward per §2.6,
epoch flagged degraded, and the archived rows purged (`purge_task`) so an
identical resubmission next epoch validates cleanly. Strikes are deferred as of
the 2026-07-08 M4 hardening pass: until they are implemented, repeated safety
offenders are still zeroed per epoch but their quota remains the configured
default.

### 9.5 Anti-spam in testnet form

Per-miner quota (4/epoch, deterministic truncation) — **the only bound on
validator compute in v0** (see §2.6's dedup honesty note: exact-hash dedup
catches only byte-identical resubmissions; task_id-mutated copies each cost a
full Docker validation before the semantic duplicate gate rejects them); top-k
aggregation; archive duplicate gate with reject/review thresholds; deferred
strike system; size caps. Reputation queues, family-coverage steering, embedding
novelty, semantic pre-gate dedup — explicitly deferred.

### 9.6 Mock vs. must-be-real for demo credibility

**May be mock/local-only:** solver panel (deterministic MockSolver, clearly
labeled — frontier component is a stand-in); emissions (testnet emissions are 0
anyway); second validator (replaced by determinism replica); commit-reveal;
on-chain commitments. **Must be real:** Docker verification with fail-closed
evidence; safety scanner rejecting a live hostile package; probes; duplicate
collapse; hash re-derivation; the axon/dendrite transport with signed miners
(M4+); the testnet registration + at least one weight event or its diagnosed
fallback (M6); the archive rows backing every number shown.

---

## 10. Dependency / Environment Plan

- **Python:** 3.11 (matches Dolores `.venv` 3.11.15; inside bittensor 10.5's
  supported ≥3.10,<3.15). Single interpreter for everything.
- **Venv:** dedicated `$SUBNET/.venv`. Do **not** develop inside the Dolores venv
  (bittensor's dependency tree stays out of the research repo). Dolores installed
  into the subnet venv as a **non-editable local path install**; after any Dolores
  change: `pip install --no-deps --force-reinstall "$DOLORES"` (preflight warns on
  staleness).
- **Bittensor SDK:** `bittensor>=10.5,<11` (pure-python wheel, arm64-fine;
  `bittensor-wallet`/`bittensor-drand` ship arm64 wheels). `bittensor-cli` comes
  with it; btcli is only ever run by Leon (H6) except read-only queries
  (`burn-cost`, `metagraph`, `hyperparameters`) which the agent may run with
  explicit `--network test|ws://127.0.0.1:9944` only — never without a network
  flag (btcli defaults to mainnet).
- **Docker:** Docker Desktop (H1) for (a) the Dolores verifier image
  `dolores-verifier-pytest:0.1.0` (python:3.11-slim + pytest 9.1.1 + hypothesis
  6.155.7) and (b) optionally `ghcr.io/opentensor/subtensor-localnet:devnet-ready`
  (M5).
- **Local path dependency:** `DOLORES_REPO` env var (default the absolute path
  above) used only by preflight/diagnostics; runtime code imports `dolores` from
  the venv install, so no `sys.path` hacks remain (delete that logic from the old
  bridge).
- **CI/smoke:** a `make ci` target (or GH Actions later, per H5): `ruff check .`,
  `pytest -q` with **mock mode only** (no Docker, no bittensor import required —
  one test asserts `mock` mode works with bittensor uninstalled via a subprocess
  `pip uninstall` sandbox or an import-blocker fixture), plus a separate
  `make smoke-docker` (M2 planted-set run) executed manually before demos.
- **No credential assumptions:** the repo contains no keys, reads no `.env`,
  never touches `FIREWORKS_API_KEY`; wallets live in `~/.bittensor/wallets/` and
  only their *names* appear in configs; `.gitignore` covers `wallets/`, `work/`,
  `.venv/`.

---

## 11. Deliverables (exact artifacts at completion)

**Code modules:** `src/dolores_subnet/{config,protocol,synapse,packaging,bridge,gates,scoring,archive,epoch,chain}.py`; `neurons/{miner,validator}.py`.
**CLI commands:** `scripts/preflight.py --mode <m>`; `scripts/local_epoch.py`;
`scripts/report.py [--replay-check]`; `scripts/seed_adversarial.py`;
`neurons/miner.py`/`validator.py` with `--mode {mock,offline,wire,localnet,testnet}`.
**Test files:** `tests/test_{protocol,packaging,gates,scoring_weights,bridge_mock,epoch_offline,synapse_roundtrip}.py` — all green via `pytest -q`.
**Configs:** `configs/solver_panel.mock.yaml`, `configs/testnet.json`.
**Docs:** this plan (+ dated Deviations appendix); `docs/runbooks/testnet-runbook.md`;
`docs/hackerhouse/demo-script.md`; refreshed `README.md` + `pitch.md`;
`docs/diary/*` (≥ 8 entries).
**Demo logs:** timed rehearsal transcript; `work/demo/` leaderboard output; the
pre-recorded epoch capture + staged evidence screenshots (§7.3 fallback set).
**Archive files:** `work/m3_a`, `work/m6/` — `archive.duckdb`, `submissions.jsonl`,
epoch dirs with `weights_epoch_*.json` + reports; public-safe `exports/`.
**Testnet receipts or fallback proof:** extrinsic hashes + metagraph dumps in
`work/m6/`, or the fallback artifact + diagnosed reason; `configs/testnet.json`.
**Tags:** `demo-floor-v0` (M3), `testnet-v0` (M6), `hackerhouse-demo` (M7).

---

## 12. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Test-TAO Discord delay (faucet disabled) | High | Blocks M6 only | H3 starts day 1; M3 demo floor + M5 localnet make the demo chain-independent; §7.4 fallback narration rehearsed |
| Bittensor/Dolores dependency conflict in one venv | Medium | Blocks M0 | Ordered resolution path in M0; worst case two-venv subprocess split (STOP-LEON decision) |
| Validator can't set weights on testnet (no permit: subnet not started, tempo not elapsed, or stake below threshold) | Medium-High | Degrades M6 to tier (b) | `subnets start` + tempo wait + permit check are explicit M6 steps; H3 over-asks stake headroom; owner sudo-set where possible; mock-weight artifact keeps the epoch complete and the demo honest |
| Docker runtime issues on macOS (daemon down, arm64 image quirks, slow builds) | Medium | Blocks M2+ gates | Preflight catches before every gate; image pre-built and cached; fail-closed semantics already correct in Dolores; localnet M5 is waivable |
| Determinism leaks (wall-clock in scores, timestamps, dict order) | Medium | Blocks M2/M3 gates | Known leak already engineered out: runtime_cost excluded from task values by construction (§2.6); canonical normalization + artifact `timing`-confinement schema test; double-run diffs are the gate |
| Epoch too slow for a live demo (~6 container runs per package) | High | Demo quality | Explicit demo profile (3 miners × quota 1, ≤ 5 min measured at M3); quota-2 gate profile; pre-warmed image; pre-recorded epoch capture as the on-stage fallback |
| Dolores backend drift (repo evolves under us; non-editable install staleness) | Medium | Subtle wrong-version bugs | Preflight staleness check; reinstall command documented; subnet pins no Dolores internals beyond the audited API surface |
| Scoring looks too mock-like (frontier = MockSolver) | High (perception) | Demo credibility | Lead with what's real (Docker evidence, safety, probes, dedup); label the panel mock explicitly; never quote frontier numbers as capability claims |
| Demo overpromising vs. claims discipline | Medium | Reputation | §7.4 banned-claims list enforced at M7 gate against `limitations.md`/`claims-and-evidence.md` |
| Synapse payload ceiling below our 1 MB budget | Low-Med | M4 rework | Measured empirically in M4 with a padded package; cap set to 80 % of measured |
| Testnet reset/netuid recycling mid-hackerhouse | Low | Re-run M6 | Everything scripted in the runbook; netuid treated as disposable; receipts preserved offline |
| Hackerhouse time pressure | High | Scope | Strict milestone order; M3 tag is the always-shippable floor; M5 and both M6 stretches are pre-declared cuts |

---

## 13. Deviations Appendix

Agents append dated entries here when reality forces a change; each entry names
the milestone, the deviation, and the approval trail.

### 2026-07-08 — M4 wire module and chain seam

The implementation uses `src/dolores_subnet/wire.py` for the Bittensor
`bt.Synapse` subclass plus local axon/dendrite helpers instead of the original
`synapse.py` filename. `src/dolores_subnet/chain.py` now exists as the explicit
non-signing chain seam with `ChainClient` and `NullChain`. Real
`SubtensorChain`/`set_weights` code was deferred to M5/M6 at that point and
still requires STOP-LEON approval before any signing or public testnet action.
This is superseded by the M6 chain-readiness entry below. Approval trail: Fable
conformance review dated 2026-07-08 and the M4 hardening diary.

### 2026-07-08 — M4 unreachable and oversized wire response semantics

Unreachable miners are no longer represented by synthetic task payloads. The
validator records an out-of-band terminal outcome with `status="unreachable"`,
`task_value=0.0`, no package hash, and a reason containing the observed
transport failure. This status decays through the normal EMA path and does not
set `degraded=true`; `infra_error` is reserved for validator/Docker/backend
infrastructure failures. Oversized aggregate wire responses are likewise
validator-observed terminal `invalid` outcomes, not `infra_error`.

### 2026-07-08 — M2/M6 strikes explicitly deferred

The earlier §9.4 wording claimed the strike system was implemented in
`gates.py`; that was inaccurate. Strikes are explicitly deferred until a later
anti-spam pass. Current behavior is per-epoch zeroing plus quota and duplicate
gates only.

### 2026-07-08 — M7 demo paths corrected

The copy-paste demo commands in §7.2 are superseded by
`docs/hackerhouse/demo-script.md`. Actual artifacts live under
`work/<run>/subnet_archive/...`, including `archive.duckdb`, `submissions.jsonl`,
and `epochs/epoch_<N>/weights_epoch_<N>.json`.

### 2026-07-08 — M7 funding and public-chain claim update

H3 funding is now complete: the `dolores-test` coldkey has 10.0 test TAO free
and 0.0 staked on `--network test`. This does not make M6 complete. No public
subnet is registered, no validator permit exists, no on-chain weights have been
set. The old subnet-creation cost wording is superseded by the current
read-only command `btcli subnet burn-cost --network test`; M7 observed
`1.0000 τ`, but the burn cost is dynamic and must be re-queried immediately
before any STOP-LEON H4/H6 public-chain action. Subnet creation also carries the
14,400-block (~2-day) per-account reuse/rate-limit warning.

### 2026-07-08 — M6 chain-readiness layer implemented without extrinsics

`src/dolores_subnet/chain.py` now includes the real chain seam:
`SubtensorChain`, a private `_Substrate` facade, read-only preflight,
metagraph hotkey-to-UID mapping, dry-run weight payload receipts, and a
live-capable `set_weights` path behind four gates. The live path requires
client allowance via `--allow-extrinsics`, `DOLORES_ALLOW_EXTRINSICS=1`, CLI
`--chain live`, and the typed confirmation string `I-AM-LEON-AND-I-APPROVE`;
otherwise it records
`error/extrinsics_not_allowed` and does not call `set_weights`. `NullChain`
keeps the original fallback record. Chain receipts are written separately as
`chain_receipt_epoch_<N>.json`, while deterministic weight artifacts keep only
a stable receipt reference. No public-chain write, registration, stake,
transfer, or `set_weights` action was executed in this pass.
