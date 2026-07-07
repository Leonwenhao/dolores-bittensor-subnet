# Generator v3 Design

Date: 2026-07-03. Owner: Fable (orchestrator). Status: implementation spec.

## Why v3

The corrected re-baseline (`work/m12_rebaseline_20260703_094907`) showed the
frozen v2 set is saturated: 120/125 attempts passed, 3 genuine verification
failures, 3/25 tasks frontier (all boundary cases at 0.80 with a single
failing model). The generator, not the measurement, is now the bottleneck.
v3 must (a) raise genuine difficulty and (b) scale far beyond 5 hand-authored
variants per family, deterministically.

## Package layout

`src/dolores/proposer/families.py` becomes a package:

```
src/dolores/proposer/families/
  __init__.py     # public API + registry (see below)
  core.py         # shared machinery: _package, _render, combo engine, size lint
  parser.py       # parser_roundtrip
  stateful.py     # stateful_register
  optimization.py # algorithmic_optimization
  specgap.py      # spec_gap_contract
  bugfix.py       # multi_file_bugfix
```

Back-compat: `from dolores.proposer.families import FAMILY_BUILDERS,
propose_family, propose_calibration_batch` must keep working (used by
`templates.py`, `scripts/generate_calibration_batch.py`, tests).

## Core engine (core.py)

Each family module defines:

```python
FAMILY = "parser_roundtrip"                 # descriptor task_type
def combos() -> list[dict]:                 # full deterministic combo space
def build(combo: dict) -> TaskPackage:      # pure function of the combo
```

`combos()` returns the full axis product as plain dicts (hundreds+ entries,
order deterministic — sorted axis iteration, no randomness). `build()` must
depend ONLY on the combo dict, never on seed or index, so a given task_id is
permanently stable across seeds and batches.

Core provides:

```python
def propose_family(family: str, count: int, seed: int = 0,
                   band: str | None = None) -> list[TaskPackage]
```

- Filter combos by band when given (`combo["band"]` is `core` or `stretch`).
- Order: `random.Random(f"dolores-v3:{family}:{seed}").shuffle(pool)` then
  take the first `count`. Same (family, seed, band, count) → identical tasks.
- Raise `ValueError` if `count` exceeds the pool (fail loudly, never repeat).
- After building, assert unique task_ids and unique stable hashes; assert the
  size lint (below); assert every non-optimization reference contains
  `# PROBE-DROP` and every optimization starter exists (naive probe).

Size lint (enforced at build time, same numbers as the tests): total
reference file content per task ≤ 120 lines and ≤ 4000 chars.

`propose_calibration_batch()` returns 5 tasks per family at seed 0
(25 total) — the standard local rehearsal batch.

Descriptors/metadata per task (archive-cell metadata, no schema change —
encoded as concept tokens):

- `family:<family>` (added by `_package` already)
- `archetype:<slug>` — the structural sub-template
- `target_band:core|stretch`
- `gen:v3` — generator version marker
- plus family knob tokens (e.g. `knob_deciding_examples:0`)

`estimated_difficulty`: `medium` for core, `hard` for stretch.
Lineage: `proposer_type="template"`, `proposer_model="<family>-v3"`.

Task IDs: `<prefix>_<archetype>_<theme>[_<param-slug>]`, all lowercase
snake case, unique by construction across the combo space (the combo tuple
maps 1:1 to the id). IDs must not encode seed or index.

## Verifier / scanner constraints (all families)

- pytest-only tests; Hypothesis allowed with
  `@settings(derandomize=True, database=None)`.
- No network, subprocess, dynamic exec, parent paths, `~`, absolute host
  paths, `shutil.rmtree` (AST safety scanner rejects these).
- Deterministic large inputs inside test files via a hand-rolled LCG
  (`x = (x * 1103515245 + 12345) % 2**31`), never `random` without a fixed
  seed and never wall-clock-dependent values (perf budgets via
  `time.monotonic` deltas are allowed and established).
- Probe engine contract (`scoring/probes.py`, unchanged):
  - references tag family-defining edge lines with `# PROBE-DROP`; stripping
    them must yield code that fails verification
    (probe `<family>_edge_removed`);
  - optimization starters are the `naive_complexity` probe: correct but slow,
    must fail the hidden perf budget;
  - the `reference_return_none` mutation probe must also fail — avoid
    references whose functions can return None and still pass.

