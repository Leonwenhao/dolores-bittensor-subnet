# Example Dolores task packages

Four hand-picked, public-safe task packages that show what a **real miner submission**
looks like on the Dolores Autocurricula subnet. Two are genuine known-good tasks you can
learn from; two are deliberately broken teaching examples that show what the validator's
gauntlet rejects.

> Read **[`AGENTS.md`](../../AGENTS.md)** (repo root) first — it is the end-to-end miner
> runbook (install, wallet, register on netuid 523, self-validate, serve). This directory is
> the "what a package looks like" companion to it (see AGENTS.md §6 "Build a task package").
>
> **Fastest way to your own submission:** don't hand-author from scratch — fork one of these and
> mutate it. `python scripts/prepare_mutation_task.py --name <id>` copies `honest_example` to
> `my_task_<id>/`, rewrites its `task_id`, and drops the stale `wire.json`; then follow AGENTS.md's
> **Fast Path** + **Mutation Guide**. Validate with `scripts/validate_task.py --run-tests` and
> `--dedup-against examples/tasks` before serving.

## The four examples

| dir | what it is | fate at the validator |
|---|---|---|
| `honest_example/` | Known-good `parser_roundtrip` task (v3-accepted). Single-file quoted-field codec with a reference solution, public + hidden tests. | **Rewardable** — reference passes, hidden tests are strong. |
| `harder_v3_example/` | Known-good `multi_file_bugfix` task (v3-accepted, difficulty 0.8). A 4-file `order_desk` package with a shared-state aliasing bug to fix. | **Rewardable** — harder, higher frontier value. |
| `duplicate_example/` | Intentional near-copy of `honest_example` (renamed `task_id` + a cosmetic whitespace tweak in the prompt). | **Zero** — see "Why the broken ones earn zero". |
| `invalid_example/` | Copy of `honest_example` whose **reference solution is deliberately broken** (a stub that returns `None`). | **Zero** — reference fails its own hidden tests in Docker. |

Each example directory contains:

- `task.yaml` — the task package in the engine's on-disk form (what `TaskPackage.load(dir)`
  reads and what `packaging.materialize` writes).
- `wire.json` — the **ready-to-serve wire submission**: the exact JSON envelope a miner sends
  over transport, produced by `packaging.to_wire`. Same shape as `tests/fixtures/planted/wire/*.json`.

## Package format, in brief

A **wire submission** (`wire.json`) has exactly these top-level keys (see AGENTS.md §6):

- `schema_version` — must equal `dolores-subnet-v0`
- `task_id` — must match `package.task_id`
- `package_hash` — the engine's `stable_hash()` of the package; the validator recomputes and
  must match. `stable_hash` excludes the volatile `metadata.created_at`, so the hash is stable
  across regeneration. **You never hand-compute it** — the engine does.
- `package` — the full package dict: `task_id`, `title`, `domain`, `prompt`, `starter_files`,
  `reference_files`, `public_tests`, `hidden_tests`, `constraints`, `descriptors`, `lineage`,
  `metadata`.
- `family`, `declared_difficulty` — routing/labeling hints.

Max canonical size is **200 KiB** per submission. All four examples are ~3–4 KiB.

## Validate one locally (free, deterministic)

From the repo root, with the project venv active. This checks everything deterministic —
schema, size, hash, and the pre-gates — without touching the chain or Docker:

```bash
python - <<'PY'
import json, sys
sys.path.insert(0, "src")
from dolores_subnet.packaging import from_wire, canonical_size
from dolores_subnet.gates import run_pre_gates, GateContext
from dolores_subnet.config import SubnetConfig, MAX_PACKAGE_BYTES

s = json.load(open("examples/tasks/honest_example/wire.json"))
from_wire(s)                       # schema_version + size + parse + hash_match (raises on failure)
d = run_pre_gates(s, SubnetConfig(), GateContext(quota=1), miner_hotkey="self")
print("passed", d.passed, "size", canonical_size(s), "/", MAX_PACKAGE_BYTES, dict(d.gates))
PY
```

Observed results (this is what these examples actually do):

