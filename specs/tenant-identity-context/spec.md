# Capability: tenant-identity-context

> Change: `2026-08-30-tenant-identity-config-contract`
> Canonical: `canonical/specs/code/tenant-identity-context.yaml`
> Overall confidence: high

## Purpose

Provide every admitted request with an immutable, versioned and secret-free tenant identity derived only from trusted server-side authentication state.

## REQ-TIC-001 — Frozen trusted request identity

#### Scenario: SC-TIC-001 · high

- **GIVEN** multi-tenancy and a valid key bound to `acme`.
- **WHEN** `AuthMiddleware` admits the request.
- **THEN** `request.state.tenant_context` SHALL contain contract `1.0`, tenant `acme`, and source `api_key`; it SHALL be immutable, contain no key, and preserve `api_key_name`.

#### Scenario: SC-TIC-002 · high

- **GIVEN** two concurrent requests bound to different tenants.
- **WHEN** both enter downstream handlers.
- **THEN** each request SHALL observe only its own Context; neither SHALL mutate the other, and Rate Limit/routing SHALL execute after identity assignment.

## REQ-TIC-002 — Untrusted input cannot select tenants

#### Scenario: SC-TIC-003 · high

- **GIVEN** an `acme` key and `X-Tenant-ID: globex`.
- **WHEN** the request is admitted.
- **THEN** Context SHALL remain `acme`; the Header SHALL NOT enter Context or become a public selection contract; Provider semantics SHALL remain unchanged.

#### Scenario: SC-TIC-004 · high

- **GIVEN** multi-tenancy with a missing or invalid Bearer token.
- **WHEN** authentication runs.
- **THEN** the existing OpenAI-compatible 401 SHALL be returned; no default/alternative Context SHALL be created and no token SHALL be exposed.

## REQ-TIC-003 — Bounded consumer contract

#### Scenario: SC-TIC-005 · medium

- **GIVEN** the maximum valid declarations.
- **WHEN** an admitted request is resolved.
- **THEN** middleware SHALL use a startup-built expected-O(1) key lookup, SHALL NOT scan all declarations, and downstream code SHALL consume Context rather than credentials.
