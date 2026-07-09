"""Fork a known-good task package into your own, ready to mutate.

Copies a curated example (default: examples/tasks/honest_example) to
my_task_<name>/ at the repo root, rewrites the top-level task_id to <name>,
and deletes the stale wire.json (the serve path recomputes it from task.yaml,
so an edited wire.json is a footgun). Engine-free on purpose: it works before
the dolores engine is installed. Then mutate meaningfully — see AGENTS.md
"Mutation Guide".

Usage:
    python scripts/prepare_mutation_task.py --name my_parser_v2
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9_]+$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=str(REPO_ROOT / "examples" / "tasks" / "honest_example"),
        help="task package dir to fork (default: examples/tasks/honest_example)",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="new task_id / dir suffix; must match [a-z0-9_]+",
    )
    args = parser.parse_args()

    if not NAME_RE.match(args.name):
        print(f"FAIL: --name must match [a-z0-9_]+ (got {args.name!r})")
        return 1

    source = Path(args.source).expanduser()
    if not (source / "task.yaml").is_file():
        print(f"FAIL: source has no task.yaml: {source}")
        return 1

    dest = REPO_ROOT / f"my_task_{args.name}"
    if dest.exists():
        print(f"FAIL: destination already exists: {dest}")
        return 1

    shutil.copytree(source, dest)
    (dest / "wire.json").unlink(missing_ok=True)

    task_yaml = dest / "task.yaml"
    lines = task_yaml.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("task_id:"):
            lines[i] = f"task_id: {args.name}\n"
            break
    else:
        shutil.rmtree(dest)
        print(f"FAIL: no top-level 'task_id:' line in {task_yaml}")
        return 1
    task_yaml.write_text("".join(lines), encoding="utf-8")

    print(f"Created {dest} (task_id={args.name}, wire.json removed)")
    print("Now mutate MEANINGFULLY (a rename is not a mutation — it scores zero):")
    print("  1. Change the actual file bytes: new grammar/format/edge-case in")
    print("     reference_files + starter_files (unchanged bytes -> dedup 1.0 -> reject).")
    print("  2. Tag edge-case logic with '# PROBE-DROP' and add a hidden test that")
    print("     exercises exactly that edge (so the planted wrong-solution probes FAIL).")
    print("  3. Rewrite prompt + descriptors.concepts to match; keep")
    print("     lineage.parent_task_id: null.")
    print("  Then validate:")
    print(f"  4. python scripts/validate_task.py --task-dir {dest.name} --run-tests")
    print(
        f"  5. python scripts/validate_task.py --task-dir {dest.name} "
        "--dedup-against examples/tasks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
