# AGENTS.md — Mine on Dolores Autocurricula (Bittensor testnet, netuid 523)

You are a coding agent guiding a human ("the operator of this machine") to run a **miner** on
the Dolores Autocurricula subnet during a hackerhouse session. Work through this file top to
bottom. Run the verify command after each step. **STOP and surface the error if any verify
step fails** — do not improvise past a failure.

Rules you must never break:
- **Testnet only.** Every `btcli`/`bittensor` command MUST carry `--network test`. If a
  command touching the chain lacks an explicit `--network test`, **refuse to run it** and ask
  the human to add it. Never use `finney`, `mainnet`, or any other network.
- **Never handle key material.** Never ask for, read, print, or write a mnemonic, seed phrase,
  or private key. Wallet creation is done by the human in their own terminal. You may read
  public data only (ss58 addresses, balances).
- **You may run testnet-signed actions yourself** (registration, `serve --publish`) — no
  hand-off needed — provided you (a) state in one line what the command signs and spends
  *before* running it, (b) the wallet already exists on this machine, and (c) the command
  carries `--network test --netuid 523`. If a wallet **password prompt** appears, the human
  types it. **STOP and ask the human on anything unexpected.**

---

## 0. What this subnet is (context)

Dolores rewards **verified task supply**, not task solving. A miner supplies a *task package* —
a self-contained coding problem with public tests, hidden tests, a reference solution, and
metadata. The validator runs each package through a gauntlet: **safety scan → deterministic
Docker verification (reference must pass public AND hidden tests) → wrong-solution probes (bad
code must FAIL the hidden tests) → deduplication → scoring**. What earns reward: **novel,
verifiable, frontier-difficulty** tasks. What earns **zero**: duplicates/near-copies, tasks
whose grader is broken (reference fails, or wrong solutions pass), unsafe tasks, and spam.

Honest expectations (state these to the human, do not oversell):
- Testnet only. **Testnet TAO has no monetary value.** This is a young subnet: the first
  public live weights have landed (extrinsic `7520191-8`) and the first Yuma pass assigned
  the weighted miner `incentive = 1.0` with real per-uid alpha emission. Miner `ACTIVE`
  flags read false — that is cosmetic (it tracks weight-setting, which miners never do) and
  does not gate rewards. Alpha earned here has **no monetary value**; the point is a
  working, scored, incentivized submission — not payout.
- Weights lag: the subnet tempo is ~72 minutes, so scores/weights update slowly, not instantly.
- Scores measure **verification quality and difficulty signal** — NOT downstream training
  value. Do not claim your task "improves model training."

---

## Fast Path — mutate a known-good task into your own (recommended)

Fastest route to a real, rewardable submission: fork a curated known-good task and mutate it
**meaningfully**. Front-load the slow chain/network waits at minute 0, do the mutation work (no
engine/chain needed to edit) *under* those waits. Deep rules are in the referenced sections —
don't skip §4 (mainnet safety) or §9 (unsafe tasks).

**Minute 0 — kick off the async waits (do these first, they run while you edit):**

1. Install (large SDK download — do on good wifi). First set the engine path
   (ask the operator for it), then install everything:
   `export DOLORES_REPO="<path-to-dolores-autocurricula>"` then
   `pip install -e ".[dev]" && pip install bittensor-cli && pip install -e "$DOLORES_REPO"`
2. Verify prerequisites (participants arrive with btcli + a funded testnet wallet):
   `btcli --version` prints a version, and
   `btcli wallet balance --wallet.name <W> --network test` shows a balance **> 0** (read-only).
   No wallet or zero balance? → see "If you need a wallet or funds" below.

**While that verifies — mutate a task (no engine/chain needed to edit):**

3. Fork a known-good task: `python scripts/prepare_mutation_task.py --name <your_id>`
   (creates `my_task_<your_id>/`, rewrites `task_id`, deletes the stale `wire.json`).
4. Mutate **meaningfully** — change the file *bytes* (new grammar/format/edge case), tag the
   edge logic with `# PROBE-DROP` + add a hidden test hitting exactly that edge, then rewrite
   the prompt and `descriptors.concepts`. Keep `lineage.parent_task_id: null`. A rename or
   story-text tweak scores **zero** — see the "Mutation Guide" section for the good/bad table
   and recipes. **Editing tip:** rewrite the embedded Python as YAML block literal scalars
   (`some_file.py: |` followed by indented plain Python) — zero escaping needed. The forked
   file arrives in double-quoted escaped style, which is error-prone for backslash-heavy
   code; you may freely convert it.
