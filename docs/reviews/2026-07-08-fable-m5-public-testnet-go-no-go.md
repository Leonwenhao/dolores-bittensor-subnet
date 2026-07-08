# Fable Review — M5 Full Localnet Rehearsal & Public Testnet Go/No-Go

Date: 2026-07-08 (afternoon)
Reviewer: Fable (lead), orchestrating four Opus 4.8 review slices
(extrinsic-gate audit, M5 artifact audit, testnet protocol readiness,
demo/claims risk). All load-bearing findings below were personally
re-verified by the lead reviewer against code, artifacts, or the installed
SDK before adjudication.

Scope reviewed: HEAD `1245791 document m5 localnet commit-reveal rehearsal`,
the full M5 localnet rehearsal evidence in `work/m5_full/`, the commit-reveal
detection fix in `src/dolores_subnet/chain.py`, and live read-only public
testnet state (balance, burn-cost, hyperparameters of recent subnets).

No signing, spending, registration, staking, weight-setting, subnet creation,
GitHub push, paid provider call, or wallet-secret inspection was performed.
All public-chain commands were read-only with explicit `--network test`.

---

## 1. Executive Verdict

**GO WITH CONDITIONS.**

Leon may register the public testnet subnet now. The create → start →
register ×3 → stake sequence was fully rehearsed on localnet today with
receipts for every step, the total burned cost is ~1.0015 τ against a
verified 10.0 τ balance, and none of the open code issues touch the
registration path.

The conditions attach to **live weights**, not registration:

- **C1 (P0). Resolve the commit-reveal strategy before expecting on-chain
  weights.** Fresh public testnet subnets are born with
  `commit_reveal_weights_enabled=true` (verified live: 6/6 sampled subnets,
  netuids 480–522). The repo currently fail-closes on commit-reveal, so on
  our own fresh subnet the validator would skip every submission with
  `reason=commit_reveal_enabled` — correct fail-closed behavior, but it means
  registration alone produces no on-chain weights. Two workable paths exist
  (§5); neither blocks the create.
- **C2 (P1). Fix the commit-reveal probe's fail-open exception path before
  any public `--chain live` run.** A transient RPC error during the probe is
  currently swallowed and reported as "commit-reveal disabled"
  (`chain.py:167-169`), which could let a live run submit plaintext weights
  into a commit-reveal subnet. Small fix + test (§7 Codex prompt).
- **C3. Every write command follows the STOP-gated command sheet in §6.**

---

## 2. Gate Table

| Gate | Status | Basis |
|---|---|---|
| M4 wire mode | **COMPLETE** (unchanged) | Signed off in `2026-07-08-fable-post-hardening-readiness-review.md` |
| M5 localnet | **PARTIAL — STRONG** | 6 of 7 acceptance criteria PROVEN (create, start, register ×3, permit, `dry_run_ok`, live submission accepted); nonzero read-back NOT PROVEN, blocked by localnet commit-reveal that could not be disabled (§3) |
| M6 chain-readiness | **IMPLEMENTED, one P1** | Four-layer gate, single signing path, network allowlist, honest receipts all re-verified intact at HEAD; commit-reveal probe fails open on exception (§4, B-2) |
| M7 hackerhouse demo | **LOCKED & CREDIBLE** | Rehearsed 3-part demo (~2m25s epochs, ~5–8 min with narration), Docker-only, no network, fallback artifacts preserved |
| Public testnet readiness | **CONDITIONAL GO** | Funds verified (10.0 τ), costs verified (~1.0015 τ burned), sequence rehearsed; commit-reveal strategy (C1) and probe fix (C2) required before live weights are meaningful |

---

## 3. What M5 Proved and Did Not Prove

Artifact-audited criterion by criterion (all paths under `work/m5_full/`):

