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