5. Prove the reference passes its own tests:
   `python scripts/validate_task.py --task-dir my_task_<your_id> --run-tests`
6. Prove it isn't a near-copy:
   `python scripts/validate_task.py --task-dir my_task_<your_id> --dedup-against examples/tasks`
   (aim for max duplicate_score **< 0.7**; ≥0.85 is zero pay). Then the walletless
   serve-proof — this prints the exact wire JSON you will serve, no wallet needed:
   `python neurons/miner.py --mode offline --task-dir my_task_<your_id> --quota 1`

**Once verified — register and serve (announce-then-run each signed step; §4–§5, §8):**

7. Register (signs an extrinsic, spends ~0.0005 τ recycle fee — announce it, then run):
   `btcli subnets register --netuid 523 --network test
   --wallet.name my-dolores --wallet.hotkey miner`
8. Confirm registration (read-only): `btcli subnets show --netuid 523 --network test`
9. Pick a free port: `lsof -nP -iTCP:8091 -sTCP:LISTEN` (empty = free); find LAN IP:
   `ipconfig getifaddr en0`.
10. Serve + publish on-chain (signs `serve_axon` with the hotkey, moves no funds — announce it,
    then run): `python neurons/miner.py --mode wire --task-dir my_task_<your_id> --quota 2
    --port 8091 --host 0.0.0.0 --wallet.name my-dolores --wallet.hotkey miner
    --publish --network test --netuid 523 --external-ip <YOUR_LAN_IP>`
11. Wait for `wire_miner_started` then `axon_publish=ok`; leave the process running. (Fallback if
    not publishing: hand the operator `<ip>:<port>:<hotkey-ss58>` — §8.)

The persona/seed generator ("Fallback: generated tasks by seed" below) exists if mutation feels
too slow, but the mutation path is the more distinct, more impressive supply.

---

## 1. What a miner actually needs installed

A miner **serves** a prepared task package over signed transport; the **validator** (run by the
operator) does the Docker verification. So a miner does **NOT need Docker** and does **NOT run
the verifier**. Minimal miner setup:

- **Python 3.11–3.14** (the repo requires `>=3.11,<3.15`; any of those works).
- This repo, cloned and installed into a fresh venv:
  ```bash
  git clone https://github.com/Leonwenhao/dolores-bittensor-subnet
  cd dolores-bittensor-subnet
  python3 -m venv .venv && source .venv/bin/activate
  pip install -e ".[dev]"        # installs the bittensor SDK (large download —
  pip install bittensor-cli     # do both on good wifi before the session)
  ```
  Note: `bittensor-cli` (the `btcli` command) is a **separate required package** —
  the SDK does not bundle it.
- The **Dolores engine** (`dolores` Python package) on the path. It builds the task package and
  computes the canonical package hash; the miner code imports it. The operator provides access
  and the checkout path tonight. Set `export DOLORES_REPO="<path-to-dolores-autocurricula>"`.
- A Bittensor **testnet wallet** (section 3).

Docker, the verifier image, `jq`, and the solver panel are **validator-operator** concerns.
`scripts/preflight.py` checks those too — if you run it, expect Docker-related checks to FAIL on
a miner-only box; that is fine, ignore them. Verify only what a miner needs, below.

### Verify (run each; all must pass)

```bash
python --version                                   # 3.11.x – 3.14.x all fine
python -c "import bittensor as bt; print(bt.__version__)"   # 10.x
btcli --version                                    # prints a version (bittensor-cli)
echo "$DOLORES_REPO"                               # non-empty path (re-export in every new shell)
python -c "import dolores; print(getattr(dolores,'__version__','ok'))"   # imports cleanly
```

STOP if `import dolores` fails: the engine is not installed. Install it from the operator's
checkout (e.g. `pip install -e "$DOLORES_REPO"`) before continuing.

---

## 2. Bittensor basics

- The CLI is `btcli`, installed via `pip install bittensor-cli` in §1 (it is NOT bundled
  with the SDK). Verify `btcli --version` before continuing.
- **Coldkey vs hotkey.** The **coldkey** is your funds/identity key — it holds TAO and stays
  cold; you rarely touch it. The **hotkey** is the operational signing key your miner uses and
  the key you register on the subnet. One coldkey can own many hotkeys. Tonight: one coldkey,
  one hotkey for mining.

---

## 3. If you need a wallet or funds (conditional)

