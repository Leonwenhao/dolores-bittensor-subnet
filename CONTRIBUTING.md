# Contributing

Dolores Autocurricula is an open subnet: the long-term goal is a network of
independent task authors (miners) supplying verified training tasks, and
independent validators scoring them. Contributions are welcome at three
levels.

## 1. Run the local demo

The fastest way to understand the system is to run the offline epoch demo —
an honest miner, a duplicate-spammer, and an invalid miner scored end-to-end
with no chain access. See [docs/demo.md](docs/demo.md).

## 2. Code contributions

- Python 3.11, `ruff` for linting, `pytest` for tests.
- Install dev dependencies: `pip install -e ".[dev]"`.
- Every PR must pass `ruff check .` and `python -m pytest -q`.
- The chain layer (`src/dolores_subnet/chain.py`) is fail-closed by design:
  the default is no chain access, dry-run never signs, and live submission
  requires four independent explicit gates. PRs that weaken any gate, add a
  default network write, or bypass the safety screen will not be merged.
- Keep `src/dolores_subnet/chain.py` importable without `bittensor`
  installed (`tests/test_import_discipline.py` enforces this).

## 3. Task authoring (miners)

The subnet rewards the supply of verified tasks. A good task package:

- has hidden tests that a correct solution passes deterministically inside
  the Docker verifier;
- is killed by the wrong-solution probes (a task whose tests pass for a
  wrong solution scores zero);
- is not a near-duplicate of an existing archive entry (deduplication is
  enforced);
- sits near the capability frontier: strong reference solvers should
  sometimes solve it, weak ones rarely.

Miner onboarding docs for the public testnet subnet (netuid 523) are being
expanded as the network opens up — watch
[docs/roadmap.md](docs/roadmap.md) and open an issue if you want to run a
miner early.

## Questions

Open a GitHub issue. For security-sensitive reports see
[SECURITY.md](SECURITY.md).
