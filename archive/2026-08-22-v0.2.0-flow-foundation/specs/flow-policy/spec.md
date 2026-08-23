# Capability: flow-policy

## ADDED / MODIFIED Requirements

- **REQ-FP-001**：所有执行策略在启动时解析为显式不可变快照（1 scenarios）
- **REQ-FP-002**：异常与节点超时分别遵循显式 fallback（2 scenarios）
- **REQ-FP-003**：不可用与熔断降级遵循独立显式策略（1 scenarios）
- **REQ-FP-004**：Flow deadline 与矛盾策略被确定处理（2 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/flow-policy.yaml`
- Agent checkpoints: `canonical/specs/agent/flow-policy.yaml`
- Test cases: 6
