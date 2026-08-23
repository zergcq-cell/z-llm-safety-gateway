# Capability: observability

## ADDED / MODIFIED Requirements

- **REQ-OBS-701**：Prometheus 提供有界 Flow 与 Node 指标且禁用时零影响（2 scenarios）
- **REQ-OBS-702**：Tracing 保留 Flow、Node 与嵌套调用关系且不记录内容（1 scenarios）
- **REQ-OBS-703**：所有可观测标签与属性受到显式基数和隐私约束（1 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/observability.yaml`
- Agent checkpoints: `canonical/specs/agent/observability.yaml`
- Test cases: 4
