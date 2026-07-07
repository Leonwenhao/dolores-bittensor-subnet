# Current State

Last updated: 2026-07-04

## Project Status

Dolores Autocurricula has moved beyond the original v0 plumbing proof. The
core verifier/archive/scoring/export pipeline works locally and with real
Fireworks solver calls, with finish-reason/truncation telemetry. Generator v3
is implemented: seeded deterministic combo engines across five families
(1,840-combo total pool vs the previous 25 hand-authored variants), a
composed batch generator with an auditable manifest, and a clean 50-task
local/Docker rehearsal (`work/v3_rehearsal_20260704`). The first paid v3
Fireworks calibration has now completed. The current bottleneck is revising
the family mix/difficulty from that calibration before 2k release mechanics.

## Current Gate

The fresh v2 25-task Fireworks ladder completed:

- Run dir: `work/m12_fireworks_ladder_v2_20260702_180725`
- Archive DB: `work/m12_fireworks_ladder_v2_20260702_180725/rehearsal.duckdb`
- Audit: `work/m12_fireworks_ladder_v2_20260702_180725/final_audit_summary.json`
- Original archive label: 14 accepted frontier tasks, 11 too-easy review tasks,
  125 solver attempts.
- Fable sanity-check: many accepted labels are likely truncation artifacts; the
  corrected result may be closer to 3 genuine frontier tasks and 22 too-easy or
  unclassifiable tasks.

Measurement fixes landed 2026-07-03 (Fable implementation pass; see
`build diary/entries/2026-07-03-003-measurement-fixes-truncation-classification.md`
and `fable research/outputs/2026-07-03-fable-solver-measurement-generator-difficulty-report.md`):

- [x] Fireworks `finish_reason` captured; failed length-finish attempts are
  classified `truncation_error`.
- [x] Prompt/completion token split recorded when the provider returns it;
  `token_usage` total preserved.
- [x] `truncation_error` added to the infrastructure-excluded clean solve-rate
  set; score audits expose per-class `excluded_class_counts`.
- [x] Solver prompt rewritten (system/user split, code-only contract, no
  trailing-period `path=solution.py.` example).
- [x] Bounded failed-output telemetry persisted (`output_hash`, `output_chars`,
  head/tail samples on failures).
- [x] `spec_gap_contract` redesigned: the gap is implied by the prompt and
  pinned only by hidden tests; a starter-passes-public/fails-hidden invariant
  test enforces this.
- [x] Reference-size lint added so no family requires cap-flirting output.

Paid re-baseline completed 2026-07-03:

- Run dir: `work/m12_rebaseline_20260703_094907`
- Report: `work/m12_rebaseline_20260703_094907/run_report.md`
- Audit: `work/m12_rebaseline_20260703_094907/final_audit_summary.json`
- Result: 3 accepted frontier tasks, 22 too-easy review tasks, 125 solver
  attempts.
- Error classes: `none=120`, `verification_failure=3`, `timeout_error=1`,
  `truncation_error=1`, `parse_error=0`.
- Accepted tasks: `parser_roundtrip_cargo_codec`,
  `parser_roundtrip_roster_codec`, `stateful_cart_register`.

Generator v3 landed 2026-07-04 (Fable orchestration + Opus subagents; see
`build diary/entries/2026-07-04-001-generator-v3-implementation.md` and
`docs/generator-v3-design.md`; Codex independent assessment recorded in
`build diary/entries/2026-07-04-002-fable-opus-orchestration-assessment.md`):

- [x] `src/dolores/proposer/families/` package with seeded combo engine
  (`propose_family(family, count, seed, band)`); pools: parser 1392,
  stateful 182, optimization 140 (redesigned upward), spec-gap 108 (invariant
  holds for all combos), bugfix 18 (coupled bugs).
- [x] `scripts/generate_v3_batch.py`: mix targets, core/stretch bands, hard
  local gates, `batch_manifest.json`.
- [x] 50-task rehearsal: deterministic regeneration (identical hashes), mock
  panel 50/0 rejected with all probes caught, Docker sample 16/50 all
  `containerized=true` incl. naive-starter budget failure in-container.
- [x] 197 tests passing; ruff clean.
- [x] Codex independently verified the generator package shape, pool sizes,
  50-task manifest mix and duplicate score, and generated a fresh 10-task v3
  sanity batch at `work/codex_sanity_v3_10_20260703`.

Fable + Opus orchestration pattern accepted 2026-07-04 (see
`build diary/decisions/ADR-003-fable-orchestrator-opus-subagents.md`):

- [x] Use Fable as principal architect/final reviewer for high-leverage,
  limited-window work.
- [x] Let Opus subagents handle scoped implementation/review work when useful.
- [x] Require Codex to independently verify concrete repo state and smoke paths
  after Fable returns.

Paid generator-v3 calibration completed 2026-07-03/04:

- Run dir: `work/v3_fireworks_calibration_20260703_133658`
- Report: `work/v3_fireworks_calibration_20260703_133658/run_report.md`
- Audit: `work/v3_fireworks_calibration_20260703_133658/final_audit_summary.json`
- Result: 50 tasks, 250 Fireworks solver attempts, 15 accepted frontier,
  34 too-easy review, 1 too-hard review, 0 rejected.
