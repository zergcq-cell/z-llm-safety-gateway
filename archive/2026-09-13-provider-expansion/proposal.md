# v0.4.0 Change 5 — Provider 扩展

## Why

网关当前支持 OpenAI、Azure OpenAI 和 OpenAI-compatible Provider，但 Anthropic Claude 与 Google Gemini 使用不同的认证、请求、响应和流式协议。本 change 为多租户 Flow 提供稳定的 Claude/Gemini Provider 适配，同时保持统一 Provider contract 与协议兼容。

## What Changes

- 新增 Anthropic Claude Provider adapter。
- 新增 Google Gemini Provider adapter。
- 扩展统一 Provider contract、路由、模型端点、错误和 SSE 兼容矩阵。
- 保持租户 Provider 路由隔离、凭据脱敏和既有 Provider 回归兼容。

## Capabilities

### New

- **anthropic-provider-adapter**：Claude API 认证、格式转换、非流式与流式调用。
- **gemini-provider-adapter**：Gemini API 认证、格式转换、非流式与流式调用。
- **provider-format-conversion**：Provider 特有格式与统一内部契约之间的显式转换。
- **provider-compatibility-matrix**：新增与既有 Provider 的协议、错误和路由兼容验证。

### Modified

- **provider-proxy**：在统一生命周期和错误契约下支持新增 Provider。
- **provider-router**：支持租户范围内的 Anthropic/Gemini 路由解析。
- **streaming-contract**：将 Provider 原生流转换为稳定网关 SSE 事件。

## Impact

**代码**：Provider 抽象、路由、配置模型、请求/响应转换、SSE、错误映射、模型端点及测试。

**配置**：新增可选 Provider 配置；现有配置无需迁移，凭据继续使用受保护配置路径。

**基础设施**：增加 HTTP mock、流式事件、错误矩阵、租户路由和兼容性测试；不引入外部服务。

## Constraints

- 严格执行 STDD 六阶段和 RED→GREEN→REFACTOR。
- 保持 HTTP/SSE、统一错误结构、超时、取消和默认无重试语义。
- API Key、原始请求内容和未清理的上游异常不得泄漏。
- 不改变 Flow 核心、租户策略 schema 或现有 Provider 行为。
- 不自动创建 tag、发布版本或推送 GitHub。

## Non-goals

- OAuth 2.0（Change 6）。
- 多模态安全检测或图像生成端点（Change 7）。
- Provider failover、模型聚合控制面或动态热加载。
- 发布 v0.4.0。

## Risk Areas

- 格式转换语义丢失：字段级映射和边界测试。
- 流式事件不一致：统一 chunk、结束和错误事件，覆盖中途失败。
- 租户凭据串用：配置快照、路由隔离和脱敏测试。
- 上游错误、取消或超时泄漏：稳定错误映射、deadline 和取消传播。

## Critical / Anchoring

这是安全关键、跨系统且间接涉及 Provider 计费的变更。采用 L3 锚定，基于现有 Provider abstraction/router 和 v0.3.0 租户隔离四项变更。

路线文档原先未承诺 v0.4.0 Provider 范围；本提案经确认将其明确为 v0.4.0 Change 5，并在交付阶段记录设计调整。

## Project Principle Check

1. **插件 / Flow**：Provider 特有逻辑放在 adapter；Flow 与核心只负责稳定契约、生命周期、路由和执行机制。
2. **显式策略 / 失败**：认证失败、限流、超时、取消、上游不可用和流式失败均有稳定错误码与可观测信号；不做隐式重试或跨租户回退。
3. **透明边界 / 稳定契约**：调用方继续使用统一 HTTP/SSE 和错误契约；转换限定在 Provider 边界，延迟和资源有界。
4. **证据 / 数据保护**：Provider、模型、租户范围和失败原因可审计；API Key、原始内容和敏感上游细节默认脱敏。
5. **取舍 / 偏离**：仅显式建立 v0.4.0 Change 5 路线归属，无实现层偏离。

## Success Criteria

- Anthropic 和 Gemini 的非流式请求通过统一 Provider contract 成功完成。
- 两者流式响应转换为稳定、可验证的网关 SSE 事件序列。
- 认证、模型字段、系统消息、响应结构及全部主要失败类型均有测试覆盖。
- 多租户 Provider 路由不会跨租户使用配置或凭据。
- 现有 OpenAI、Azure OpenAI、OpenAI-compatible Provider 回归通过。
- API Key、请求内容和原始异常不会出现在响应、日志或审计证据中。
- 通过完整测试、Ruff、mypy、失败模式和兼容性质量门。
