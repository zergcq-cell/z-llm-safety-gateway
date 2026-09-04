# Capability: config-system

> Change: `2026-09-01-tenant-flow-policy-resolution`
> Canonical: `canonical/specs/code/config-system.yaml`
> Overall confidence: high

## Purpose

Prove that accepted tenant policy configuration is consumed by production wiring while legacy behavior and milestone boundaries remain accurate.

## REQ-CFG-703 — Production wiring consumes tenant policies

### SC-CFG-704 · high

- **GIVEN** a real YAML with two tenants, policies, Flows, bindings and routes.
- **WHEN** authenticated HTTP sync and streaming requests enter `create_app`.
- **THEN** production wiring **SHALL** resolve and execute each tenant's policy and authorized Provider end to end.
- **AND** Context, Detector state and Provider selection SHALL not cross tenants; HTTP/SSE contracts remain compatible.

### SC-CFG-705 · high

- **GIVEN** the documented tenant policy YAML uses real environment interpolation.
- **WHEN** `load_config` and `create_app` consume it.
- **THEN** it **SHALL** validate and compile through production models, factories and routing.
- **AND** fields SHALL exist at documented paths and no canonical/human/error/log/repr/Context surface SHALL expose secrets.

## REQ-CFG-704 — Compatibility and roadmap boundaries remain accurate

### SC-CFG-706 · high

- **GIVEN** current single-tenant YAML, explicit Flow fixtures and HTTP/SSE tests without policy fields.
- **WHEN** full regressions run.
- **THEN** all previously valid configuration and public behavior **SHALL** remain compatible.
- **AND** no legacy file SHALL require tenant policy fields or observe changed status/body/header/payload/SSE order.

### SC-CFG-707 · high

- **GIVEN** current project docs and canonical indexes.
- **WHEN** documentation contracts inspect v0.3.0 state.
- **THEN** they **SHALL** accurately report change 1/4 delivered and change 2/4 active or delivered.
- **AND** v0.3.0 SHALL remain incomplete, later isolation changes pending, and no tag or artifact version created.