| Criterion | Verdict | Best evidence |
|---|---|---|
| Subnet created (netuid 2, burn 1000 localnet τ) | **PROVEN** | `02_subnet_show.json` (netuid 2, owner `5ELE…`, uid 0 = validator); `02_subnets_after_create.json` (`total_tao_emitted` 10.0 → 1010.0) |
| Emission started | **PROVEN** | `03_start_subnet.txt` (extrinsic `4221-2`) |
| Registered validator uid 0, miner-0 uid 1, miner-1 uid 2 | **PROVEN** | `04_uid_map.txt`, `04_register_miner_{0,1}.json` (extrinsics `4837-2`, `5355-3`) |
| Validator permit | **PROVEN** (true at first poll, 0 extra stake needed) | `05_permit_poll.txt`, `05_permit_threshold.txt` |
| `dry_run_ok` receipt — first ever | **PROVEN** | `dry_run/.../chain_receipt_epoch_1.json`, replay OK |
| Live `set_weights` accepted by a real substrate node | **PROVEN as submission-with-inclusion; hashes not captured** | `live/.../chain_receipt_epoch_2.json` (`mode=submitted`, `success=true`); see nuance below |
| Nonzero weights read back from the metagraph | **NOT PROVEN** | `09_read_back.txt` (`weights row: [0.0, 0.0, 0.0]`) — expected pre-reveal state under commit-reveal, not a payload bug |

Nuances the lead reviewer adjudicated personally:

- **The epoch-2 receipt is stronger than its null hashes suggest.** The repo
  calls `set_weights` with `wait_for_inclusion=True` (`chain.py:199`), so the
  SDK's `success=true` was returned only after inclusion. The null
  `block_hash`/`extrinsic_hash`/`included`/`finalized` fields are an
  attribute-name mismatch: SDK 10.5.0's `ExtrinsicResponse`
  (`bittensor/core/types.py:286`) carries that data inside
  `extrinsic_receipt`, not as top-level attributes, and
  `_submission_from_response` (`chain.py:671-694`) probes the old names.
  Observability gap (P2), not missing proof.
- **The one-uid payload is correct, and it is the honest-wins story.**
  Epoch 2's payload `uids_emitted=[1], weights_u16=[65535]` looks odd next to
  two registered miners, but `weights_epoch_2.json` shows the duplicate
  spammer scored 0.0 (dedup caught its resubmissions) and the honest miner
  took weight 1.0; `_payload` excludes zero-weight hotkeys by design. The
  payload digest is byte-identical between dry-run and live, and all four
  replays re-verified passing at HEAD.
