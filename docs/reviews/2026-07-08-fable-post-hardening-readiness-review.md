# Fable Post-Hardening Readiness Review — Dolores Bittensor Subnet

Date: 2026-07-08. Reviewer: Fable (orchestrator), with four Opus 4.8 subagent
review slices (fix verification, artifact evidence, docs/claims, next-phase
planning). Scope: closure of the prior review
(`docs/reviews/2026-07-08-fable-implementation-conformance-review.md`) after
Codex's hardening commit `39f75f7 harden m4 wire readiness`, plus a next-phase
recommendation now that 10.0 test TAO has arrived on the coldkey.

Safety posture during this review: no extrinsics, no signing, no spend, no
wallet-material access, no paid calls. The only public-chain touch was two
read-only queries with explicit `--network test` (burn cost; both run and
independently re-verified by me).

---

## 1. Executive Verdict

**Is M4 now sign-off ready?** **Yes — sign off M4 as "local wire mode
complete."** Every M4-blocking finding from the prior review (F-01, F-02,
F-04-as-gate, F-05, F-06, F-07) is closed with code, tests, and fresh on-disk
artifacts; I verified the load-bearing fixes first-hand and an independent
artifact slice reproduced the replay checks. Two hardening items are honestly
*partial* (the response-size cap runs after transport deserialization; the
serialization test is in-process Pydantic, not a measured axon/dendrite
ceiling) — these are M6 public-exposure residuals, recorded below, not M4
blockers. Scope the sign-off precisely: **real signed axon/dendrite transport
between local processes with static endpoints, chain-free** — not metagraph
discovery, not chain weights.

**Is the project ready to move forward?** Yes. Git tree clean at `39f75f7`,
44 tests pass, ruff clean, all three wire preflights pass (all re-verified
this session), documentation errs toward understatement rather than
inflation, and the Deviations Appendix is finally in order.

**What should the next phase be?** In order: **(1) finish M7 to
"demo-locked"** (timed clean-clone rehearsal + pre-recorded fallback capture —
hours of work, protects the guaranteed hackerhouse deliverable), **(2) build
the real `SubtensorChain` client behind the existing allowlist** (the single
remaining load-bearing code gap; needed by both M5 and M6; no extrinsics
until Leon approves), **(3) M5 localnet rehearsal** to exercise that code at
zero cost, **(4) M6 public testnet, human-gated as ever**. A material
economics update supports this: the plan's ~100 TAO subnet-creation estimate
is obsolete — live query today shows **`btcli subnet burn-cost --network
test` → 1.0 τ** (btcli 9.x replaced the returnable lock with a recycled
burn). The 10 test TAO on hand is plausibly sufficient for our own subnet.
Section 5 has the full plan.

---

## 2. Prior Finding Closure Table

