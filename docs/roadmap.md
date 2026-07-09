# Roadmap

Everything below that is not marked **done** is **planned** and not yet
implemented. Current status is tracked in
[`testnet-status.md`](testnet-status.md).

## Shipped

- **Real solver-panel calibration mode.** The validator can optionally measure
  gauntlet-surviving tasks against a panel of named frontier/open models
  (Fireworks provider) and fold the measured difficulty into scoring, instead
  of the default mock panel. Operator-gated (explicit spend opt-in +
  budget cap + dry-run preview), cached by task hash, off by default. The
  capability is merged; publishing "measured against `<models>`" claims waits
  for an operator-approved real calibration run that produces artifacts.
- **First public testnet weights.** Netuid 523 accepted the first public
  `set_weights` submit on 2026-07-09 (`7520191-8`), and direct read-back
  confirmed `Weights[523,0] = [(1, 65535)]`.

## Near term — make the loop repeatable

The immediate path is narrow and sequential:

1. **Repo-native SDK reliability.** The first public submit used a direct async
   substrate fallback because the repo SDK dry-run path hit testnet websocket
   hangs. Make the repo-native path retry-aware and reliably receipt-writing.
   *(planned)*
2. **Small real solver-panel calibration.** Run an operator-approved,
   budget-capped Fireworks calibration on one to three accepted tasks and publish
   the sidecar artifact. *(planned)*
3. **External cohort miners.** Have at least one non-first-party participant
   serve an authored task package and earn nonzero weight on testnet. *(planned)*
4. **On-chain miner discovery.** Publish miner axons via `serve_axon` so miners
   are discoverable on-chain and show `ACTIVE`, instead of being served with
   explicit endpoints handed to the validator. *(planned)*
5. **Emission/incentive observation.** After further tempo boundaries, record
   whether incentive/emission remain zero (fresh-testnet behavior) or begin to
   accrue, and document the finding. *(planned)*

## Mid term — open the network

- **External miners.** Move from first-party miners to open registration.
  *(planned)*
- **Miner onboarding docs.** A clear guide for what a good task package looks
  like and how submissions are scored, so third parties can contribute without
  hand-holding. *(done for the initial cohort agent path)*
- **Task-family coverage steering.** Incentive weighting that steers supply
  toward under-covered task families instead of rewarding whatever is easiest to
  produce. *(planned)*
- **Verifier-quality leaderboard.** Public per-miner ranking by verified,
  deduplicated, frontier-signaled contribution — the durable reputation surface.
  *(planned)*

## Long term — vision

- **Mainnet consideration.** Only after the testnet loop demonstrates
  deterministic validation, live weights, and real external contributor
  interest. Economics remain out of scope until then. *(planned)*
- **Curriculum archive exports.** Publish the accepted-task archive in formats
  usable outside crypto — Hugging Face datasets and `verifiers`-compatible
  environment exports — so the curriculum is useful to any lab, not just to the
  subnet. *(planned)*
- **Score → training-value validation.** Run downstream training ablations to
  test whether the validator's task score actually predicts training value. Until
  this is done, scores claim *verifiability, novelty, and frontier signal* — not
  proven training impact. Closing this gap is the most important long-term
  research goal. *(planned)*