- **The all-zero read-back was the expected commit-reveal state.** The chain
  had `commit_reveal_enabled=true` throughout (proven by the post-fix
  receipts and probes); committed weights are invisible in the metagraph
  until reveal. The pre-fix code failed to detect this (probe list lacked the
  SDK's real method name), which is why epoch 2 submitted at all.
- **The post-fix skip is correct fail-closed behavior.** Epochs 3 and 4
  return `mode=skipped, reason=commit_reveal_enabled` with `payload=null,
  submission=null` — the skip fires in `_readiness_skip_reason`
  (`chain.py:526-527`) before payload construction or any signing, and the
  vocabulary is consistent with the receipt schema's other skip reasons.
- **Evidence hygiene caveats.** `02_create_subnet.json` records
  `success:false` — a failed first create attempt (bad signature/nonce quirk)
  polluted the named artifact; creation is proven by the corroborating files
  cited above. `03_start_subnet.json` is empty (the `.txt` twin carries the
  evidence). The epoch-2 receipt embeds `commit_reveal_enabled:false` — a
  frozen pre-fix mis-read. None of these change the verdicts, but do not
  present those three files as primary evidence.
- **The commit-reveal disable failures were chain/tooling quirks, not repo
  bugs.** btcli sudo hit a websocket-subscription bug; the owner SDK path hit
  `AdminActionProhibitedDuringWeightsWindow` 518 times because this localnet
  has `admin_freeze_window=10` with `tempo=10` — the admin window never
  opens; root-sudo returned outer `success:true` while events showed
  `Sudo.Sudid` with an inner module error (lesson: outer sudo success ≠ inner
  call success). Public testnet has `tempo=360`, so the owner toggle should
  have a usable window there (§5).

---

## 4. Code Safety Re-Audit at HEAD

Re-verified intact (evidence: slice 1, spot-checked by lead):

- **Single signing path.** One `set_weights` call site
  (`chain.py:192-201`), one caller (`apply_weights`, `chain.py:456`).
  Default invocation (`--chain off` → `NullChain`) cannot sign; no single
  flag, env var, or config edit reaches the extrinsic — the four-layer AND
  gate (`chain.py:623-633`: `allow_extrinsics` flag, `DOLORES_ALLOW_EXTRINSICS=1`
  env, `publish=="live"`, typed `I-AM-LEON-AND-I-APPROVE`) is pinned by
  `test_live_gates_block_set_weights_until_all_layers_are_present`.
- **Network allowlist.** `assert_safe_network` (`config.py:92-108`) is a
  strict whitelist (`test`, `ws://127.0.0.1:9944`, `ws://127.0.0.1:9945`);
  finney in any spelling is rejected, and validation fires at config
  construction before any bittensor import. `miner.py` has no network arg and
  never constructs a Subtensor.
- **Receipts do not overstate.** `read_back` is honestly `null` (the
  `read_back_weights` stub remains, `chain.py:203-205`); `submitted_ok`
  claims submission, not confirmation; nothing fabricates hashes.
- **Commit-reveal detection is correct for SDK 10.5.0 on the happy path.**
  The probe's first name, `commit_reveal_enabled`, is the only one of the
  three that exists on the installed `Subtensor` (subtensor.py:976), and the
  new test pins it.
- `ruff` clean; 62 tests pass.

**The one material defect (B-2, P1):** the probe swallows exceptions
(`except Exception: continue`, `chain.py:167-168`) and returns `False` when
no probe succeeds (`chain.py:169`). The 10.5.0 method contains
`assert call is not None`, so a transient RPC hiccup raises, is swallowed,
and commit-reveal is reported **off** — fail-open. Under all four live gates
this could submit plaintext weights into a commit-reveal subnet on public
testnet. No test pins fail-closed on probe error. Related test gaps: probe
precedence when multiple names exist is unpinned, and the test fake's
`read_back_weights` returns `{"matches_submitted": True}` while production
returns `None`.

---

## 5. Commit-Reveal Strategy (the C1 decision)

Live facts (read 2026-07-08 ~13:50, `--network test`):

- All six sampled testnet subnets (netuids 480, 500, 519, 520, 521, 522) have
  `commit_reveal_weights_enabled=true`, `commit_reveal_period=1` tempo,
  `tempo=360` blocks (~72 min), `weights_rate_limit=100` blocks (~20 min).
  A fresh subnet will be born commit-reveal-enabled.
- The owner toggle **exists and is owner-permitted** (not root-only):
  `btcli sudo set --netuid <N> --param commit_reveal_weights_enabled
  --value false` (verified in btcli 9.23.1 source: `owner_settable: True`,
  `RootSudoOnly.FALSE`). It is blocked during the admin freeze window — the
  thing that made it impossible on localnet (`tempo=10` = window). With
  public `tempo=360` the window should be open most of the epoch.
- The SDK **auto-handles commit-reveal**: `Subtensor.set_weights`
  (subtensor.py:8228) routes to a timelocked commit (CRv4) when commit-reveal
  is on, and the commit reveals automatically ~1 tempo later. The only thing
  preventing the repo from working under commit-reveal today is its own
  fail-closed skip at `chain.py:526`.

**Recommended sequence:** try the owner toggle first (path A — zero code
change, LEON-signed, outside the freeze window; verify the flag flipped via a
read before any live run). In parallel, queue the Codex pass (§7) that adds a
gated commit-reveal-aware path (path B) — that is the durable fix, since
commit-reveal is the network default and the mainnet reality, and it removes
the dependency on a hyperparameter toggle. Path A unblocks this week; path B
is the right end state.

---

## 6. Should We Register Now? Yes — LEON-Only Command Sheet

Registration is safe now: rehearsed end-to-end on localnet today, and
everything below the live-weights line is independent of C1/C2.

**Budget (live reads, 2026-07-08 ~13:48; re-read starred values at go-time):**

| Item | Cost | Note |
|---|---|---|
| Balance (`5ELE…JHVG`) | 10.00 τ free | `btcli wallet balance --ss58 … --network test` |
| Create (burn)* | 1.0000 τ | dynamic; consumed, not returned |
| Register validator* | 0.0005 τ | recycle, current testnet rate |
| Register miners ×2* | 0.0010 τ | recycle |
| Stake for permit | 1–2 τ, **recoverable** | fresh subnet: any small stake tops the 64-validator cap |
| **Burned total** | **~1.0015 τ** | buffer ≈ 8.5+ τ after stake |

Timing expectation: first repo-attempted `set_weights` ≈ registration +
~100 blocks (~20 min, rate limit); under commit-reveal add ~1 tempo (~72 min)
to reveal. Total to first visible weights ≈ 1.5–2 h after registration.

Every command below that signs or spends is **LEON ONLY**, uses explicit
`--network test`, and has a STOP gate. The agent runs only the read-only
verification steps. This mirrors the localnet sheet
(`docs/runbooks/m5-localnet-command-sheet.md`) phase for phase.

**Phase 0 — AGENT (read-only preflight).**
Re-read burn-cost and balance; confirm both within budget. STOP if burn-cost
> 1.5 τ (re-plan budget) or balance < 10 τ.

```bash
.venv/bin/btcli subnets burn-cost --network test
.venv/bin/btcli wallet balance --ss58 5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG --network test
```

**Phase 1 — LEON: create (ONE-SHOT — STOP GATE).**
The subnet name/identity folds into the create extrinsic and cannot be
re-done for ~14,400 blocks (~2 days) per account. Confirm the final name,
GitHub URL, and contact BEFORE running. Localnet note: a first attempt there
failed with a bad signature and did not consume funds or the slot — if create
errors, STOP and diagnose (do not blind-retry).

```bash
.venv/bin/btcli subnets create \
  --wallet-name dolores-test --wallet-hotkey validator \
  --subnet-name "<FINAL NAME>" \
  --github-repo https://github.com/Leonwenhao/dolores-bittensor-subnet \
  --subnet-contact "<CONTACT>" \
  --network test
# Record the assigned netuid. Verify:
.venv/bin/btcli subnets list --network test --json-output   # AGENT may run
```

**Phase 2 — LEON: start (gated by read-only check).**

```bash
.venv/bin/btcli subnets check-start --netuid <N> --network test   # AGENT may run
.venv/bin/btcli subnets start --netuid <N> --wallet-name dolores-test --network test
```

**Phase 3 — LEON: register validator + both miners (read-back after each).**

```bash
.venv/bin/btcli subnets register --netuid <N> --wallet-name dolores-test --wallet-hotkey validator --network test
.venv/bin/btcli subnets register --netuid <N> --wallet-name dolores-test --wallet-hotkey miner-0  --network test
.venv/bin/btcli subnets register --netuid <N> --wallet-name dolores-test --wallet-hotkey miner-1  --network test
.venv/bin/btcli subnets show --netuid <N> --network test --json-output   # AGENT: verify 3 uids
```

**Phase 4 — LEON: stake for permit.**

```bash
.venv/bin/btcli stake add --amount 1.0 --netuid <N> \
  --wallet-name dolores-test --wallet-hotkey validator \
  --safe --tolerance 0.05 --network test
```

**Phase 5 — AGENT: permit poll (read-only), then preflight.**
Poll the metagraph until `validator_permit=true` for
`5DyNfBdYMMUMiSRNpVCWPm7Lfoexa2A7z7L11QCMMdEmCLdm`; then
`scripts/preflight.py --mode testnet … --netuid <N>` must PASS readiness.
STOP if the permit has not appeared after 2 tempos.

**Phase 6 — LEON: commit-reveal toggle attempt (C1 path A).**

```bash
.venv/bin/btcli sudo set --netuid <N> \
  --param commit_reveal_weights_enabled --value false \
  --wallet-name dolores-test --network test
# AGENT verifies the flag actually flipped (localnet lesson: outer success
# can mask inner failure):
.venv/bin/btcli subnets hyperparameters --netuid <N> --network test
```
If blocked by the admin freeze window, retry at a different point in the
tempo. If it will not flip after 3 attempts, STOP — fall back to path B
(§7 Codex pass) before any live run.

**Phase 7 — dry-run epoch first (no signing), then LEON: live.**
**STOP GATE: do not run the live command until C2 (probe fail-open fix) has
landed and tests pass.** Dry-run first; inspect the receipt for
`reason=dry_run_ok`.

```bash
# LEON, single shell; unset the env var afterward:
export DOLORES_ALLOW_EXTRINSICS=1
.venv/bin/python neurons/validator.py --mode testnet --network test \
  --netuid <N> --chain live --allow-extrinsics \
  --confirm-live I-AM-LEON-AND-I-APPROVE \
  --epoch <E> --quota 2 --work work/testnet_live \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
unset DOLORES_ALLOW_EXTRINSICS
```

**Phase 8 — AGENT: manual read-back (read-only).**
The receipt's `read_back` field is a stub; read the metagraph weights row
directly. If commit-reveal is still enabled, expect zeros until ~1 tempo
after submission — poll again after the reveal window before judging.

**Phase 9 — bookkeeping.** Update `configs/testnet.json`
(`public_subnet_registered`, `netuid`, balances), write the diary entry,
replay-check the epoch artifacts.

---

## 7. Smallest Codex `/goal` Prompt (C2 + path B)

> `/goal` Harden the chain layer's commit-reveal handling in
> `src/dolores_subnet/chain.py`. (1) Fail closed on probe failure: in
> `_Substrate.commit_reveal_enabled` (lines 154-169), if every probe raises
> or no probe name exists, do not return False — surface "unknown" and have
> `_readiness_skip_reason` skip with a new reason
> `commit_reveal_probe_failed`. Add a test where the probe raises and assert
> the epoch receipt is `mode=skipped, reason=commit_reveal_probe_failed` with
> no `set_weights` call. (2) Add an explicit opt-in flag
> `--allow-commit-reveal` (validator CLI → `SubnetConfig` →
> `SubtensorChain`): when set, a `commit_reveal_enabled=true` subnet does NOT
> skip — the SDK's `set_weights` auto-routes to a timelocked commit (CRv4,
> verified in bittensor 10.5.0 subtensor.py:8228) — and the receipt records
> `mode=submitted, reason=submitted_commit_reveal` plus
> `commit_reveal_enabled=true` so nobody mistakes it for an immediately
> readable weight. Default (flag absent) keeps today's fail-closed skip. (3)
> Enrich `_submission_from_response` (lines 671-694) to read
> `response.extrinsic_receipt` for block hash / extrinsic hash / inclusion
> when present (SDK 10.5.0 moved these off the top-level ExtrinsicResponse).
> Keep chain.py module-top bittensor-free, keep all four live gates
> unchanged, keep ruff/pytest green, and do not touch any other behavior.

