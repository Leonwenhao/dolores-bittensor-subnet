# Fable Implementation Conformance Review — Dolores Bittensor Subnet

Date: 2026-07-08. Reviewer: Fable (orchestrator), with four Opus 4.8 subagent
review slices (plan conformance, security/safety boundaries, protocol/
architecture, demo/operator readiness). Reference: the authoritative plan at
`docs/architecture/fable-testnet-development-plan.md` (2026-07-07).

Review posture: strict, testnet-grade auditability. No chain operations, no
signing, no wallet-material access, and no paid calls were performed during
this review. All local checks run were the allowed non-signing set.

---

## 1. Executive Verdict

**Is this implementation on-plan?** Yes, substantially — with one structural
deviation (the plan's `synapse.py` + `chain.py` pairing was replaced by a
single `wire.py` covering only the synapse half) and a cluster of M4-edge gaps
detailed below. The core promise of the plan — a deterministic, fail-closed,
evidence-logged validation loop that rewards task *supply* — is genuinely
implemented, not simulated.

**What is genuinely complete?**

- **M0–M3 are complete and real.** 35 tests pass, ruff clean, mock preflight
  all-PASS. The M3 demo floor is verified first-hand: the determinism diff
  between two independent offline epoch runs (`work/m3_a` vs `work/m3_b`,
  after `del(.timing)`) is **empty**; `report.py --replay-check` exists and
  passes; all 7 planted adversarial fixtures are committed; the hidden-test
  export leak test exists and passes; the `demo-floor-v0` tag exists.
- **M4 achieved a real wire run.** This was the load-bearing question and the
  answer is yes: `wire.py` defines a genuine `bt.Synapse` subclass, real
  `bt.Axon`/`bt.Dendrite` cross-process transport ran on localhost with the H2
  wallets, hotkeys were recorded validator-side from constructed `AxonInfo`
  (never self-reported), and the kill test produced a genuine transport error
  (`Service unavailable at 127.0.0.1:8092/DoloresTaskSynapse`) — evidence only
  producible by a real dendrite→axon attempt against a stopped process. Wire
  preflight passes for all three hotkeys (verified this session).

**What is not complete?**

- **M4 is partial, not done.** Five gaps block sign-off: (1) unreachable
  miners are conflated with `infra_error` against the plan's explicit
  "distinct from infra_error" gate; (2) the mandated max-size synapse
  serialization round-trip test does not exist; (3) the chain seam
  (`NullChain`/`chain.py`) was never built; (4) the entire M4 implementation
  is **uncommitted** working-tree state; (5) the plan's §13 Deviations
  Appendix was never updated for any of this.
- **M5 not started** (waivable stretch, per plan).
- **M6 blocked — correctly and maximally.** No `set_weights`/extrinsic code
  exists anywhere in the repo; `weight_result.mode` is hardcoded `"fallback"`.
  Chain contact would require net-new code *plus* human action. Note the flip
  side: M6 is not merely waiting on test TAO — the `SubtensorChain` layer
  itself is unbuilt.
- **M7 not started** (no `demo-script.md`, README stale, no timed rehearsal).

**Ready for hackerhouse demo work?** Yes — the M3 offline floor is a real,
rehearsable, ≤8-minute demo from committed state today. M7 packaging work
(demo script with corrected paths, README rewrite, timed rehearsal) remains.

**Ready for public testnet?** **No — and not solely for the expected reason.**
Beyond test TAO (H3, no evidence the Discord request has been made) and the
human chain steps (H4/H6), the chain layer (`SubtensorChain`, metagraph
discovery, `set_weights`, receipt capture) does not exist yet, and three
wire-hardening findings (spoofable `infra_error`, no response-size cap,
quota default 10,000) must be fixed before exposing the validator to
non-cooperating miners.

**No P0 findings.** Nothing found that makes current claims dishonest or that
leaks secrets; the safety boundaries held everywhere we probed.

---

## 2. Milestone Matrix