| Finding | Status | Evidence | Residual risk |
|---|---|---|---|
| **F-01** unreachable ≠ infra_error | **fixed** | `wire.py:147-154` returns out-of-band `WireMiner.terminal_status="unreachable"` (no fabricated payload, `package_hash=None`); `epoch.py:81-82` scores it 0 (EMA decays); `degraded` keys on literal `infra_error` only (`epoch.py:93-97`); test `test_epoch_offline.py:80-109` asserts status, null hash, `degraded is False`, and EMA 0.35 = 0.7×0.5 decay. Kill artifact `work/m4_hardening_kill` confirms live. | A miner setting the synapse `error` field can self-declare unreachable — but that now only zeroes its own epoch score (no protected state reachable). Harmless. |
| **F-02** spoofable `wire_error` | **fixed** | `bridge.py:19` `RESERVED_WIRE_KEYS`; `bridge.py:64-76` → terminal `invalid:reserved_key:wire_error` before any pipeline logic. `infra_error` is now producible only from validator-side Docker results. | Only `wire_error` is reserved, but all other statuses are derived validator-side, so the spoof surface is closed. Low. |
| **F-03** response cap + quota default | **partial** | Aggregate cap enforced in `wire.py:157-165` (canonical size vs `MAX_RESPONSE_BYTES`, oversize → terminal `invalid`, epoch continues); `neurons/validator.py:28` `--quota` default = `DEFAULT_QUOTA` (4); count bounded `wire.py:166`. | Cap runs **after** `dendrite.query` has deserialized the full response — the plan's "checked before parse" is met at the application layer, not the transport layer. Memory bound rests on bittensor's own (unmeasured) ceiling. Close before M6 public exposure. |
| **F-04** max-size serialization test | **partial** | `test_wire.py:26-41`: genuine `model_dump_json()`→`model_validate_json()` round-trip of a ~1 MB submission list; `test_wire.py:60-79` oversize→invalid. | Real serialization, but in-process Pydantic — the actual axon↔dendrite HTTP ceiling is still unmeasured ("measure, set cap to 80%" documented-around, not performed). M6 residual. |
| **F-05** chain seam | **fixed (as designed)** | New `chain.py`: `ChainClient` Protocol + `NullChain` (no bittensor import, cannot sign); `epoch.py:39-45,110-117` threads optional `chain_client`, defaults `NullChain()`; `weight_result` = `chain_result.to_record()`. No `SubtensorChain`/`set_weights` exists — correct, M6 stays codeless by design. Behavior-preserving for old artifacts (verified: identical `weight_result` keys; replay unaffected). | None material. |
| **F-06** M4 uncommitted | **fixed** | All M4 work committed in `39f75f7`; `git status --short` clean (verified this session). | Tag hygiene: `demo-floor-v0` still points at the M3 commit (correct); no M4 tag exists yet — optional. |
| **F-07** Deviations Appendix | **fixed** | Plan §13 now has four dated 2026-07-08 entries (wire.py substitution, unreachable/oversize semantics, strikes deferral, §7.2 path correction), each naming milestone + deviation + approval trail. | None. |
| **F-09** demo paths | **fixed** | `docs/hackerhouse/demo-script.md` created with correct `work/<run>/subnet_archive/...` paths — every command and duckdb column verified against the real layout by the docs slice; §13 entry supersedes plan §7.2. | Script lacks the §7.4 fallback narration block (see §3 of this report / D-3). |
| **Hardening A (F-10)** containerized-or-not-accepted | **fixed** | `bridge.py:20,167-179`: docker mode + not containerized + lifecycle not in the rejected set → purge + `infra_error`; test `test_bridge_mock.py:95-112`. | None. |
| **Hardening B (F-11)** import discipline | **fixed** | `tests/test_import_discipline.py`: `sys.meta_path` blocker rejects `bittensor*`, imports all `dolores_subnet.*` **and** `neurons.{miner,validator}`, runs a `NullChain` mock path. Neurons now import bittensor/wire lazily inside the wire functions (`validator.py:82-84`, `miner.py:98-100` — verified first-hand). | None; genuinely regression-proof. |
| **F-08** strikes system | **deferred by design** | Explicitly documented as deferred in `docs/diary/2026-07-08-m4-hardening.md:30-32` and the §13 appendix. | Anti-spam remains quota+dedup only; revisit before M6 economy claims. |
| **F-12** replay re-derives EMA | **still open (P2)** | `epoch.py:165` still re-normalizes the artifact's stored `ema_state`. | An `update_ema_scores` bug would pass `--replay-check`. Polish. |
| **F-13** hash-order truncation | **still open (P2)** | `wire.py:81,166` still truncate by list order (twice, redundantly); hash ordering applies only at epoch processing (`epoch.py:62`). | Moot for honest miners. Polish. |
| **F-14** negative timing-confinement test | **still open (P2)** | Only `"duration_ms" in timing` asserted (`test_epoch_offline.py:76`). | Artifact clean in practice; guard absent. |
| **F-17** misc polish | **partially closed** | Closed: README stale wire line. Open: synapse `schema_version` field, `UNSEEN_PRUNE_EPOCHS` unused, dead `top_k` config, runbook rate-limit warning + testnet.json example shape, diary timing, firewall note (see §3/D-findings). | Cosmetic except the runbook items (D-1, D-2). |

**New defects introduced by the hardening commit: none at P0/P1.** The fix
slice verified offline/mock behavior is preserved and old artifacts still
replay; the only new observations are redundant double truncation and the
canonical-vs-transport byte-count nuance (both P2, both noted above).

---

## 3. Artifact Verification

**Post-hardening reruns exist as new directories** — `work/m4_hardening_wire`
(happy path) and `work/m4_hardening_kill` (kill test) — with the
pre-hardening `work/m4_wire`/`m4_wire_kill` left intact for comparison, which
is exactly right for auditability.

All six of Codex's claims **confirmed against on-disk artifacts** (artifact
slice, with independent re-execution of the replay checks):

- Happy path: honest miner (5FHE…) weight **1.000000**, epoch score 1.707393;
  duplicate spammer (5DhP…) weight **0.000000** — confirmed in
  `m4_hardening_wire` weights + rendered report.
