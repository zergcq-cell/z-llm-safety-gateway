# Prometheus Metrics

## Requirements

- `REQ-PROM-601`：暴露 detector 初始化失败 counter 和当前 up gauge。
- `REQ-PROM-602`：统计 fail-open 降级请求；metrics disabled 时所有调用安全 no-op。

## Scenarios

| ID | 行为 |
|---|---|
| SC-PROM-601 | 初始化失败 counter 使用 name/direction/type/policy |
| SC-PROM-602 | healthy=1，unhealthy/unavailable=0，标签低基数 |
| SC-PROM-603 | 每个降级 detector 每请求 counter 最多 +1 |
| SC-PROM-604 | metrics disabled 不抛错、不改变决策 |