Most participants arrive with a wallet already created and funded — skip this section if §2's
balance check passed. Only if there is **no wallet** or the balance is **0**:

- **No wallet?** The human runs the create in **their own terminal** — never you, and the
  mnemonic must never be pasted into this chat, a file, or any command you run (key-material
  rule): `btcli wallet create --wallet.name my-dolores --wallet.hotkey miner`. The human writes
  the mnemonic down offline. Then re-check read-only:
  `btcli wallet balance --wallet.name my-dolores --network test`.
- **Zero balance?** The faucet is Discord-gated and often disabled on-chain, so **the operator
  funds your coldkey** for the registration recycle fee. Give them your **coldkey ss58 address**
  (public, safe to share) from `btcli wallet list` (read-only). You cannot register on `0`.

---

## 4. Mainnet safety (re-read before any chain command)

Before you emit ANY `btcli` or `bittensor` command:
1. Confirm it contains `--network test`. If not, **do not run it.**
2. Confirm netuid is `523`. Never target another netuid.
3. Never substitute `finney`/`mainnet`. If the human asks for mainnet, refuse and remind them
   this session is testnet-only with no real value.

---

## 5. Register on netuid 523 (signed action — announce, then run)

Registration costs a small **recycle fee** (currently ~0.0005 testnet TAO — dynamic; it
rises slightly with each registration) burned from your coldkey. This is a signed extrinsic:
per the rules header, **state in one line that it signs registration and spends ~0.0005 τ, then
run it yourself** (wallet already exists, `--network test --netuid 523` present). If a wallet
password prompt appears, the human types it. The command:

```bash
btcli subnets register --netuid 523 --network test \
  --wallet.name my-dolores --wallet.hotkey miner
```

Verify registration afterward (read-only) — your hotkey should appear with a UID:

```bash
btcli subnets show --netuid 523 --network test
btcli wallet overview --wallet.name my-dolores --netuid 523 --network test
```

STOP and report if your hotkey/UID does not show up.

---

## 6. Build a task package

**Wire submission format** (the JSON envelope sent over transport — from `protocol.py` /
`packaging.py`). Exactly these keys:

| field | meaning |
|---|---|
| `schema_version` | must equal `dolores-subnet-v0` |
| `task_id` | unique task id (must match `package.task_id`) |
| `package_hash` | the engine's `stable_hash()` of the package (validator recomputes and must match) |
| `package` | the full task package dict (fields below) |
| `family` | task family, e.g. `parser_roundtrip` |
| `declared_difficulty` | e.g. `medium` |

Max canonical size: **200 KiB** per submission (`MAX_PACKAGE_BYTES`).

**Package fields** (inside `package`): `task_id`, `title`, `domain`, `prompt`,
`starter_files`, `reference_files`, `public_tests`, `hidden_tests`, `constraints`
(`timeout_seconds`, `memory_mb`), `descriptors` (`task_type`, `concepts`,
`estimated_difficulty`, `required_tools`), `lineage`, `metadata`. The reference must pass both
test sets, and the hidden tests must be strong enough to **fail a wrong solution** (Mutation Guide).

You do **not** hand-compute the hash — the engine computes `package_hash` when you serve or
validate a `task.yaml` directory. Produce a valid package via the **Fast Path** (mutate a
known-good task); the **Mutation Guide** below is the ruleset that makes a mutation actually earn
reward. The persona/seed generator is the fallback at the end of this section.

---

## Mutation Guide

You fork a curated known-good task (`scripts/prepare_mutation_task.py --name <id>`) and change it
so the validator sees a **novel, still-verifiable** task. What "meaningful" means:

| Good mutation (earns reward) | Bad mutation (scores zero) |
|---|---|
| Change the grammar/format (new delimiter, escaping, length-prefix) | Rename `task_id`/title only |
| Add a real edge case + a hidden test that exercises exactly it | Reword the story/prompt text only |
| Change a constraint that forces different reference logic | Reorder or rename tests |
| Change family parameters, updating reference **and** tests together | Cosmetic metadata / whitespace tweaks |
| | Leave reference/tests/starter bytes unchanged |
| | Anything unsafe, flaky, or networked (§9) |

**The dedup trap (real numbers).** The validator computes a `duplicate_score` of your task
against the **whole archive**: exact hash match = 1.0; else `max(prompt_word_jaccard*0.75 +
descriptor_jaccard*0.25, file_content_overlap, 0.8 if your lineage.parent_task_id points at an
archived task)`. **≥0.95 → rejected outright. ≥0.85 → "review", which also pays zero.** If you
leave the reference/tests/starter **bytes** unchanged, file overlap = **1.0** → auto-reject no
matter how you reword the prompt. **Aim for < 0.7.** Check before serving:

