# Detector Framework

## Requirements

- `REQ-DF-601`：四类已配置检测器共享初始化、状态与策略入口，失败不用 sentinel Detector。
- `REQ-DF-602`：只有成功加载的实例参与 health_check 与 shutdown。

## Scenarios

| ID | 行为 |
|---|---|
| SC-DF-601 | built-in、ML、in-process、gRPC 使用同一协调器 |
| SC-DF-602 | factory 失败登记 unavailable 并应用 required/on_error |
| SC-DF-603 | unavailable 不调用 health/shutdown；loaded 正常调用 |
