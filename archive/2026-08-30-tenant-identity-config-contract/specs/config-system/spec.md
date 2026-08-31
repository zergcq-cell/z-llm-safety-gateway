# Capability: config-system

> Change: `2026-08-30-tenant-identity-config-contract`
> Canonical: `canonical/specs/code/config-system.yaml`
> Modifies the existing cumulative config-system capability.

## REQ-CFG-701 — Backward-compatible tenancy loading

#### Scenario: SC-CFG-701 · high

- **GIVEN** existing Gateway production/example YAML and representative v0.2.2 fixtures without tenancy fields.
- **WHEN** they are loaded and their current HTTP/SSE cases run.
- **THEN** every previously valid config SHALL remain valid without edits/warnings; HTTP, SSE, Provider, Flow, and Detector behavior SHALL remain compatible; only internal default Context is added.

#### Scenario: SC-CFG-702 · high

- **GIVEN** a documented multi-tenant YAML example with environment-backed keys and literal tenant IDs.
- **WHEN** production loading parses the example.
- **THEN** it SHALL validate at exact runtime paths and no rendered/logged evidence SHALL expose interpolated keys.

## REQ-CFG-702 — Production request-path consumption

#### Scenario: SC-CFG-703 · high

- **GIVEN** `create_app` loads tenants `acme` and `globex` with distinct keys.
- **WHEN** real HTTP requests reach downstream code.
- **THEN** each request SHALL expose its configured Context, identities SHALL NOT overwrite each other, and global Provider/Flow behavior SHALL remain unchanged.