- **REPLAY OK** for both runs — re-run independently by the artifact slice
  via `report.py --replay-check 1`, not just read from the diary.
- Kill test: stopped miner `status="unreachable"`,
  `reason="unreachable:Service unavailable at 127.0.0.1:8092/DoloresTaskSynapse"`,
  `package_hash: null`, `pre_gates={transport:false}`, **`degraded: false`**,
  epoch score 0.0 and `ema_state` 0.0 (genuine decay, no carry-forward) —
  the exact pre→post behavioral flip from the old artifact
  (`infra_error`/synthetic hash/`degraded:true`).
- Happy-path values are byte-identical pre- vs post-hardening apart from
  timestamps — the hardening changed only the failure path, and determinism
  held across the rerun.

**Does the evidence prove real wire behavior? Yes — for miner↔validator
transport.** The `Service unavailable at 127.0.0.1:8092/DoloresTaskSynapse`
string is bittensor's dendrite status message, only producible by a real
dendrite→axon attempt; hotkeys are recorded from validator-side endpoint
config (the dead miner still has the correct ss58 precisely because it never
responded); every scored row carries `containerized:true, executed:true,
backend:docker, image:dolores-verifier-pytest:0.1.0`; the duckdb archives
contain real verification/solver/task-file rows. **What it does not prove:**
chain weight-setting — `weight_result` is `{mode:"fallback", reason:"offline",
receipt:null}` in every artifact. At this review point no chain client existed;
that code gap is superseded by the later M6 chain-readiness pass.

**Preflight evidence:** wire preflights re-run by me this session for
validator, miner-0, miner-1 — all PASS, exit 0. `pytest -q` → 44 passed;
`ruff check .` → clean; `git status --short` → empty (all verified
first-hand).

---

## 4. Wallet / Testnet Readiness

**Public wallet state:** wallet `dolores-test` with hotkeys `validator`,
`miner-0`, `miner-1`; coldkey `5ELE…JHVG` holds **10.0 test TAO free, 0
staked, network test**. No subnet registered, no extrinsic ever sent, no
receipts. `configs/testnet.json` remains public-only (`netuid: null`).

**What the 10 TAO unlocks — updated economics.** The plan's ~100 TAO
subnet-creation estimate is obsolete: btcli 9.x has no old lock/return command
subcommand; the post-dTAO equivalent is `btcli subnet burn-cost --network
test`, which reads **1.0000 τ today** (run by the next-phase slice and
re-verified by me). Note this is a **recycled burn, not a returnable lock**.
Budget sketch against 10 TAO: creation ~1.0; three registration burns
(floor ~0.0005 each, negligible on quiet testnet); ~8–9 TAO headroom for
validator self-stake. On a subnet we create and own, our validator faces no
competing validators, so the mainnet-analog ~1000-stake figure should not
apply — but the actual permit threshold is **empirically unconfirmed**; M5
localnet (or the M6 permit-wait itself) is where it gets measured.

**Cautions:** burn cost is *dynamic* — it ramps with recent subnet creations
and decays back; re-query immediately before any H4 approval. Subnet creation
remains **one-shot per account per ~14,400 blocks (~2 days)** — a botched
create wastes both the burn and days of calendar. This warning is still
missing from the runbook (D-2 below).

**What remains human-gated (unchanged):** H4 spend approval against a fresh
burn-cost reading; H6 Leon at the keyboard for every extrinsic (create →
start → register ×3 → stake → ≥1 tempo wait → `validator_permit` check
before any weight epoch); H5 naming; H8 GitHub remote (still none
configured). **TAO arrival does not itself authorize anything** — and later M6
chain-readiness code still does not authorize live chain writes.

**Doc staleness fixed in M7 and M6 chain-readiness:** README, runbook, and
`configs/testnet.json` now say 10.0 test TAO is present, no public subnet is
registered, and the current blockers are Leon-approved create/register/stake/
live-weight actions, netuid, permit, and receipts, not funding arrival.

---

## 5. Next-Step Recommendation

**Recommended order (one recommendation, not a menu):**

1. **M7 to "demo-locked" first** (Codex; hours; zero external dependency).
   Run the clean-clone bootstrap + timed 5-minute demo-profile path and
   commit the transcript; produce the pre-recorded fallback epoch capture
   (§7.3); append the §7.4 fallback narration block to `demo-script.md`.
   This locks the guaranteed hackerhouse deliverable before any new risk is
   taken.
