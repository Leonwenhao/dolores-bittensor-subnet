# Example task packages

These fixtures explain the `dolores-subnet-v1` submission boundary. They are
development examples, not a queue of tasks to serve unchanged.

For controlled-cohort installation and operation, use only immutable public
release artifacts and follow
[`docs/hackerquest-miner-quickstart.md`](../../docs/hackerquest-miner-quickstart.md).
Do not use a local engine path, private endpoint, synthetic generator shortcut,
or manual testnet endpoint.

## Fixtures

| Directory | Purpose | Controlled-cohort result |
|---|---|---|
| `honest_example/` | Core `parser_roundtrip` / `quoted_fields` task with a correct reference and author tests. | Supported shape; still must pass live holdout and dedup. |
| `duplicate_example/` | Cosmetic copy of `honest_example`. | Zero value after deduplication. |
| `invalid_example/` | Supported parser shape with a deliberately broken reference. | Zero value after Docker verification. |
| `harder_v3_example/` | Valid `multi_file_bugfix` research task. | Unsupported by the narrow cohort holdout policy. |

Each directory contains:

- `task.yaml` — the pinned engine's on-disk `TaskPackage` form;
- `wire.json` — the exact public subnet submission envelope.

The engine's on-disk model still names the miner-supplied non-public test
mapping `hidden_tests`. In this cohort those tests are **author tests**, not
validator ground truth. `packaging.to_wire` maps that field to `author_tests`.
The active validator-private holdout is generated separately and appears in
neither file.

## Wire format

A `wire.json` object contains:

- `schema_version`: exactly `dolores-subnet-v1`;
- `task_id`: equal to the package task ID;
- `package_hash`: the engine's canonical stable hash;
- `package`: task content with `author_tests`, never `hidden_tests`;
- `family` and `declared_difficulty`: routing metadata.

The validator limits one canonical submission to 200 KiB, recomputes the stable
hash, and rejects malformed paths, execution material, schema versions, sizes,
and hash claims before expensive work.

## Author-side validation

After installing the immutable public `0.2.0rc1` releases, validate the known
supported example without Docker or chain access:

```bash
dolores-miner validate --task-dir examples/tasks/honest_example
```

Expected validation includes `family=parser_roundtrip`,
`archetype=quoted_fields`, a package hash, and an `author_tests` count.
Author-side validation proves schema/hash/policy compatibility only. It does not
prove novelty, private-holdout strength, reference correctness, or reward.
The full doctor is an operational post-publication audit; use the exact command
in the external-miner quickstart rather than a task-only invocation.

To create new supported content, use the installed generator rather than
copying an example byte-for-byte:

```bash
dolores-miner init \
  --output dolores-tasks \
  --archetype quoted_fields \
  --seed 41
dolores-miner validate --task-dir <TASK_DIR_PRINTED_BY_INIT>
```

Meaningfully revise the task and its author tests while preserving the declared
core parser contract. Cosmetic renames and whitespace edits are duplicates.

## Why examples can still score zero

`dolores-miner validate` intentionally does not run validator infrastructure.
The operator subsequently performs:

1. authenticated request and miner-signed response verification;
2. safety and reference/author-test execution in the hardened
   `dolores-verifier-pytest:0.2.0rc1` image;
3. known-wrong probes;
4. the secret-keyed validator-private holdout;
5. archive deduplication and scoring.

`duplicate_example` preserves the source/test overlap of the honest fixture, so
renaming its task ID cannot make it novel. `invalid_example` has a reference
that fails execution. `harder_v3_example` may be useful engine research input,
but unsupported families fail closed in the first cohort rather than bypassing
the private holdout.

Do not serve the duplicate, invalid, or unsupported fixtures to the cohort.