| M | Status | Evidence | Gaps | Next action |
|---|--------|----------|------|-------------|
| **M0** env/preflight | **complete** | `config.py:37-123` (mode enum, allowlist, mainnet hard-fail); `scripts/preflight.py`; commit `617a65f`; diary `2026-07-07-m0.md`; pip check + preflight PASS re-verified this session | none material | — |
| **M1** packaging/wire format | **complete** | `packaging.py`, `protocol.py`, `tests/test_packaging.py` + `test_protocol.py`; commit `b6b2165`; diary present; round-trip/tamper/size/WireError tests all green | none | — |
| **M2** validator core | **complete** | `bridge.py` (exact three-way infra discriminator, `bridge.py:181-186`), `gates.py` (ordered cheap-first), `archive.py` (`purge_task`, `archive.py:33-48`), `seed_adversarial.py:21-79` (all 7 planted cases); commit `150cf32`; diary records exact expected statuses twice | strikes system deferred silently (see F-08) | document or implement strikes |
| **M3** offline demo floor | **complete** | Empty determinism diff `m3_a` vs `m3_b` (verified first-hand); `report.py --replay-check` → `REPLAY OK`; export leak test `test_bridge_mock.py:78-97`; `local_loop.py`/`dolores_bridge.py` deleted; tag `demo-floor-v0` at `71b5066`; diary with leaderboard + timing | stale strings in `egg-info/` trip the documented grep gate verbatim (F-15) | regenerate/ignore egg-info |
| **M4** wire integration | **partial** | Real axon/dendrite run: `work/m4_wire/` + `work/m4_wire_kill/` artifacts with real ss58s, `containerized=true`, genuine dendrite failure message; `wire.py:12` (`DoloresTaskSynapse(bt.Synapse)`); wire preflight ×3 PASS (this session); diary `2026-07-08-m4-wire.md` | F-01, F-04, F-05, F-06, F-07 below | fix unreachable semantics, add serialization test, commit, update Deviations Appendix |
| **M5** localnet rehearsal | **not started** (waivable) | no `work/m5/`, no `SubtensorChain`, no metagraph discovery | expected — off critical path | waive in diary or defer until chain layer exists |
| **M6** public testnet | **blocked (correctly)** | zero extrinsic code (grep: no `set_weights` in src/neurons/scripts); `weight_result.mode` hardcoded `"fallback"` (`epoch.py:108`); `configs/testnet.json` public-only, `netuid: null`; mainnet guard `config.py:90-106` | chain layer unbuilt; H3 was later completed with 10.0 test TAO | build chain seam behind the M6 human gate |
| **M7** demo packaging | **not started** | no `docs/hackerhouse/demo-script.md`; `README.md:65` still lists wire mode as pending; no rehearsal transcript | plan §7.2 template paths are wrong (F-09) | author demo-script with corrected `subnet_archive/` paths; rewrite README; timed rehearsal |

**Direct answers to the three posed questions:**

- **Is the M3 demo floor real?** Yes. Real Docker verification
  (`containerized=true, executed=true` on every scored row), byte-identical
  weight artifacts across independent runs, working replay check, committed
  fixtures, tag in place.
- **Is M4 complete or only preflight-ready?** Neither — it is materially past
  preflight-ready (a real cross-process signed wire run happened, including
  the kill test) but short of complete per the plan's own gates (findings
  F-01, F-04, F-05, F-06, F-07).
- **Is M6 correctly human-blocked?** Yes, maximally: no code path can emit a
  chain extrinsic because no extrinsic code exists; the network allowlist
  hard-fails finney/mainnet/unset; the only chain touch anywhere is the
  read-only `subtensor.block` reachability check in `preflight.py:236`,
  gated to localnet/testnet modes.

---

## 3. Findings

No P0 findings. P1 = must fix before the named gate can be signed off.
P2 = polish / hardening.

### P1

**F-01 — Unreachable miner is conflated with `infra_error` (plan: "distinct from infra_error")**
- Severity: P1. Blocks: strict M4 sign-off; M6. Not the offline demo.
- Evidence: `wire.py:107-122` fabricates a synthetic submission payload with a
  `wire_error` key for any failed dendrite response; `bridge.py:61-68` maps it
  to `status="infra_error"`. `work/m4_wire_kill/subnet_archive/submissions.jsonl`
  row 3: `"status":"infra_error"`, `"task_id":"infra_unreachable_1"`; the
  epoch artifact has `"degraded": true`. Plan M4 (lines 757-759, 776-778)
  requires `reason="unreachable"`, **distinct** from `infra_error`, and §2.6
  reserves `degraded` for validator-side infrastructure failure.
