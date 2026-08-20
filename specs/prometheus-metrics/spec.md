# Prometheus Metrics

## 2026-08-20 合并：Detector Availability

> 来源：`2026-08-19-detector-readiness-fail-safe`

- `REQ-PROM-601`：暴露 detector 初始化失败 counter 和当前 up gauge。
- `REQ-PROM-602`：统计 fail-open 降级请求；metrics disabled 时所有调用安全 no-op。

新增指标为 `safety_detector_initialization_failures_total`、`safety_detector_up` 和
`safety_gateway_degraded_requests_total`，标签不得包含异常正文、endpoint 或凭据。
