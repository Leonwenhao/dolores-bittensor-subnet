# Fable M5/M6 Readiness Review — 2026-07-08

Reviewer: Fable (lead architecture/release-readiness reviewer), orchestrating
five bounded Opus 4.8 review slices (chain implementation, M5 evidence,
next-action decision, docs/claims hygiene, public-testnet go/no-go) and
personally verifying load-bearing claims. Repo reviewed at branch
`m4-blocked-runbooks`, HEAD `b38fa67` ("rehearse m5 localnet path"), clean
tree; implementation commit under review `1b33f44` ("add m6 chain dry-run
readiness"). No signing/spend/extrinsic command was run anywhere (localnet
included); all public-chain reads used `--network test`; no implementation
code was modified.

---

## 1. Executive Verdict

**M6 chain-readiness is implemented correctly.** The chain-implementation
slice returned three clean verdicts, each of which I re-verified against my
own full read of `src/dolores_subnet/chain.py` and `neurons/validator.py`:
**GATES: SUFFICIENT** (the only SDK `set_weights` call site, `chain.py:452`,
sits behind a four-layer AND gate; the dry-run path returns at `chain.py:416`
before the gate and can never sign), **IMPORT-DISCIPLINE: INTACT** (module top
bittensor-free; the blocker test now instantiates `SubtensorChain` with a fake
substrate), and **DEFAULT-SIGN-PATH: NONE** (every default — `build_chain_client
publish="off"`, validator `--chain off`, preflight `dry-run` read-only — is
non-signing). 61 tests pass, ruff clean. Findings are P2-only.

**M5 partially passed, and the partial is healthy, not a blocker.** The
rehearsal proved live RPC through our `_Substrate` facade against a real
chain, a real preseeded-subnet read (`apex`, netuid 1), the correct fail-closed
`validator_unregistered` receipt with `submission: null`, arm64 container
operation, and a replay-verifiable localnet epoch. Everything it did not prove
(register/stake/permit/live `set_weights`/dry-run happy path) is
signing-gated by design — the evidence slice confirmed nothing achievable
without signing was left undone, because **the dry-run happy path itself
requires a validator permit** (verified first-hand: `_readiness_skip_reason`
runs at `chain.py:377` before the dry-run branch at `:416`).

**Public testnet is advisable AFTER one prerequisite, not immediately.** The
go/no-go slice found nothing broken — code gates green, RPC healthy
(sub-second reads), budget plausible at the freshly re-read 1.0 τ burn — but
five operator items are open, and the substantive one is the full-M5
decision.

**Recommended next action: Option A — complete the full M5 localnet signing
rehearsal (Leon-supervised, ~30–45 minutes), then go public.** Rationale
(adjudicated across slices 3 and 5): every *code-path* failure on public
testnet is cheap and recoverable — the single expensive, irreversible failure
is operator error on the one-shot `btcli subnet create` (~1 τ burn + a ~2-day
rate-limit window), and the only mitigation for that is rehearsing the
identical command sequence, which the partial M5 did not touch (zero signing
happened). Full M5 also exercises, at zero TAO, the three real-substrate seams
mocks cannot cover: `process_and_convert` against a real metagraph, the real
`Subtensor.set_weights` call, and `_submission_from_response` parsing a real
`ExtrinsicResponse`. Localnet runs fast blocks (487→1153 within the short
rehearsal session), so the tempo wait is minutes, not 72. If the hackerhouse
clock becomes binding, the sanctioned fallback is the create-early interleave
(public create first, localnet rehearsal during the public tempo wait) — no
code risk depends on the ordering, only the create-rehearsal benefit.

---

## 2. Closure Review for `1b33f44`

### What is correct (verified with file:line evidence)

