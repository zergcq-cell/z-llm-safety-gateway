# Capability: tenant-policy-resolution

> Change: `2026-09-01-tenant-flow-policy-resolution`
> Canonical: `canonical/specs/code/tenant-policy-resolution.yaml`
> Overall confidence: high

## Purpose

Resolve one immutable tenant execution policy from trusted request identity, without fallback, secret propagation, or cross-request drift.

## REQ-TPR-001 — Trusted identity selects one request policy

### SC-TPR-001 · high

- **GIVEN** authenticated acme and globex requests bound to valid compiled policies.
- **WHEN** policy resolution runs after authentication.
- **THEN** the resolver **SHALL** select only the bundle referenced by the trusted `TenantContext`.
- **AND** it SHALL attach frozen `TenantPolicyContext v1.0`, expose only safe identities, and run before availability and Provider selection.

### SC-TPR-002 · high

- **GIVEN** an acme request claims another tenant, policy, or Provider in untrusted input.
- **WHEN** policy and Provider resolution run.
- **THEN** the policy **SHALL** remain the one bound to acme.
- **AND** untrusted selection hints SHALL not participate and no public tenant-policy selection protocol SHALL be introduced.

## REQ-TPR-002 — Runtime policy invariants fail closed

### SC-TPR-003 · medium

- **GIVEN** enabled tenancy with missing `TenantContext`, policy, or compiled bundle state.
- **WHEN** resolution runs.
- **THEN** the request **SHALL** fail with OpenAI-compatible HTTP 503 `tenant_policy_unavailable`.
- **AND** no global/legacy/other policy fallback or secret-bearing error SHALL occur.

### SC-TPR-004 · high

- **GIVEN** an unchanged single-tenant configuration.
- **WHEN** an admitted request reaches policy resolution.
- **THEN** it **SHALL** keep the existing global Flow, Detector, result policy, and router behavior.
- **AND** legacy `TenantContext` remains available without requiring tenant policies.

## REQ-TPR-003 — Resolution is isolated, stable and bounded

### SC-TPR-005 · high

- **GIVEN** concurrent tenant requests using input, sync/async output, SSE, buffer, sliding-window and post-audit paths.
- **WHEN** request and background stages execute.
- **THEN** every stage **SHALL** use its originating request's bundle and `FlowExecutionSnapshot`.
- **AND** requests SHALL not mutate or re-resolve each other and background tasks SHALL not read global defaults.

### SC-TPR-006 · medium

- **GIVEN** maximum supported policy, binding and route declarations.
- **WHEN** one request resolves and routes.
- **THEN** policy selection **SHALL** use expected O(1) lookup and routing SHALL inspect at most 256 rules.
- **AND** structural operation counts, not coverage-instrumented wall-clock timing, SHALL prove the bound.
