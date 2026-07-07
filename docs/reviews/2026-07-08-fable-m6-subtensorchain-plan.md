# Fable M6 / SubtensorChain Planning Review — 2026-07-08

Reviewer: Fable (lead architecture/release-readiness reviewer), orchestrating
five bounded Opus 4.8 review slices (conformance, Bittensor mechanics,
SubtensorChain design, test/localnet strategy, operator runbook) and personally
verifying load-bearing claims. Repo state reviewed: branch `m4-blocked-runbooks`
at commit `8677875` ("lock m7 hackerhouse demo"), clean tree. No implementation
code was modified during this pass. No signing/spend/extrinsic command was run;
all public-chain reads used `--network test`. This is a historical planning
review; later M6 chain-readiness work supersedes its "not yet implemented"
status statements.

---

## 1. Executive Verdict

**Yes — we are ready to start M6 chain-readiness implementation today.**
The conformance slice returned `M6-START: CLEAR`: tree clean at `8677875`, ruff
clean, 44 tests passing, commit `8677875` verified docs/artifacts-only, the
`ChainClient`/`NullChain` seam is in place in `src/dolores_subnet/chain.py`, and
zero extrinsic code exists anywhere in `src/`, `neurons/`, or `scripts/`
(verified by grep). There are no P0 or P1 findings against the current state.

**Order: build the M6 read-only + dry-run chain layer FIRST, then run a
timeboxed M5 localnet rehearsal, then M6 public testnet.** This resolves the
apparent M5-vs-M6 tension: at the reviewed commit, M5 could not run because
localnet mode had no chain client (`neurons/validator.py:41-46` rejected it), so
the chain client is the critical path for both. Once built, M5 becomes a
~90-minute, zero-TAO dress rehearsal that measures the two most expensive
unknowns (validator-permit stake threshold, live `set_weights` acceptance)
before the one-shot, ~2-day-rate-limited public `subnet create`. The historical
reason to pre-waive M5 is gone: the `subtensor-localnet:devnet-ready` image is
published multi-arch **including arm64/linux** (personally verified via
`docker manifest inspect`), the Docker daemon is up, and ports 9944/9945 are
free.

**Recommended next `/goal` scope for Codex** (no extrinsics, no chain writes):

> Implement M6 chain-readiness: extend `src/dolores_subnet/chain.py` with a
> `_Substrate` facade and `SubtensorChain` (read-only preflight, hotkey→uid
> mapping, dry-run weight publication, four-layer-gated live path that is
> unreachable by default), add `netuid` to `SubnetConfig`, add
> `--chain {off,dry-run,live}` + `--netuid` to `neurons/validator.py` with a
> lazy `run_chain` path, extend `scripts/preflight.py` chain checks, write the
> separate `chain_receipt_epoch_N.json` artifact, add the mocked-substrate test
> suite (~18 tests below), and update the runbook. Verification: ruff, pytest
> (existing 44 + new tests), `test_import_discipline` still green, offline/wire
> artifacts byte-identical to today.

STOP-LEON gates are unchanged: no `subnet create`, `register`, `stake add`, or
live `set_weights` happens in this scope. M5 localnet signing and everything in
§6 remains Leon-at-the-keyboard.

---

## 2. Current State Verification

Personally re-verified or verified by the conformance slice on 2026-07-08:

