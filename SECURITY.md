# Security Policy

This repository contains software that can sign blockchain extrinsics when
explicitly configured to do so. Security reports are taken seriously.

## Reporting

Do not disclose vulnerability details in a public issue. GitHub private
vulnerability reporting is the required channel for this release, but it is
currently disabled and therefore blocks public cohort launch. A reporter should
use an already-established private contact only to ask the maintainer to enable
the repository channel; the maintainer must then receive and triage the report
privately before launch. See `docs/security-disclosure-packet.md` for the exact
operator gate.

Highest-interest areas:

- any path that could cause a network write without all explicit gates
  (`--chain live`, `--allow-extrinsics`, the `DOLORES_ALLOW_EXTRINSICS`
  environment variable, and the typed confirmation);
- sandbox escapes from the Docker verification of miner-supplied tasks;
- ways a malicious task package could reach the validator host un-sandboxed
  (the safety screen runs before any execution);
- wallet or key material exposure.

## Scope notes

- Miner-supplied task packages are treated as untrusted input end-to-end.
- The validator never needs a coldkey at runtime; hotkey files are read by
  the Bittensor SDK only.
- No secrets belong in this repository; `.gitignore` excludes wallet and
  environment files.
