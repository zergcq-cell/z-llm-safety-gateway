# Required Detector Policy

## Requirements

- `REQ-RDP-001`：required 初始化失败必须终止启动，并清理此前创建的检测器和审计资源。
- `REQ-RDP-002`：optional 故障由 `on_error` 决定 not-ready/fail-closed 或 ready/degraded/fail-open；多故障取最严格结果。

## Scenarios

| ID | 行为 |
|---|---|
| SC-RDP-001 | built-in、ML、in-process、gRPC 任一 required 初始化失败均中止启动 |
| SC-RDP-002 | fatal startup 逆序清理并刷新关闭审计 |
| SC-RDP-003 | optional fail_closed 启动供诊断但 not-ready，业务阻断 |
| SC-RDP-004 | optional fail_open 允许 degraded，检测器跳过 |
| SC-RDP-005 | 多故障采用最严格策略，输出排序确定 |
