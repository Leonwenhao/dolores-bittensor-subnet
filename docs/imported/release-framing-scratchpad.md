# Release Framing Scratchpad

Working notes for future release notes, technical report language, and paper framing.

## Untrusted Curriculum Contributions

Autocurricula is not only a task generator. It is a task intake, quarantine, and verification system for untrusted curriculum contributions.

Because Dolores accepts tasks from agents, users, contributors, and eventually incentive-network participants, every submitted task package must be treated as untrusted code until proven otherwise. A task can contain reference code, tests, starter files, and scripts. Running that package locally is equivalent to running a random program from the internet.

Release framing:

> In open curriculum systems, tasks are executable artifacts, not passive data. The safety boundary is therefore part of the curriculum layer itself: generated tasks must be sandboxed, verified, scored, and quarantined before they enter the archive.

## Local Verifier Versus Sandbox Verifier

The local verifier is useful for trusted fixtures, demos, and developer smoke tests. It is not the right default for public or generated tasks.

For generated tasks, the safe default is:

- run in Docker, Daytona, E2B, a VM, or another sandbox
- disable network access by default
- enforce memory and timeout limits
- use an isolated temporary workspace
- prevent access to `.env`, SSH keys, home directories, host credentials, and repo secrets
- fail closed if the sandbox is unavailable

Release framing:

> The open-curriculum problem is adversarial by default. Once anyone can propose tasks, verification is not a convenience feature; it is the security model.

## Fail-Closed Execution

A key hardening lesson: sandbox fallback must not silently remove the sandbox.

For trusted demos, falling back from Docker to local execution can be convenient. For generated or public-submitted tasks, it is a security bug. If a user requests Docker and Docker is unavailable, the system should stop immediately rather than quietly running on the host.

Release framing:

> Dolores treats `containerized=true` as an evidence claim. A task only receives that mark when it actually ran in a container. If the sandbox is unavailable during generated-task evaluation, the run fails closed.

Potential paper angle:

> Open task generation changes the threat model for RL environments. The proposer can be malicious, incompetent, or reward-seeking. Therefore, the archive must record not only task content and solver pass rates, but also verification provenance: where the code ran, whether it was containerized, which tests passed, and whether known-bad solutions were caught.

