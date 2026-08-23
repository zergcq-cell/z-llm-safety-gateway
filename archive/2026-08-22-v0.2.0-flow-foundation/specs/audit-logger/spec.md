# Capability: audit-logger

## ADDED / MODIFIED Requirements

- **REQ-AUD-701**：审计记录以加法字段关联 Flow 与 Node 证据（2 scenarios）
- **REQ-AUD-702**：审计证据与内容存储策略分离并默认保护数据（1 scenarios）
- **REQ-AUD-703**：流式证据和 sink 故障采用显式有界持久化（2 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/audit-logger.yaml`
- Agent checkpoints: `canonical/specs/agent/audit-logger.yaml`
- Test cases: 5