| Item | Status | Evidence |
| --- | --- | --- |
| Repo state | Clean tree at `8677875`; ruff clean; **44 tests pass** | slice-1 run of `git status --short`, `ruff check .`, `pytest -q` |
| Commit `8677875` | Docs/configs/demo-artifacts only — no `src/`, `neurons/`, `scripts/`, `tests/` changes | `git show --stat 8677875` |
| M4 | Signed off, local wire mode complete (post `39f75f7`) | prior review + artifacts re-verified |
| M7 | Demo-locked; transcript numbers match demo-script expectations and on-disk `work/m7_demo_rehearsal/*` artifacts exactly (honest 1.0 / spammer 0.0 / kill-path `unreachable`, `degraded:false`, `weight_result.mode:"fallback"`) | slice-1 jq verification of all three `weights_epoch_1.json` |
| Docs hygiene | No stale status claims, no unsafe unmarked signing commands, SS58 keys consistent everywhere, all finney/mainnet mentions are prohibitions | slice-1 sweep; only trivial P2 notes (a ~1s timing rounding in demo-script.md:37; the runbook's forward-looking M6 config template omits `balance.source`/`chain_client` fields) |
| Wallet / TAO | `dolores-test`, 10.0 test TAO free / 0.0 staked, `netuid: null`, `status: funded_no_public_subnet_registered` | `configs/testnet.json` (coherent with README/runbook) |
| Burn cost | `btcli subnets burn-cost --network test --json-output` → `{"burn_cost": {"rao": 1000000000, "tao": 1.0}, "error": ""}` — **1.0 τ live**, dynamic, re-query at go-time | slice-2 and slice-5 live reads (endpoint healthy, sub-second response) |
| Chain seam | `ChainClient` Protocol + `NullChain` only; `run_epoch(..., chain_client=None)` defaults to `NullChain()` at `epoch.py:110`; grep for `set_weights\|add_stake\|register\|transfer\|extrinsic` across `src/ neurons/ scripts/` hits only the chain.py docstring | slice-1 + my own reads |
| Localnet feasibility | arm64 manifest published for `ghcr.io/opentensor/subtensor-localnet:devnet-ready`; Docker daemon up (aarch64, 28.3.0); ports 9944/9945 free; image not yet pulled (multi-GB pull pending) | slice-4; arm64 manifest personally re-verified |

**Remaining blockers to M6 tier (a)** — all expected, none new:

1. `SubtensorChain` unbuilt (this plan's subject).
2. `SubnetConfig` has no `netuid` field; `neurons/validator.py` has no
   `--netuid`/`--chain` args (verified against its current arg list).
3. STOP-LEON human gates H4 (spend approval vs fresh burn cost), H5 (subnet
   identity strings — now needed *at create time*, see §4), H6 (Leon at
   keyboard for every extrinsic).

---

## 3. `SubtensorChain` Design

Adopted from the design slice with two adjudications by me (commit-reveal
posture; receipt layout confirmed). Design only — no code written.

### 3.1 Placement and import discipline

Everything stays in `src/dolores_subnet/chain.py`. **Constraint verified
first-hand:** `tests/test_import_discipline.py:27` imports
`dolores_subnet.chain` under a `sys.meta_path` blocker that raises on any
`bittensor*` import, and asserts NullChain's exact record. Therefore:

- Module top of `chain.py` stays bittensor-free.
- All `import bittensor` statements live inside `_Substrate` method/ctor bodies
  and `SubtensorChain` call paths — never at class-definition time. Defining
  the classes in the module is safe; only *instantiation* touches bittensor.
- `NullChain`, `ChainClient`, and `ChainWeightResult.to_record()`'s
  `{mode, receipt, reason}` shape are frozen: `scripts/report.py:80` reads only
  `mode`, and `tests/test_epoch_offline.py:105,131` assert the exact fallback
  record (both personally verified). New modes/reasons appear only on
  SubtensorChain runs.

### 3.2 Class shape

- **`_Substrate`** — a thin private facade over `bt.Subtensor` + wallet and the
  single mockable seam for tests. Read-only methods: `block()`,
  `subnet_exists()`, `sync_metagraph(lite=True)`, `hotkey_uid(ss58)`,
  `validator_permit(uid)`, `weights_rate_limit()`,
  `blocks_since_last_update(uid)`, `commit_reveal_enabled()`,
  `read_back_weights(validator_uid)`, and
  `process_and_convert(uids, weights)` (wrapping
  `weight_utils.process_weights_for_netuid` →
  `convert_weights_and_uids_for_emit`; verified at
  `weight_utils.py:214/:165` in the installed SDK 10.5.0). One signing method:
  `set_weights(uids, weights, version_key)` → `ExtrinsicResponse`
  (SDK signature verified at `subtensor.py:8154`; response type at
  `types.py:286`).
- **`SubtensorChain(network, netuid, wallet_name, wallet_hotkey, publish="dry_run", allow_extrinsics=False, substrate=None)`**
  — constructor calls `assert_safe_network(network)` **before** any bittensor
  touch; no default network; finney/mainnet/unset refuse exactly as today.
  Implements the existing `ChainClient.apply_weights(...)` protocol so it drops
  into `run_epoch` with zero changes to the epoch engine's logic. Also exposes
  a read-only `preflight()` (block, subnet_exists, validator uid/registration,
  permit, rate-limit, commit-reveal flag) and `map_hotkeys(...)`.
- **`build_chain_client(cfg, publish="off")`** — factory used by
  `neurons/validator.py`; `off` → `NullChain()`, else lazily constructs
  `SubtensorChain`. Reads the `DOLORES_ALLOW_EXTRINSICS` env gate.
- New vocabulary: `mode ∈ {fallback, dry_run, submitted, skipped, error}` and a
  fixed reason enum (see §3.5) — additive; the NullChain path never emits them.

### 3.3 Extrinsic gate (the STOP-LEON mechanism in code)

**Four-layer AND gate — all required to reach `set_weights`, none defaulted
on:**

1. `SubtensorChain(publish="live", allow_extrinsics=True)` (code defaults:
   `dry_run` / `False`).
2. Env var `DOLORES_ALLOW_EXTRINSICS=1` — the keystone: it cannot be introduced
   by editing repo code; it must be exported in Leon's own shell.
3. CLI `--chain live` on the validator (default `off`; agents never pass more
   than `dry-run`; `live` appears in no script, test, or runbook default).
4. Submit-time confirmation: interactive TTY prompt requiring the literal
   string `I-AM-LEON-AND-I-APPROVE` naming the netuid and uid count; the
   non-TTY fallback flag is inert unless layers 1–3 already hold.

The prompt lives in the CLI (`neurons/validator.py`), the AND-gate check in the
library, so library code never blocks on stdin in tests. An unattended agent,
CI, or a fat-fingered command line each fails at least one layer. Gate misses
produce `error/extrinsics_not_allowed` — recorded, never raised into the epoch.

### 3.4 Determinism and receipts (two-file layout)

Replay (`assert_replay_matches`, `epoch.py:169-177`) compares only
`epoch_scores` and `weights` — verified first-hand — so a volatile receipt would
not break replay, but it would break the clean `del(.timing)` audit-diff
property. Therefore:

- **`weights_epoch_N.json`** stays fully deterministic. On chain runs its
  `weight_result.receipt` holds only a deterministic reference:
  `{receipt_file, payload_digest, netuid, n_uids}` where `payload_digest` is
  the sha256 of the canonical `{uids_emitted, weights_u16, version_key,
  netuid}` JSON — stable across dry-run replays.
- **`chain_receipt_epoch_N.json`** (new, same epoch dir) holds everything
  volatile: full payload (hotkey→uid pairs, normalized weights, emitted u16
  vector, `dropped_hotkeys`), submission record (`extrinsic_success`, block,
  extrinsic hash, timestamps, inclusion/finalization flags), and a read-back
  block (`matches_submitted`). In `dry_run` mode `submission`/`read_back` are
  null and `payload` is complete — this is the auditable "what WOULD be
  submitted" artifact Leon approves in §6 step 9. Read-back runs only in
  `submitted` mode and is best-effort (null on failure, not an epoch error).

**Implementation ordering note (personally verified):** `epoch.py` calls
`apply_weights` at line 110 but only creates the epoch dir at lines 134-135.
The receipt writer must `mkdir -p` the epoch dir itself, or the existing
`mkdir` moves above the chain call. One-line change; flag it in the goal.

### 3.5 Hotkey→uid mapping and failure modes

Mapping policy (adjudicated: **partial submission with explicit record**, not
fail-closed-on-any-gap): resolve the validator's own uid first (missing →
`error/validator_unregistered`, fail closed); map each epoch hotkey via the
metagraph; unregistered miner hotkeys are dropped into a `dropped_hotkeys`
list that is always recorded in the receipt, and the emitted vector is
renormalized by `process_weights_for_netuid`. Fail closed only when the result
would be empty or the validator cannot act. Never submit a silently truncated
payload.

| Condition | `mode` | `reason` |
| --- | --- | --- |
| NullChain / offline | `fallback` | `offline` (unchanged) |
| All weights zero | `skipped` | `all_zero` |
| Whole epoch infra-degraded | `skipped` | `epoch_degraded_all_infra` |
| RPC unreachable / timeout | `error` | `rpc_unreachable` / `rpc_timeout` |
| `netuid` unset / subnet absent | `error` | `netuid_unset` / `netuid_absent` |
| Validator hotkey unregistered | `error` | `validator_unregistered` |
| Registered but no permit | `skipped` | `no_permit` |
| No epoch hotkey maps to a uid | `skipped` | `no_registered_miners` |
| Within `weights_rate_limit` window | `skipped` | `rate_limited` |
| Commit-reveal enabled on subnet | `skipped` | `commit_reveal_enabled` |
| Extrinsic rejected: version key | `error` | `version_key_mismatch` |
| Extrinsic `success=False` (other) | `error` | `extrinsic_failed` |
| Gate not satisfied but live requested | `error` | `extrinsics_not_allowed` |
| Dry-run computed | `dry_run` | `dry_run_ok` |
| Live submitted + included | `submitted` | `submitted_ok` |

**Commit-reveal adjudication** (slices 2 and 3 diverged): the SDK's
`set_weights` auto-detects and routes commit-reveal (`subtensor.py:8228`), so
technically no code is needed — but a commit-reveal submission has delayed
reveal semantics that break our receipt + immediate-read-back evidence model.
**v0 declines explicitly** (`skipped/commit_reveal_enabled`). We own the subnet
and control the hyperparameter, so this path should never fire; if it does,
that itself is signal worth stopping on.

**`version_key`:** pin to `cfg.spec_version` (=1), do not adopt the SDK's
`version_as_int` default; treat chain-side mismatch as
`error/version_key_mismatch`.

### 3.6 Integration deltas

| File | Change |
| --- | --- |
| `src/dolores_subnet/config.py` | Add `netuid: int | None = None` to `SubnetConfig` + `from_env` (source: `configs/testnet.json` first, `BT_NETUID` env / `--netuid` CLI override). No change to `assert_safe_network`. |
| `src/dolores_subnet/chain.py` | Add `_Substrate`, `SubtensorChain`, `build_chain_client`, mode/reason enums, `HotkeyUidMapping`. NullChain/protocol/record shape untouched. |
| `neurons/validator.py` | Add `--chain {off,dry-run,live}` (default `off`) + `--netuid`; new lazy `run_chain(args)` mirroring `run_wire`'s import discipline; route `Mode.LOCALNET/TESTNET` there instead of the current stub at lines 41-46. Metagraph-based miner discovery feeds the same `run_epoch` engine via `MinerLike` wrappers (open question g3 — confirm before implementation). |
| `scripts/preflight.py` | Extend the existing `chain_reachability_check` (lines 230-240) with `SubtensorChain.preflight()` read-only outputs for chain modes. Preflight never constructs a live-publish client. |
| `src/dolores_subnet/epoch.py` | No functional change except the epoch-dir mkdir ordering note in §3.4. |

---

## 4. Bittensor Testnet Mechanics

Verified against the installed **btcli 9.23.1** and **bittensor SDK 10.5.0**
(all citations checked against site-packages; live reads used `--network test`
and returned sub-second).

**Headline finding: btcli has NO weights command.** `set_weights` must go
through the SDK (`Subtensor.set_weights`, `subtensor.py:8154`, returns
`ExtrinsicResponse` with internal registration and rate-limit pre-checks).
This makes the `SubtensorChain` build mandatory for M6 tier (a) — there is no
CLI workaround.

| Operation | Command / SDK call | Type |
| --- | --- | --- |
| Subnet creation cost | `btcli subnets burn-cost --network test --json-output` | read-only |
| Create subnet (+ identity) | `btcli subnets create --network test --wallet.name dolores-test --subnet-name "..." --github-repo <url> --subnet-contact <email>` | **signing** |
| Can `start` be called yet | `btcli subnets check-start --netuid <N> --network test` / `Subtensor.is_subnet_active` | read-only |
| Start emissions (owner) | `btcli subnets start --netuid <N> --network test --wallet.name dolores-test` | **signing** |
| Register neuron | `btcli subnets register --netuid <N> --network test --wallet.name dolores-test --wallet.hotkey <hk>` | **signing** |
| Per-neuron registration cost | `btcli subnets hyperparameters --netuid <N> --network test` (Burn field) / `Subtensor.recycle(netuid)` | read-only |
| Stake | `btcli stake add --netuid <N> --network test --wallet.name dolores-test --wallet.hotkey validator --amount <A> --safe --tolerance 0.05` | **signing** |
| Metagraph / permits / uids | `btcli subnets show --netuid <N> --network test --json-output` / `Subtensor.metagraph(netuid)` → `.validator_permit`, `.stake`, `.uids`, `.hotkeys` | read-only |
| Set weights | SDK only: `Subtensor.set_weights(wallet, netuid, uids, weights, version_key=..., wait_for_inclusion=True)` | **signing** |
| Payload shaping | `weight_utils.process_weights_for_netuid` → `convert_weights_and_uids_for_emit` (u16, drops zeros) | local |
| Current block | `Subtensor.get_current_block()` | read-only |

Confirmations and cautions:

- **The old lock/return cost command is gone; `burn-cost` is the replacement** — confirmed absent
  from btcli 9.23.1 help; live value **1.0 τ** (recycled burn, anneals over ~2
  days, dynamic — re-query immediately before H4 approval).
- **`btcli subnets start` exists** and post-dTAO testnet subnets start
  inactive; the read-only `check-start` answers "allowed yet?" before Leon
  signs. This command was previously missing from our runbook.
- **Identity at create time:** `subnets create` folds `--subnet-name`,
  `--github-repo`, `--subnet-contact` into the one-shot creation extrinsic —
  **H5 naming must be final before create**, not after.
- **Rate limits:** subnet create ~14,400 blocks (~2 days) per account (chain
  constant `NetworkRateLimit`, not in hyperparameters — unconfirmed exact
  figure from installed tooling); `weights_rate_limit` enforced inside
  `set_weights`; tempo = 360 blocks (~72 min) confirmed live from the testnet
  subnet list.
- **Commit-reveal:** off by default on a fresh subnet; owner-controlled; SDK
  auto-routes if enabled; v0 declines (§3.5).
- **Validator permit:** granted to top-K stakers up to the `max_validators`
  hyperparameter. With only our three hotkeys and `max_validators` almost
  certainly ≥ our validator count, the permit *should* land with modest stake —
  but a minimum-stake floor may exist as a chain-level constant we could not
  read from the installed tooling. **This is the #1 uncertainty M5 exists to
  measure.** Per-neuron registration burn on our subnet is also unknowable
  until the subnet exists (read `recycle(netuid)` right after create, before
  approving the three registrations).

---

## 5. Implementation Plan

Milestone-sized tasks for Codex, in order. Tasks 1–4 are the recommended next
`/goal`; none touches a chain write.

**Task 1 — chain client core** (`src/dolores_subnet/chain.py`,
`src/dolores_subnet/config.py`): `_Substrate` facade, `SubtensorChain` with
read-only preflight + `map_hotkeys` + dry-run + gated live path, mode/reason
enums, `build_chain_client`, `netuid` on `SubnetConfig`. Receipt writer creates
the epoch dir if absent (§3.4 ordering note).

**Task 2 — validator + preflight integration** (`neurons/validator.py`,
`scripts/preflight.py`): `--chain`/`--netuid` args, lazy `run_chain` path
routing LOCALNET/TESTNET modes, metagraph miner discovery wrapper, preflight
chain-readiness extension. Module tops stay bittensor-free.

**Task 3 — tests** (new `tests/test_chain_client.py` + one addition to
`tests/test_import_discipline.py`), all mocked at the `_Substrate` seam:
network-safety refusals (unset/finney/mainnet), dry-run default + payload
correctness + zero `set_weights` calls, partial mapping + `dropped_hotkeys`,
validator-unregistered / no-permit / rate-limited / commit-reveal / all-zero /
netuid-absent / rpc-unreachable outcomes, live gate blocked without env var,
live submit success (env monkeypatched, prompt stubbed) with receipt + read-back,
live extrinsic failure, `weight_result` shape stability (offline record
byte-identical to today), replay unaffected by the receipt file, and the
import-discipline extension (referencing `SubtensorChain` under the blocker is
fine; only instantiation imports bittensor). ~18 tests.

**Task 4 — docs**: runbook M6 section updated with §6 below (adds
`check-start`, identity-at-create, `--safe --tolerance` staking, receipt
conventions, `--json-output` evidence forms); demo-script §3 optional chain
note updated; diary entry.

**Verification for the goal:** `.venv/bin/ruff check .`;
`.venv/bin/python -m pytest -q` (existing 44 + new all green — especially
`test_import_discipline` and `test_epoch_offline` untouched-behavior);
offline + wire epoch artifacts byte-identical to pre-change runs
(`del(.timing)` diff empty); `preflight.py --mode testnet` all-PASS including
chain reachability; a dry-run invocation against `--network test` producing a
`chain_receipt` with `submission: null` — **only if** a netuid exists to point
at; otherwise the dry-run path is exercised via the mocked tests plus, later,
M5 localnet.

**Task 5 — M5 localnet rehearsal** (after tasks 1–4; ~90-minute timebox on the
chain-contact portion): agent pulls and starts
`ghcr.io/opentensor/subtensor-localnet:devnet-ready` (arm64 published), runs
`preflight --mode localnet`; **LEON ONLY** runs create → start → register ×3 →
stake on `ws://127.0.0.1:9944` (throwaway localnet funds, same LEON-ONLY
convention as the runbook); after ≥1 tempo the agent runs the read-only permit
check, then a Leon-supervised epoch with `--chain live` on localnet produces
the first real receipt. Capture: permit threshold actually observed (the #1
measurement), receipt + metagraph read-back under `work/m5/`, diary entry.
**Waive** to the mocked-test substitutes only if the container genuinely fails
on arm64 or the timebox expires — record the waiver in the diary per the plan.
Note: in localnet/testnet modes the *neurons themselves* sign extrinsics
(`serve_axon` on the miner, `set_weights` on the validator), so neuron runs in
those modes are Leon-supervised, not pure agent runs — the runbook should say
this explicitly (today it only marks btcli commands LEON ONLY). This is about
the planned chain-mode code, not current behavior (current code rejects those
modes).

**Task 6 — M6 public testnet** per §6, gated on the §5-of-slice-4 checklist:
tasks 1–4 green, M5 green or waived-with-substitutes, fresh burn-cost re-query,
H4/H5/H6.

---

## 6. Operator Runbook (M6 flow)

Full detail belongs in `docs/runbooks/testnet-runbook.md` (task 4); this is the
authoritative summary. Evidence convention: `work/m6/NN_step.txt|json` for
console/JSON captures, `work/m6/receipts/<action>.json` per signed action,
`configs/testnet.json` updated after each state change, diary transcript.
Steps 0–7 are runnable once tasks 1–2 land; 8–10 need nothing further.

0. **Preconditions** (CODEX-SAFE): clean tree, pytest, ruff, `preflight --mode
   testnet` ×3 hotkeys all-PASS. Any miss → stop.
1. **Chain preflight** (CODEX-SAFE): `burn-cost --json-output`, wallet balance,
   `subnets list` — all `--network test`. A read hanging >60s: retry ≤3 with
   backoff, else abort the day. Never open a signing window on a flaky RPC.
2. **STOP-LEON S1**: approve create against the *just-read* burn cost; budget
   math (create `C` + 3×registration `R` + stake headroom ≤ 10.0 τ; `R`
   unknowable until after create — floored pre-create, re-confirmed at S3);
   acknowledge the one-shot ~2-day rate limit; finalize identity strings (H5).
3. **Create** (LEON-ONLY S2): `btcli subnets create --network test ...` with
   identity flags. Agent read-back: `subnets list` + `subnets show --netuid <N>
   --json-output` confirming our coldkey owns it; record netuid in
   `configs/testnet.json` (`status: public_subnet_registered_no_weights`).
   **Lost-receipt rule:** if output is lost to an RPC drop, re-query state
   first — never blind-retry a create (extrinsics are atomic; no receipt ≠ no
   burn).
4. **Start** (CODEX-SAFE check → LEON-ONLY S4): poll `check-start` read-only;
   meanwhile read `hyperparameters` for the real registration `Burn` →
   **STOP-LEON S3** re-confirm `3R + stake` fits remaining balance; when
   check-start is green Leon runs `subnets start`.
5. **Register** (LEON-ONLY S5): validator first, then miner-0, miner-1 — one
   extrinsic each with a `subnets show` read-back between each; record the
   uid↔hotkey map.
6. **Stake** (LEON-ONLY S6): `stake add ... --safe --tolerance 0.05`. Stake is
   recoverable (slippage only, unlike burns). Amount: if M5 measured the
   threshold, use it plus margin; if M5 was waived, **stake 5.0 τ first** —
   at a hackerhouse each failed attempt costs a ~72-minute tempo wait, so
   over-asking recoverable stake beats iterating (top-up loop remains the
   fallback). Keep ≥0.5 τ free.
7. **Permit wait** (CODEX-SAFE): ≥1 tempo (360 blocks ≈ 72 min), then read-only
   metagraph poll until `validator_permit` reads `True` for
   `5DyN…CLdm`. No weight epoch before True. Still False after top-ups →
   record the observed threshold and fall back to tier (b), documented.
8. **Dry-run epoch** (CODEX-SAFE): validator `--mode testnet --netuid <N>
   --chain dry-run` → `chain_receipt` with full payload, `submission: null`.
   This exact vector is what Leon approves next.
9. **STOP-LEON S7 — live `set_weights`** (LEON-ONLY): Leon reviews the dry-run
   vector (uids, weights, `version_key=1`), exports
   `DOLORES_ALLOW_EXTRINSICS=1` in his own shell, reruns with `--chain live`,
   types the confirmation. Expect `mode: submitted`, receipt with block +
   extrinsic hash. Rate-limit error → wait, don't spam.
10. **Read-back** (CODEX-SAFE): metagraph weights row for our validator uid
    matches the artifact within u16 quantization; cross-check receipt block.
    Mismatch beyond quantization → do NOT claim tier (a); investigate uid
    mapping/version_key before any re-set.
11. **Record** (CODEX-SAFE writes): `configs/testnet.json`
    (`status: public_testnet_weights_set`, `validator_permit: true`, fresh
    balance block), diary with receipts and budget actuals. `testnet-v0` tag
    **only** on tier (a) — STOP-LEON S8.

**STOP-LEON table:** S1 approve-create (irreversible burn below) · S2 create ·
S3 post-create budget re-confirm (registration burns below) · S4 start · S5
three registrations · S6 stake (+top-ups; recoverable) · S7 approve vector +
live set_weights · S8 claims/tag approval.

**Automation split:** Codex may automate every read-only step (0, 1, 3/5/10
read-backs, 4a/4b polling, 7 permit loop, 8 dry-run, 11 file writes) and may
*prepare* exact command strings for Leon — but `create`, `start`, `register`
×3, `stake add`, and live `set_weights` stay manual forever (H6). No command
without `--network test`; nothing containing `finney`; never read wallet key
files or `.env`.

**Flaky-RPC posture:** `--network test` maps to the single endpoint
`wss://test.finney.opentensor.ai:443`; btcli has no failover list. Reads are
idempotent — retry with backoff. Signing windows require a healthy RPC;
recovery from any lost receipt is always re-query-then-decide, never
blind-resubmit. Endpoint was healthy at planning time (sub-second responses).

**Irreversibility:** create burn + its ~2-day rate-limit window and each
registration burn are unrecoverable; stake is recoverable minus slippage;
`set_weights` costs only a fee and is overwritten by the next epoch.

---

## 7. Claims Hygiene

**Claimable now (post-M7, unchanged):** demo-locked offline + localhost-wire
subnet loop with Docker-backed verification, adversarial gates, EMA weights,
archive evidence, replay checks, signed axon/dendrite transport; 10.0 test TAO
on a testnet wallet; deliberately gated chain step.

**After the read-only + dry-run chain layer (tasks 1–4):** "the validator can
compute, shape (u16 + on-chain hyperparameter processing), and audit the exact
weight vector it would submit on-chain, against the live testnet, without
signing anything" and "chain-mode failure semantics are typed and tested." NOT
claimable: any on-chain presence.

**After M5 localnet (if run):** "the full create→register→stake→permit→
set_weights→read-back loop has been executed end-to-end against a real
subtensor chain, with receipts" — qualified *localnet*, never "testnet."

**After public subnet registration (steps 3–5):** "registered public testnet
subnet, netuid N, owned by our coldkey" — but NOT "live subnet", NOT weights,
NOT permit until step 7 reads True.

**Only after a real `set_weights` receipt + matching metagraph read-back
(steps 9–10):** "on-chain weights on public Bittensor testnet, receipt in
repo" — and only then the `testnet-v0` tag. Under any fallback outcome the
record is "human-blocked/diagnosed," never "failed," and no tier-(a) claim is
made. Never claimable in this phase: emissions, public miners, mainnet
readiness, training-improvement results.

---

## 8. Subagent Appendix

Five Opus 4.8 slices, run in parallel; I reconciled the outputs and personally
verified every load-bearing claim below.

- **Slice 1 — conformance:** clean tree at `8677875`, ruff clean, 44 tests
  pass; commit verified docs-only; no stale claims/unsafe docs; SS58 keys
  consistent; M7 transcript matches artifacts; verdict `M6-START: CLEAR` with
  five P2-only notes.
- **Slice 2 — mechanics:** btcli 9.23.1 / SDK 10.5.0 surface mapped;
  **no btcli weights command** (SDK-only set_weights); `burn-cost` confirmed
  as the old lock/return cost replacement, 1.0 τ live; `check-start` discovered;
  registration cost = recycle hyperparameter (post-create readable);
  commit-reveal auto-routed by SDK; permit = top-K stake under
  `max_validators`. Uncertainties preserved honestly: permit stake floor,
  per-neuron burn on a fresh subnet, exact `NetworkRateLimit` constant.
- **Slice 3 — design:** `_Substrate` facade + `SubtensorChain` in `chain.py`;
  four-layer extrinsic gate; two-file deterministic/volatile artifact split;
  failure-mode vocabulary; ~18 mocked tests; seven open questions (I resolved:
  partial submission with `dropped_hotkeys` — yes; commit-reveal — decline in
  v0; TTY prompt in CLI, gate in library; read-back submitted-mode-only,
  best-effort; `version_key` pinned to spec_version; netuid config-file-first;
  metagraph-discovery-feeds-run_epoch confirmed as the intended shape but
  flagged for Codex to confirm at implementation time).
- **Slice 4 — localnet strategy:** arm64 image published (reverses the waive
  assumption), daemon up, ports free; real M5 blocker is the unbuilt client;
  recommendation build-client-then-timeboxed-M5 adopted; pre-create gate
  checklist adopted into §5/§6; risk-retirement table adopted.
- **Slice 5 — runbook:** full 12-step flow with STOP-LEON table, automation
  split, lost-receipt recovery rule, `--safe` staking, identity-at-create
  discovery; independently confirmed the chain-client dependency and current
  validator arg surface.

**Disagreements adjudicated:** (1) commit-reveal — slice 2 "SDK handles it, no
code needed" vs slice 3 "decline explicitly": adopted explicit decline for
receipt/read-back auditability (§3.5). (2) First stake amount — slice 5's 1.0 τ
incremental loop vs slice 4's 8–9 τ over-ask: adopted 5.0 τ first-try when M5
is waived, since each retry costs a ~72-min tempo and stake is recoverable
(§6.6). (3) Slice 4 described localnet-mode neurons as emitting
`serve_axon`/`set_weights` extrinsics — true of the *planned* chain-mode code,
not the current repo (validator.py rejects those modes today); framed
accordingly in §5 with the runbook-convention recommendation kept.

**Personally verified by me (Fable):** `test_import_discipline.py:27` imports
`dolores_subnet.chain` under the bittensor blocker; `report.py:80` +
`test_epoch_offline.py:105,131` freeze the `weight_result` contract;
`assert_replay_matches` compares only `epoch_scores`/`weights`
(`epoch.py:169-177`); the `apply_weights`-before-mkdir ordering at
`epoch.py:110` vs `:134-135`; `set_weights` at SDK `subtensor.py:8154`,
`ExtrinsicResponse` at `types.py:286`, weight helpers at
`weight_utils.py:165/:214`; arm64 present in the localnet image manifest;
`preflight.py:230-240` chain-reachability check exists;
`neurons/validator.py:41-46` rejects chain modes today and its arg surface has
no `--netuid`/`--chain`; `configs/testnet.json` current state; burn-cost 1.0 τ
(live reads by two slices, consistent with my prior direct query).

No signing, spend, or extrinsic command was executed at any point in this
review. No implementation code was modified.
