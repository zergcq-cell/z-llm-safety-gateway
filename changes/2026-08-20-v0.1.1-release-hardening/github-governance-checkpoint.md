# GitHub Governance Checkpoint

Checked read-only on 2026-08-21 before Gate 3. Remote writes are intentionally deferred until
Gate 3 approval.

## Current Remote State

- Existing labels: `accessibility`, `bug`, `documentation`, `duplicate`, `enhancement`,
  `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`.
- Missing required Dependabot label: `dependencies`.
- Milestones: none; `v0.1.1` and `v0.2.0` are missing.
- GitHub private vulnerability reporting: disabled.
- Local bug/feature/PR templates: present and validated.

## Gate 3 Post-Approval Actions

1. Enable GitHub private vulnerability reporting so the `SECURITY.md` private channel is live.
2. Create the `dependencies` label (`0366d6`, “Dependency updates”) required by Dependabot.
3. Create milestone `v0.1.1` for this release-hardening closure.
4. Create milestone `v0.2.0` for the next public-test feature release.
5. Re-read labels, milestones, and private reporting state and attach the response evidence to
   the delivery report.

GitHub Discussions remains optional for v0.1.1. The issue chooser provides the documented bug
and feature feedback path; security and conduct incidents use private reporting.
