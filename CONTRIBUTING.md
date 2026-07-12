# Contributing

Dolores is currently preparing a controlled public-testnet cohort, not an open
production network. Contributions are welcome in code, task authoring, tests,
and operational evidence.

## Code contributions

- Use Python 3.11.
- Keep subnet and engine release candidates aligned at `0.2.0rc1`.
- After the pinned engine release is public, install this checkout with
  `python -m pip install -e ".[dev]"`; do not wire it to an adjacent/private
  engine path.
- Run `ruff check .` and `python -m pytest -q`.
- Add regression coverage for security, state, protocol, and packaging changes.
- Preserve the default Bittensor Axon verifier, response-payload signatures,
  required body-hash fields, endpoint policy, and four independent live-weight
  gates.
- Keep public-testnet miner discovery metagraph-owned. Manual endpoints belong
  only to explicit loopback/local test fixtures.
- Keep generated or external task execution Docker-only and fail closed; never
  fall back to host execution.

The validator Docker image is `dolores-verifier-pytest:0.2.0rc1`. Its Dockerfile
is a packaged engine resource, and its runtime must remain non-root, networkless,
read-only, capability-free, and resource-limited.

## Task contributions

The first cohort accepts only core `parser_roundtrip` tasks using the
`escape_delim`, `error_contract`, or `quoted_fields` archetype. Start from the
installed command:

```bash
dolores-miner init --output dolores-tasks --archetype quoted_fields --seed 17
dolores-miner validate --task-dir <TASK_DIR>
```

A useful task has deterministic author tests, a correct reference solution,
meaningful wrong-solution coverage, safe paths and execution, and novel task
content. Miner-supplied tests are **author tests**, not validator ground truth.
The pinned engine's on-disk model retains the internal field name
`hidden_tests`; the public `dolores-subnet-v1` wire format maps that content to
`author_tests`. The validator-owned holdout remains private and is never part of
a contribution.

Do not submit the intentionally duplicate or invalid examples as cohort work.
See [`examples/tasks/README.md`](examples/tasks/README.md) for their purpose and
[`docs/hackerquest-miner-quickstart.md`](docs/hackerquest-miner-quickstart.md)
for the approved public-artifact onboarding path once releases are published.

## Chain and provider safety

Pull requests and local tests must not register wallets, publish axons, submit
weights, transfer funds, contact participants, or make paid provider calls.
Every authorized chain command must explicitly include
`--network test --netuid 523`. Paid solver calibration stays off unless a separately approved,
budget-capped run supplies every spend gate.

## Security reports

Do not post exploit details in a public issue. Follow [`SECURITY.md`](SECURITY.md).
The controlled cohort remains blocked until the pending private report is
received and triaged against the release candidate.
