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
- **Signed/on-chain actions are the human's to run.** You may draft the exact command, but the
  human presses enter on anything that spends testnet TAO or signs an extrinsic (wallet
  creation, registration).

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

## 3. Create a testnet wallet (human runs these)

The human runs these in their own terminal. **You (the agent) must not run wallet-create
commands, and must never see the mnemonic.** Pick a wallet name and hotkey name (examples below;
let the human choose).

```bash
btcli wallet create --wallet.name my-dolores --wallet.hotkey miner
# (wallet creation is local — no network flag involved. If regenerating an existing
#  key, the human uses `btcli wallet regen_*` privately — never paste a mnemonic into
#  this chat, a file, or any command you run.)
```

The human writes the mnemonic down offline. When done, verify **read-only** that the wallet
exists and check its balance:

```bash
btcli wallet balance --wallet.name my-dolores --network test
```

- **Getting testnet TAO:** the faucet is Discord-gated and often disabled on-chain. **Tonight
  the operator will fund your coldkey** so you can pay the registration recycle fee. Ask the
  operator, giving them your **coldkey ss58 address** (public, safe to share) — get it with
  `btcli wallet list` (read-only).

STOP if balance is `0` when you reach section 5 — you cannot register without a small amount of
testnet TAO. Ask the operator to fund you.

---

## 4. Mainnet safety (re-read before any chain command)

Before you emit ANY `btcli` or `bittensor` command:
1. Confirm it contains `--network test`. If not, **do not run it.**
2. Confirm netuid is `523`. Never target another netuid.
3. Never substitute `finney`/`mainnet`. If the human asks for mainnet, refuse and remind them
   this session is testnet-only with no real value.

---

## 5. Register on netuid 523 (signed action — human runs it)

Registration costs a small **recycle fee** (currently ~0.0005 testnet TAO — dynamic; it
rises slightly with each registration) burned from your coldkey. This is a
signed extrinsic: **the human runs it.** You draft it exactly:

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
`estimated_difficulty`, `required_tools`), `lineage`, `metadata`. The reference solution must
pass both `public_tests` and `hidden_tests`; the hidden tests must be strong enough to **fail a
wrong solution**.

You do **not** hand-compute the hash. Generate a real, valid package with the engine and let it
compute everything. Tonight's supported path produces genuine `parser_roundtrip` packages keyed
by a **unique seed** — the seed is what makes your supply distinct from other participants. Pick
a seed no one else is using (e.g. a big random number):

```bash
# Emit the exact wire submissions you will serve, to inspect them:
python neurons/miner.py --mode offline --persona honest \
  --seed 730214 --quota 2 > my_submissions.json
```

**Authoring your own task (the more impressive path):** copy a curated example from
`examples/tasks/` (start from `honest_example/` or `harder_v3_example/`), adapt the prompt,
tests, and reference solution, and give it a unique `task_id`. Keep the directory shape
(`task.yaml` plus the files it references). Validate it with one command:

```bash
python scripts/validate_task.py --task-dir path/to/my_task
```

Then serve it directly — no seed needed:

```bash
python neurons/miner.py --mode wire --task-dir path/to/my_task \
  --port 8091 --host 0.0.0.0 \
  --wallet.name my-dolores --wallet.hotkey miner
```

`--task-dir` accepts a single package directory or a parent directory containing several, and
is repeatable. If authoring feels too slow tonight, the persona path above is the fallback.

---

## 7. Self-validate before serving

You can check locally everything that is deterministic — **schema, size, hash, and in-batch
duplication** — without the validator. You **cannot** locally decide what the validator's Docker
gauntlet decides (reference actually passing in Docker, wrong-solution probes, dedup against the
full archive, difficulty scoring).

For an authored task directory, the one-command check is:

```bash
python scripts/validate_task.py --task-dir path/to/my_task
```

For persona-emitted wire JSON, run this against the JSON you emitted:

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

Expect `ALL_LOCAL_GATES_PASS`. STOP and fix (usually: use a different unique seed, or reduce
size) if any line says `FAIL`/`REJECT`. Note: the local `epoch_duplicate` gate only catches
duplicates **within this batch** — the validator additionally dedups against the whole archive,
so a task that is a near-copy of an existing archived task will still score zero on-chain.

---

## 8. Serve your miner (tonight's submission path)

Miners serve an **axon**; the operator's validator dendrites into it and pulls your submissions.
Serving requires your wallet to exist (§3) — the §6 offline emit is the only walletless smoke
test. Two prerequisites for the command:

- **Pick a free port.** `8091` is the convention, but check it first
  (`lsof -nP -iTCP:8091 -sTCP:LISTEN` — empty means free). If it's taken (shared machine,
  earlier attempt still running), use any free port — the port is part of your endpoint.
- **Bind reachable.** Use `--host 0.0.0.0`, not `127.0.0.1` (local-only). Find your LAN IP
  with `ipconfig getifaddr en0` (macOS).

```bash
# Persona path (generated tasks, differentiated by your seed):
python neurons/miner.py --mode wire --persona honest \
  --seed 730214 --quota 2 --port 8091 --host 0.0.0.0 \
  --wallet.name my-dolores --wallet.hotkey miner

# OR authored-task path (serve your own validated package):
python neurons/miner.py --mode wire --task-dir path/to/my_task \
  --quota 2 --port 8091 --host 0.0.0.0 \
  --wallet.name my-dolores --wallet.hotkey miner
```

Wait for the log line `wire_miner_started ... endpoint=<host>:<port> hotkey=<ss58>`.
(The first axon bind may trigger a macOS/Linux firewall prompt — the human should allow it.)

**Being found — two options:**

1. **Auto-discovery (preferred): publish your axon on-chain.** Add these flags to the serve
   command above: `--publish --network test --netuid 523 --external-ip <YOUR_LAN_IP>`
   (and `--external-port <PORT>` if it differs from `--port`). This signs a `serve_axon`
   extrinsic with **your hotkey** — it publishes only your IP and port, moves no funds, and
   because the human runs the miner command, the human is the one signing. Wait for the log
   line `axon_publish=ok`. The operator's validator then discovers you from the metagraph
   automatically — nothing to hand over. (One publish per ~50 blocks per hotkey; re-running
   with the same IP/port is a free no-op.)
2. **Fallback: hand the operator your endpoint triple** exactly as they need it:

```
<reachable-ip>:<port>:<your-hotkey-ss58>
```

**Do not spam.** The dedup gate catches near-copies; resubmitting the same package (or a trivial
variant) earns **zero** and wastes your per-epoch quota. Serve distinct, seed-differentiated
tasks. Keep the process running so the validator can reach you at query time.

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
[ ] btcli subnets register --netuid 523 --network test ...  (human ran it)
[ ] btcli subnets show --netuid 523 --network test          -> my hotkey/UID present
[ ] task ready: EITHER offline emit (--persona honest --seed <UNIQUE>) printed
    ALL_LOCAL_GATES_PASS, OR authored dir passed scripts/validate_task.py
[ ] port free (lsof check), then miner serving: --mode wire ... --host 0.0.0.0
[ ] log shows wire_miner_started
[ ] discovered: --publish flags added and log shows axon_publish=ok,
    OR operator has my <ip>:<port>:<hotkey-ss58> triple
[ ] miner process left running for the validator to query
```

If every box is checked, the miner is live. Report your UID to the operator and keep the
miner running.
