# Security Disclosure Enablement and Triage Packet

This packet prepares the human-gated action required to receive the pending
private security report without exposing vulnerability details.

## Current public facts

- Repository: `Leonwenhao/dolores-bittensor-subnet`
- Public issue: #4, “Enable private vulnerability reporting (or share a
  security contact) for a pending disclosure”
- `SECURITY.md` directs reporters to GitHub private security advisories.
- A read-only GitHub API check on 2026-07-12 returned
  `{"enabled":false}` for the repository's private-vulnerability-reporting
  setting.
- Issue #4 intentionally contains no vulnerability details, and none are
  reproduced here.

The controlled cohort security gate remains `PENDING-HUMAN` until a private
channel exists, the report is received, and the release-relevant findings are
triaged.

## STOP-LEON action

`STOP-LEON`

1. **Exact proposed action**

   Enable GitHub private vulnerability reporting for
   `Leonwenhao/dolores-bittensor-subnet`. If the repository UI cannot expose that
   setting, provide the reporter with a private security contact or invite them
   to a draft private GitHub Security Advisory instead.

2. **What this changes, signs, spends, or publishes**

   This changes one GitHub repository security setting or opens a private
   advisory/contact channel. It does not change code, publish the pending
   findings, sign a wallet action, spend funds, contact cohort participants, or
   write to Bittensor.

3. **Exact UI step**

   In the GitHub repository, open **Settings**, locate the repository's
   **Security** or **Code security and analysis** settings, find **Private
   vulnerability reporting**, and select **Enable**. GitHub may move the setting
   between Security and Advanced Security sections; verify the setting by
   reading it back as enabled before replying to the reporter.

   Do not use a mutating API or CLI command on the operator's behalf without the
   same explicit approval.

4. **Evidence that prerequisites are met**

   - the repository is public;
   - `SECURITY.md` already requests private advisories;
   - issue #4 records a reporter waiting for a private channel;
   - the 2026-07-12 read-only setting check reports disabled;
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
  setting is pending.
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