---

## 8. Remaining Blockers, Ranked

| # | Pri | Blocker | Blocks | Fix |
|---|---|---|---|---|
| B-1 | **P0** | Fresh testnet subnets are commit-reveal-enabled; repo fail-closes → no on-chain weights after registration | Live weights (not registration) | §5: owner toggle (path A) and/or §7 Codex pass (path B) |
| B-2 | **P1** | Commit-reveal probe fails open on exception (`chain.py:167-169`); no fail-closed test | Any public `--chain live` run | §7 Codex pass, part 1 |
| B-3 | **P1** | Receipt `submission` drops inclusion metadata (probes attribute names absent from SDK 10.5.0 `ExtrinsicResponse`; data lives in `extrinsic_receipt`) | Evidence quality of public receipts | §7 Codex pass, part 3 |
| B-4 | P2 | `read_back_weights` stub → receipt `read_back` always null; manual metagraph poll required | Nothing (workaround documented) | Optional implementation later |
| B-5 | P2 | `version_key`: repo passes its own `SPEC_VERSION=1` (`chain.py:459`, `config.py:192`) as the chain version_key. Accepted while the subnet's `weights_version` stays ≤ 1 (fresh default 0; worked on localnet) | Nothing now; future rejection risk if hyperparam is raised | Document; consider SDK `version_as_int` in a later pass |
| B-6 | P2 | Test fake's `read_back_weights` returns `{"matches_submitted": True}` vs production `None`; probe-precedence untested | Test fidelity | Fold into §7 or later |
| B-7 | P2 | Artifact hygiene: `02_create_subnet.json` records the failed first attempt (`success:false`); `03_start_subnet.json` empty; epoch-2 receipt embeds pre-fix `commit_reveal_enabled:false` | Nothing (noted here; artifacts are immutable evidence) | None — cite corroborating files instead |

