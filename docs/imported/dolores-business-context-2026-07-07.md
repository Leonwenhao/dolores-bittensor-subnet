# Dolores Research / Autocurricula Business Context

Date prepared: 2026-07-07  
Prepared from: current chat context plus project materials in `/Users/leonliu/Desktop/Dolores Autocurricula`  
Scope: business/product/positioning context for future chats in this project folder  
Excluded by request: Fireworks run cost estimates

## 1. Retrieval Target And Assumptions

This note captures the reusable business context for Dolores Research and
Dolores Autocurricula so future chats can start from the same framing. It is
not a full strategy report, market scan, or implementation plan. It is a
source-backed context layer: what the project is, why it matters, what has
actually been built, what evidence exists, what should not be overclaimed, and
which source documents should frame future analysis.

Assumptions:

- The authoritative project source is the local Dolores Autocurricula repo at
  `/Users/leonliu/Desktop/Dolores Autocurricula`.
- Current project state is taken from the build diary and run artifacts as of
  2026-07-04.
- Fable research memos are useful business/research inputs, but market facts in
  those docs are time-sensitive and should be refreshed before external use.
- The next business question will likely involve alpha launch, Sentient grant
  framing, Bittensor testnet positioning, open-source contributor strategy, or
  fundraising narrative.

## 2. Source Hierarchy

Use this priority order when sources disagree:

1. **Live repo state and run artifacts** for what was built, tested, and
   measured.
2. **Build diary / STATE** for current project direction, gates, and decisions.
3. **Claims and limitations notes** for what can be said publicly without
   overclaiming.
4. **Fable research outputs** for strategy, research synthesis, and
   positioning options.
5. **Older planning docs** for intent, not current truth.

Core source files:

- `/Users/leonliu/Desktop/Dolores Autocurricula/build diary/STATE.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/build diary/paper-notes/claims-and-evidence.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/build diary/paper-notes/limitations.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/build diary/notebooklm-next-batch.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/docs/release-framing-scratchpad.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/docs/generator-v3-design.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/fable research/outputs/2026-07-02-fable-dolores-research-strategy-memo.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/fable research/outputs/2026-07-02-fable-dolores-product-roadmap.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/fable research/outputs/2026-07-02-fable-bittensor-subnet-research.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/fable research/outputs/2026-07-04-fable-v3-calibration-generator-strategy.md`
- `/Users/leonliu/Desktop/Dolores Autocurricula/fable research/outputs/2026-07-04-fable-task-family-design-deep-research-report.md`

## 3. The Business Thesis

The strongest Dolores thesis is:

> Frontier and open model labs are moving from static data toward RL on
> verifiable tasks. The bottleneck is not merely having many environments; it
> is having verified, deduplicated, difficulty-labeled tasks near a model's
> capability frontier, with enough provenance to trust the result. Dolores
> Research builds the open curriculum layer for that: proposer systems,
> verifier-hardened archives, solver-panel scoring, and exportable datasets.

The sharper version for investors and grant reviewers:

> Dolores builds the verifier-hardened task archive and proposer stack for
> RLVR. The open engine creates credibility and community distribution; the
> company monetizes hosted curation, provenance-certified domain task streams,
> and solver-panel evaluation infrastructure.

Important positioning choice:

- **Do lead with:** verifier-hardened archive, frontier scoring, provenance,
  task quality, reproducible scorer, open artifact.
- **Do not lead with:** generic "AI curriculum layer," vague "proposer
  models," or crypto-token economics.

## 4. Company / Product / Protocol Split

Keep these separate in future positioning:

### Dolores Research

The company. It should be framed as the entity that builds and eventually sells
hosted curriculum infrastructure:

- hosted task curation/scoring engine;
- provenance and verifier-quality audits;
- domain-specific task streams;
- proposer/scorer infrastructure;
- private/customer-specific curriculum pipelines later.

### Dolores Autocurricula

The open-source engine and dataset pipeline. Current function:

- validate task packages;
- verify references in Docker;
- evaluate solver panels;
- score frontier usefulness;
- store lineage/audit rows in DuckDB;
- export Hugging Face-style datasets, JSONL, and verifier-compatible artifacts;
- support a public/read-only dashboard.

### Bittensor Subnet

The public adversarial proving ground and contributor-acquisition channel, not
the whole business. The current best framing is:

> A testnet task-supply market where miners propose verifiable software-task
> packages and validators score them for validity, verifier robustness,
> novelty, and frontier usefulness.

Mainnet should not be treated as a dependency for the alpha release or the
company's fundraise story. Testnet is enough for the hacker-house proof of
concept.

### Open Archive

The credibility asset. It should live on Hugging Face/GitHub with:

- full dataset card;
- reproducible scorer;
- public task packages;
- provenance metadata;
- model-panel results;
- technical report.

## 5. Current Build State

The project has moved beyond initial plumbing. The repo now has:

- a working verifier/archive/scoring/export pipeline;
- Docker/generated-mode verification with fail-closed behavior;
- Fireworks solver-panel support with finish-reason and truncation telemetry;
- generator v3 with deterministic seeded task families;
- DuckDB archive rows for tasks, solver runs, verification, scores, and lineage;
- HF/JSONL/verifier exports;
- build diary and paper notes for evidence tracking.