- Explanation: `infra_error` semantics protect the miner — EMA carried forward
  unchanged, no decay, archive rows purged. A miner that simply goes offline
  therefore keeps its prior weight frozen indefinitely instead of decaying
  toward zero, and the whole epoch gets flagged as "our infrastructure
  failed" when in fact one miner was down. Three of four review slices
  independently flagged this; the M4 diary documents the behavior but the
  plan's Deviations Appendix does not.
- Fix: add a distinct `unreachable` terminal status set out-of-band by the
  validator (e.g. a `WireMiner.unreachable` flag, never a payload key); score
  it 0 for the epoch (EMA decays); do not set `degraded`; keep `infra_error`
  for Docker-down-class failures only. Re-run the kill test asserting the
  distinction.

**F-02 — The `infra_error` signal is miner-spoofable (`wire_error` read from miner-controlled payload)**
- Severity: P1. Blocks: M6 (gaming vector). Not the M4 honest-miner demo.
- Evidence: `bridge.py:61` — `if wire.get("wire_error"):` — trusts a key
  inside the submission dict. On the success path, `wire.py:107-108` passes
  `response.submissions` through verbatim, and the miner's forward function
  sets `synapse.submissions` to arbitrary dicts (`neurons/miner.py:110-114`).
- Explanation: a malicious miner can inject `"wire_error": "x"` into its own
  submissions to self-declare infrastructure failure every epoch — freezing a
  previously high EMA (no decay, no strike, rows purged) while doing no work.
  This inverts the plan's provenance rule (§2.4: transport identity/state is
  validator-side, "never self-reported by the response").
- Fix: strip or reject any reserved control key (`wire_error`) appearing in
  miner-supplied payloads before `validate_submission`; carry validator-
  observed unreachability via a separate channel (see F-01's fix — the two
  findings share one root cause and one fix).

**F-03 — No total response-size cap enforced, and wire quota defaults to 10,000**
- Severity: P1. Blocks: M6 (validator DoS). Low risk for the cooperative demo.
- Evidence: `config.py:17` defines `MAX_RESPONSE_BYTES = 1024*1024` — grep
  confirms it is enforced nowhere. `neurons/validator.py:29`:
  `parser.add_argument("--quota", type=int, default=10_000)` (verified
  first-hand). `wire.py:124` slices `payloads[:quota]` after full
  deserialization. Only the per-package 200 KB gate (`gates.py:65`) bounds
  size, and it runs post-deserialization.
- Explanation: a hostile axon can return an enormous submissions list; the
  validator materializes all of it, and with the default quota up to 10,000
  packages per miner would each get full Docker verification (~1-3 min each).
  The plan's "response size checked before parse" (§2.4) and the ≤1 MB budget
  are not implemented at the network layer.
- Fix: enforce `max_response_bytes` on the aggregate payload in
  `query_miners` before constructing `WireMiner`; cap submission count at the
  configured quota default (4), not 10,000; lower the CLI default.

**F-04 — Plan-mandated max-size synapse serialization test does not exist**
- Severity: P1. Blocks: M4 sign-off.
- Evidence: `tests/test_synapse_roundtrip.py` absent. `tests/test_wire.py:8-17`
  constructs a synapse in-memory and asserts `.deserialize() is synapse` —
  it never exercises actual wire serialization nor the 1 MB budget.
- Explanation: the plan (M4, line 780) requires proof that
  serialize→deserialize preserves a max-size submission list, precisely
  because payload truncation at the transport ceiling is M4's named failure
  mode ("measure, don't guess"). No measurement exists in-repo.
- Fix: add a test that round-trips a ~1 MB submission list through the actual
  synapse JSON serialization path; record the measured ceiling; set the config
  cap to 80% of measured per the plan.