---

## 9. Hackerhouse Claims Table

**Demo verdict:** even with public testnet delayed, the locked M7 demo
(offline epoch + wire happy-path + wire kill-test; Docker required, no
network; ~2m25s of epochs, 5–8 min narrated; fallback artifacts preserved) is
a credible, rehearsed stage path. Reference the localnet rehearsal verbally;
keep `09_read_back.txt` and the epoch-2 receipt JSON off screen (the
all-zero row and the frozen `commit_reveal_enabled:false` mis-read invite the
wrong question) — show the postfix `mode=skipped, reason=commit_reveal_enabled`
receipts instead if asked about fail-closed behavior.

| Tier | Claim | Evidence / wording |
|---|---|---|
| **Safe today** | Full validator loop runs locally: Docker-backed Dolores verification → gates → scoring → EMA → weights → archive → replay | `work/m7_demo_rehearsal/`, demo transcript |
| Safe today | Honest miner beats duplicate-spammer and invalid miner deterministically (1.0 vs 0.0), replay-verified | offline & wire reports, `REPLAY OK` |
| Safe today | Real signed Bittensor axon/dendrite transport between processes; unreachable-miner handled distinctly from infra errors | `work/m7_demo_rehearsal/wire_*` |
| Safe today | On localnet we created a subnet, started emission, registered a validator + 2 miners, obtained a validator permit, and produced the first `dry_run_ok` receipt | `work/m5_full/` (§3 table) |
| Safe today | Chain layer is fail-closed with a four-layer live gate; 62 tests, ruff clean | `chain.py`, this review |
| **Careful wording** | Live `set_weights`: *"On localnet a live set_weights extrinsic was accepted by a real substrate node (inclusion-waited, success=true). That subnet had commit-reveal enabled, so the value sits committed-not-revealed and a direct metagraph read shows zero — expected behavior, and our validator now fail-closed skips under commit-reveal rather than submitting a vote it can't read back."* Never say "weights visible on chain." |
| Careful wording | End-to-end: *"We've rehearsed the entire create→register→stake→permit→submit sequence against a real substrate node; the one step not yet closed is a nonzero metagraph read-back, blocked by commit-reveal."* |
| Careful wording | M5 status: *"a healthy partial — every gap is commit-reveal or signing-gated, not a code defect."* |
| **Must wait for public receipts** | "Running on Bittensor testnet", any public netuid, public permit/stake/weights, emissions, public miners, `testnet-v0` tag, any training-improvement result |

