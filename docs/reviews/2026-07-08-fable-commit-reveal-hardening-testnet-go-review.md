# Fable Review — Commit-Reveal Hardening & Public Testnet Go Decision

Date: 2026-07-08 (afternoon)
Reviewer: Fable (lead), orchestrating four Opus 4.8 review slices (hardening
code review; test/receipt review; testnet readiness & live-weight path;
dirty-tree/launch hygiene). Load-bearing findings re-verified personally.

Scope: commit `ba65010 harden commit-reveal chain readiness` (Codex's
implementation of §7 from
`docs/reviews/2026-07-08-fable-m5-public-testnet-go-no-go.md`), plus live
read-only public testnet state and pre-launch tree hygiene.

No public-chain write, signing, spend, registration, staking, weight-setting,
git push, tag, paid provider call, or wallet-secret inspection was performed.

---

## 1. Executive Verdict

- **Public testnet subnet registration: GO.** No code blocker remains. The
  only preconditions are procedural: commit the dirty docs and **push to
  GitHub before running `subnets create`** (§6, step 0) — the create
  extrinsic embeds `--github-repo` in the on-chain identity, and the public
  repo is currently missing `ba65010` entirely (local is 1 commit ahead).
- **First public live-weight run: GO WITH CONDITIONS.** The hardening closes
  every P0/P1 from the prior review. Conditions: follow the Path A sequence
  (owner-toggle commit-reveal off, **verify the flag reads false**, then
  live weights), with Path B (`--allow-commit-reveal`) as the sanctioned
  fallback; expect no submission to be possible until ~1 tempo (~72 min)
  after register+stake (validator permit + rate limit); and keep the P2
  items in §4 on the Codex queue — none block the run.

All three §7 prescriptions are verified implemented and correct:
B-2/C2 (fail-closed probe), B-1 path B (`--allow-commit-reveal` opt-in),
B-3 (`extrinsic_receipt` metadata). Codex's report was accurate; the four
extrinsic gates are untouched and `--allow-commit-reveal` is strictly
additive.

---

## 2. Evidence Table

| Claim | Evidence |
|---|---|
| Probe fails closed on every unknown path (method absent, kwargs raise, positional raise, preflight-level raise, None return) — no path maps unknown→disabled | `chain.py:154-172` (probe returns `bool \| None`, never False on failure); `chain.py:311-325` (both raise and None → `reason=commit_reveal_probe_failed`); `chain.py:551-553` (double guard in `_readiness_skip_reason`); test `test_commit_reveal_probe_failure_skips_without_set_weights` (asserts skip + zero `set_weights` calls) |
| Default still skips CR-enabled subnets | `chain.py:554-555` (`commit_reveal_enabled and not self.allow_commit_reveal`); test `test_commit_reveal_enabled_skips_without_set_weights` (extended, not weakened) |
| `--allow-commit-reveal` cannot be accidentally enabled | CLI `store_true` only (`validator.py:38`) → explicit param → `bool(None)=False` default (`config.py:247`); no env/config-file binding (grep-verified); test `test_commit_reveal_opt_in_loads_only_from_explicit_arg` pins that even `DOLORES_ALLOW_COMMIT_REVEAL=1` is ignored |
| Four live gates intact; allow_commit_reveal is additive, not a substitute | `_missing_extrinsic_gates` unchanged (`chain.py:651-661`); `allow_commit_reveal` appears only in `_readiness_skip_reason` (`chain.py:554`); single `set_weights` call site (`chain.py:476`) reachable only after both checks |
| `submitted_commit_reveal` cannot fire with unknown CR state | `chain.py:514-518` reason selection; None is unreachable there because the readiness gate returns `commit_reveal_probe_failed` first (proven in slice 1 Q4) |
| Receipts now capture real inclusion metadata | `_submission_from_response` reads `extrinsic_receipt` (`chain.py:701-770`); real SDK `ExtrinsicReceipt` exposes `block_hash`, `block_number`, `extrinsic_hash`, `extrinsic_idx`, `is_success` (verified in `.venv` source); test `test_submission_from_response_reads_extrinsic_receipt_metadata` |
| Suite health | ruff clean; `pytest -q` = **68 passed** (independently re-run by two slices); 6 new tests + 2 extended, zero assertions removed (git-diff verified); import discipline holds |
| Reveal is chain-side and automatic under Path B | bittensor 10.5.0 `commit_timelocked_weights_extrinsic` (`core/extrinsics/weights.py:24`): one extrinsic carrying a drand-timelocked commit with a future `reveal_round`; **no client-side reveal call exists on this path** — the chain decrypts when the drand round arrives; validator may exit after commit |
| Live testnet state (read 14:32–14:35) | Balance 10.0 τ free (unchanged); burn-cost 1.0 τ (unchanged); newest subnet netuid 440: `commit_reveal_weights_enabled=True`, `weights_version=0`, `max_weights_limit=65535`, tempo=360, `weights_rate_limit=100`, `min_burn=0.0005` τ |
| version_key / max-weight risks cleared for a fresh subnet | Repo submits `version_key=1` vs fresh-subnet `weights_version=0` floor (passes); single-uid full-weight payload allowed at `max_weights_limit=65535` |
| Operator docs match code | Runbook/README/configs use the real flag and reason strings (cross-checked against `chain.py` at HEAD); CR receipts described as "commit evidence, not immediate metagraph read-back evidence" |