**F-05 — No chain seam: `NullChain`/`chain.py`/`SubtensorChain` unbuilt; `run_epoch` signature diverges**
- Severity: P1. Blocks: M5 and M6 (not M4 function).
- Evidence: `epoch.py:38-44` — `run_epoch(cfg, miners, *, epoch_id, quota)`;
  plan §2.7 specifies `run_epoch(cfg, miners, chain)` with an injected chain
  client. No `NullChain`/`SubtensorChain`/`set_weights` anywhere in `src/`.
  `weight_result.mode` hardcoded `"fallback"` (`epoch.py:108`).
  `WEIGHTS_RATE_LIMIT_BLOCKS`, `TEMPO_BLOCKS` defined but unused.
- Explanation: one of the plan's two core injection boundaries does not
  exist. Today this is what makes M6 maximally safe (a genuine plus); it also
  means M5/M6 need net-new code, not just human steps — worth stating plainly
  in planning and in the pitch.
- Fix: introduce the chain `Protocol` + `NullChain` (importable without
  bittensor) now; implement `SubtensorChain` (lazy bittensor import) only when
  M5/M6 approach, behind the existing network allowlist.

**F-06 — The entire M4 deliverable is uncommitted; `demo-floor-v0` tag predates it**
- Severity: P1. Blocks: demo packaging (M7 clean-clone), work-loss risk.
- Evidence: `git status` — untracked: `wire.py`, `tests/test_wire.py`,
  `configs/testnet.json`, diaries `h2-wallets`/`m4-wire`; modified:
  `neurons/miner.py`, `neurons/validator.py`, `bridge.py`, runbook,
  `m4-blocked` diary. Last commit `b369128` predates all M4 code.
- Explanation: a clean clone (the M7 rehearsal path, or any teammate) has no
  wire mode, no wallet config, and no record of H2/M4. The plan's milestone
  convention requires committed diary + code for "done."
- Fix: commit the M4 work as one coherent commit on `m4-blocked-runbooks`
  (after or alongside the F-01/F-02 fix decision — Leon's call whether to
  commit as-is with the deviation documented, or fix first).

**F-07 — Deviations Appendix never updated**
- Severity: P1 (process). Blocks: plan integrity for M4 sign-off.
- Evidence: plan §13 (lines 1416-1420) still reads "Empty at plan creation";
  `git diff` shows no edits to the plan file.
- Explanation: two material deviations are documented only in diaries: (a)
  `wire.py` replacing `synapse.py`+`chain.py` (with the chain half missing),
  (b) unreachable-as-`infra_error`. The plan's own docs policy requires dated
  appendix entries; the appendix is what future agents treat as authoritative.
- Fix: append dated entries for both deviations (plus the strikes deferral,
  F-08) with their approval trail.

**F-08 — Strikes system entirely absent though the plan marks it "implemented in gates.py"**
- Severity: P1 (claims hygiene) / P2 (function). Blocks: nothing today;
  relevant to M6 anti-spam posture and to what we may claim.
- Evidence: `grep -rni strike src/ neurons/ scripts/` → zero hits;
  `miner_state.json` persists EMA only (`epoch.py:188-191`); `GateContext`
  (`gates.py:22-27`) has no strike input. Plan §9.4/§9.5: "≥3 safety strikes
  across epochs → miner quota drops to 1 (implemented in `gates.py` from
  `miner_state.json`)."
- Explanation: the plan's second anti-spam layer silently does not exist —
  unlike the honestly-deferred §9.5 items, nothing records this as deferred.
- Fix: either implement (persist `{ema, strikes}` per hotkey, increment on
  safety `rejected`, clamp quota to 1 at ≥3) or add an explicit deferral note
  to the diary + Deviations Appendix and stop claiming it.

**F-09 — Plan §7.2 demo commands use wrong artifact paths (missing `subnet_archive/`)**
- Severity: P1 for M7 authoring (copy-paste failure on stage); P2 today.
- Evidence: actual layout is `work/<x>/subnet_archive/{archive.duckdb,
  submissions.jsonl,epochs/…}` (`config.py:176-202`, confirmed on disk);
  plan §7.2 steps 4-5 (lines 1186-1193) reference `work/demo/archive.duckdb`
  etc. without the `subnet_archive/` segment.