```bash
python scripts/validate_task.py --task-dir my_task_<id> --dedup-against examples/tasks
```

**The PROBE-DROP contract.** The validator plants three wrong solutions your hidden tests **must
fail**: (1) your starter files as-is, (2) your reference with every `return X` turned into
`return None`, (3) your reference with every line containing `# PROBE-DROP` deleted. So: tag your
edge-case / core logic lines with `# PROBE-DROP`, and make sure a **hidden test exercises exactly
that edge** — otherwise probe (3) passes and your task scores zero. Prove the reference itself
passes first:

```bash
python scripts/validate_task.py --task-dir my_task_<id> --run-tests
```

**Recipes for `honest_example`** (single-file `parser_roundtrip`, start here):
- Change the grammar to a **pipe delimiter + backslash-escaping** (prototyped duplicate_score
  ~0.51, all probes caught).
- Add a real edge case (**trailing delimiter** or **unicode field**) with a `# PROBE-DROP` trap
  and a hidden test hitting it.
- Switch to **length-prefixed fields** instead of quoting.

**Ambitious recipe for `harder_v3_example`** (multi-file): add a second shared-state bug class —
a module-level cache leak plus a mutable-default memo dict in a new `pricing.py` — and change the
dedup contract to **order-preserving** dedup, updating the reference and tests together.

**Do / Verify / STOP checklist:**
```
DO
[ ] prepare_mutation_task.py --name <id>   (forks, rewrites task_id, drops wire.json)
[ ] change file BYTES: new grammar/format/edge case in reference + starter
[ ] tag edge logic with # PROBE-DROP; add a hidden test hitting that exact edge
[ ] rewrite prompt + descriptors.concepts to match; lineage.parent_task_id: null
VERIFY
[ ] validate_task.py --task-dir my_task_<id> --run-tests      -> reference PASSES
[ ] validate_task.py --task-dir my_task_<id> --dedup-against examples/tasks -> max < 0.7
STOP if
[ ] --run-tests fails (reference broken = invalid_example failure = zero)
[ ] dedup max >= 0.85 (zero pay) — mutate more, don't serve
```

---

## Fallback: generated tasks by seed

If mutation feels too slow, the engine can emit genuine `parser_roundtrip` packages keyed by a
**unique seed** — the seed is what makes your supply distinct. Pick a seed no one else is using
(a big random number). Emit and inspect the exact wire submissions you'll serve:

```bash
python neurons/miner.py --mode offline --persona honest \
  --seed 730214 --quota 2 > my_submissions.json
```

Self-validate the emitted JSON (deterministic gates only — schema, size, hash, in-batch dup):

```bash
python - <<'PY'
import json, sys
sys.path.insert(0, "src")
from dolores_subnet.packaging import from_wire, canonical_size
from dolores_subnet.gates import run_pre_gates, GateContext
from dolores_subnet.config import SubnetConfig, MAX_PACKAGE_BYTES

subs = json.load(open("my_submissions.json"))
cfg, ctx = SubnetConfig(), GateContext(quota=len(subs))
ok = True
for s in subs:
    try:
        from_wire(s)                      # schema_version + size + parse + hash_match
    except Exception as e:
        ok = False; print("REJECT", s.get("task_id"), e); continue
    d = run_pre_gates(s, cfg, ctx, miner_hotkey="self")
    print(("PASS " if d.passed else "FAIL "), s["task_id"],
          "size", canonical_size(s), "/", MAX_PACKAGE_BYTES, dict(d.gates))
    ok = ok and d.passed
print("ALL_LOCAL_GATES_PASS" if ok else "LOCAL_GATE_FAILURE")
PY
```

Expect `ALL_LOCAL_GATES_PASS`. STOP and fix (usually: a different unique seed, or reduce size) if
any line says `FAIL`/`REJECT`. The local `epoch_duplicate` gate only catches **in-batch**
duplicates; the validator also dedups against the whole archive, so a near-copy still scores zero
on-chain (`--dedup-against` above is the closest local approximation).

---

## 8. Serve your miner (tonight's submission path)

