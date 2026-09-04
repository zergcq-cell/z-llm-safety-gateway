# Capability: provider-proxy

> Change: `2026-09-01-tenant-flow-policy-resolution`
> Canonical: `canonical/specs/code/provider-proxy.yaml`
> Overall confidence: high

## Purpose

Route chat and models requests only within the authenticated tenant's bounded Provider domain while preserving protocol passthrough.

## REQ-PROXY-010 — Chat routing is tenant-bounded

### SC-PROXY-013 · high

- **GIVEN** two policies route the same model pattern to different Providers.
- **WHEN** both tenants send the same model.
- **THEN** each request **SHALL** call only its own policy-selected Provider.
- **AND** request/model passthrough remains unchanged and Provider objects remain private and shared.

### SC-PROXY-014 · high

- **GIVEN** a model matches only global or another tenant rules.
- **WHEN** tenant routing runs.
- **THEN** it **SHALL** return compatible 404 `model_not_found` without calling a Provider.
- **AND** the error SHALL not enumerate other routing topology or secrets.

### SC-PROXY-015 · high

- **GIVEN** untrusted tenant, policy, Provider or routing hints.
- **WHEN** the Router view selects a Provider.
- **THEN** it **SHALL** ignore every hint and match the standard model field only inside the captured policy domain.

## REQ-PROXY-011 — Models uses an explicit tenant Provider

### SC-PROXY-016 · high

- **GIVEN** a valid explicit `models_provider` in the tenant policy.
- **WHEN** `GET /v1/models` runs.
- **THEN** it **SHALL** query only that Provider and preserve status/body/content-type passthrough.
- **AND** it SHALL not aggregate or query the global first Provider; legacy mode retains current first-Provider behavior.

## REQ-PROXY-012 — Router views reuse private adapters safely

### SC-PROXY-017 · medium

- **GIVEN** policies share or separately reference global Providers.
- **WHEN** Router views and safe policy Contexts are built.
- **THEN** Provider adapters **SHALL** initialize once per global definition and be reused only by authorized views.
- **AND** safe Context/errors/logs SHALL not expose Provider objects, URLs, Keys, or raw rules.
