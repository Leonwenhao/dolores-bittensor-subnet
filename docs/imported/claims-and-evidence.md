# Claims And Evidence

This file collects paper/story claims that must remain evidence-backed.

## Claim: The verifier/archive pipeline can preserve real provider-run provenance.

Evidence:

- Fireworks run `work/m12_fireworks_20260702_145212`.
- 10 solver attempts across DeepSeek V4 Pro and GLM 5.2.
- Solver rows recorded Docker/generated/containerized execution and log hashes.
- JSONL and HF-style exports included solver and verification rows.

Limitation:

- Only 5 simple template tasks and 1 attempt per solver.

## Claim: Simple static coding templates saturate frontier open coding models.

Evidence:

- DeepSeek V4 Pro solved 5/5.
- GLM 5.2 solved 5/5.
- All tasks had solve rate 1.0 and were classified too easy.

Limitation:

- One narrow task family; this does not characterize all easy benchmarks.

## Claim: The core product bottleneck is task difficulty generation.

Evidence:

- Infrastructure held during real provider calls.
- The failure mode was not provider, parser, Docker, archive, or export.
- The failure mode was lack of difficulty signal.
- Generator-v3 calibration
  `work/v3_fireworks_calibration_20260703_133658` showed that task-family
  difficulty remains the binding problem even after scalable generation:
  parser and bugfix produced useful frontier cells, while optimization,
  spec-gap, and stateful saturated the panel.

Limitation:

- The family mix is not ready to scale directly to 2k; generator v3 needs a
  revised composition and targeted redesign.

## Claim: Model-relative frontier calibration is required.

Evidence:

- P0 hardening added `solver_frontier` audit records.
- A task can be too easy for a frontier model and useful for a smaller model.
- Fresh Fireworks ladder
  `work/m12_fireworks_ladder_v2_20260702_180725` produced 14 accepted frontier
  tasks and 11 too-easy review tasks across five models and five task families.
- The same batch showed strong model skew: `gpt_oss_120b_floor` passed 24/25
  while `glm_5p2_frontier` passed 13/25, so family usefulness depends on the
  solver tier.

Limitation:

- The real ladder used one attempt per solver, so rates are directional rather
  than benchmark-stable.

## Claim: Dolores can preserve provenance in a real 25-task provider ladder.

Evidence:

- Fresh Fireworks ladder
  `work/m12_fireworks_ladder_v2_20260702_180725` completed 125 provider solver
  attempts.
- Archive provenance checks found zero successful solver rows without
  Docker/containerized execution and zero reference rows without
  Docker/containerized execution.
- HF Parquet and JSONL exports matched archive row counts: 25 tasks, 120 task
  files, 125 solver results, 25 scores, 25 lineage rows, and 25 verification
  runs.

Limitation:

- The v2 archive used frozen candidates and is useful mainly as a measurement
  correction baseline, not as a public dataset candidate.

## Claim: Generator v3 can produce useful frontier cells, but family quality is
uneven.

Evidence:

- Paid v3 calibration
  `work/v3_fireworks_calibration_20260703_133658` completed 50 tasks and 250
  solver attempts with 15 accepted frontier tasks, 34 too-easy review tasks,
  1 too-hard review task, and 0 rejected tasks.
- A later Fable audit reclassified those accepted labels by attempt-level
  evidence: 3 gold-standard frontier tasks, all
  `parser_roundtrip/nested_groups`; 3 accepted `error_contract` tasks plus
  1 too-hard task likely tainted by an unpinned error-position convention; and
  9 valid but boundary/mid-tier accepted tasks.
- Codex checked the key archive evidence in
  `work/v3_fireworks_calibration_20260703_133658/rehearsal.duckdb`:
  `error_contract` failures mostly share the same "1 failed, 4 passed"
  signature, while `nested_groups` failures are multi-test structural failures
  across multiple solvers.
- `multi_file_bugfix`: 3/5 accepted frontier labels, but each was a 0.80
  boundary single-failure case and the pool is only 18 combos.
- `algorithmic_optimization`: 0/10 accepted frontier tasks.
- `spec_gap_contract`: 0/7 accepted frontier tasks.
- `stateful_register`: 0/13 accepted frontier tasks.

Limitation:

- Current v3 should not be scaled directly to 2k. The honest launch claim is
  infrastructure proof plus a small verified-frontier subset, not a 2k
  frontier-difficulty catalog. Parser needs ambiguity/noise cleanup, bugfix
  needs pool expansion, and the saturated families need redesign or removal
  from the launch mix.

## Claim: Dolores can run a paid solver-panel calibration with exportable
dataset artifacts.

Evidence:

- V3 calibration archive includes 50 tasks, 226 task files, 250 solver
  results, 50 scores, 50 lineage rows, and 50 verification rows.
- HF and JSONL export manifests match archive row counts.
- Prime/verifier structural export was regenerated with all 15 accepted tasks.
- Export manifests now report panel-aware solver metadata limitations rather
  than stale mock-solver language.

Limitation:

- Export lifecycle filters, public-safe hidden-test policy, and cost accounting
  are still required before public release.