---

## 3. What Changed Since the Prior Verdict

Prior review conditions and their status:

| Prior item | Status |
|---|---|
| C1/B-1 (P0): commit-reveal strategy | **CLOSED.** Both paths now exist: owner toggle (Path A, procedural) and `--allow-commit-reveal` (Path B, code). New decisive fact: the SDK's CR path is a single timelocked-commit extrinsic with **automatic chain-side reveal** — no client reveal step, no need for the validator to stay alive. |
| C2/B-2 (P1): probe fail-open | **CLOSED.** Fail-closed with `commit_reveal_probe_failed`, tested. |
| B-3 (P1): receipt loses inclusion metadata | **CLOSED** for the fields the SDK actually has (`block_hash`, `block_number`, `extrinsic_hash`, `extrinsic_idx`, `receipt_success`). `included`/`finalized` remain permanently null — the SDK exposes no such attributes anywhere; cosmetic (§4 P2-3). |
| B-5 (P2): version_key | Verified safe on a fresh subnet (`weights_version=0` floor). Keep in sync if the hyperparameter is ever raised. |

---

## 4. Remaining Blockers — none blocking; all P2

| # | Pri | Item | Detail |
|---|---|---|---|
| P2-1 | P2 | Unguarded lazy-property reads in receipt writing | `chain.py:761-769` reads SDK `extrinsic_idx`/`is_success`, which are lazy properties that can perform RPC and raise; the `_submission_from_response` call site (`chain.py:497`) is unguarded. Currently masked because `sign_and_send_extrinsic` pre-resolves both before returning — incidental, not contractual. Wrap defensively so a post-submit receipt write can never raise after on-chain success. |
| P2-2 | P2 | Mode-label divergence for probe failure | standalone `preflight()` records `mode="error"` (`chain.py:317`); the epoch receipt records `mode="skipped"` (`chain.py:401-407`). Same reason string; both fail closed. Cosmetic. |
| P2-3 | P2 | `included`/`finalized` always null in production | Real SDK has no `is_included`/`is_finalized`; the fake fabricates them. Drop the fields or document them as reserved. |
| P2-4 | P2 | Test-fake read-back divergence (carried over) | `FakeSubstrate.read_back_weights` returns `{"matches_submitted": True}` vs production `None`; the new CR submit test does not assert `read_back is None`, so it tolerates a receipt shape implying immediate readability. |
| P2-5 | P2 | Two coverage gaps | No end-to-end `apply_weights` test for the probe-returns-None path (only unit-level); no test that `allow_commit_reveal=True` with a missing extrinsic gate still blocks (`extrinsics_not_allowed`). Architecturally safe; untested. |
| P2-6 | P2 | Runbook dry-run ordering | The runbook's first dry-run block reads as if `dry_run_ok` is expected on a fresh (CR-enabled) subnet; without `--allow-commit-reveal` it will skip with `commit_reveal_enabled` before building a payload. The correct caveat exists a paragraph later — reorder for clarity. |

