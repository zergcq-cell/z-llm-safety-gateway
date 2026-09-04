# Capability: tenant-config-contract

> Change: `2026-08-30-tenant-identity-config-contract`
> Canonical: `canonical/specs/code/tenant-config-contract.yaml`
> Overall confidence: high

## Purpose

Define a strict, bounded tenant declaration schema and reject every statically detectable identity-binding ambiguity before the Gateway accepts traffic.

## REQ-TCC-001 — Explicit, strict, bounded tenant declarations

#### Scenario: SC-TCC-001 · high

- **GIVEN** valid `tenancy.enabled=true`, two tenant slugs, enabled API Key auth, and one bound key per tenant.
- **WHEN** `load_config` validates the YAML.
- **THEN** `GatewayConfig` SHALL expose both declarations and bindings; IDs SHALL be lowercase ASCII slugs of 1–64 characters; declaration order SHALL NOT create a fallback; unknown tenancy fields SHALL be rejected.

#### Scenario: SC-TCC-002 · high

- **GIVEN** empty, uppercase, whitespace, Unicode, path-like, edge-separated, or over-64-character IDs.
- **WHEN** each configuration is validated.
- **THEN** startup SHALL fail with a tenant field path and without exposing any API Key.

#### Scenario: SC-TCC-003 · medium

- **GIVEN** more than 1024 tenants or 4096 API Keys.
- **WHEN** cross-field validation runs.
- **THEN** startup SHALL fail with `tenant_limit_exceeded` or `tenant_api_key_limit_exceeded`, using bounded O(T+K) validation.

## REQ-TCC-002 — Fail-closed startup consistency

#### Scenario: SC-TCC-004 · high

- **GIVEN** tenancy enabled with auth disabled, no tenants, or a key lacking `tenant_id`.
- **WHEN** `load_config` validates the configuration.
- **THEN** startup SHALL fail with `tenancy_enabled_requires_auth`, `tenancy_requires_tenants`, or `api_key_tenant_required`; no configuration SHALL be silently repaired.

#### Scenario: SC-TCC-005 · high

- **GIVEN** duplicate tenant IDs, unknown bindings, duplicate key values, duplicate/empty key names, or a tenant without a key.
- **WHEN** validation runs.
- **THEN** startup SHALL fail with a case-specific stable reason, no secret SHALL be exposed, and no alternative tenant SHALL be selected.

#### Scenario: SC-TCC-006 · high

- **GIVEN** tenancy absent/disabled with tenant declarations or key bindings, plus an unchanged legacy control configuration.
- **WHEN** validation runs.
- **THEN** the contradictory configuration SHALL fail with `tenancy_disabled_with_tenant_configuration`, while the unchanged legacy control SHALL remain valid.

## REQ-TCC-003 — Identity-only scope

#### Scenario: SC-TCC-007 · high

- **GIVEN** valid tenancy declarations and key bindings.
- **WHEN** the schema and admitted request are inspected.
- **THEN** tenancy SHALL NOT define tenant-specific Flow, detector, threshold, word-list, provider, evidence, metrics, or resource policy; existing global configuration SHALL remain authoritative.


<!-- 合并自 2026-09-01-tenant-flow-policy-resolution -->
# Capability: tenant-config-contract

> Change: `2026-09-01-tenant-flow-policy-resolution`
> Canonical: `canonical/specs/code/tenant-config-contract.yaml`
> Overall confidence: high

## Purpose

Evolve the delivered identity-only tenant declaration into a strict, bounded and unambiguous policy-reference contract.

## REQ-TCC-004 — Named policy declarations are explicit and bounded

### SC-TCC-008 · high

- **GIVEN** two tenants referencing valid named policies.
- **WHEN** `load_config` validates the YAML.
- **THEN** policy declarations **SHALL** expose explicit stage refs, bindings, result policy and routing.
- **AND** IDs SHALL be bounded slugs, stage fields SHALL be present and may be explicit null, and unknown fields SHALL fail safely.

### SC-TCC-009 · medium

- **GIVEN** two tenants share a policy or a policy/binding/rule limit is exceeded.
- **WHEN** validation and compilation run.
- **THEN** explicit sharing **SHALL** be accepted and exceeded limits SHALL fail with stable codes.
- **AND** a shared policy compiles once and declaration order SHALL not select fallback.

## REQ-TCC-005 — Static reference ambiguities fail at startup

### SC-TCC-010 · high

- **GIVEN** missing policies or policy IDs, duplicate policy IDs, or unknown tenant-policy references.
- **WHEN** cross-field validation runs.
- **THEN** startup **SHALL** fail with `tenant_policy_required`, `duplicate_tenant_policy_id`, or `unknown_tenant_policy`.
- **AND** no policy SHALL be synthesized or selected by order.

### SC-TCC-011 · high

- **GIVEN** unknown Flow refs or missing, duplicate, or unused capability bindings.
- **WHEN** selected stage Flows are expanded.
- **THEN** startup **SHALL** fail with a stable Flow/binding reason code.
- **AND** every Detector capability SHALL have exactly one binding, with existing nested Flow limits preserved.

### SC-TCC-012 · high

- **GIVEN** unknown route Providers, conflicting exact patterns, or an unauthorized models Provider.
- **WHEN** routing validation runs.
- **THEN** startup **SHALL** fail with the corresponding stable tenant routing reason code.
- **AND** no Provider Key SHALL leak; non-identical overlaps retain explicit first-match ordering.

## REQ-TCC-006 — Tenant and legacy execution sources remain unambiguous

### SC-TCC-013 · high

- **GIVEN** tenant policies coexist with global routing, detector, stage, or binding selectors.
- **WHEN** raw source validation runs.
- **THEN** startup **SHALL** fail with `conflicting_tenant_policy_sources`.
- **AND** global declarations and deployment transport settings remain valid while no selector is silently ignored.

### SC-TCC-014 · high

- **GIVEN** disabled tenancy with policy fields and an unchanged legacy control.
- **WHEN** both load.
- **THEN** policy contradictions **SHALL** fail with `tenancy_disabled_with_tenant_policy`, while the legacy control SHALL remain valid and compatible.