---

## 10. Documentation Changes Made in This Review

Three documentation-only factual corrections (the pre-existing "live
set_weights … unexecuted" phrasing became false once the Leon-authorized
localnet submission happened, and would visibly contradict verbal claims at
the hackerhouse):

1. `README.md` (~line 51): now says never executed **on any public network**,
   with the localnet exception and diary pointer.
2. `docs/hackerhouse/demo-script.md` (line ~8): same correction.
3. `configs/testnet.json` `chain_client` field: same correction.

No implementation code, tests, or artifacts were modified.

---

## 11. Subagent Appendix

Four Opus 4.8 slices, run in parallel, findings reconciled by the lead:

1. **Extrinsic-gate audit** — confirmed single signing path, default-safe,
   four-layer gate, strict allowlist, honest receipts; found B-2 (probe
   fail-open) and the test gaps in B-6.
2. **M5 artifact audit** — corroborated the full rehearsal sequence,
   resolved the one-uid payload as correct honest-wins behavior, re-ran all
   four replays (pass), catalogued B-7 and the three commit-reveal-disable
   failure modes as chain/tooling quirks.
3. **Testnet protocol readiness** — live balance (10.0 τ) and burn-cost
   (1.0 τ); established commit-reveal-by-default on fresh testnet subnets
   (B-1) and both remediation paths; live cost/timing table; found B-3/B-5
   version-drift items in installed SDK source.
4. **Demo/claims risk** — M7 demo verdict, ranked demo paths, three-tier
   claims table, and the stale-doc findings fixed in §10.

Lead-reviewer personal verifications: commit-reveal fix diff and probe
behavior; epoch-2 receipt + `weights_epoch_2.json` reconciliation;
`wait_for_inclusion=True` at `chain.py:199`; `ExtrinsicResponse` field
inventory in installed SDK source (types.py:286); `version_key` provenance
(`config.py:192` → `chain.py:459`).