Miners serve an **axon**; the operator's validator dendrites into it and pulls your submissions.
Serving requires your wallet to exist (§3) — the walletless smoke test is the offline emit
(`--mode offline --task-dir my_task_<id>` for a mutated task, or the seed emit in the Fallback
section). Two prerequisites for the command:

- **Pick a free port.** `8091` is the convention, but check it first
  (`lsof -nP -iTCP:8091 -sTCP:LISTEN` — empty means free). If it's taken (shared machine,
  earlier attempt still running), use any free port — the port is part of your endpoint.
- **Bind reachable.** Use `--host 0.0.0.0`, not `127.0.0.1` (local-only). Find your LAN IP
  with `ipconfig getifaddr en0` (macOS).

```bash
# Mutation path (recommended): serve your mutated package.
python neurons/miner.py --mode wire --task-dir my_task_<id> \
  --quota 2 --port 8091 --host 0.0.0.0 \
  --wallet.name my-dolores --wallet.hotkey miner

# OR persona fallback (generated tasks, differentiated by your seed):
python neurons/miner.py --mode wire --persona honest \
  --seed 730214 --quota 2 --port 8091 --host 0.0.0.0 \
  --wallet.name my-dolores --wallet.hotkey miner
```

`--task-dir` accepts a single package directory or a parent of several, and is repeatable.

Wait for the log line `wire_miner_started ... endpoint=<host>:<port> hotkey=<ss58>`.
(The first axon bind may trigger a macOS/Linux firewall prompt — the human should allow it.)

**Being found — two options:**

1. **Auto-discovery (preferred): publish your axon on-chain.** Add these flags to the serve
   command above: `--publish --network test --netuid 523 --external-ip <YOUR_LAN_IP>`
   (and `--external-port <PORT>` if it differs from `--port`). This signs a `serve_axon`
   extrinsic with **your hotkey** — it publishes only your IP and port and moves no funds.
   Per the rules header, announce that one line (signs `serve_axon`, spends nothing), then run
   it yourself. Wait for the log line `axon_publish=ok`. The operator's validator then
   discovers you from the metagraph automatically — nothing to hand over. (One publish per ~50
   blocks per hotkey; re-running with the same IP/port is a free no-op.)
2. **Fallback: hand the operator your endpoint triple** exactly as they need it:

```
<reachable-ip>:<port>:<your-hotkey-ss58>
```

**Do not spam.** The dedup gate catches near-copies; resubmitting the same package (or a trivial
variant) earns **zero** and wastes your per-epoch quota. Serve distinct, meaningfully-mutated (or
seed-differentiated) tasks. Keep the process running so the validator can reach you at query time.

---

## 9. Unsafe-task rules (hard reject → wasted slot)

The safety scanner rejects and zeroes any task whose code or tests attempt:
- **network calls** (sockets, HTTP, DNS, any egress),
- **filesystem escape** (writing/reading outside the sandboxed task dir, absolute paths, `..`),
- **subprocess / shell tricks** (`subprocess`, `os.system`, `eval`/`exec` of external input,
  spawning processes).

Tasks must be pure, self-contained, deterministic compute. A rejected task wastes your quota —
do not attempt any of the above "to make a harder task."

---

## 10. Final checklist (run top to bottom)

```
[ ] python --version            -> 3.11.x–3.14.x
[ ] python -c "import bittensor" -> 10.x, no error
[ ] btcli --version             -> prints a version (pip install bittensor-cli if not)
[ ] echo "$DOLORES_REPO"        -> non-empty (re-export in every new shell)
[ ] python -c "import dolores"  -> no error
[ ] btcli wallet balance --wallet.name <W> --network test   -> funded (>0)
[ ] EVERY chain command carries --network test and --netuid 523
[ ] btcli subnets register --netuid 523 --network test ...  (announced, then agent-run)
[ ] btcli subnets show --netuid 523 --network test          -> my hotkey/UID present
[ ] task ready (recommended): prepare_mutation_task.py fork, mutated meaningfully,
    validate_task.py --run-tests PASSED and --dedup-against examples/tasks max < 0.7
[ ] (or persona fallback: --persona honest --seed <UNIQUE> printed ALL_LOCAL_GATES_PASS)
[ ] port free (lsof check), then miner serving: --mode wire ... --host 0.0.0.0
[ ] log shows wire_miner_started
[ ] discovered: --publish flags added and log shows axon_publish=ok,
    OR operator has my <ip>:<port>:<hotkey-ss58> triple
[ ] miner process left running for the validator to query
```

If every box is checked, the miner is live. Report your UID to the operator and keep the
miner running.
