# Degraded Safety Visibility

## Requirements

- `REQ-DSV-001`：fail-open 继续与 fail-closed 拒绝都必须留下请求级降级证据。
- `REQ-DSV-002`：API、日志、审计与指标仅暴露稳定、低基数、脱敏字段。

## Scenarios

| ID | 行为 |
|---|---|
| SC-DSV-001 | fail-open 请求含 `safety_degraded` 与 `detector_availability` |
| SC-DSV-002 | fail-closed 503 同时产生结构化日志和请求审计 |
| SC-DSV-003 | endpoint、凭据及原始异常正文不出现在任何外部信号中 |
