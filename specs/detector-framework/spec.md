# Detector Framework

## 2026-08-20 合并：统一初始化与生命周期

> 来源：`2026-08-19-detector-readiness-fail-safe`

- `REQ-DF-601`：built-in、ML、in-process plugin 与 gRPC sidecar 共享初始化、状态与策略入口，失败不使用 sentinel Detector。
- `REQ-DF-602`：只有成功加载的实例参与健康检查和正常关闭；部分初始化资源执行有界 best-effort cleanup。

duck-typed plugin 未实现可选 `health_check` 时保留既有健康状态。gRPC 取消、异常或超时时仍必须关闭本地 channel。