- **Gate audit.** Execution must pass, in order: all-zero short-circuit
  (`chain.py:331`), netuid guard (`:350`), read-only readiness state (`:363`
  — subnet exists, validator registered, permit, rate-limit, commit-reveal),
  non-empty hotkey mapping (`:397`), the dry-run return (`:416`, *before* the
  gate — dry-run can never reach `set_weights`), then the four-layer AND gate
  (`_missing_extrinsic_gates`, `:619-629`): `allow_extrinsics=True` (default
  False) + `DOLORES_ALLOW_EXTRINSICS=1` env (the keystone — not settable from
  repo code) + `publish=="live"` + `confirmation == "I-AM-LEON-AND-I-APPROVE"`.
  Any miss → `error/extrinsics_not_allowed` with a receipt naming the missing
  gates, no submission. The TTY prompt lives in the CLI
  (`validator.py:185-196`) with `--confirm-live` as the non-TTY fallback,
  exactly per the design adjudication.
- **Network safety.** Constructor calls `assert_safe_network` before any
  bittensor touch (`chain.py:244`); `_Substrate` is built lazily (`:257`).
  Finney/mainnet/unset remain categorically unreachable.
- **Import discipline.** Module top of `chain.py` imports only
  hashlib/json/os/dataclasses/typing/config; the two `import bittensor` sites
  are inside `_Substrate.__init__` (`:87`) and `process_and_convert`
  (`:172-173`). `test_import_discipline` now instantiates `SubtensorChain`
  with a fake substrate under the blocker and reaches `dry_run`.