- Fix: author `demo-script.md` from corrected paths and rehearse every line
  verbatim; add a §13 note that §7.2 paths are superseded by the demo script.

### P2

**F-10 — Missing `containerized`-or-not-accepted assertion (defense-in-depth).**
Plan §8.1/M2 requires asserting `verification.containerized or status in
{rejected, review, invalid, infra_error}` on every docker-mode outcome.
`bridge.py:154-169` derives status without it (fail-closed flags are
correctly hardcoded at `bridge.py:96-97`, so this is a belt, not a hole).
Fix: one assertion in `_outcome_from_pipeline`.

**F-11 — No bittensor-absent CI test (plan §10).** Import discipline actually
holds (verified empirically: with `bittensor` blocked, every module except
`wire.py` imports; `epoch.py` stays clean) but nothing prevents regression.
Note `neurons/{miner,validator}.py` now import `wire` (hence bittensor) at
module top, contrary to the plan's lazy-import instruction — works because
bittensor is installed, but the CI test would have caught it. Fix: add
`tests/test_import_discipline.py` with a `sys.meta_path` blocker.

**F-12 — Replay check is near-circular for weights.** `epoch.py:149`
re-normalizes the artifact's own stored `ema_state` rather than re-deriving
the EMA step from prior state + `submissions.jsonl`; a bug in
`update_ema_scores` would pass `--replay-check`. Fix: replay from the
previous epoch's persisted state.

**F-13 — Wire-transport quota truncation is by list order, not ascending
hash** (`wire.py:74,124`), diverging from §9.5's deterministic-truncation
rule. Moot for honest miners; fix by sorting by `package_hash` before the
slice or letting the gate be the sole truncator.

**F-14 — No negative schema test confining wall-clock to `.timing`.** The
artifact is actually clean (all volatile values isolated in
`epoch.py:99-116`), but only `"duration_ms" in timing` is asserted
(`test_epoch_offline.py:63`); nothing asserts absence elsewhere. Fix: walk
the artifact and assert no volatile keys outside `.timing`.

**F-15 — Stale-reference grep gate technically red via `egg-info`.**
`src/dolores_bittensor_subnet.egg-info/{PKG-INFO,SOURCES.txt}` still contain
`local_loop`/`dolores_bridge` strings from an old README; source/scripts/
neurons are clean. Fix: delete/regenerate egg-info (it is gitignored but
present on disk where the documented grep runs).

**F-16 — M4↔M3 parity requirement unproven.** Plan requires wire outcomes to
match offline for identical personas/seeds; the M4 run used seeds 201/202 vs
M3's miner-index seeds, and the duplicate-spammer outcome pattern differed
(M4: one `review` + one `rejected`; M3: one accepted + one rejected). Not
demo-blocking (spam still collapses to weight 0.0) but the diary's
equivalence claim is asserted, not evidenced. Fix: one same-seed offline run
+ committed normalized diff, or document why parity doesn't hold
(archive-state-dependent `duplicate_resistance` is the likely benign cause).

**F-17 — Miscellaneous polish.** `DoloresTaskSynapse` omits the
`schema_version` request field (§2.4/§9.1) — schema negotiation happens only
per-submission. `UNSEEN_PRUNE_EPOCHS=20` defined, never used (unbounded
`miner_state.json` growth). `cfg.top_k`/`DEFAULT_TOP_K` dead (quota
hardcoded as k, which matches plan v0 intent). `submissions.jsonl` omits
`wall_ms`/receipt fields from the plan's record list (arguably the right
determinism call — document it). M4 diary omits measured epoch timing
(76.5 s per the artifact) where the M3 diary recorded timing. Runbook's
example `testnet.json` shape (flat) differs from the real file (nested); the
14,400-block/2-day subnet-create rate limit is in the plan but missing from
the runbook's M6 section. `README.md:65` still lists wire mode as a pending
step. H1 firewall state (prompt appeared? pre-allowed?) unrecorded despite
the bind having succeeded.

