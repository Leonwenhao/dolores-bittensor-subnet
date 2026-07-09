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

## Near term — get to first public live weights

The immediate path is narrow and sequential:

1. **Validator permit.** Poll permit/rate readiness after the tempo boundary
   (tempo = 360 blocks) until `validator_permit` flips true. *(pending)*
2. **First public live weights.** With the permit live and commit-reveal
   verified off, submit the first `set_weights` on netuid 523 through the gated
   live path. *(pending)*
3. **Public read-back evidence.** Record the submission extrinsic and the
   metagraph read-back confirming the nonzero weight vector, and publish it in
   `testnet-status.md`. *(pending)*

## Mid term — open the network

- **External miners.** Move from first-party miners to open registration.
  *(planned)*
- **Miner onboarding docs.** A clear guide for what a good task package looks
  like and how submissions are scored, so third parties can contribute without
  hand-holding. *(planned)*
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