---

## 5. Recommended Next-Action Sequence

1. **Leon (or Codex, no signing): commit the dirty docs** (§8 — decision:
   yes, both, plus the two files from this review session), then
   **`git push`**. Do not run `subnets create` before the push: the on-chain
   `--github-repo` identity must point at a repo that contains the
   commit-reveal layer.
2. **Leon: registration block** (§6) — create → check-start → start →
   register ×3 → stake. ~1.002 τ burned + recoverable stake.
3. **Leon: Path A toggle** — `btcli sudo set --netuid <N> --param
   commit_reveal_weights_enabled --value false --network test`, then verify
   via a hyperparameters read that it is **False** (localnet lesson: outer
   sudo success can mask inner failure). Note the on-chain param name is
   `commit_reveal_weights_enabled` (the repo's internal probe field is the
   shorter `commit_reveal_enabled`).
4. **Wait ~1 tempo (~72 min)** after register+stake — the validator permit is
   assigned at an epoch boundary and `blocks_since_last_update` starts at 0,
   so the repo will fail-closed skip (`no_permit` / `rate_limited`) until
   then. Confirm readiness with a dry-run receipt (`reason=dry_run_ok`).
5. **Leon: live weights** (§7) — Path A command if the flag verified false;
   Path B command (add `--allow-commit-reveal`, expect
   `submitted_commit_reveal`, read-back ~72 min later) if the toggle stays
   blocked by an admin freeze window after 3 attempts.
6. **Codex (queue, non-blocking):** P2-1 defensive wrap; P2-4/P2-5 test
   fixes; P2-3 field cleanup; P2-2/P2-6 cosmetic doc/label alignment.

Timeline expectation from create to a **visible nonzero metagraph weights
row**: Path A ~72–90 min; Path B ~144–160 min (commit visible immediately,
weights row zero until the drand reveal ~1 tempo after submission).

---

## 6. Public Testnet Registration Command Sheet (LEON ONLY, `--network test`)

Every command below signs or spends and is LEON ONLY. Agent runs only the
read-only verification steps marked AGENT.

**Step 0 — STOP GATE (procedural).** Dirty docs committed; `git push`
completed; GitHub repo shows `ba65010`+. AGENT re-reads burn-cost and
balance; STOP if burn-cost > 1.5 τ or balance < 10 τ.

```bash
.venv/bin/btcli subnets burn-cost --network test          # AGENT
.venv/bin/btcli wallet balance --ss58 5ELE5RrYaxhRLoumvMenr2rSqpZZLX4nxNnYA5B7mLLNJHVG --network test   # AGENT
```

**Step 1 — create (one-shot identity; final name/contact BEFORE running).**
A bad-signature or RPC-failed attempt consumes nothing (proven on localnet);
if create errors, STOP and diagnose, don't blind-retry.

```bash
.venv/bin/btcli subnets create \
  --wallet-name dolores-test --wallet-hotkey validator \
  --subnet-name "<FINAL NAME>" \
  --github-repo https://github.com/Leonwenhao/dolores-bittensor-subnet \
  --subnet-contact "<CONTACT>" \
  --network test
# Record netuid <N>.
.venv/bin/btcli subnets list --network test --json-output   # AGENT verify
```

**Step 2 — start (gated).**

```bash
.venv/bin/btcli subnets check-start --netuid <N> --network test   # AGENT
.venv/bin/btcli subnets start --netuid <N> --wallet-name dolores-test --network test
```