## Family specs

### parser_roundtrip (share 30%) — expand

Archetypes (axis `archetype`):

1. `escape_delim` (core): fields joined by DELIM; ESC escapes ESC and DELIM.
2. `quoted_fields` (core): fields containing DELIM are wrapped in QUOTE;
   QUOTE inside a quoted field is doubled (CSV-style).
3. `nested_groups` (stretch): records within a document; GROUP_DELIM between
   records, FIELD_DELIM between fields, one ESC escaping all three specials.
4. `keyed_fields` (stretch): `key=value` fields; parse canonicalizes
   (duplicate keys: last wins; keys sorted on format). Roundtrip law:
   `parse(format(d)) == d` and `format(parse(s))` is canonical.
5. `error_contract` (core): `escape_delim` plus a strict rule — dangling
   escape at end of input raises `ValueError` naming the position.

Other axes: theme (≥ 8 noun sets), DELIM (≥ 5), ESC/QUOTE (≥ 5, never equal
to DELIM). Pool comfortably > 400 combos.

Starter: `format_record` correct, `parse_record` naive (no escape/quote
handling) → fails hidden. Public: 2 example tests that the STARTER ALSO
FAILS (keep the family "starter fails somewhere public" property — this is a
fix-the-parser family, not spec-gap). Hidden: Hypothesis roundtrip property +
edge cases (empty fields, specials-only field, adjacent specials; error cases
for `error_contract`). Reference ≤ 60 lines. PROBE-DROP on escape/quote
handling lines.

### stateful_register (share 25%) — expand + harden

Interface: one module exposing `apply_commands(commands) -> list` (outputs
per command; compact, no classes). Archetypes:

1. `capacity_ledger` (core): add/remove/query with capacity + deterministic
   eviction rule (e.g. reject vs evict-lowest-priority).
2. `undo_register` (stretch): set/delete/undo with multi-level undo.
3. `txn_register` (stretch): begin/commit/rollback (single-level nesting) over
   set/delete; reads inside a txn see uncommitted state.
4. `idempotent_events` (core): events carry ids; duplicate ids are ignored;
   outputs report applied/skipped.
5. `expiry_store` (stretch): put with TTL; reads at explicit times; expired
   entries vanish exactly at boundary (inclusive/exclusive pinned by tests).

Axes: archetype × theme (≥ 8) × 1-2 rule knobs each (tie rule, capacity,
boundary rule). Pool > 150. Hidden tests include one long deterministic
script (30-60 commands, literal expected outputs — compute them from the
reference when authoring the template, embed as literals). PROBE-DROP on the
invariant branch (idempotency skip, rollback restore, expiry boundary).
Reference ≤ 80 lines.

### algorithmic_optimization (share 20%) — redesign upward

Every task: public correctness examples (small), hidden = (a) brute-force
cross-check at small/medium n (exact equality against an O(n²)-style `_brute`
embedded in the hidden test), (b) performance budget at large n
(`elapsed < 2.5` via `time.monotonic`), ideally at two scales. Starter is a
CORRECT naive implementation (passes public + brute check, fails budget).
Family test asserts the reference clears the large case in < 1.0s (≥ 2.5x
margin). `timeout_seconds=60` on the package.

Archetypes (chosen so the REFERENCE itself is fast in pure CPython — dict/
deque/sort-dominated; Fenwick/BIT-style references were rejected as too slow):

1. `window_spread` (core): longest contiguous window with max-min ≤ D.
   Reference: monotonic deques O(n). n ≈ 180-220k.
2. `distinct_window` (core): distinct-count aggregate over sliding windows of
   size W. Reference: dict counts O(n). Naive: `len(set(window))` per
   position. n ≈ 180-220k.
3. `event_rooms` (core): max simultaneous overlap from intervals.
   Reference: boundary sweep O(n log n) (C-speed sort). Naive per-interval
   scan O(n²) — brute-check case ≤ 3k. n ≈ 120-160k.
4. `kth_pair_gap` (stretch): k-th smallest |v_i − v_j| over all pairs.
   Reference: sort + binary search on answer + two-pointer count.
   n ≈ 50-60k (the two-pointer runs ~17·n Python steps — keep the reference
   well under 1.0s). Naive O(n²) is hopeless — brute-check case ≤ 1.5k.

