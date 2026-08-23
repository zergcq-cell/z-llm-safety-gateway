# Capability: flow-runtime

## ADDED / MODIFIED Requirements

- **REQ-FR-001**：Runtime 有界并行执行节点与 item，输出顺序确定（2 scenarios）
- **REQ-FR-002**：Stop policy 取消 pending 调用并保留完整终态（1 scenarios）
- **REQ-FR-003**：嵌套 Flow 复用相同执行、限制与证据语义（1 scenarios）
- **REQ-FR-004**：取消、deadline 与硬限制均产生确定行为（2 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/flow-runtime.yaml`
- Agent checkpoints: `canonical/specs/agent/flow-runtime.yaml`
- Test cases: 6