**Step 3 — register ×3, read-back after each.**

```bash
.venv/bin/btcli subnets register --netuid <N> --wallet-name dolores-test --wallet-hotkey validator --network test
.venv/bin/btcli subnets register --netuid <N> --wallet-name dolores-test --wallet-hotkey miner-0  --network test
.venv/bin/btcli subnets register --netuid <N> --wallet-name dolores-test --wallet-hotkey miner-1  --network test
.venv/bin/btcli subnets show --netuid <N> --network test --json-output   # AGENT: 3 uids
```

**Step 4 — stake (recoverable).**

```bash
.venv/bin/btcli stake add --amount 1.0 --netuid <N> \
  --wallet-name dolores-test --wallet-hotkey validator \
  --safe --tolerance 0.05 --network test
```

**Step 5 — AGENT: permit poll + preflight.** Poll until
`validator_permit=true` for `5DyNfBdY…CLdm` (expect up to ~1 tempo); then
netuid-aware preflight must PASS. STOP if no permit after 2 tempos.

---

## 7. First Live-Weight Command Sheet (LEON ONLY)

**Path A (primary) — commit-reveal off, immediate readability:**

```bash
# A1. Toggle (retry at a different point in the tempo if freeze-window-blocked):
.venv/bin/btcli sudo set --netuid <N> \
  --param commit_reveal_weights_enabled --value false \
  --wallet-name dolores-test --network test
# A2. AGENT — verify the flag actually reads False (mandatory STOP gate):
.venv/bin/btcli subnets hyperparameters --netuid <N> --network test
# A3. Dry-run first; expect reason=dry_run_ok. Then live:
export DOLORES_ALLOW_EXTRINSICS=1
.venv/bin/python neurons/validator.py --mode testnet --network test \
  --netuid <N> --chain live --allow-extrinsics \
  --confirm-live I-AM-LEON-AND-I-APPROVE \
  --epoch <E> --quota 2 --work work/testnet_live \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
unset DOLORES_ALLOW_EXTRINSICS
# Expect: mode=submitted, reason=submitted_ok, submission carries
# block_hash/block_number/extrinsic_hash/extrinsic_index/receipt_success.
# AGENT: manual metagraph read-back ~1-2 blocks later — nonzero row expected.
```

**Path B (fallback if the toggle will not flip after 3 attempts) — keep CR
on, explicit opt-in:**

```bash
export DOLORES_ALLOW_EXTRINSICS=1
.venv/bin/python neurons/validator.py --mode testnet --network test \
  --netuid <N> --chain live --allow-extrinsics --allow-commit-reveal \
  --confirm-live I-AM-LEON-AND-I-APPROVE \
  --epoch <E> --quota 2 --work work/testnet_live \
  --wallet.name dolores-test --wallet.hotkey validator --timeout 45
unset DOLORES_ALLOW_EXTRINSICS
# Expect: mode=submitted, reason=submitted_commit_reveal. This is COMMIT
# evidence only. The chain auto-reveals ~1 tempo (~72 min) later (drand
# timelock; no further validator action needed). AGENT: read back the
# metagraph AFTER the reveal window; do not judge the zero row before it.
```

Common to both paths: the receipt's `read_back` field is a stub (always
null) — the AGENT metagraph poll is the real verification. Never leave
`DOLORES_ALLOW_EXTRINSICS` set.

---

## 8. Dirty Docs — Commit Before Registration? Yes.

- `docs/hackerhouse/demo-script.md` (modified): the working-tree version is
  the true one — HEAD's "STOP-LEON gated and unexecuted" is now false; the
  edit aligns it with the localnet-caveat framing already committed to
  README/configs in `ba65010`. Not a conflict with `ba65010` (which didn't
  touch this file). Commit it.
