# Security Disclosure Enablement and Triage Packet

This packet records the completed intake enablement and prepares the still
human-gated reply and private triage without exposing vulnerability details.

## Current public facts

- Repository: `Leonwenhao/dolores-bittensor-subnet`
- Public issue: #4, “Enable private vulnerability reporting (or share a
  security contact) for a pending disclosure”
- `SECURITY.md` directs reporters to GitHub private security advisories.
- An approved GitHub API change followed by read-back at
  `2026-07-12T19:32:08Z` returned `{"enabled":true}` for the repository's
  private-vulnerability-reporting setting.
- Issue #4 intentionally contains no vulnerability details, and none are
  reproduced here.

The private-channel gate is now `PASS`. The overall controlled-cohort security
gate remains `PENDING-HUMAN` until the report is received and its
release-relevant findings are triaged.

## Completed authorized enablement

Status: `PASS`

1. **Exact completed action**

   GitHub private vulnerability reporting was enabled for
   `Leonwenhao/dolores-bittensor-subnet` after explicit operator approval.

2. **What this changes, signs, spends, or publishes**

   This changes one GitHub repository security setting or opens a private
   advisory/contact channel. It does not change code, publish the pending
   findings, sign a wallet action, spend funds, contact cohort participants, or
   write to Bittensor.

3. **Exact API operation and read-back**

   The approved operation used GitHub's documented
   `PUT /repos/{owner}/{repo}/private-vulnerability-reporting` endpoint. A
   subsequent `GET` returned `{"enabled":true}`.

   No issue reply, advisory content, repository code, or chain state changed.

4. **Evidence that prerequisites are met**

   - the repository is public;
   - `SECURITY.md` already requests private advisories;
   - issue #4 records a reporter waiting for a private channel;
   - the post-change read-back reports enabled;
   - no vulnerability details need to be moved through a public channel.

5. **Rollback or recovery**

   Private vulnerability reporting can be disabled again in the same repository
   setting after the report is resolved, although leaving it enabled is the safer
   continuing posture. If an alternate private contact is used, revoke any
   temporary advisory access after coordinated closure. Preserve the private
   advisory and triage record according to GitHub's normal security workflow;
   disabling intake must not delete the evidence needed for remediation.

## Private-channel reply after enablement

Reply on issue #4 only with a short statement that private reporting is now
available and ask the reporter to use the private channel. Do not ask for finding
details, exploit steps, attachments, or patches in the public issue.

Suggested public-safe reply:

> Private vulnerability reporting is now enabled. Please submit the report
> through the repository's private vulnerability reporting flow. We will
> acknowledge and triage it there.

Sending the reply is a separate external communication and requires explicit
operator approval.

## Private triage record

Keep this record inside the private advisory, not in this public document.

Required fields:

- advisory identifier and received-at timestamp;
- reporter acknowledgement timestamp;
- affected released and candidate versions;
- severity and exploitability assessment;
- reproduction status in an isolated test environment;
- affected trust boundary: transport, replay, quotas, sandbox, holdout,
  endpoint publication, validator state, chain gates, or release packaging;
- assigned remediation owner;
- fix revision and regression-test evidence;
- disclosure/credit coordination and target date;
- release decision: blocking, fixed, accepted risk, duplicate, or not applicable.

Never copy private reproduction details, active exploit material, wallet paths,
credentials, operator secrets, or holdout cases into public issues, normal PR
descriptions, CI logs, cohort evidence, or launch copy.

## Cohort release consequences

- Local implementation and non-publishing verification may continue while the
  report receipt and triage are pending.
- Do not publish the cohort release, invite external miners, amplify the subnet,
  or claim cohort readiness before the report is privately received and triaged.
- A finding that affects the controlled-cohort threat model must be fixed and
  covered by a regression test before publication.
- A finding that cannot be evaluated privately leaves the security gate
  `PENDING-HUMAN`; absence of disclosed detail is not evidence that no finding
  exists.

## Public-safe closeout evidence

After private triage, the public cohort checklist should record only:

- private advisory identifier;
- triage completed timestamp;
- affected release-candidate disposition;
- public fix revision and passing test identifiers, if disclosure permits;
- whether coordinated public disclosure remains pending.

Do not summarize the vulnerability itself until the reporter and operator agree
on coordinated disclosure.