2. **Build `SubtensorChain` + metagraph discovery** (Codex; code only, no
   extrinsics). This is the single remaining load-bearing gap, needed by
   both M5 and M6, and fully faucet-independent. Safety gates that must
   survive: bittensor imports inside methods only (keep
   `test_import_discipline.py` green); every subtensor construction through
   `assert_safe_network` with explicit `network=`; unit tests that
   finney/unset raise; `set_weights` argument shaping + receipt capture
   tested against a mocked subtensor, never a live one.
3. **M5 localnet rehearsal** (Codex prep, Leon H6 signs with throwaway
   localnet funds). Exercises create/start/register/stake/permit-wait/
   `set_weights`/metagraph-readback at zero cost and measures the permit
   threshold empirically. Arm64 image failure remains a documented waive
   path — tolerable now that M6 costs ~1 TAO instead of ~100.
4. **M6 public testnet** — now genuinely attainable with the TAO on hand,
   still STOP-LEON at every extrinsic, `testnet-v0` tag only under tier (a).

**Codex should also close, opportunistically:** the doc fixes D-1..D-3
below; before M6 exposure, the F-03/F-04 residual (measure the real
transport ceiling, set the cap to 80% of measured) and a decision on strikes
(F-08: implement or keep loudly deferred).

**Leon's list, in order:** (1) optional but cheap — H3 over-ask top-up in
Discord as insurance against a burn-cost spike (public coldkey address
only); (2) H5 naming decision, then H8 create the GitHub remote (M7's
clean-clone rehearsal wants it; none exists); (3) H6 for the M5 localnet
btcli sequence when Codex has the chain client ready; (4) H4 approval
against a **freshly re-queried** burn-cost, then H6 for the M6 sequence.

**If Bittensor people ask for a demo today:** show the offline epoch floor
(real Docker verification, adversarial rejections with named gates,
determinism diff, replay check) and the local wire run including the kill
test — all backed by committed artifacts — with the §7.4 narration: the
weights step writes the identical artifact the chain call consumes; the
chain call is one function at the top, queued behind human-approved testnet
setup. Never claim a registered netuid, a receipt, or a permit.

**Documentation fixes rolled up (from the docs slice):**
- **D-1 (P1, before M6):** runbook's `testnet.json` example (flat shape,
  "create the file") contradicts the real nested file that already exists —
  replace with the actual shape, change "create" to "update (add netuid)".
- **D-2 (P1, before M6):** add the 14,400-block/2-day one-shot
  subnet-create rate-limit warning above the LEON-ONLY create command, plus
  "re-query `burn-cost` at go-time".
- **D-3 (P1, before demo):** append §7.4 fallback narration + §7.3
  pre-recorded-backup note to `demo-script.md`; fix the three TAO-arrival
  staleness strings (README:49, runbook:24, `configs/testnet.json:4` —
  prefer dropping the dynamic `status` field from config entirely).
- **D-4 (P2):** surface the measured epoch duration (~77 s wire epoch,
  `timing.duration_ms=76538`) in the hardening diary; one line recording
  that axons bound successfully (firewall resolved); reconcile plan §7.2's
  "~2-4 min" figure with measured numbers.

---

## 6. Claims We Can Make Now

| Claim | Evidence |
|---|---|
| Deterministic offline epoch demo floor, replayable | `demo-floor-v0`; empty `del(.timing)` diff (verified in prior review); `REPLAY OK` re-verified today |
| Adversarial packages rejected with named gates, real containerized execution evidence | committed planted fixtures; `containerized:true/executed:true/image:dolores-verifier-pytest:0.1.0` on every scored row |
| **Real signed axon/dendrite wire transport, hardened:** unreachable miners decay (no EMA freeze), self-reported infra spoofing rejected, response size capped, quota default 4 | `39f75f7`; `work/m4_hardening_wire` + `m4_hardening_kill`; tests `test_wire.py`, `test_epoch_offline.py:80-135`, `test_bridge_mock.py:95-112` |
| Kill-resilience: a dead miner scores zero with a genuine transport-error reason; the epoch completes undegraded | `m4_hardening_kill`: `unreachable`, `package_hash:null`, `degraded:false`, honest miner 1.0 |
| Chain-injection seam exists and cannot sign | `chain.py` (`NullChain`, no bittensor import); import-discipline test green with bittensor blocked |
| 44 tests pass, lint clean, clean tree, wire preflights pass ×3 | re-run this session |
| Local testnet wallet identities exist and **10.0 test TAO is on the coldkey (network test), unspent** | balance per Leon's context; `configs/testnet.json` public addresses |
| Testnet subnet creation currently costs ~1.0 τ burn (point-in-time) | `btcli subnet burn-cost --network test` → 1.0000 τ, read-only, run twice today |
| Docs and Deviations Appendix accurately reflect status without inflation | docs slice audit: every entrypoint leads with "M6 blocked" |

