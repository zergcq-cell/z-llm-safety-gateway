# Capability: node-evidence-chain

## ADDED / MODIFIED Requirements

- **REQ-NEC-001**：每个 Flow 和 Node 产生版本化、确定排序的核心证据（2 scenarios）
- **REQ-NEC-002**：全部终态、部分执行与降级都有可辨识证据（1 scenarios）
- **REQ-NEC-003**：证据默认最小化、脱敏且有硬大小边界（2 scenarios）
- **REQ-NEC-004**：流式聚合与证据持久化失败均显式可见（2 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/node-evidence-chain.yaml`
- Agent checkpoints: `canonical/specs/agent/node-evidence-chain.yaml`
- Test cases: 7
