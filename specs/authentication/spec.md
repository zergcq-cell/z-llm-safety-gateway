# Capability: authentication

> Change: `2026-08-30-tenant-identity-config-contract`
> Canonical: `canonical/specs/code/authentication.yaml`
> Modifies the existing authentication capability; SC-AUTH-001 through SC-AUTH-007 remain authoritative.

## REQ-AUTH-006 — Optional API Key tenant binding

#### Scenario: SC-AUTH-008 · high

- **GIVEN** legacy auth with a key/name pair and no tenancy or `tenant_id`.
- **WHEN** that key authenticates.
- **THEN** existing allow, `api_key_name`, and client response behavior SHALL remain unchanged; the request SHALL receive only the internal `default`/`legacy_single_tenant` Context.

#### Scenario: SC-AUTH-009 · high

- **GIVEN** enabled tenancy and validated key bindings.
- **WHEN** `AuthMiddleware` is constructed.
- **THEN** middleware SHALL precompile key-to-Context lookup; unknown/unbound mappings SHALL already have failed, and duplicate keys SHALL NOT overwrite an earlier tenant.

## REQ-AUTH-007 — Compatible, secret-safe middleware behavior

#### Scenario: SC-AUTH-010 · high

- **GIVEN** production `create_app` configured for multi-tenancy.
- **WHEN** valid and invalid requests traverse the middleware chain.
- **THEN** Request ID SHALL precede Auth, Context SHALL precede Rate Limit/routing, invalid credentials SHALL retain the existing 401 and request ID, and no response/error/log SHALL expose key values.