- `docs/reviews/2026-07-08-fable-m5-public-testnet-go-no-go.md` (untracked):
  finished, dated review artifact; no secrets. Commit it. (Its self-reported
  "62 tests" is correct for its own scope at `1245791`; don't quote it as
  current.)
- Also new this session: this report and the Phase-8 correction to
  `docs/runbooks/m5-localnet-command-sheet.md` (§10). Commit together.

Suggested message:
`align public docs with commit-reveal hardening; add go/no-go and hardening reviews`

Then **push before create** (§5 step 1 rationale: local is 1 commit ahead of
origin; the on-chain repo link must not point at pre-hardening code).

Claims-sweep result (slice 4): README, configs, runbook, demo-script (with
the working-tree edit) are all accurate at HEAD — no remaining "unexecuted"
without the localnet caveat, no doc implying commit-reveal receipts are
read-back evidence, no reason/flag strings that don't exist in code.

---

## 9. Hackerhouse Claims Table

**After registration (before live weights):**

| Claim | Basis |
|---|---|
| "Dolores is a registered subnet on Bittensor testnet — netuid N, here's the on-chain identity pointing at our repo" | `subnets show --netuid N` |
| "Validator and two miners are registered on-chain; validator holds a permit" | metagraph read (after permit epoch) |
| Everything in the prior review's "safe today" tier (full local loop, adversarial gating, localnet rehearsal incl. accepted live submission) | unchanged |
| NOT yet: "weights live on testnet" — the weights row is zero until the live run | — |

**After a Path A live run (or Path B + reveal window):**

| Claim | Basis |
|---|---|
| "Our validator sets weights on Bittensor testnet — here's the nonzero metagraph row and the receipt with block hash and extrinsic index" | epoch receipt + AGENT read-back |
| "Honest miner outweighs the duplicate spammer on-chain" | weights artifact + metagraph row |
| Path B nuance: between commit and reveal, say "weights are committed on-chain (timelocked); they become readable at the next epoch" — never "visible now" | `submitted_commit_reveal` receipt |

---

## 10. Documentation Changes Made in This Review

One documentation-only correction (authorized category: prevents an
immediately false claim): `docs/runbooks/m5-localnet-command-sheet.md`
Phase 8 — added a HEAD-behavior-change note and replaced the single
`submitted_ok` acceptance line with the three actual outcomes
(`submitted_ok` when CR disabled; `submitted_commit_reveal` with
`--allow-commit-reveal`; `skipped/commit_reveal_enabled` without the flag).
The sheet previously promised `submitted_ok` from a command that now
fail-closed skips. No implementation code, tests, or artifacts touched.

---

## 11. Subagent Appendix

1. **Hardening code review** — all three §7 items verified fail-closed and
   correctly isolated; four gates untouched; found P2-1 (lazy-property
   receipt reads), P2-2 (mode label divergence, independently spotted by the
   lead first), P2-3 (`included`/`finalized` phantom fields).
2. **Test/receipt review** — 68 passed, 6 new tests + 2 extended, zero
   weakened; found P2-4 (fake read-back divergence unaddressed) and P2-5
   (two coverage gaps); confirmed runbook receipt language unambiguous.
3. **Testnet readiness** — live balance/burn-cost unchanged (10.0 τ / 1.0 τ
   at 14:32); established that CR reveal is chain-side automatic (drand
   timelock, no client reveal) — the fact that makes Path B viable; permit +
   rate-limit make ~1 tempo the earliest submit for all paths; version_key
   and max_weights_limit cleared for fresh subnets; recommended Path A with
   Path B fallback.
4. **Launch hygiene** — dirty demo-script edit is the true version; commit
   both dirty files; push before create (repo-identity staleness); found the
   command-sheet Phase-8 false acceptance (fixed, §10); claims sweep
   otherwise clean.

Lead verifications: `ba65010` full diff read before slicing; probe-failure
receipt mode traced first-hand (`chain.py:402-407`); command-sheet Phase 8
read and corrected.
