# Security Policy

z LLM Safety Gateway sits on a security-sensitive request path. We welcome responsible
research and will work with reporters on coordinated disclosure.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x | Yes |
| 0.0.x | No; upgrade to the latest 0.1.x release |

Security fixes are applied to the latest supported patch release. The `main` branch may contain
unreleased work and is not a substitute for a supported release.

## Reporting a Vulnerability

Use GitHub's private vulnerability reporting form:

[Report a vulnerability privately](https://github.com/zergcq-cell/z-llm-safety-gateway/security/advisories/new)

Do not open a public issue, discussion, or pull request for an unpatched vulnerability. Before a
fix is available, do not publish exploit code, payloads, affected deployments, secrets, or other
details that would make exploitation easier.

Please include, when possible:

- affected version, deployment mode, and configuration;
- impact and the security boundary that is crossed;
- minimal reproduction steps or a proof of concept with secrets removed;
- suggested mitigations and whether the issue is already public;
- a safe way and preferred schedule for follow-up.

## Response Targets

- We aim to acknowledge a complete report within **3 business days**.
- We aim to provide an initial severity and scope assessment within **7 business days**.
- While remediation is active, we aim to send an update at least every 7 business days.
- Fix timing depends on severity and release risk; critical issues receive immediate priority.

These are response targets, not a guarantee. If you receive no acknowledgement after 3 business
days, update the same private advisory rather than opening a public report.

## Coordinated Disclosure

We will validate the report, agree on severity and affected versions, prepare a fix and tests,
and coordinate release notes and disclosure timing with the reporter. We prefer disclosure after
a supported release or mitigation is available. If users face active exploitation, we may publish
an advisory earlier with the minimum details needed to protect deployments.

We will credit reporters who request attribution. We ask reporters to preserve confidentiality
until the coordinated disclosure date and to avoid accessing, changing, or retaining other
people's data.

## Out of Scope

- reports that only identify a dependency version without a reachable impact in this project;
- denial of service that requires unrestricted administrator access to the same deployment;
- social engineering, physical attacks, or attacks against third-party LLM providers;
- automated scanner output without a reproducible security impact.

Out-of-scope reports may still be useful as regular bug reports once they contain no sensitive
or exploitable details.
