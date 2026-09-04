# Capability: default-detector-flow

## ADDED / MODIFIED Requirements

- **REQ-DDF-001**：旧 detector YAML 被确定性编译为 input/output 默认 Flow（2 scenarios）
- **REQ-DDF-002**：默认 reducer 与 stop policy 保持 Pipeline 结果语义（2 scenarios）
- **REQ-DDF-003**：所有 detector 执行路径共享请求级 Flow snapshot（2 scenarios）
- **REQ-DDF-004**：Detector 聚合作为可注册 reducer capability 而非通用核心分支（1 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/default-detector-flow.yaml`
- Agent checkpoints: `canonical/specs/agent/default-detector-flow.yaml`
- Test cases: 7


<!-- 合并自 2026-09-01-tenant-flow-policy-resolution -->
# Capability: default-detector-flow

> Change: `2026-09-01-tenant-flow-policy-resolution`
> Canonical: `canonical/specs/code/default-detector-flow.yaml`
> Overall confidence: high

## Purpose

Execute the Flow, Detector configuration and result policy selected for one trusted tenant without moving domain behavior into the core.

## REQ-DDF-005 — Tenant policy drives Flow and Detector behavior

### SC-DDF-008 · high

- **GIVEN** two policies select Flows producing different actions for identical content.
- **WHEN** authenticated requests execute.
- **THEN** each request **SHALL** use only its selected Flow identities and Node policies.
- **AND** all action/risk/stop/failure semantics follow that Flow while Flow Runtime remains tenant-neutral.

### SC-DDF-009 · high

- **GIVEN** the same Detector capability has different thresholds, word lists and flag escalation in two policies.
- **WHEN** identical content is processed.
- **THEN** each result **SHALL** use only its policy's binding and reducer policy.
- **AND** raw config SHALL not enter safe Context/errors/logs and differently configured instances SHALL not be substituted.

## REQ-DDF-006 — All paths retain the selected snapshot and lifecycle domain

### SC-DDF-010 · high

- **GIVEN** a request uses every input/output/stream/background path.
- **WHEN** stages read runtime values.
- **THEN** all stages **SHALL** use one captured tenant bundle.
- **AND** no global values SHALL reappear, async work SHALL retain the bundle, and public HTTP/SSE ordering SHALL remain compatible.

### SC-DDF-011 · high

- **GIVEN** same-named Detectors in two policies and only one is unavailable.
- **WHEN** availability snapshots are captured.
- **THEN** each policy **SHALL** observe only its own Detector status.
- **AND** required initialization failure in any declared policy SHALL prevent readiness.

## REQ-DDF-007 — Core domain boundaries remain intact

### SC-DDF-012 · medium

- **GIVEN** tenant policy compilation and execution.
- **WHEN** imports and runtime branches are inspected.
- **THEN** Flow core **SHALL NOT** import tenant, Detector or Provider domains to decide behavior.
- **AND** plugin config, Flow composition and reducer aggregation SHALL remain in their existing boundaries.
