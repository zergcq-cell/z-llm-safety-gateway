# Audit Logger

## 2026-08-20 合并：Detector Readiness Fail-Safe

> 来源：`2026-08-19-detector-readiness-fail-safe`

- `REQ-AUDIT-601`：状态变化产生 `detector_lifecycle`，重复状态不重复写。
- `REQ-AUDIT-602`：required 致命失败在启动异常前完成审计 flush/close；审计禁用仍有结构化日志。
- `REQ-AUDIT-603`：请求审计通过 `safety_degraded` 与 `detector_availability` 区分完整和降级安全处理。

| 场景 | 行为 |
|------|------|
| SC-AUDIT-601 | 生命周期事件字段完整且只在变化时记录 |
| SC-AUDIT-602 | fatal startup 事件持久化；审计关闭时日志兜底 |
| SC-AUDIT-603 | fail-open 请求记录确定排序的 availability |
| SC-AUDIT-604 | 不保存秘密、endpoint 或异常正文 |


<!-- 合并自 2026-08-22-v0.2.0-flow-foundation -->
# Capability: audit-logger

## ADDED / MODIFIED Requirements

- **REQ-AUD-701**：审计记录以加法字段关联 Flow 与 Node 证据（2 scenarios）
- **REQ-AUD-702**：审计证据与内容存储策略分离并默认保护数据（1 scenarios）
- **REQ-AUD-703**：流式证据和 sink 故障采用显式有界持久化（2 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/audit-logger.yaml`
- Agent checkpoints: `canonical/specs/agent/audit-logger.yaml`
- Test cases: 5
# Tenant attribution extension (2026-09-08)

Audit entries may carry the trusted `TenantObservationContext` envelope outside FlowEvidence v1.0. The envelope contains no content or credentials and sink failures preserve the original safety action.