## 7. Claims We Still Cannot Make

| Claim | What would make it true |
|---|---|
| Registered public testnet subnet / our own netuid | Leon-approved `btcli subnet create --network test` + netuid recorded |
| Any on-chain `set_weights` / live weights / extrinsic receipt | `SubtensorChain` built (currently zero chain-writing code) + M6 epoch with receipt |
| Validator permit | stake + ≥1 tempo + `metagraph.validator_permit==True` |
| Real testnet miner/validator economy or emissions | registered subnet + repeated epochs |
| Wire transport over the public chain with metagraph discovery | discovery code (unwritten) + M5/M6 run |
| Localnet rehearsal completed | `work/m5/` receipts (M5 not started) |
| A timed clean-clone demo rehearsal | committed transcript (not yet run) |
| Measured transport ceiling / pre-parse DoS bound | F-03/F-04 residual work |
| Strike-based anti-spam | F-08 implementation (explicitly deferred) |
| (Banned regardless, plan §7.4) mainnet, 2k-task archive, 15 strong frontier tasks, production-grade isolation, scorer-predicts-training-value | never claim |

---

## 8. Subagent Appendix

**Slice 1 — Fix verification.** Adversarial line-by-line closure check of
`39f75f7` against F-01..F-17. Verdict: F-01/F-02/F-05 + both hardenings
fully fixed with tests; F-03/F-04 partial (post-deserialization cap;
in-process serialization test); F-12/F-13/F-14/F-17 remain open P2 polish;
no new P0/P1 defects; offline/mock behavior preserved.

**Slice 2 — Artifact evidence.** Confirmed all six of Codex's run claims
against `work/m4_hardening_*`, independently re-ran both replay checks
(`REPLAY OK`), documented the exact pre→post behavioral flip on the kill
path, and verified real dendrite transport evidence. Flagged correctly that
`weight_result` remains fallback-only (no chain claim available) and that
some diary side-claims (reserved-key rejection, quota default) are proven by
tests, not run artifacts — slice 1 covered those.

**Slice 3 — Docs/claims.** No status inflation found anywhere; errors are
stale understatements. F-07/F-09 resolved; open items rolled into D-1..D-4.
Verified every demo-script command against the real CLI flags and archive
schema.

**Slice 4 — Next-phase planning.** Produced the recommended order and the
burn-cost discovery (1.0 τ; the old lock/return command no longer exists in
btcli 9.x).
**Disagreements I adjudicated as orchestrator:** (a) slice 4 flagged
"neurons import bittensor at module top" as a risk — stale; slices 1's
finding is correct and I verified first-hand that imports are lazy
(`validator.py:82-84`, `miner.py:98-100`); (b) slice 4 listed F-10 as
possibly unclosed — slice 1 confirmed it closed (`bridge.py:167-179` +
test), which I accept on its cited evidence. Slice 4's permit-threshold
reasoning (uncontested self-owned subnet → modest stake suffices) is
plausible but unverified — treated as a hypothesis for M5 to test, not a
claim.

**What I personally verified as orchestrator:** `git status --short` clean;
`git show --stat 39f75f7` (21 files, matching Codex's claim list);
`pytest -q` (44 passed); `ruff check .` (clean); wire preflights ×3 (PASS,
exit 0); `wire.py` in full (out-of-band `terminal_status`, no fabricated
payloads, size cap, canonical-size function); `chain.py` in full (NullChain,
no bittensor import); `epoch.py` terminal-outcome flow, `degraded`
computation (infra_error-only), EMA decay path for unreachable, and the
chain-client threading into `weight_result`; `bridge.py` reserved-key
rejection (`RESERVED_WIRE_KEYS`, `invalid:reserved_key:wire_error`);
`neurons/validator.py:28` quota default = `DEFAULT_QUOTA`; lazy bittensor
imports in both neurons; and the live `btcli subnet burn-cost --network
test` → 1.0000 τ reading. No wallet material, key files, or `.env` content
was read; no signing, spend, or extrinsic was performed or attempted.
