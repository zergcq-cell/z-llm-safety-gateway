# 后续候选需求：v0.3.0 Roadmap 盘点

> 本文件记录 2026-08-28 的只读盘点结论，不属于 Codex-only STDD 适配的实现范围，
> 不代表 v0.3.0 范围已经确认。每项功能必须通过独立 STDD change 再确认。

## 当前进度基线

- Gateway 当前发布版本为 v0.2.2；Detector SDK 为 v0.1.1。
- v0.1.0 已完成首个公开测试版；v0.1.1 完成检测器 fail-safe、CI 和发布加固。
- v0.2.0 已完成 Flow Foundation；v0.2.1、v0.2.2 完成版本热修复、可复现发布和证据闭环。
- 本地基线为 1061 passed、1 skipped、93.33% coverage，Ruff 和 Mypy 通过。
- `DESIGN.md` 将 v0.3.0 定义为下一功能里程碑，但明确要求由独立 STDD change 确认范围。

## 已发现的 Roadmap 漂移

1. `PLAN_v0.1.1.md` 的“后续 v0.2.0”仍列出新检测器、Provider failover、Redis、Helm 和 mTLS，
   但实际 v0.2.0 已用于 Flow Foundation。
2. `RELEASE_NOTES_v0.1.0.md` 的 What's Next 仍保留发布时预测，不再代表当前排期。
3. Redis 在 `docs/configuration.md` 中写为 v0.2.0+，而代码与现行 spec 已明确推迟到 v1.1+。
4. 正式 roadmap 没有给 v0.3.0 分配可验收范围，因此不应直接开始任一候选功能。

## 建议的后续顺序

### R-01：统一 Roadmap 事实源（P0，documentation change）

- 建立或指定唯一的当前 roadmap 入口。
- 将旧 release notes 和历史计划明确标为历史快照。
- 修正 Redis 等版本归属冲突。
- 为每个计划项记录状态、目标版本、依赖和对应 STDD change。

### R-02：v0.3.0 需求发现与范围确认（P0，独立 thorough change）

- 收集真实部署反馈和 v1.0.0 API 稳定性证据。
- 在以下候选能力中确定单一主目标，不一次性全部实现：
  - Provider 能力插件化，以及 Anthropic/Gemini 适配；
  - 基于显式 Flow 策略的 Provider failover；
  - 独立 jailbreak / hallucination 检测插件；
  - gRPC sidecar 原生 mTLS。
- 明确兼容策略、失败模式、延迟预算、审计证据和隐私边界。

### R-03：后续基础设施与企业能力（P1/P2）

- Redis 分布式限流：依照当前代码和 spec 保持 v1.1+，除非新 STDD change 显式调整。
- K8s Helm Chart：在运行时配置和部署契约稳定后处理。
- RBAC、多租户：需要先定义租户身份、配置隔离和审计边界。
- Agent execution rails：需要独立定义 tool-call/trajectory 契约和有界执行策略。
- Observability UI、Plugin marketplace：在核心 API 和插件分发契约稳定后处理。

## 建议的最近两项工作

1. 完成当前 `2026-08-28-codex-only-stdd-adaptation` change。
2. 随后启动独立的 `roadmap-source-of-truth` 文档 change，完成 R-01；再通过 R-02 决定 v0.3.0 主目标。