---

## 4. Security and Safety Notes

**Wallet handling — clean.** Code references wallets by name/hotkey only
(`bt.Wallet(name=…, hotkey=…)`); the only address reads are public
`coldkeypub.ss58_address`/`hotkey.ss58_address`. Preflight wallet check is
existence-only ("exists (not read)"). No mnemonic/seed/private-key handling
anywhere. `configs/testnet.json` contains public ss58s only — safe to commit
(and committing public chain identities should be a conscious choice; it is
consistent with plan §M6).

**Mainnet protection — strong.** `assert_safe_network` (`config.py:90-106`)
hard-fails on unset, `finney`, `mainnet`, and any `finney.opentensor.ai:443`
endpoint that is not `test.finney`; the allowlist is exactly
`{test, ws://127.0.0.1:9944, ws://127.0.0.1:9945}`. Both the `BT_NETWORK` env
var and CLI network flags route through the allowlist — no injection path
found. The single subtensor construction in the codebase
(`preflight.py:236`) passes explicit `network=`. Wire mode is genuinely
chain-free (`bt.Wallet`/`bt.Axon`/`bt.Dendrite` against explicit 127.0.0.1
targets only). Optional belt: wrap the `preflight.py:236` call site in a
local `assert_safe_network`.

**Docker/verifier assumptions — fail-closed, with one missing belt.**
`allow_docker_fallback=False, allow_unsafe_local=False` hardcoded on the
validator path (`bridge.py:96-97`); the three-way
infra/safety/failed discriminator matches plan §2.3 verbatim
(`bridge.py:181-186`); `purge_task` deletes from all six tables, is called on
`infra_error` only and never on safety rejections, with tests for both. The
missing `containerized`-or-not-accepted assertion is F-10. Hidden-test export
protection is real: filtered DB copy + `DELETE FROM task_files WHERE
file_role='hidden_tests'` (`archive.py:51-63`) with a leak test.

**No-secret / no-paid-call compliance — verified.** Full-history scan
(`git log -p --all`) for mnemonics/keys/`FIREWORKS`/`.env` found only
documentation of the rules themselves. No `work/`, `.duckdb`, egg-info,
wallet, or env file was ever committed; `.gitignore` covers all of them
(verified via `git ls-files`). No HTTP client usage outside bittensor's own
transport. No Fireworks or paid-provider call sites exist.

**Public-testnet-specific caveats (before M6 exposure):** fix F-01/F-02/F-03
first — on a public netuid, miner payloads are adversarial by definition, and
today a miner can (a) freeze its EMA by self-reporting `wire_error`, (b) DoS
the validator with an oversized response list under a 10,000 default quota.
The strikes layer (F-08) is also absent, so repeated safety offenders face no
escalating penalty beyond per-epoch zeros.

---

## 5. Claims We Can Make Today

Each claim is backed by an artifact or a command re-runnable on this machine.

| Claim | Evidence |
|---|---|
| A deterministic offline epoch (generation → gates → Docker verification → scoring → EMA → weights → archive → leaderboard) runs end-to-end | `work/m3_a` vs `work/m3_b` empty diff after `del(.timing)` — reproduced during this review; tag `demo-floor-v0` |
| Adversarial packages are rejected with named gates (safety, hash lie, oversize, parse, failed reference, duplicate) | committed fixtures `tests/fixtures/planted/`; M2 diary status table; re-runnable via `neurons/validator.py --mode offline --submissions tests/fixtures/planted/wire` |
| Verification evidence is real containerized execution, not a label | `submissions.jsonl` rows: `containerized=true, executed=true, image dolores-verifier-pytest:0.1.0` |
| Real localhost axon/dendrite transport with signed hotkey identity ran, including graceful handling of a killed miner | `work/m4_wire/`, `work/m4_wire_kill/`; genuine dendrite `Service unavailable` evidence; hotkeys recorded from validator-side `AxonInfo` |
| Quality wins, spam and invalid collapse to zero weight | `work/m4_wire/.../report_epoch_1.md` (honest 1.0, spammer 0.0); M3 leaderboard |
| Hidden tests never leave the validator archive; public exports are filtered | `archive.py:51-63` + leak test `test_bridge_mock.py:78-97` |
| Any epoch's weights are replayable from the evidence log | `report.py --replay-check` → `REPLAY OK` (with the F-12 caveat: the EMA step is re-used, not re-derived) |
| Testnet-only wallet identities exist locally; wire preflight passes for validator, miner-0, miner-1 | preflight runs this session, all PASS exit 0; `configs/testnet.json` public addresses |
| The weight artifact schema is identical for chain and fallback modes | `weight_result` block in every `weights_epoch_1.json` |
| Mainnet is code-level unreachable | `config.py:90-123` allowlist + hard-fail; zero extrinsic code in repo |
| No secrets in the repo or its history | full-history scan clean; `.gitignore` verified |

