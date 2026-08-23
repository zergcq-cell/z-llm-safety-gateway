# Detector Framework

## 2026-08-20 合并：统一初始化与生命周期

> 来源：`2026-08-19-detector-readiness-fail-safe`

- `REQ-DF-601`：built-in、ML、in-process plugin 与 gRPC sidecar 共享初始化、状态与策略入口，失败不使用 sentinel Detector。
- `REQ-DF-602`：只有成功加载的实例参与健康检查和正常关闭；部分初始化资源执行有界 best-effort cleanup。

duck-typed plugin 未实现可选 `health_check` 时保留既有健康状态。gRPC 取消、异常或超时时仍必须关闭本地 channel。


<!-- 合并自 2026-08-22-v0.2.0-flow-foundation -->
# Capability: detector-framework

## ADDED / MODIFIED Requirements

- **REQ-DF-701**：四类 Detector 通过统一 Capability lifecycle 协调器参与 Flow（2 scenarios）
- **REQ-DF-702**：Detector SDK 与插件发现契约保持不变（1 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/detector-framework.yaml`
- Agent checkpoints: `canonical/specs/agent/detector-framework.yaml`
- Test cases: 3
