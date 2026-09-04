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
