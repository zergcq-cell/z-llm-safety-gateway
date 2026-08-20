# Degraded Safety Visibility

## Requirements

- `REQ-DSV-001`：fail-open 继续与 fail-closed 拒绝都必须留下请求级降级证据。
- `REQ-DSV-002`：API、日志、审计与指标只暴露稳定、低基数、脱敏字段。

`safety_degraded` 与确定排序的 `detector_availability` 是请求审计的公开降级证据；
endpoint、凭据、敏感正文和原始异常不得进入外部信号。