- Recorded tokens: 983,503 total (122,971 prompt, 860,532 completion).
- Family read: `parser_roundtrip` strong but noisy (12/15 frontier,
  1 too-hard, parser-heavy truncation/timeout); `multi_file_bugfix` useful
  but small (3/5 frontier); `algorithmic_optimization`, `spec_gap_contract`,
  and `stateful_register` saturated the panel.
- Infra attempts: `truncation_error=13`, `timeout_error=1`, slightly above the
  <5% target at 14/250 = 5.6%.
- Exports regenerated after fixing panel-aware export limitation text; targeted
  `pytest -q tests/test_export.py` passed.

Fable's salvaged task-family research and deeper v3 calibration audit landed
2026-07-04 (see
`fable research/outputs/2026-07-04-fable-task-family-design-deep-research-report.md`,
`fable research/outputs/2026-07-04-fable-v3-calibration-generator-strategy.md`,
and
`build diary/entries/2026-07-04-004-fable-salvaged-task-family-research.md`):

- The research report is useful but partially verified: 21 primary sources,
  104 extracted claims, and 13 claims adversarially verified before the
  original run hit the usage limit.
- The 50-task calibration should be framed as infrastructure proof plus a
  small verified-frontier subset, not as 15 strong frontier tasks.
- Attempt-level audit reclassifies the run into roughly 3 gold-standard
  frontier tasks (`parser_roundtrip/nested_groups`), 3 accepted parser
  `error_contract` artifacts plus 1 too-hard artifact, and 9 accepted
  boundary/mid-tier tasks.
- Codex checked the key archive evidence: `error_contract` failures mostly
  share the same "1 failed, 4 passed" signature, while `nested_groups` failures
  are multi-test structural failures; GLM 5.2 consumed 352,917 tokens with
  12 truncations and 1 timeout and no genuine verification failures.
- Revised direction: promote nested parser tasks, pin `error_contract`, expand
  bugfix, prototype execution-reasoning and inverse codec tasks, drop
  standalone spec-gap, remove launch-mix optimization, and redesign stateful
  around interacting invariants.

Still required before any larger paid batch or public HF dataset:

- Ask Fable/Codex to review the v3 calibration and produce a revised family
  plan: parser truncation/noise fix, parser too-hard diagnosis, bugfix pool
  expansion, and redesign/drop calls for saturated families.
- Add batch sharding/resume support so a 2k run does not depend on one long
  process.
- Add family-level acceptance targets and batch composition checks.
- Add export lifecycle filters: accepted-only, review-only, public-safe, and
  internal/full.
- Decide and implement the public-safe hidden test policy.
- Populate provider cost accounting; `cost_estimate` is still zero in the
  archive.
- Generate a model x family solve-rate report from the v2 archive.

## Last Known Good Evidence

- Generator v3 pass (2026-07-04): `ruff check .` clean, `pytest -q` 197
  passed, run_smoke/docker_smoke green, 50-task batch deterministic and
  gate-clean, mock rehearsal 50 processed / 0 rejected / all probes caught,
  16-task Docker sample all `containerized=true`. NOTE: `.venv` is a
  NON-editable install again (editable pth processing proved unreliable on
  this machine) — after source changes run
  `.venv/bin/pip install -q . --no-deps` before using the CLI or scripts.
- Codex independent generator-v3 assessment (2026-07-04): verified pool sizes
  (parser 1392, stateful 182, optimization 140, spec-gap 108, bugfix 18),
  verified 50-task manifest mix and max duplicate score 0.7875, and generated
  `work/codex_sanity_v3_10_20260703` successfully.
- V3 Fireworks calibration (2026-07-03/04): 50 processed / 15 accepted /
  35 review / 0 rejected; 250 solver rows; 50 Docker reference rows; HF/JSONL
  exports row counts match archive counts; verifier export includes all 15
  accepted tasks; `pytest -q tests/test_export.py` passed after export
  limitation text cleanup.
- Fable measurement-fix pass (2026-07-03): `ruff check .` clean, `pytest -q`
  128 passed, run_smoke and docker_smoke green, all five redesigned spec-gap
  references pass in Docker (`containerized=true`, generated mode).
- Fable parser/timeout/clean-score patch reported `ruff check .` clean,
  `pytest -q` 111 passed, smoke and Docker smoke green.
- Fresh Fireworks ladder completed in
  `work/m12_fireworks_ladder_v2_20260702_180725`.
- Archive contains 25 tasks, 25 scores, 125 solver rows, 25 reference
  verification rows, and 25 lineage rows.
- Successful solver rows not Docker/containerized: 0.
- Reference verification rows not Docker/containerized: 0.
- HF Parquet and JSONL export row counts matched archive counts.

## Active Direction

Generator v3 is implemented, locally rehearsed, paid-calibrated, and now
post-audited by Fable. Next: implement a generator v3.1/v4 pass before any 2k
generation. The minimum pass should pin parser `error_contract`, add audit
metrics for genuine failures and ambiguity signatures, update the panel/cost
path, expand bugfix, prototype execution-reasoning and inverse codec tasks, and
redesign or defer saturated families. Then run a 100-task local/Docker
rehearsal and only after that a small paid calibration. The Fable-orchestrator
workflow should be reused for Bittensor testnet subnet design and
implementation, with Codex checking concrete outputs afterward.