## 6. Claims We Cannot Make Yet

| Claim | Receipt required |
|---|---|
| A registered public testnet subnet / our own netuid | `btcli subnet create --network test` receipt; `configs/testnet.json.netuid` non-null (currently `null`) |
| Live on-chain weights / any `set_weights` extrinsic | extrinsic hash + block in `weight_result.receipt` (all current artifacts: `mode:"fallback", receipt:null`) — also requires the not-yet-built chain layer |
| Validator permit held | `metagraph.validator_permit == True` for our UID after stake + ≥1 tempo |
| Real testnet miner/validator economy, staking, emissions | registered subnet + stake receipts + permit + weight receipts |
| Wire transport over the *public* testnet with metagraph discovery | M4 proved localhost + static endpoints only; metagraph discovery is unwritten (M5/M6 code) |
| Localnet chain rehearsal completed | `work/m5/` receipts + metagraph dump (absent; M5 not started) |
| A timed ≤8-min demo from a clean clone | committed `demo-script.md` + rehearsal transcript (absent), and the clone currently lacks all M4 work (F-06) |
| Wire outcomes byte-match offline outcomes for identical seeds | the same-seed comparison run (F-16) |
| Miner-quota/strike anti-spam beyond per-epoch zeros | strikes implementation (F-08) |
| (Banned regardless, per plan §7.4) live on mainnet; 2k-task archive; 15 strong frontier tasks; production-grade isolation; scorer predicts training value | never claim |

---

## 7. Recommended Fix Plan

**Smallest set before M4 wire demo sign-off** (≈1 focused day):
1. F-01 + F-02 together (shared root cause): distinct validator-side
   `unreachable` status, strip `wire_error` from miner payloads, kill-test
   asserts the distinction, `degraded` reserved for validator-side infra.
2. F-04: real max-size serialization round-trip test; record the measured
   transport ceiling.
3. F-03 (minimum viable): drop the `--quota` default from 10,000 to the
   config default (4) and enforce `MAX_RESPONSE_BYTES` in `query_miners`.
4. F-06 + F-07: commit everything as one coherent M4 commit; append the dated
   Deviations Appendix entries (wire.py substitution, unreachable semantics,
   strikes deferral).

**Smallest set before M6 public testnet** (after test TAO exists; keep
human-gated):
1. F-05: chain seam — `NullChain` protocol now, `SubtensorChain` (metagraph
   sync, hotkey→UID map, `set_weights` + receipt capture) behind the existing
   allowlist; thread `chain` into `run_epoch`.
2. F-10: the containerized-or-not-accepted assertion.
3. F-08: strikes, or an explicit documented deferral.
4. F-11: bittensor-absent CI test (protects the mock path as chain code grows).
5. Metagraph-based miner discovery with the same-machine localhost fallback
   (plan M5/M6) — currently unwritten.
6. Re-run preflight `--mode testnet` and the runbook permit-wait sequence
   verbatim; M6 execution itself stays STOP-LEON at every extrinsic.

**Smallest docs/demo packaging before hackerhouse** (independent of chain):
1. Author `docs/hackerhouse/demo-script.md` from plan §7.2 with corrected
   `subnet_archive/` paths (F-09); rehearse verbatim; commit the timed
   transcript.
