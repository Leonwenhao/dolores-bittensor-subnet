# Dolores Autocurricula: A Bittensor Subnet Specification

## 1. Executive Summary

**Bottom line: Build the subnet as a "verifiable software-task proposer market" — miners submit complete, self-contained RL task packages; validators verify them deterministically in Docker and score them against a held-out solver panel for frontier usefulness — but do NOT ship the founder's exact framing as v0. The single highest-leverage change is to reward *frontier-calibrated, verifier-hardened tasks* (tasks where weak solvers fail and strong solvers pass, with tests that survive adversarial probing), not merely "novel valid tasks." This is the wedge no one else owns and it is directly monetizable outside crypto.**

The founder's instinct is ~80% right. "Miners propose verifiable software tasks; validators score them by safety, validity, novelty, verifier strength, and frontier usefulness against a solver panel" is the cleanest first subnet. It is the mirror image of Ridges (SN62), which rewards *solving* a fixed benchmark; Dolores rewards *producing* the benchmark. That complementarity is a genuine market gap: the open-RL ecosystem (Prime Intellect's Environments Hub, R2E-Gym, SWE-Gym, DeepSWE, SWE-RL) is bottlenecked on task/environment supply. A June 2026 paper ("Breaking the Solver Bottleneck," Wolf et al., Vmax/Goodfire AI) states this plainly: "The limiting resource for training agents via reinforcement learning (RL) is increasingly frontier task supply: valid, solvable tasks just difficult enough to train the current model."

Three refinements make it defensible:

- **Reward the frontier, not the task.** A task's value is its *discrimination* — the gap between weak-solver and strong-solver pass rates, combined with verifier robustness. This imports the "learnable frontier" objective from Absolute Zero (Zhao et al., 2505.03335) and PROPEL and makes trivial/impossible/duplicate spam worthless by construction.
- **Validators own the hidden tests and the private validation pool.** Miners never supply the ground-truth evaluation signal they are scored on. This is the ARC Prize / SWE-Bench Pro tiered model adapted to a live incentive market — the only credible defense against contamination and answer-leakage.
- **Keep the subnet a proving ground, not the company.** The subnet validates contributors and produces an open archive; Dolores Research monetizes hosted curriculum engines, private domain streams, and solver-panel eval infra off-chain. This split mirrors Rayon Labs (Chutes/Gradients) and Macrocosmos (Apex/Data Universe), the two most credible "company-behind-subnet" precedents.

**Confirmed facts** are cited throughout; **design recommendations** are labeled. The economics are grounded in the mid-2026 dTAO state, which materially shapes the launch plan:

- **Registration is a *burned*, non-recoverable cost.** Per Bittensor's official Dynamic TAO FAQ (docs.learnbittensor.org): "the cost to register the subnet is now burned, rather than being a lock cost returned to the subnet creator on de-registration." The most recent figure is ~1,500 TAO (~$470K, effective ~May 12, 2026, per Crypto Briefing, June 13 2026), dynamic (doubles per registration, decays over time). *Note:* some secondary outlets still describe registration as locked/recoverable — that reflects the pre-October-2025 regime and is contradicted by current official docs.
- **In-subnet emission split (confirmed):** per docs.bittensor.com/emissions, "At the end of each tempo (360 blocks)… 41% of emissions go to miners… 41% to validators (and their stakers), and 18% to the subnet's owner."
- **Subnet cap doubled 128 → 256** via the "Robin τ" expansion (May 2026, per CoinMarketCap); ~128–130 subnets were established/emitting around mid-2026.
- **Emissions are being concentrated among top subnets.** The May 13, 2026 "Conviction" emissions refactor concentrates TAO rewards among "roughly 30 productive subnets" and "adjusts future inflows based on prior emissions and buybacks" (TradingView News, 13 May 2026; abittensorjourney.com, "Navigating Bittensor: May 2026").

**Consequence for the plan: do not register a mainnet subnet until Stage 2.** The burn cost is real and unrecoverable, and emissions concentration means a new subnet must attract genuine stake/price signal to earn anything.

*(One factual conflict is flagged and left open in §12: whether the network reverted from the flow-based "Taoflow" model to a price-based model in June 2026. Sources disagree; I do not rely on a resolution of this for any recommendation.)*

## 2. Recommended v0 Subnet Design

### 2.1 North star

**v0 rewards exactly one thing: the marginal addition of a frontier-calibrated, verifier-hardened, novel software task to the validated archive.** One miner role. One artifact type. One deterministic-plus-stochastic scoring pipeline.

Rationale for a single role in v0:
- Multi-track incentive designs (proposers + solvers + verifiers + curators) are legible but they multiply the attack surface and validator workload. Every additional reward track is a new gaming vector and a new consensus-divergence risk under Yuma Consensus.
- Ridges (SN62) shows a single, sharply-defined artifact can reach open-source SOTA. Per SimplyTao: "Within four months of launch, the project achieved open-source state of the art on the full 500-question SWE-Bench Verified set with a score of 73.6%." Ridges later reported ~80% on SWE-Bench with "< $1M rewarded to miners" in ~45 days (Altcoin Buzz). The lesson is focus.
- Solving is already well-served (Ridges, DeepSWE). Verifier-improvement and curation fold into the *scoring* of the proposer artifact rather than paid as separate tracks (a good task package already *includes* a strong verifier).

