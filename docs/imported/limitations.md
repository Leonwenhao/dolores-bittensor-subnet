# Limitations

## Current Limitations

- The first real Fireworks run used only 5 simple template tasks and saturated
  frontier models.
- The fresh 25-task Fireworks ladder used only 1 attempt per solver.
- The corrected 25-task re-baseline showed most frozen v2 tasks were too easy.
- The 50-task v3 calibration produced 15 accepted frontier labels, but a later
  attempt-level audit reduces the defensible gold-standard frontier subset to
  roughly 3 tasks, all `parser_roundtrip/nested_groups`; the rest are
  boundary/mid-tier labels or likely `error_contract` specification artifacts.
- `algorithmic_optimization`, `spec_gap_contract`, and `stateful_register`
  saturated the v3 calibration panel and should not be scaled as-is.
- `parser_roundtrip` remains noisy: parse errors are solved, but
  truncation/timeout pressure exceeded the <5% infra target.
- The v3 calibration included one `parser_roundtrip` too-hard task and three
  accepted `error_contract` tasks that should be treated as ambiguity-tainted
  until the 0-based/1-based error-position convention is pinned and retested.
- Exact provider billing must be reconciled in the Fireworks dashboard.
- Per-solver calibration currently lives in audit JSON, not a normalized table.
- `cost_estimate` is zero in the archive despite paid provider usage.
- Export limitation text is now panel-aware, but lifecycle filters and
  public-safe hidden-test policy are still missing.
- Clean solve-rate exclusion now exists, but provider/output noise must still be
  monitored per family.
- The task-family generator system is validated as a seed, not yet validated for
  thousands of public HF tasks.

## Near-Term Mitigations

- Revise generator-v3 into a v3.1/v4 family mix using the paid calibration
  and Fable audit evidence.
- Pin parser `error_contract` conventions and add ambiguity-signature audit
  metrics before the next paid run.
- Expand bugfix if it stays in the public mix.
- Prototype execution-reasoning and inverse-codec families before speculative
  schema/data migration.
- Redesign or drop saturated optimization, spec-gap, and stateful families.
- Use a laddered panel for dense and frontier signal.
- Inspect ladder inversions manually.
- Add cost accounting, export lifecycle filters, and public-safe hidden-test
  policy before publishing.
- Keep Docker/generated mode as the verifier gate.

## Paper Framing Caveats

- Do not claim Dolores broadly challenges DeepSeek/GLM across all task
  families. The current evidence is narrower: a small set of nested parser
  tasks generated structural failures, while most other families saturated.
- Do not claim 15 strong frontier tasks from the v3 calibration. The archive
  has 15 accepted labels under the current scorer, but the defensible
  gold-standard subset is smaller after manual audit.
- Do not claim training improvement until a post-training experiment exists.
- Do not overclaim security; frame the current verifier as hardened and
  provenance-aware, not production-perfect isolation.
- Frame the current result as model-relative curriculum signal, not a solved
  frontier benchmark.
