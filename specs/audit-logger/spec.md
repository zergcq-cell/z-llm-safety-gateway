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