### 2.2 Why not the alternatives

| Candidate north star | Verdict | Why |
|---|---|---|
| Miners solve tasks | Reject for v0 | Ridges/DeepSWE own this; no differentiation |
| Miners improve validators/verifiers | Fold into scoring | Verifier strength is a *component* of task score, not a track |
| Miners propose frontier tasks (weak fail / strong pass) | **Adopt as core** | The scarce asset; directly monetizable; hard to fake |
| Miners generate mutations | Allow, cap, track lineage | Useful for coverage but trivially spammed; must be diversity-gated |
| Metadata/taxonomy labels | Fold into scoring | A quality component, not a standalone reward |
| Duplicate/invalid detection | Validator function, not miner | Making this a miner task invites collusive self-dealing |

### 2.3 What "frontier-useful" means operationally

A task is frontier-useful when the **solver panel** (a fixed, validator-controlled set of open models of varying capability, run via a hosted provider such as Fireworks or Bittensor's own Chutes SN64) produces a pass-rate in a target band — neither trivial (all pass) nor impossible (all fail). The canonical target from the self-play literature is a solve rate near the middle of the 0–1 range: Self-play SWE-RL rewards injection tasks whose solver pass rate is mid-range, and PROPEL targets "1–3 of 8" passes. Dolores should target a configurable band (recommend panel pass@k in [0.15, 0.6]) plus a *capability gradient*: a stronger model should pass at a meaningfully higher rate than a weaker one. A task that is uniformly hard (all models near 0) is likely broken or ambiguous, not frontier.

**Critical correction to raw solve-rate:** solve failures from provider errors, parse errors, timeouts, or infra faults must be *excluded* from the pass-rate denominator, never counted as "model inability." The pipeline must classify every failed rollout as {genuine-fail, infra-fail, parse-fail, timeout} and compute frontier metrics only over genuine attempts.

## 3. Miner Spec

### 3.1 What a miner submits (the Task Package)

A single self-contained, content-addressed archive (recommend a signed tarball whose hash is committed on-chain; payload delivered off-chain to the validator to respect on-chain size limits). Schema (extends Dolores's existing MVP task package):

**Required**
- `prompt`: the natural-language task/issue statement.
- `starter_files`: repository skeleton or file set the solver begins from.
- `public_tests`: tests visible to everyone (solver guidance + open export).
- `reference_solution`: a patch/diff that provably passes all tests.
- `hidden_test_generator`: **not raw hidden tests** — a deterministic, seeded generator (or specification + oracle) from which the validator synthesizes held-out tests. See §5.
- `environment_spec`: Dockerfile or lockfile pinning the exact execution environment (base image, dependency hashes).
- `metadata`: domain, skill tags, difficulty estimate, task family ID, estimated solve rate, expected failure mode, license, provenance (source repo/commit or "synthetic"), and — if derived — `mutation_lineage` (parent hash + transformation).

**Optional / rewarded**
- `wrong_solution_probes`: candidate incorrect solutions that *should* fail (tests verifier robustness; a task whose tests pass a known-wrong solution is penalized).
- `alt_solution_probes`: valid alternatives that *should* pass (guards against over-tight tests that accept only the reference).

### 3.2 Should miners submit hidden tests directly?

**No.** Miners submit a *hidden-test generator or specification*; validators synthesize the actual held-out tests. Reasons:
- If miners supply exact hidden tests, they can leak them into the prompt/starter code, tune them only to the reference, or publish/sell them — destroying evaluation signal.
- A seeded generator lets the validator produce *fresh* test instances per evaluation, so the miner cannot memorize which concrete assertions will run.
- Where a generator is infeasible (many real SWE tasks have fixed tests), the miner submits the full suite but the validator **partitions** it: a randomly chosen subset becomes the private held-out set, never revealed, with the split seed validator-controlled and commit-revealed. This is the live-market adaptation of SWE-Bench Pro's public / held-out / commercial split and ARC Prize's public / semi-private / private eval discipline.

### 3.3 What prevents overfitting / answer-leakage

- **Prompt/starter scanning:** static + semantic scans detect the answer embedded in prompt, comments, or starter files. A task whose reference is trivially recoverable from the prompt is disqualified.
- **Held-out synthesis:** the scored signal (hidden tests) is never in the miner's hands.
- **Wrong-solution probes:** validators additionally generate their own mutated-wrong solutions (mutation testing) and require the verifier to catch them.
- **Provenance + license gating:** tasks carry license + provenance; suspicious provenance (e.g., verbatim copy of a known benchmark such as SWE-Bench Verified) is quarantined to prevent contamination laundering. This is a live concern: NIST's CAISI found real cases of "solution contamination and grader gaming" in SWE-bench agent evaluations, and OpenAI stopped reporting SWE-bench Verified over contamination/scaffolding concerns in early 2026.

### 3.4 Conceptual miner API

- **Request (pull model):** `{epoch_id, task_family_quota, schema_version, size_limit, time_limit}`. Recommend a *pull/submission* model (miner submits to a queue) rather than synchronous request/response, because task authoring is slow — matching Ridges (miners submit `agent.py`; validators pull) and Apex (solvers submit to competitions).
- **Response:** content hash committed on-chain + package uploaded to validator-accessible storage (S3-compatible), as Ridges does with agent code.
- **Size/time limits (recommend):** package ≤ 50 MB uncompressed; environment build ≤ 10 min; reference runtime ≤ 5 min wall-clock; per-miner submission quota per epoch (§5.3) to throttle spam.
- **Valid submission conditions:** schema-valid; builds deterministically; reference passes public + synthesized hidden tests; passes safety scan; non-duplicate.
- **Invalid/zeroed conditions:** see §5.2.
- **Specialization:** miners specialize by `task_family` (async bugs, type errors, concurrency, API-migration) and difficulty band; the diversity reward (§5) pays miners who fill under-covered families rather than piling onto saturated ones — the same "coverage-steering" mechanic Macrocosmos's Data Universe (SN13) uses to direct miners toward under-represented data buckets via a dashboard.

## 4. Validator Spec

Validators execute a deterministic pipeline with bounded stochastic stages, ordered so cheap disqualifiers run before expensive solver-panel runs.

1. **Schema validation (deterministic):** reject malformed packages.
2. **Safety scan (deterministic + policy):** static analysis for destructive operations, network exfiltration, fork bombs, secrets, or sandbox-escape attempts. Any unsafe construct → quarantine + zero. This protects validator infra running untrusted code — the concern Ridges addresses with no-internet Docker sandboxes and a controlled inference gateway.
3. **Deterministic build & environment pin:** build the Docker image from `environment_spec`; verify reproducibility (layer hashes).
4. **Reference-solution verification (deterministic):** reference must pass 100% of public tests.
5. **Public/hidden separation & hidden-test synthesis (seeded):** generate/partition held-out tests using a commit-revealed seed; reference must also pass these.
6. **Wrong-solution probes (deterministic + mutation):** run miner-supplied wrong probes and validator-generated mutants; verifier must fail all. Compute *verifier robustness* = fraction of wrong solutions correctly rejected.
7. **Alt-solution check:** run miner-supplied valid alternates; over-tight tests that reject valid solutions are penalized.
8. **Solver-panel evaluation (stochastic, controlled):** run the fixed panel N times each; classify every rollout as genuine-fail / infra-fail / parse-fail / timeout; compute pass-rates over genuine attempts only; compute frontier-band membership and capability gradient.
9. **Duplicate / novelty check (deterministic):** embed the task and compare against the DuckDB archive (prompt embedding, AST/structural fingerprint of starter+reference, test-shape hash). Near-duplicates within a family collapse; cross-family novelty is rewarded.
10. **Frontier classification & final score (deterministic given inputs):** combine components per §5.
11. **Archive writeback:** store task, all verifier/solver runs, scores, lineage, classification (accepted / negative-example / quarantined).
12. **Weight setting (commit-reveal):** publish per-miner weights via commit-reveal to defeat weight-copying.

**Determinism policy**
- **Must be deterministic:** schema, safety verdict, reference verification, wrong-solution rejection, duplicate detection, final score arithmetic. Independent validators must converge under Yuma Consensus — which "rewards subnet validators… for producing miner-value evaluations that are in agreement with the… evaluations produced by other subnet validators, weighted by stake," clipping out-of-consensus weights (docs.learnbittensor.org, Yuma Consensus).
- **Controlled-stochastic:** solver-panel rollouts (temperature=0 where possible; fixed seeds; average over N; identical panel snapshot across validators for an epoch, pinned by published hash).
- **Validator discretion (minimal, bounded):** only the final manual review of the *top* candidate before archive-promotion (as Ridges manually reviews its top agent for exploits/copying). Discretion must never set the numeric score directly, to preserve consensus.

**Commit-reveal is protocol-native and required.** Per docs.learnbittensor.org: the feature "uses Drand time-lock encryption to automatically reveal validator weights after a concealment period… prevents selective revelation attacks," solving the weight-copying problem whereby lazy validators free-ride on others' evaluations.

## 5. Scoring / Emissions Spec

### 5.1 Scoring components

A task's score is a staged pipeline — gates first, then a weighted quality score.

**Stage A — Hard gates (any failure → score 0):** safety, schema validity, reference passes, hidden tests hold (don't collapse), non-duplicate, solvable-by-≥1-panel-model, not-solved-by-all-weak-models, provenance acceptable.

**Stage B — Quality score (only for tasks passing all gates):**

```
Score = w_f·Frontier + w_v·VerifierRobustness + w_n·Novelty
      + w_c·Clarity + w_m·MetadataQuality + w_d·DiversityValue
```

Recommended initial weights (design recommendation, to tune): Frontier 0.35, VerifierRobustness 0.25, Novelty 0.15, DiversityValue 0.10, Clarity 0.08, MetadataQuality 0.07. Safety and validity are gates, not weighted terms.

- **Frontier** — closeness of genuine-attempt pass-rate to the target band + magnitude of the strong-vs-weak capability gradient.
- **VerifierRobustness** — fraction of wrong solutions (miner probes + validator mutants) correctly rejected, minus penalty for rejecting valid alternates.
- **Novelty** — embedding + structural distance from nearest archived task, discounted within an over-represented family.
- **DiversityValue** — marginal archive coverage: higher for under-covered families/difficulties.
- **Clarity** — unambiguity (proxy: agreement among panel models' interpretations; low variance in failure modes).
- **MetadataQuality** — completeness + verified-correctness of tags (validator checks claimed difficulty/family match measured behavior).

### 5.2 Disqualification conditions (Stage A gates)

Unsafe task; invalid/malformed package; reference fails; tests trivial (pass a no-op solution); hidden tests collapse (a stub passes them); duplicate/near-duplicate; unsolvable by *all* panel models (after excluding infra/parse/timeout failures); solved by *all* weak models (trivial); suspicious provenance (verbatim benchmark copy); low-quality/false metadata. **The infra-error exclusion is a first-class rule:** a task is "unsolvable" only if failures are genuine model failures, never provider/parse/timeout errors.

### 5.3 Aggregation & anti-spam

- **Reward marginal archive value, not volume.** A miner's epoch reward is driven by the *sum of marginal DiversityValue-weighted scores* of their accepted tasks, with steeply diminishing returns for near-siblings in the same family. This kills "many tiny variants" farming.
- **Best-of + top-k hybrid:** count each miner's top-k accepted tasks per epoch (recommend k = 3–5) to reward quality over dumping.
- **Duplicate families:** the first strong instance gets full credit; subsequent near-duplicates get sharply discounted (novelty × diversity both collapse).
- **Cold-start:** new miners get a small guaranteed evaluation quota (to prove themselves) but zero baseline emissions; reputation accrues from accepted-task history.
- **Reputation / historical quality:** maintain an EMA of each miner's acceptance rate and mean quality; use it to prioritize the evaluation queue (not to inflate score directly) so expensive solver-panel compute goes to likely-good submissions first.

### 5.4 Emissions design (protocol mechanics, not investment advice)

- **v0: one reward track (proposers only).** Validators earn the standard 41% validator share; miners (proposers) split the 41% miner share by Yuma-consensus weights; Dolores (subnet owner) receives the confirmed 18% owner share.
- **Aggregation into weights:** each validator computes per-miner scores, normalizes to a weight vector, and sets weights via **commit-reveal** so late validators cannot copy emerging consensus. Yuma clips out-of-consensus outliers and converts the stake-weighted median into miner emissions.
- **Avoid rewarding spam volume:** enforced by §5.3 (marginal value + top-k + diversity gating) + per-miner epoch quota.
- **Zeroing/penalties:** gate failure → 0 for that task; repeated safety violations → miner deprioritized in queue (soft ban); egregious/malicious submissions caught by the owner's manual-review backstop on the top candidate.
- **Future tracks (Stage 3+ only):** a separate solver-verification track or curation bounty may be added once the proposer market is stable — each must ship with its own anti-gaming analysis.

### 5.5 Epoch flow

1. Miners submit packages (hash on-chain, payload to storage) subject to per-epoch quota.
2. Validators pull, run the §4 pipeline, prioritizing by reputation queue.
3. The epoch's solver-panel snapshot is fixed and hash-published.
4. Validators compute scores, write to archive, set weights via commit-reveal.
5. Yuma Consensus resolves weights → emissions at tempo (≈360 blocks).
6. Accepted tasks enter the tiered archive (§6); exports run periodically.

## 6. Archive Lifecycle

The archive is Dolores's durable asset and the bridge between subnet and company.

1. **Candidate submitted** → content-addressed, stored in quarantine.
2. **Validator quarantines** unsafe/invalid → stored as rejected (with reason) for audit; never exported.
3. **Valid task enters review** → full verifier + solver-panel record attached.
4. **Frontier-useful tasks accepted** → promoted; **duplicate/weak tasks** stored as *negative examples* (training signal for the proposer models Dolores sells) or rejected.
5. **Tiered publication (recommend):**
   - **Tier 0 — Public archive (open by default):** prompt + public tests + reference for *retired* tasks. Exported to Hugging Face / JSONL / `verifiers`-compatible environments — the credibility/ecosystem asset.
   - **Tier 1 — Delayed release:** accepted tasks enter Tier 0 only after a delay (≥1 epoch) so they retain evaluation value first.
   - **Tier 2 — Held-out validator tests:** synthesized hidden tests, never published; rotated/retired over time.
   - **Tier 3 — Fresh private validation pool:** continuously refreshed, never-published tasks used purely for scoring current submissions (the anti-contamination reserve — ARC's "private eval" and SWE-Bench Pro's "held-out/commercial" pattern).
6. **Periodic exports** to HF/JSONL/verifier environments from Tier 0 only.
7. **Domain-specific streams** (finance, security, systems) curated *off-chain* by Dolores and sold/hosted as products — never emitted through the subnet.

**Metadata stored for auditability (per task):** full package hash + all file hashes; environment build hash; every verifier run (public/hidden/wrong/alt) with pass/fail + error-class; every solver-panel rollout with model, seed, outcome-class, tokens/cost; computed scores + component breakdown; novelty/duplicate neighbors; lineage; validator identity + weight set; timestamps; tier + publication status.

**Open by default vs held-out:** public prompts/tests/reference of retired tasks are open; hidden tests, the fresh private pool, solver-panel raw rollouts tied to unreleased tasks, and commercial domain streams stay closed.

## 7. Defensive Robustness Analysis

Risk classes for a lawful public protocol, each with a mitigation (no operational attack detail).

| Risk class | Why a rational miner might try it | Mitigation |
|---|---|---|
| Near-duplicate flooding | Cheap to mutate one task many times | Embedding+structural dedup; novelty×diversity collapse; top-k; per-family diminishing returns |
| Overfitting to the known solver panel | Panel is fixed within an epoch | Rotate/refresh panel across epochs; keep a *fraction* of panel identity secret; score gradient not absolute pass |
| Brittle tests (pass reference only) | Easy to write over-tight assertions | Alt-solution probes penalize false rejects; clarity term |
| Hidden answer in prompt/starter | Guarantees "solvability" | Prompt/starter answer-leak scanning; disqualify |
| Reference passes, valid alternates fail | Tests encode one implementation | Alt-solution probes required for high VerifierRobustness |
| Impossible/ambiguous tasks | Look "hard," inflate frontier naively | Capability-gradient requirement + ≥1-solver-passes gate; uniform-fail → reject |
| Many tiny variants | Volume farming | Marginal-value aggregation; quota; top-k |
| Exploiting validator disagreement | Divergent scores → higher expected reward | Deterministic scoring core; fixed panel snapshot hash; commit-reveal; Yuma clipping |
| Targeting model-specific parser weaknesses | Make a strong model "fail" spuriously | Error-class classification excludes parse/format failures from pass-rate |
| Tasks hard for the wrong reason (env flakiness) | Flaky infra looks like difficulty | Determinism checks; repeated runs; timeout/infra exclusion; reject nondeterministic tasks |
| Contamination laundering (resubmitting known benchmarks) | Known tasks are "known-good" | Provenance gating; dedup against imported public benchmarks; suspicious-provenance quarantine |
| Weight-copying by lazy validators | Free-ride on others' evaluation | Commit-reveal (Drand time-lock) — protocol-native |
| Collusion (validator favoring a confederate) | Inflate a miner's emissions | Yuma clipping of out-of-consensus bonds; deterministic scoring; owner manual backstop on top candidate |

## 8. Product / Company Positioning

**The split (sharpened)**
- **Dolores Research (the company):** builds and sells hosted curriculum infrastructure — proposer models, verifier-hardening tooling, solver-panel eval infra, domain-specific task streams. Raises equity, signs enterprise/on-prem deals. This is the business.
- **The Bittensor subnet (public proving ground):** a permissionless validation + contributor-acquisition mechanism that proves the curriculum thesis in the open, recruits a global network of task authors, and produces a credibility signal (open SOTA archive). Not the company's balance sheet.
- **The open archive (credibility + ecosystem asset):** open task sets exported to HF/`verifiers`, giving Dolores the standing Prime Intellect's Environments Hub and R2E-Gym enjoy.
- **Commercial products (off-chain):** hosted curriculum engine (continuously-updated task streams at a model's edge), private domain streams (finance/security/systems), solver-panel eval-as-a-service, data pipelines, enterprise/on-prem/verifier hosting.

**Precedents to copy:** Rayon Labs runs Chutes/Gradients/Nineteen as products with real off-chain revenue and an auto-staking buyback tied to product usage; Macrocosmos runs Apex (SN1) + Data Universe (SN13) with a commercial "Gravity" data product. Both prove a company can own a subnet without *being* the subnet. (Caution: Rayon's three subnets command ~23.7% of all emissions — a centralization concern the community actively names; Dolores should avoid appearing to farm emissions and instead show real usage.)

**What to say to each audience**
- **Bittensor accelerator team:** "We are the supply side of the RL-agent economy — the proposer market that feeds solver subnets like Ridges. Deterministic verification, commit-reveal, Yuma-friendly consensus, one clean artifact. We complement the coding-agent subnets, not compete with them."
- **Sentient Foundation / OpenAGI grant reviewers:** "We keep the *curriculum layer* open. Frontier labs hoard verifiable environments; we build the open, verifier-hardened task archive for open models — the missing public good." (Sentient Foundation's $42M Open Source AGI Grant and Investment Program, announced June 24, 2026 per GlobeNewswire/Forbes, is an explicit fit: two tracks — non-dilutive grants + founder-friendly investment — requiring ≥1 open component; founded by Polygon co-founder Sandeep Nailwal; Director of Venture and Growth Sachi Kamiya framed it as "A few companies are trying to become the OPEC of intelligence — meter it, price it, decide who gets it. We're making it air.")
- **Open-source contributors:** "Author tasks, earn from the archive, and see your work train open models via HF/`verifiers` exports."
- **Investors:** "The subnet is customer-acquisition and a credibility moat; the company monetizes hosted infra and private domain streams. Even if crypto is de-emphasized, the archive, the proposer models, and the eval infra stand alone."
- **Research collaborators:** "A live, adversarially-pressure-tested pipeline for frontier-task generation — a testbed for learnable-frontier and self-play research (Absolute Zero, PROPEL, SWE-RL)."

## 9. Comparable Projects and North Stars

**Bittensor subnets**
- **Ridges (SN62)** — *the* reference point. Miners submit software-engineering *agents*; validators run them on SWE-Bench/Polyglot in isolated Docker sandboxes with no internet and a controlled inference gateway; two "Screener" stages filter before three randomly-selected validators score; the top agent is manually reviewed for exploits/copying and earns emissions winner-take-all. Competition 22 (May 2026) approved only 9 of 419 agents (2.1%) and introduced a $0.29/problem cost cap. **Copy:** screener→validator funnel, Docker sandboxing, no-internet, inference gateway, manual exploit review, cost caps. **Avoid:** pure winner-take-all (wrong for a *supply* market — you want many contributors filling many families, not one winner).
- **Apex / SN1 (Macrocosmos)** — competition framework; supports miner-vs-miner and parallel competitions; explicitly building "anti-rigid" flexible task designs (Battleships PvP experiment, Dec 2025). **Copy:** competition-owner abstraction, versatile task framing.
- **Gradients (SN56, Rayon)** — single main validator + independent auditors for a training-competition subnet, with strict per-task time limits (text 3–10 h, image 1–2 h). **Copy:** "one strong validator + auditors" as a pragmatic cold-start for expensive evaluation; time limits. **Avoid:** over-centralizing validation long-term.
- **Chutes (SN64)** — serverless inference; the natural *solver-panel backend*. Per SimplyTao: "The entire SWE-Bench evaluation can be reproduced by anyone for as little as $1.26 for all 500 questions, using Bittensor's own Chutes subnet for inference." **Use as infra.**
- **Data Universe (SN13, Macrocosmos)** — contributor market for *data* with a dashboard steering miners toward under-covered buckets. **Copy directly:** the coverage-dashboard mechanic → Dolores's DiversityValue steering.

**Outside Bittensor**
- **Prime Intellect Environments Hub + `verifiers`** — the closest analog: a community hub for RL environments (dataset + harness + rubric), integrated with prime-rl and used to train INTELLECT-3/3.1. **Copy:** the `verifiers` environment spec as your *export target* (make Dolores tasks natively importable). **Don't compete on hosting** — be the incentivized *supply funnel* into that format.
- **R2E-Gym / SWE-Gym / SWE-RL / DeepSWE** — procedural SWE environment generation (R2E-Gym's SWE-GEN builds executable envs from commits via back-translation + test generation; 8.1K+ tasks across 13 repos; SWE-Gym uses repos disjoint from SWE-Bench to avoid contamination). **Copy:** synthetic curation recipes as miner tooling; contamination-avoidance by repo-disjointness. These are your miners' likely toolkits.
- **SWE-Bench Verified / Pro** — Pro uses a three-way public (731) / held-out (858) / commercial (276) split with GPL-licensed + proprietary repos to resist contamination and monitors public-vs-held-out score divergence (>~10 pts flags overfitting). **Copy the tiered split wholesale.**
- **ARC Prize** — public-training / public-eval / semi-private / private eval tiers; reports state-of-the-art "only on the Semi-Private and Private Evaluation task sets to reduce the risk of overfitting and data contamination"; open-source + compute-capped verification (<$10K, <12 h). **Copy:** private-eval discipline and "report only on held-out."
- **Absolute Zero / PROPEL / Self-play SWE-RL** — the theoretical backbone: propose tasks at the *learnable frontier*; reward learnability (mid-range solve rate), not raw novelty. AZR "self-evolves its training curriculum… using a code executor to both validate proposed code reasoning tasks and verify answers." **Copy:** the frontier objective as your core scoring signal; PROPEL's insight that solver-in-the-loop verification is expensive motivates your reputation-queue and (later) cheap difficulty proxies.
- **Kaggle / HF community benchmarks** — crowdsourced eval with private leaderboards. **Copy:** private-holdout hygiene.

## 10. Staged Launch Roadmap

**Stage 0 — Local MVP (before any subnet work).** *Goal:* prove the scoring pipeline end-to-end offline. *Must be true:* task-package schema frozen; Docker pytest verification deterministic; solver-panel runs against open models via Fireworks/Chutes with error-class classification working; frontier/verifier-robustness/novelty scoring implemented; DuckDB archive with tiers; HF/JSONL/`verifiers` exports working. *Success:* the pipeline ranks a mixed batch sensibly and rejects planted bad tasks (trivial, impossible, leaky, duplicate, brittle). *Stop/go:* identical scores across two independent machines (determinism proven). **Do not spend the burn until this holds.**

**Stage 1 — Testnet subnet.** *Goal:* minimal miner/validator loop on Bittensor testnet (free test TAO), one task family (e.g., Python bug-fix). *Miner:* submit packages via CLI. *Validator:* full §4 pipeline, mock emissions. *Artifacts:* protocol message schema, commit-reveal wired, archive writeback. *Success:* honest miners rank above planted adversarial miners; low weight divergence. *Risks:* solver-panel cost/latency; nondeterminism. *Stop/go:* two independent validators produce consensus-compatible weights on identical submissions.

**Stage 2 — Public mainnet beta.** *Goal:* register the mainnet subnet (spend the ~1,500-TAO burn), open to real miners. *Miner:* real submissions, multiple families. *Validator:* diverse independent validators; reputation queue live; cost caps. *Artifacts:* public Tier-0 archive + HF exports; contributor dashboard (coverage map à la Data Universe). *Success:* growing accepted-task archive across ≥5 families; measurable frontier-band hit rate; open exports downloaded/used. *Risks:* gaming waves (run §7 playbook); validator centralization; earning enough emissions given the top-~30-subnet concentration policy. *Stop/go:* archive quality holds under adversarial load; ≥N independent validators.

**Stage 3 — Mature curriculum network.** *Goal:* multiple domains, richer solver panels, paid hosted infra, research partnerships. *Behavior:* domain-specialized miners; optional second reward track (with its own anti-gaming spec). *Artifacts:* commercial domain streams (off-chain), enterprise eval infra, lab/hub partnerships. *Success:* off-chain revenue; archive cited/used in open-model training; usage-tied buyback (à la Rayon). *Risks:* subnet/company boundary blur; staying in the emissions top tier.

## 11. Codex Implementation Plan

Conceptual/architectural — module names, responsibilities, interfaces, milestones. Assumes a small team, Python 3.12+, Docker, UV, DuckDB, the existing Dolores MVP.

**Repo modules to add**
- `dolores_protocol/` — shared schemas: `TaskPackage`, `VerifierRun`, `SolverRollout`, `Score`, `ArchiveRecord`; (de)serialization; content-hashing; on-chain commit payload builder.
- `dolores_miner/` — CLI + toolkit to author, locally validate, and submit packages; local dry-run harness running the *public* portion of the validator pipeline so miners self-test before submitting (mirrors Ridges `miner run-local`).
- `dolores_validator/` — the §4 pipeline as ordered, independently-testable stages: `schema`, `safety`, `build`, `reference_verify`, `heldout_synth`, `wrong_probes`, `alt_probes`, `solver_panel`, `dedup_novelty`, `score`, `archive_writeback`, `weights`.
- `dolores_solverpanel/` — inference adapters (Fireworks, Chutes, local vLLM); rollout runner; **error-class classifier** (genuine/infra/parse/timeout); pass-rate + gradient computation.
- `dolores_archive/` — DuckDB layer; tier management (0–3); export adapters (`jsonl`, `huggingface`, `verifiers`); negative-example store.
- `dolores_sim/` — offline simulation harness: synthetic honest + adversarial miners; determinism checker; scoring-distribution reports.
- `dolores_dashboard/` — coverage map, family/difficulty heatmap, leaderboard, per-task audit view.
- `dolores_chain/` — Bittensor SDK glue: registration, metagraph, commit-reveal `set_weights`, submission-hash commits.

**CLI commands**
- `dolores miner init | validate-local | submit`
- `dolores validator run [--stage …] | replay <task_hash>`
- `dolores archive export --tier 0 --format {jsonl,hf,verifiers}`
- `dolores sim run --miners honest,adversarial --check-determinism`

**Milestones**
1. **M1 — Schemas + offline pipeline (Stage 0):** `dolores_protocol`, `dolores_validator` stages, `dolores_solverpanel` with error-class classifier, `dolores_archive` tiers + exports. Smoke: score a fixed task set identically on two machines.
2. **M2 — Simulation + anti-gaming (Stage 0/1):** `dolores_sim` with adversarial miners covering every §7 risk class; assert honest > adversarial; assert planted-bad tasks are gated.
3. **M3 — Testnet loop (Stage 1):** `dolores_chain` (register on testnet, commit-reveal weights), `dolores_miner` submission path, storage integration. Smoke: two validators reach consensus-compatible weights.
4. **M4 — Mainnet beta (Stage 2):** reputation queue, cost caps, dashboard, public exports, validator onboarding docs. Checklist below.
5. **M5 — Hardening/scale (Stage 3):** panel rotation, secret-fraction panel, domain families, optional second track.

**Tests & smoke checks**
- Determinism test (same inputs → same scores across machines/runs).
- Gate tests (each disqualifier triggers correctly on planted tasks).
- Error-class classifier unit tests (infra/parse/timeout never counted as model-fail).
- Consensus test (independent validators' weight vectors within Yuma tolerance).
- Export round-trip test (Tier-0 task imports cleanly into `verifiers`).

**Testnet deployment checklist**
- Wallet coldkey/hotkey set up per Bittensor security guidance (never commit keys).
- Register subnet on testnet with test TAO; set hyperparameters (`tempo`, `commit_reveal_weights_enabled=True`, `commit_reveal_period`).
- Stand up ≥2 validators + ≥3 miners; storage bucket; solver-panel snapshot pinned by hash.
- Run one full epoch; verify archive writeback, exports, and commit-reveal weight setting; confirm determinism and consensus.

## 12. Open Questions and Highest-Risk Assumptions

1. **Solver-panel cost & latency is the central economic risk.** Every submission requires N rollouts across a multi-model panel; agentic SWE rollouts "can take tens of minutes" (PROPEL). If per-task evaluation cost approaches per-task reward, the subnet is uneconomic. *Mitigations to prototype:* reputation-gated queue, cheap difficulty proxies (PROPEL-style activation probes) before full panel runs, Chutes for cheap inference. **Stress-test in Stage 0.**
2. **Determinism vs. realism.** Real SWE tasks are somewhat nondeterministic (flaky tests, timing). Over-strict determinism gates reject good tasks; too loose invites flakiness gaming. The right threshold is unknown.
3. **Panel rotation vs. comparability.** Rotating the panel defeats overfitting but breaks cross-epoch score comparability. Needs a versioning/normalization scheme.
4. **Winner-take-all vs. broad distribution.** Ridges' winner-take-all suits a *solving* race; a *supply* market likely needs broad distribution to fill many families — but breadth invites spam. The exact aggregation curve (top-k, diminishing returns) needs empirical tuning.
5. **Emissions concentration policy (confirmed trend, unresolved impact).** The May 13, 2026 refactor concentrates rewards among "roughly 30 productive subnets" (TradingView News). A new subnet must attract genuine stake/price signal to earn. *Assumption:* the archive's open credibility + company backing can attract enough stake. Unproven.
6. **The price-vs-flow emissions-model question is unresolved in sources (FLAG).** My research surfaced a claim that Bittensor reverted from the flow-based "Taoflow" model to a price-based model in June 2026 (attributed to the learnbittensor.org emissions doc), but other sources (abittensorjourney.com; TradingView, 13 May 2026) describe the "Net TAO flow" model as active/extended via the May refactor. I could not reconcile these. **Verify the live emissions-allocation basis via `btcli` / current official docs before making any staking or registration-timing decision.** No recommendation in this report depends on which is true; both agree that a subnet can receive ~0% emissions if it attracts no stake/flow.
7. **Registration timing.** The burn cost (~1,500 TAO, dynamic, non-recoverable) means mistiming is expensive. *Assumption:* Stages 0–1 de-risk enough to justify Stage-2 registration. Confirm live cost with `btcli subnet burn-cost --network finney` immediately before registering.
8. **Contamination arms race.** As Tier-0 tasks are published they contaminate future evals; the fresh private pool must be replenished faster than it leaks. Sustainability at scale is unproven.
9. **Legal/licensing of derived tasks.** Tasks derived from real repos carry license obligations; provenance gating helps but compliance for commercial domain streams is nontrivial. (SWE-Bench Pro's use of GPL/proprietary repos is a contamination *feature* but a commercial *constraint* — Dolores must be careful which licenses enter paid streams.)
10. **Overlap risk with Prime Intellect.** If the Environments Hub adds incentivized contribution, Dolores's wedge narrows. *Assumption:* the Bittensor-native incentive + verifier-hardening + frontier-calibration focus is differentiated enough. Monitor.

---

*Confirmed facts are attributed to named sources inline (Bittensor official docs, Ridges/Macrocosmos/Prime Intellect docs and repos, arXiv papers, and dated 2026 reporting). All scoring weights, schema fields, tier structures, API shapes, and roadmap thresholds are labeled design recommendations to be empirically tuned. The one material source conflict (price-vs-flow emissions model) is flagged in §12 and no recommendation relies on its resolution.*