2. Rewrite README (current status incl. M4, quickstart reproducing the M3
   gate, honest chain status); refresh `pitch.md` numbers.
3. Runbook polish: add the 2-day subnet-create rate-limit warning; reconcile
   the `testnet.json` example shape; record firewall state (F-17).
4. Pre-record the fallback epoch capture per plan §7.3.
5. Leon: H5 naming → H8 GitHub remote (currently none configured) → H4/H6
   when chain-client code is ready and burn-cost has been re-queried.

---

## 8. Subagent Review Appendix

Four Opus 4.8 slices ran independently; findings were cross-checked against
each other and against my own first-hand verification.

**Slice 1 — Plan conformance.** Produced the milestone matrix backbone.
Called M0–M3 complete with evidence, M4 "partial with a real run," M6
"maximally blocked" (no extrinsic code). Origin of F-01 (as plan-gate
violation), F-04, F-05 (files/deviation framing), F-06, F-07, F-15, F-16.

**Slice 2 — Security/safety boundaries.** Sharpest unique finding: F-02 (the
miner-spoofable `wire_error`) and F-03 (unused `MAX_RESPONSE_BYTES` + the
10,000 quota default). Also F-10, and a substantial verified-safe list
(allowlist behavior, no bare `bt.subtensor()`, wallet boundaries, clean git
history, purge/export protections) adopted into §4.

**Slice 3 — Protocol/architecture.** Verified scoring math is *exactly* the
plan's formula (`round((aggregate − 0.05·runtime_cost)/0.95, 6)` with
non-accepted→0), EMA/normalization/all-zero/all-infra semantics conform, and
— empirically, with `bittensor` import-blocked — that import discipline holds
everywhere except `wire.py`. Origin of F-08 (strikes), F-11, F-12 (replay
near-circularity), F-13, F-14, and the dead-config items in F-17.

**Slice 4 — Demo/operator readiness.** Settled the "was M4 real?" question
affirmatively via the dendrite `Service unavailable` transport evidence;
origin of F-09 (plan §7.2 path bug), the ordered human task list (§7), the
claims tables (§5/§6), and most F-17 polish items.

**Disagreements / uncertainty.** No slice contradicted another on substance;
differences were emphasis (slice 1 treats F-01 as an M4-gate failure, slice 2
as an M6 gaming vector, slice 4 as an accepted-deviation candidate — all
three views are represented above). Unresolved uncertainties: (a) whether the
strikes/chain-seam/response-cap omissions were conscious deferrals (diaries
are silent); (b) whether bittensor 10.x imposes its own transport size
ceiling that partially mitigates F-03 (unmeasured — F-04's test would answer
it); (c) a minor timestamp oddity — the runbook says the M4 rehearsal ran
2026-07-08 while the artifacts' timing block reads 2026-07-07T16:xx UTC
(plausibly timezone labeling); (d) slice 3 did not read the Dolores source
directly, so a Dolores-side schema drift would only surface at Docker
runtime (the preflight freshness check is the existing mitigation).

**What I verified personally as orchestrator (not delegated):** the full
allowed command suite this session — `pytest -q` (35 passed), `ruff check .`
(clean), `preflight --mode mock` (all PASS), `preflight --mode wire` for
validator/miner-0/miner-1 (all PASS, exit 0); the empty `m3_a`/`m3_b`
determinism diff; the `demo-floor-v0` tag; the absence of any git remote;
that `work/`, egg-info, and caches are untracked; `wire.py` line-by-line
(genuine `bt.Synapse`/`bt.Dendrite`/`AxonInfo`, hotkey from validator-side
endpoint config, and the fabricated `wire_error` payload path); the
`m4_wire`/`m4_wire_kill` artifacts (statuses, weights, `degraded` flags,
`infra_unreachable_1` row); `tests/test_wire.py` in full (no serialization
coverage); `config.py`'s allowlist/hard-fail logic; `neurons/validator.py:29`
(quota default 10,000); `bridge.py:61` (payload-trusting `wire_error`); and
`configs/testnet.json` (public-only). No wallet material, key files, or
`.env` content was read at any point; no chain, signing, or paid operations
were performed.