Axes: archetype × theme (≥ 6) × parameter variant (≥ 3 size/limit tuples).
Pool > 70. Perf margins must be tuned so the reference is ≥ 2.5x under
budget on a laptop (assert in tests) and the naive starter exceeds budget in
Docker by a wide margin at the large scale.

### spec_gap_contract (share 15%) — expand under the invariant

Hard invariant (already test-enforced): STARTER PASSES ALL PUBLIC TESTS AND
FAILS ONLY HIDDEN TESTS. The gap rule is implied by prompt wording, never
exemplified publicly. `knob_deciding_examples:0`.

Gap archetypes: `tie_break` (never round toward X), `strict_reject`
(unknown/invalid input raises ValueError, never coerced),
`idempotent_retransmit` (duplicates ignored, first wins),
`boundary_inclusive` (inclusive bounds / equal-bounds pinning),
`minimal_cover` (touching spans merge), `stable_order` (equal-key order
preserved). Each with a theme (≥ 6) and small param knobs. Pool > 100.
Starter: the obvious-but-gap-violating implementation. Reference: gap lines
tagged PROBE-DROP so the family probe reproduces the starter's blind spot.
Keep the five redesigned 2026-07-03 variants as seed combos of their
archetypes (parameterized), not as special cases.

### multi_file_bugfix (share 10%) — harden materially, reduced share

3-4 files per task. Archetypes:

1. `coupled_pagination` (stretch): off-by-one in the paging module AND a
   second bug in the aggregator (e.g. paging applied twice / wrong order).
   Hidden tests fail unless BOTH are fixed; each single fix still fails.
2. `shared_state_alias` (core): mutable default argument / module-level list
   shared across calls; symptom only appears across repeated calls (hidden).
3. `stale_cache` (core): read cache not invalidated on update; hidden test
   interleaves update/read.

Starter = buggy code; reference = fixed. PROBE-DROP lines chosen so
stripping them reintroduces one bug (partial-fix probe). Axes: archetype ×
theme (≥ 6). Pool ≥ 18. Reference ≤ 100 lines total.

## Batch composition

`scripts/generate_v3_batch.py --total N --seed S --out DIR
[--band-mix core=0.7,stretch=0.3]`:

- Family mix (largest-remainder rounding): parser .30, stateful .25,
  optimization .20, specgap .15, bugfix .10.
- For each task: local reference verification (PytestRunner) must pass;
  scanner must be clean; incremental duplicate gate against the batch so far
  (score < 0.85) — any violation aborts with the offending pair named.
- Writes each task dir plus `batch_manifest.json`: generator version, seed,
  band mix, per-family counts, and per-task rows
  `{task_id, task_hash, family, archetype, band}`.
- Local/Docker only. Never calls providers.

Standard runs: 50 (15/12/10/8/5), 100 (30/25/20/15/10), 2000
(600/500/400/300/200 — requires sharding/resume, out of scope for this pass).

## Acceptance gates before any 2k run

Local (rehearsal, this pass): 100% references pass locally; Docker
verification on a ≥ 20% sample all `containerized=true`; probes 100% caught;
spec-gap and optimization starters pass public / fail hidden; intra-family
duplicate scores < 0.85 across the batch; scanner clean; size lint green;
deterministic regeneration reproduces identical hashes.

Paid calibration (later, operator-run): per family — infra+truncation < 5%
of attempts; clean-rate frontier yield ≥ 20%; ≥ 1 genuine failure from a
top-2 model in ≥ 10% of tasks; a task counts as gold only with ≥ 2 genuine
failures. Families that miss gates are excluded from the 2k composition, and
the mix re-normalizes over the survivors.

## Test plan

Shared (`tests/test_task_families.py`, updated): keep all current invariants
(validity, uniqueness, scanner, references pass, starter fails, probes,
size lint, spec-gap public/hidden invariant, calibration batch dup gate) and
add: seeded determinism (same seed → same hashes; disjoint seeds select
different subsets), cross-seed ID stability (same task_id → same hash), and
a 40-per-family uniqueness + duplicate-score sweep (no verification runs —
cheap). Per-family test files (`tests/test_family_<name>_v3.py`) own the
expensive checks on small samples (≤ 6 verifications per family per file).
Suite runtime must stay under ~7 minutes.