Current system-of-record status from `build diary/STATE.md`:

- Generator v3 has been implemented, locally rehearsed, paid-calibrated, and
  post-audited.
- The next step is **not** a 2k run. It is a generator v3.1/v4 pass:
  parser/error-contract fixes, audit metrics, panel/cost path, bugfix
  expansion, execution-reasoning and inverse-codec prototypes, and redesign or
  deferral of saturated families.
- After that: 100-task local/Docker rehearsal, then a small paid calibration.

## 6. Evidence We Can Use

Strong evidence:

- The verifier/archive pipeline can preserve provider-run provenance.
- Docker/generated-mode execution and archive provenance are central product
  strengths.
- The system can run real solver-panel calibrations and export usable dataset
  artifacts.
- v3 proved the generator architecture can create task families and archive
  them, but also showed family quality is uneven.
- Task difficulty generation is the current product bottleneck, not archive
  plumbing.

Current v3 calibration facts:

- 50 tasks.
- 250 solver attempts.
- 15 accepted frontier labels under the current scorer.
- 34 too-easy review tasks.
- 1 too-hard review task.
- 0 rejected tasks.
- Later Fable/Codex audit: only about 3 tasks are defensible
  gold-standard frontier tasks, all `parser_roundtrip/nested_groups`.
- `error_contract` parser tasks are likely ambiguity-tainted until the
  0-based/1-based error-position convention is pinned and retested.
- `algorithmic_optimization`, `spec_gap_contract`, and `stateful_register`
  saturated the panel and should not be scaled as-is.

Best honest public framing:

> Dolores has a working provenance-complete curriculum pipeline and early
> evidence that it can generate small verified-frontier cells. The next
> milestone is expanding from a small frontier subset into a larger,
> family-balanced public archive without overclaiming difficulty.

## 7. What Not To Claim Yet

Avoid these claims until stronger evidence exists:

- "We have 2k frontier tasks."
- "The v3 calibration produced 15 strong frontier tasks."
- "Dolores broadly challenges DeepSeek/GLM across all task families."
- "The scorer predicts training improvement."
- "The verifier is production-perfect security isolation."
- "The Bittensor subnet is the company."
- "The task proposer model is already the moat."

Safer versions:

- "The archive has accepted labels, but manual audit identifies a smaller
  gold-standard frontier subset."
- "The current evidence is narrow but real: nested parser tasks produced
  structural failures, while most other families saturated."
- "The verifier is hardened, fail-closed, and provenance-aware."
- "The scorer is transparent and auditable; predictive training value is a
  future ablation."
- "Bittensor is a validation and contributor channel."

## 8. Task-Family Direction

Current task-family read:

- **Parser/round-trip codec:** flagship family. Promote nested groups, add
  inverse/streaming variants, pin error-contract conventions.
- **Multi-file bugfix:** promising but small-sample. Expand from 18 combos to
  120+ before trusting it for a large share.
- **Execution reasoning:** first new family to prototype. Examples:
  predict-output, find-the-input, induction from examples.
- **Inverse codec:** strong new axis for parser tasks.
- **Stateful systems:** redesign around interacting invariants, not longer
  scripts.
- **Spec-gap:** drop as standalone; fold validated hidden behavioral contracts
  into other families.
- **Algorithmic optimization:** current forms are too canonical; remove from
  launch mix unless redesigned into something less retrieval-saturated.

Business implication:

The launch story should be about **measured, tiered task archives** and
methodology honesty, not just task count.

## 9. Alpha Launch Shape

Credible alpha release should include:

- public GitHub repo;
- HF dataset snapshot;
- reproducible scorer/export pipeline;
- technical report or blog;
- dataset card with complete sections;
- dashboard or HF Space;
- clear contribution guide;
- selected task-family examples;
- claims-and-limitations section.

The dataset should be tiered:

- `frontier-verified`;
- `mid-tier-verified`;
- `review`;
- `unverified` or mock-only;
- quarantine/rejected internal rows not pushed as public claims.

Important pre-release blockers:

- generator v3.1/v4 pass;
- 100-task local/Docker rehearsal;
- small paid calibration;
- sharding/resume for large generation;
- family-level acceptance targets;
- export lifecycle filters;
- public-safe hidden-test policy;
- cost accounting, even if not part of this note;
- full-batch duplicate verification.

## 10. Sentient / OpenAGI Context

Best Sentient framing:

> Dolores Autocurricula is open public-goods infrastructure for RLVR:
> an open engine and archive that supplies verified, frontier-calibrated tasks
> to open models, with provenance and reproducible scoring.

Why it fits:

- open-source component is central, not cosmetic;
- Sentient cares about open agentic/reasoning infrastructure;
- Dolores can produce public artifacts: dataset, scorer, proposer, report,
  verifier-quality benchmark;
- the work helps open models compete with closed labs' internal RL pipelines.

Recommended ask structure:

- grant track first;
- alpha artifact as proof;
- proposal organized around open archive, reproducible scorer, task generator,
  and later Bittensor testnet as distribution/proving ground.

Do not make the Sentient ask dependent on Bittensor mainnet.

## 11. Investor / Raise Context

The raise story should be artifact-first:

> Here is a live open archive, a reproducible scorer, real solver-panel
> provenance, early frontier cells, and a clear path to community-scaled task
> supply. We are building the quality/provenance layer for RL task generation.

Best wedge:

- verifier-hardened task archive;
- transparent scorer;
- provenance and dedup;
- frontier-calibrated task families;
- open-source distribution;
- Bittensor as supply-side validation.

Likely objections:

- "Is this just Prime Intellect?"
  - Answer: Prime Intellect hosts environments and infra; Dolores scores,
    verifies, deduplicates, and certifies which tasks are worth training on.
- "Does the score predict training value?"
  - Answer: not claimed yet. First prove panel-relative difficulty and
    verifier quality; downstream training ablation is later.
- "Why open source?"
  - Answer: distribution, credibility, contribution flywheel; moat becomes
    archive, methodology, hosted engine, and domain streams.
- "Why crypto?"
  - Answer: not required. Bittensor is a public adversarial proving ground and
    contributor market, not the company thesis.

## 12. Bittensor Testnet Context

Ambitious Bittensor pitch:

> Solver subnets need hard tasks. Dolores is the supply side: miners propose
> verifiable software tasks; validators run them through Docker, held-out tests,
> wrong-solution probes, dedup, and a solver panel; the best tasks enter an open
> archive that can train and evaluate open agents.

MVP testnet scope:

- one artifact type: task package;
- one miner role: proposer;
- validator runs the existing Dolores verification/scoring pipeline;
- mock or small real solver panel;
- public dashboard of accepted tasks and contributor rankings;
- no mainnet economics required.

What ports from Dolores Autocurricula:

- task schema;
- Docker verification;
- safety/provenance model;
- wrong-solution probes;
- solver-panel scoring;
- archive lifecycle;
- duplicate gates;
- export pipeline;
- dashboard concepts.

What must be added:

- Bittensor miner/validator protocol;
- task submission queue;
- scoring-to-weights mapping;
- held-out/private evaluation policy;
- anti-spam and per-miner quotas;
- commit-reveal or equivalent anti-copying design;
- validator determinism checks;
- public testnet dashboard.

## 13. Open-Source Contributor Context

The open-source contributor pitch:

> Contribute verifiable tasks, probes, task-family generators, and verifier
> improvements that enter a public archive used by open-model researchers.

Contributor mechanisms to prioritize:

- "good first task" list by task family;
- task package templates;
- CI that validates schema/reference/tests;
- public acceptance criteria;
- contributor leaderboard;
- clear route from PR to archive inclusion;
- optional Bittensor rewards later.

Do not ask contributors to understand the whole research thesis before
contributing. Give them narrow task/probe/generator lanes.

## 14. NotebookLM Context

NotebookLM should be used as a synthesis layer, not a raw artifact dump.

Upload in batches after meaningful milestones. Prefer Markdown summaries and
reports over raw JSON, DuckDB, Parquet, or JSONL exports.

Current next-batch sources:

- build diary current state;
- v2 measurement correction docs;
- v3 generator docs;
- v3 Fireworks calibration report;
- Fable v3 calibration strategy;
- Fable salvaged task-family research;
- claims/evidence and limitations;
- scorer/archive methodology;
- product roadmap;
- strategy memo;
- Bittensor subnet research.

Do not upload:

- `.env`;
- credentials;
- raw DuckDB;
- raw final audit JSON;
- raw JSONL exports unless NotebookLM support changes.

## 15. Unresolved Decisions

Open decisions that will shape future business analysis:

- What exact alpha dataset size is credible after v3.1/v4?
- Should the alpha ship 2k total tasks with a smaller verified-frontier subset,
  or delay until frontier-family yield is higher?
- How should public hidden tests be handled: withheld, delayed, or published
  only for retired tasks?
- What is the official frontier band for public labeling: current `[0.20,
  0.80]`, a tighter RL-signal band, or multiple tier definitions?
- Which solver panel replaces or shadows GLM 5.2?
- Which first customer/Sentient demo surface matters most: dataset, dashboard,
  scorer reproducibility, or Bittensor testnet?
- Does the first public release include an open proposer model, or is that
  deferred until after the archive/scorer are stable?

## 16. Future-Chat Starting Point

For future chats, assume this baseline unless newer build diary entries say
otherwise:

- Dolores Research is the company.
- Dolores Autocurricula is the open engine/archive.
- Bittensor is a testnet/proving-ground and contributor channel.
- The strongest current claim is infrastructure/provenance plus early
  verified-frontier evidence, not large-scale frontier dataset completion.
- The next development gate is generator v3.1/v4 and a 100-task local/Docker
  rehearsal.
- The next business gate is a credible alpha source pack: GitHub, HF dataset,
  scorer, dashboard, technical report/blog, and clean limitations.

