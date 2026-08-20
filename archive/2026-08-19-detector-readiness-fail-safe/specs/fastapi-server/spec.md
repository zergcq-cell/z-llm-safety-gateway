# FastAPI Server

## Requirements

- `REQ-FAST-601`：lifespan 保存所有配置项状态，并传播 required 初始化失败。
- `REQ-FAST-602`：input/output 的严格问题都必须在任何 Provider 工作前返回专用 503。
- `REQ-FAST-603`：fail-open 允许请求继续，但跳过故障检测器并携带降级快照。

## Scenarios

| ID | 行为 |
|---|---|
| SC-FAST-601 | 成功和失败配置都写入 app-scoped 状态 |
| SC-FAST-602 | required 失败传播启动异常，never ready |
| SC-FAST-603 | input 严格问题返回精确 503/error/header |
| SC-FAST-604 | output 严格问题在 sync/stream/async Provider 前阻断 |
| SC-FAST-605 | fail-open 跳过故障 detector，Provider 继续，审计/指标获快照 |