- **Determinism.** The receipt writer mkdirs its own directory (`:574-575`,
  resolving the plan's epoch.py ordering gotcha with no change to `epoch.py`);
  the `weight_result` embedded in the deterministic artifact carries only
  `{receipt_file, payload_digest, netuid, n_uids}` (`:609-614`) — no volatile
  fields; `payload_digest` is sha256 over the canonical sorted payload
  (`:662-664`); volatile data (chain state, submission, block numbers) is
  quarantined in `chain_receipt_epoch_N.json`; replay ignores it (verified by
  `test_receipt_file_is_separate_and_replay_stays_stable` and re-verified live
  by the M5 evidence slice: `REPLAY OK` on the on-disk localnet artifact).
- **Fail-closed mapping.** Unregistered miners drop into `dropped_hotkeys`
  (`:304-316`); validator-unregistered is an `error` (`:511-515`); an empty
  map is `skipped/no_registered_miners` (`:397`); `version_key` pinned to
  `spec_version` at the call site (`:455`).
- **Config safety.** `netuid` precedence CLI > `BT_NETUID` env >
  `configs/testnet.json` (TESTNET mode only); non-int and negative netuids
  rejected with `ConfigError`.
- **NullChain contract.** Byte-identical to before; offline/wire artifacts and
  their tests untouched.

### What is risky / missing (all P2 — none blocks M6 start)

| id | Finding | Evidence |
| --- | --- | --- |
| R1 | **`read_back_weights` is a stub returning `None`** (found first-hand; corroborated by slice 3). Even a successful live submit writes `read_back: null`. The receipt's read-back field is vestigial; operator-flow step 10's read-back MUST be the separate manual metagraph poll, and the field should not be cited as evidence. Optionally implement before public step 10; not blocking. | `chain.py:199-201` |
| R2 | Reason vocabulary is a strict subset of the plan: `version_key_mismatch` and `rpc_timeout` are never emitted; extrinsic failures collapse to `extrinsic_failed`, readiness exceptions to `rpc_unreachable`. No wrong emissions — just coarser diagnosis on live failures. | `chain.py:369,375,462-488` |
| R3 | Test gaps: no test for the `rpc_unreachable` exception path; no direct constructor-refuses-finney test (covered only transitively via `assert_safe_network` unit tests); `version_key==1` never asserted although the fake captures it; live-submit test does not assert receipt `submission`/`read_back` contents. | `tests/test_chain_client.py` |
| R4 | `test_live_gates_block...` relies on `DOLORES_ALLOW_EXTRINSICS` being absent without `monkeypatch.delenv` — fails loudly (not silently) if a shell has it exported, but is non-hermetic. | `test_chain_client.py:298-320` |
| R5 | Honest framing: the four gates prevent *accidental/default/CI* signing, not a determined actor with shell control (the confirmation literal is public source; the env var can be self-set). The categorical guarantee is `assert_safe_network` — finney/mainnet are impossible, test/localnet extrinsics are procedurally gated. This matches the design intent but should be understood as procedural, not cryptographic. | `chain.py:13,619-629` |
| R6 | **Design consequence, not a defect:** `dry_run_ok` is unreachable without a registered validator *and* a permit, on any chain (readiness check precedes the dry-run branch). The first real `dry_run_ok` can only occur post-registration — on localnet if we do full M5, otherwise first on public testnet at step 8 with create/register/stake already sunk. This strengthens the case for full M5. | `chain.py:377,416,511-524` |

**Are the safety gates sufficient?** Yes, for their stated purpose — no
default, test, CI, preflight, or dry-run path can sign; live requires four
independent opt-ins including one (the env var) that cannot originate from
repo code; and the network allowlist is enforced before any SDK touch. R5's
caveat is inherent to any non-cryptographic gate and matches the threat model
(preventing accidents, not insiders).

---

## 3. M5 Evidence Review for `b38fa67`

### What was actually exercised (all evidence re-verified on disk)

- Live RPC through `_Substrate`/`bt.Subtensor` against a real chain — blocks
  advanced 487→1153→1319 across the session's reads.
- Read of a real, preseeded subnet: `apex`, netuid 1, owner `5C4h…`, single
  uid 0 — discovered, not created.
- The fail-closed path end-to-end in production shape: preflight and
  `apply_weights` both returned `validator_unregistered`; the receipt
  (personally read) shows `mode: error`, `submission: null`,
  `read_back: null`, `active_hotkey_to_uid: {}`, both miner hotkeys in
  `dropped_hotkeys`, `chain_state.block: 1153`, `subnet_exists: true`.
- A full real localnet-mode epoch behind it: 4 genuine submissions,
  Docker-verified (`containerized: true`, ~105 s), deterministic weights,
  `REPLAY OK` re-run live during this review.
- arm64 container operation (image digest `592aa28…`, already pulled, 777 MB).
- Clean teardown: ports 8091/8092/9944/9945 clear; `work/` gitignored, zero
  tracked files in the run dir; secret-pattern scan clean.
- The `b38fa67` preflight change is a **healthy compat fix**, not a weakened
  check: bittensor 10.5.0 exposes `bt.Subtensor` (capital S); the new code
  prefers it, falls back to the deprecated lowercase form, and FAILs if
  neither exists — with a new test pinning the behavior.

### The 0.512/0.488 weights — provenance resolved

The receipt's `normalized_weights` put miner-1 (spammer persona, 0.5116)
above miner-0 (honest, 0.4883). This is the **genuine output of a real
epoch**, not a synthetic vector: with fresh seeds (501/502 vs M4's 201/202),
the spammer's first submission — by definition novel — legitimately cleared
verification (task_value 0.896) while its second was rejected, and the honest
miner's second landed in `review` (0), leaving 0.896 vs 0.856. Not a scoring
regression; it never mattered to the chain path, which fail-closed before any
submission. "static_dry_run" means *static miner endpoints + chain dry-run
flag*, not static weights. **Doc fix D-1:** the diary reports these numbers
without noting they invert M4's clean 1.0/0.0 result or explaining the seed
change — a skim reader could misread it; one clarifying sentence needed.

### What was not exercised

No extrinsic of any kind, anywhere: no create/start/register/stake, no permit,
no live `set_weights` through the gates, no dry-run happy path (unreachable
without a permit — R6), no hotkey→uid mapping with registered keys, no live
rate-limit behavior, no real `ExtrinsicResponse` parsing, and no
metagraph-based miner discovery (miners used static endpoints;
`neurons/miner.py` still supports only offline/wire modes — noted as a gap for
the public flow, where miners likewise can run on static endpoints, so not
blocking).

### Is partial M5 acceptable?

**Yes — HEALTHY-PARTIAL** (both the evidence slice and my own reading concur).
Every gap is signing-gated by design and stops exactly at the boundary the
safety rules impose; the code did everything it could do without a signature,
and did it correctly against a real chain. The partial is a *checkpoint*, not
a substitute: the remaining rehearsal value (§4) is real.

---

## 4. Next-Step Decision

**Option A — full M5 localnet signing rehearsal first. Recommended.**

Cost/benefit (from the decision slice, cost table verified against the
irreversibility analysis):

- **What failure costs on public testnet if we skip (Option B):** a dry-run
  payload bug is found at step 8, read-only, free to re-run — annoying only. A
  live `set_weights` bug costs a fee and a rate-limit wait. A uid-mapping bug
  costs one wrong epoch, overwritten next epoch. An unattainable permit
  strands the ~1 τ create burn but the stake is recoverable. **None of these
  requires redoing the create.** The one expensive failure is botching the
  one-shot `create` itself (burn + ~2-day rate-limit window) — an *operator*
  risk that only command rehearsal mitigates, and the partial M5 rehearsed
  zero commands.
- **What full M5 buys:** the create/start/register/stake command sequence
  rehearsed end-to-end; the three never-exercised real-substrate seams
  (`process_and_convert` with a real metagraph, real `set_weights`, real
  response parsing) validated at zero TAO; first real `dry_run_ok` (R6 makes
  this impossible any other way pre-permit); qualitative permit-attainability
  with our 3-hotkey topology. Wall-clock ~30–45 min (localnet fast blocks make
  the tempo wait minutes), Leon at keyboard ~20–30 min. The image is already
  pulled.
- **Option A-minus (register on the preseeded `apex` instead of creating):
  rejected.** It still requires stake + tempo for a permit (R6), so it saves
  only the create/start steps — which are precisely the rehearsal value — and
  measures the permit against apex's hyperparameters, not the defaults a fresh
  create produces.
- **Option B (public now): rejected but close.** Defensible if the clock
  forces it — the code risks are all recoverable — but it goes public with the
  real-substrate weight path never exercised anywhere and the irreversible
  create command never rehearsed.
- **Option C (more implementation first): rejected.** Nothing on the P2 list
  blocks; R1 (read-back stub) is worked around by the manual metagraph poll
  and can be implemented after the localnet rehearsal proves the rest.
- **Sanctioned fallback — interleave:** if hackerhouse time binds, do the
  public create first and run the localnet rehearsal during the ~72-minute
  public tempo wait. No code risk depends on ordering; the only loss is
  rehearsing create before spending it.

Residual risk accepted under Option A: localnet chain constants (permit
threshold, registration burn) may not transfer to testnet — mitigated by the
5.0 τ recoverable first-stake convention; public commands still run for the
first time on public, with rehearsed muscle memory rather than guarantees.

---

## 5. Public Testnet Operator Checklist

Go/no-go status today (from the operator slice; live reads re-run this
session: burn-cost **1.0 τ** fresh, balance **10.0 free / 0 staked** confirmed
on-chain, RPC sub-second):

**GREEN (9):** 61 tests · ruff · import discipline · preflight testnet mode
(reachability PASS, readiness correctly SKIPs while netuid unset) · M5 partial
documented · create affordable at fresh burn · RPC healthy · rate-limit
warning documented · rollback rules documented (lost receipt → re-query,
never blind-retry create).

**OPEN (5):** the full-M5 decision (resolved by this review: **complete it**,
per §4) · post-create budget re-check (registration burn R readable only after
create; permit threshold unmeasured until M5) · H5 identity strings
(`--subnet-name`/`--github-repo`/`--subnet-contact` fold irreversibly into
create — finalize and record before the signing window) · H4 approval against
a go-time burn re-read · H6 Leon at keyboard.

**Budget arithmetic and NO-GO thresholds** (S_max = 10.0 − C − 3R − 0.5
reserve − 0.1 fees): at C=1.0 and R≤1.0, the 5.0 τ first-stake fits with
0.4–1.4 τ headroom. **NO-GO triggers:** R > ~1.13 τ (5.0 stake no longer
fits — reduce stake or reassess at STOP-LEON S3), or a burn-cost spike at
go-time that squeezes S_max below any plausible permit threshold. Stake is
recoverable; C and 3R are not.

**Flow with STOP-LEON gates** (full detail in the runbook; verified against
the implemented flags):

0. Preconditions — pytest/ruff/preflight ×3 hotkeys (agent).
1. Chain preflight: fresh burn-cost, balance, subnets list, all
   `--network test` (agent).
2. **STOP-LEON S1** — approve create vs fresh burn; identity strings final;
   one-shot rate-limit acknowledged.
3. **LEON S2** — `btcli subnet create --network test ...` (+identity flags);
   agent read-back (`subnets show` owner check), record netuid in
   `configs/testnet.json`. Lost output → re-query before any retry.
4. Agent polls `check-start`; reads hyperparameters for real registration
   burn R → **STOP-LEON S3** budget re-confirm → **LEON S4** `subnets start`.
5. **LEON S5** — register validator, miner-0, miner-1 (read-back between
   each; uid↔hotkey map recorded).
6. **LEON S6** — `stake add --safe --tolerance 0.05`, amount informed by the
   M5 measurement (else 5.0 τ), ≥0.5 τ kept free.
7. Agent waits ≥1 tempo (~72 min), polls metagraph until `validator_permit`
   is True for `5DyN…CLdm`. No weight epoch before True.
8. Agent dry-run epoch:
   `neurons/validator.py --mode testnet --netuid <N> --chain dry-run --epoch 1
   --quota 2 --work work/m6 --wallet.name dolores-test --wallet.hotkey
   validator` → receipt `mode: dry_run`, `submission: null`.
9. **STOP-LEON S7** — Leon reviews the dry-run vector, then runs live:
   `export DOLORES_ALLOW_EXTRINSICS=1` + same command with `--chain live
   --allow-extrinsics --confirm-live I-AM-LEON-AND-I-APPROVE` → expect
   `mode: submitted` with block/extrinsic hash in the receipt's `submission`.
10. Agent read-back via **manual metagraph poll** (NOT the receipt's
    `read_back` field — R1): validator's weight row matches the artifact
    within u16 quantization.
11. Agent records: config status update, diary, budget actuals. `testnet-v0`
    tag only on receipt + matching read-back — **STOP-LEON S8**.

Signing steps (S2, S4, S5, S6, S9) are LEON-ONLY forever; the agent prepares
exact command strings and runs every read-only step.

---

## 6. Claims Hygiene

The docs/claims slice returned **CLEAN — zero misleading claims**; all five
states (partial M5 / dry-run-readiness M6 / no public subnet / no on-chain
weights anywhere / no permit) are accurately distinguished everywhere, and the
two highest-risk strings were already correctly updated in the commits
(`configs/testnet.json` `chain_client` field; demo-script chain note).

**Can be said now:** the full validator loop runs locally (offline + wire) with
Docker-backed verification, adversarial gates, EMA weights, replay-verified
artifacts; the chain layer exists with read-only, dry-run, and four-way-gated
live tiers, 61 tests; the fail-closed chain path was proven against a real
localnet chain (real RPC, real preseeded subnet, `validator_unregistered`
receipt with null submission); the localnet container runs on this machine;
10.0 test TAO funded, burn cost read at 1.0 τ.

**Cannot be said yet:** any registration, permit, stake, dry-run *success*
(`dry_run_ok` has never occurred — R6), live `set_weights` anywhere (localnet
included), "M5 complete", "M6 complete", "on testnet".

**After full M5 localnet:** "the complete create→register→stake→permit→
set_weights→read-back loop has executed end-to-end against a real chain, with
receipts" — always qualified *localnet*.

**After public subnet creation (steps 3–5):** "registered public testnet
subnet, netuid N, owned by our coldkey" — not "live", no weights/permit claims
until steps 7–10.

**Only after a live `set_weights` receipt + matching metagraph read-back:**
"on-chain weights on public Bittensor testnet, receipt in repo" — and only
then `testnet-v0`. Fallback outcomes are recorded as human-blocked/diagnosed,
never "failed". Still never claimable: emissions, public miners, mainnet
readiness, training-improvement results.

**Doc fixes queued (all small):** D-1 the M5 diary seed/weights transparency
sentence (§3); D-2 plan status line still says "gated on real chain-client
code" (now stale — code exists); D-3 README "dry-run artifacts" → "fallback
artifacts and one fail-closed error receipt", and README's M5 line should say
"partial done"; D-4 runbook: mark the chain-code precondition complete, add
`--subnet-name` and `--safe --tolerance` to the M6 command examples; D-5
m7-demo-lock diary internal "(superseded)" marker.

---

## 7. Subagent Appendix

Five Opus 4.8 slices in parallel; I reconciled and personally verified the
load-bearing claims.

- **Slice 1 — chain implementation:** full gate-audit trace; verdicts GATES
  SUFFICIENT / IMPORT-DISCIPLINE INTACT / DEFAULT-SIGN-PATH NONE; findings
  F1–F4 (P2: missing reason emissions, test gaps, non-hermetic env test,
  procedural-not-cryptographic framing). Missed the `read_back_weights` stub,
  which I found in my own read and slice 3 independently confirmed.
- **Slice 2 — M5 evidence:** verdicts HEALTHY-PARTIAL / MATCHES-DIARY;
  resolved the 0.512/0.488 provenance (real epoch, fresh-seed artifact, not a
  regression, not synthetic); confirmed the preflight tweak is a fail-closed
  bittensor-10.5 compat fix; re-ran replay live (`REPLAY OK`); secret scan and
  gitignore hygiene clean.
- **Slice 3 — next action:** recommended Option A (full localnet rehearsal,
  sequential), rejecting A-minus (apex registration forfeits the create
  rehearsal and still needs stake+tempo) and pure B; produced the
  failure-cost table showing the one-shot create as the only expensive
  irreversible risk; surfaced the two load-bearing code facts (dry-run
  requires permit; read-back stub).
- **Slice 4 — docs/claims:** CLEAN, zero P1; six P2/P3 fixes (D-1…D-5 above
  consolidate them); CLI/flag cross-check of runbook vs implemented code came
  back consistent; SS58/netuid usage consistent, no apex/public conflation.
- **Slice 5 — go/no-go:** fresh live reads (burn 1.0 τ, balance 10.0,
  endpoint sub-second); checklist 9 GREEN / 5 OPEN / 0 BLOCKED; budget
  arithmetic with NO-GO thresholds (R > ~1.13 τ at C=1.0); exact code-derived
  dry-run and live invocation strings; verdict ADVISABLE-AFTER-X where X = the
  M5 decision + H5 strings + go-time human gates.

**Disagreements adjudicated:** slice 3 argued for completing full M5; slice 5
was neutral ("record waive-vs-complete"). I adopted slice 3's recommendation —
the create-rehearsal argument plus R6 (dry-run unreachable pre-permit) plus
the never-exercised real-substrate seams tip it decisively, at a ~30–45 minute
cost — with the create-early interleave as the explicit fallback if time
binds. No other slice conflicts arose; slice 2's seed-artifact explanation and
slice 3's code findings were mutually consistent.

**Personally verified by me (Fable):** full read of `chain.py` post-`1b33f44`
(single `set_weights` call site `:452`; four-gate check `:619-629`; dry-run
return `:416` precedes the gate; readiness check `:377` precedes dry-run — R6;
receipt mkdir `:574-575`; deterministic receipt reference `:609-614`;
`read_back_weights` stub `:199-201`; `version_key=spec_version` `:455`); full
read of `neurons/validator.py` (flag surface, `_live_confirmation` TTY prompt
`:185-196`, lazy bittensor imports in `run_wire`/`run_chain`, module-top
import of chain symbols safe because `chain.py` stays bittensor-free); the M5
chain receipt JSON on disk (mode/reason/null submission/dropped hotkeys/block
1153); `git show --stat` for both commits (`1b33f44` code+tests+docs;
`b38fa67` docs+compat-fix+test); clean tree at HEAD.

No extrinsic, no signing, no spend, no mainnet/finney contact, and no
implementation-code modification occurred during this review.
