# Required Detector Policy

## Requirements

- `REQ-RDP-001`：required 初始化失败必须终止启动，并有界清理此前创建的检测器和审计资源。
- `REQ-RDP-002`：optional 故障由 `on_error` 决定 not-ready/fail-closed 或 ready/degraded/fail-open；多故障取最严格结果。

该策略一致应用于 built-in、ML、in-process plugin 与 gRPC sidecar。