- `honest_example` and `harder_v3_example` — `from_wire` succeeds and all pre-gates pass.
- Their reference solutions pass their own public **and** hidden tests
  (`6 passed` each via `pytest`).
- `duplicate_example` and `invalid_example` also pass the *deterministic* pre-gates when
  submitted alone — the pre-gates only check schema/size/hash/quota/exact-duplicate. They are
  killed later, by the Docker gauntlet and archive dedup (below), which is exactly the point.

To reproduce the reference-solution check for a good task, write its `reference_files`,
`public_tests`, and `hidden_tests` to a temp dir and run `pytest` there. For the full Docker
verification, the operator's validator runs `dolores-verifier-pytest:0.1.0` — that is the run
that ultimately gates reward and is not something a miner self-scores.

## How to serve one as a miner

**Mutation path (recommended)** — fork an example, mutate it, validate, serve:

```bash
python scripts/prepare_mutation_task.py --name my_id            # -> my_task_my_id/ (task_id set, wire.json dropped)
# ... mutate meaningfully: change file bytes, PROBE-DROP + hidden test, prompt/concepts ...
python scripts/validate_task.py --task-dir my_task_my_id --run-tests               # reference passes its own tests
python scripts/validate_task.py --task-dir my_task_my_id --dedup-against examples/tasks  # max duplicate_score < 0.7
python neurons/miner.py --mode wire --task-dir my_task_my_id --port 8091 --host 0.0.0.0 \
  --wallet.name <W> --wallet.hotkey <HK>
```

**Persona fallback** — genuine generated packages differentiated by **seed** (AGENTS.md §6):

```bash
python neurons/miner.py --mode offline --persona honest --seed <YOUR_UNIQUE_SEED> --quota 2 > my_submissions.json   # inspect the envelopes
python neurons/miner.py --mode wire    --persona honest --seed <SAME_SEED> --port 8091 --host 0.0.0.0 \
  --wallet.name <W> --wallet.hotkey <HK>                                                                            # serve the axon
```

`wire.json` here is the single-submission form of each element of the array that
`--mode offline` prints; the wire miner serves a **list** of such objects. Use these files as
reference templates for structure and for local `from_wire` validation. Follow AGENTS.md §7–§8
for the actual self-validate-then-serve flow.

## Why the broken ones earn zero — do NOT submit them

`duplicate_example/` and `invalid_example/` exist **only** to demonstrate the gauntlet.
Serving them as-is earns **zero** and wastes a submission slot:

- **`duplicate_example`** — cosmetically renaming a `task_id` and tweaking whitespace does not
  make a task novel. The validator computes a `duplicate_score` against the **whole archive**
  (exact-hash match, prompt/descriptor Jaccard, and **file-content overlap**), and takes the max.
  Because this copy leaves the reference/tests/starter **bytes unchanged**, its file overlap is
  **1.0** → the task is **rejected outright** (`duplicate_score ≥ 0.95`). Even a near-copy that
  edited some bytes lands in the **≥0.85 "review" band, which also pays zero**. (A byte-identical
  resubmission is additionally caught pre-serve by the deterministic `epoch_duplicate` gate.)
  Reproduce the score locally: `python scripts/validate_task.py --task-dir
  examples/tasks/duplicate_example --dedup-against examples/tasks` prints `1.00`. Safe target for
  a real mutation: **< 0.7**.
- **`invalid_example`** — its reference solution is a stub that returns `None`, so it fails its
  own hidden tests inside the Docker verifier. A task whose own reference can't pass is invalid
  and scores zero. (Real rejections also include: hidden tests too weak to fail a wrong
  solution, unsafe code, or oversize packages.)

## Provenance & scrubbing

`honest_example` and `harder_v3_example` are derived from tasks accepted by an internal v3
calibration run and reconstructed through the real engine schema. They have been scrubbed of
all run/provider metadata, internal identifiers, and absolute paths; `task_id`s were renamed to
neutral example names. Only public-safe task content (prompt, files, tests, reference solution,
schema-required descriptors, MIT license) remains.
