# v0.4.0 - Security & Observability

## Why

v0.1.0~v0.3.0 完成了框架、Pipeline 检测器和流式审计，但网关完全没有任何安全防护（无认证/限流/TLS/请求大小限制/CORS/优雅停机），也无可观测性（无 Prometheus 指标/OpenTelemetry 追踪）。同时，对前三个版本的功能 Review 发现了一批遗留缺陷：P0 级别的阈值命名空间冲突、PII 命名不一致、流式 SSE 分片漏检，以及 P1 级别的 per-detector 超时/熔断配置失效、审计字段失真、同步超时未强制等。这些缺陷直接影响安全网关的检测正确性与合规可信度。

## What Changes

- 新建 API Key 认证（Bearer token，401）
- 新建 token_bucket 限流（429 + Retry-After）
- 新建原生 TLS 终止
- 新建请求大小限制（max_request_size，413）
- 新建 CORS 支持
- 新建优雅停机（SIGTERM）
- 新建 Prometheus 指标（/metrics）
- 新建 OpenTelemetry 追踪
- 重构 SecurityConfig（Auth/TLS/RateLimit/CORS/RequestID + TimeoutConfig）
- 重构 ObservabilityConfig / ServerConfig
- 重构阈值命名空间（count vs confidence 分离）
- 修复 PII 命名不一致
- 修复 per-detector timeout/circuit_breaker 未传递
- request_id 中间件配置接线
- 修复流式 SSE 分片漏检
- 修复流式审计 final_action 错取输入侧
- 修复流式审计 detectors/window_count 缺失
- 修复后审计 request_id/语言未传播
- 修复 sync_timeout 未强制
- 修复审计字段与 DESIGN 12.1 不一致

## Capabilities

### New Capabilities

- **authentication**：API Key Bearer token 认证，401 未授权响应
- **rate-limiting**：token_bucket 限流，per api_key/ip，429 + Retry-After
- **tls**：原生 TLS 终止
- **request-size-limit**：max_request_size 请求体限制，413 响应
- **cors**：可选 CORS 支持
- **graceful-shutdown**：SIGTERM 优雅停机，in-flight 请求完成
- **prometheus-metrics**：gateway/detector/provider/recall 指标，/metrics 端点
- **opentelemetry-tracing**：可选 OTel 追踪，可配置 exporter/sampling

### Modified Capabilities

- **config-system**：SecurityConfig/ObservabilityConfig/ServerConfig 重构，阈值命名空间分离，修复 PII 命名、timeout/circuit_breaker 传递
- **fastapi-server**：认证/限流/TLS/CORS/请求限制/优雅停机集成，/metrics 端点，request_id 配置接线
- **sse-streaming**：修复 SSE 分片漏检、审计 final_action/detectors/window_count、后审计上下文传播
- **audit-logger**：补齐审计字段（duration/user_id/applied），统一 post_audit schema

## Impact

**代码层面**：
- 涉及 config、middleware、routes、pipeline、detectors、streaming、audit、providers 约 20+ 文件
- 新增 auth/rate_limit/tls/metrics/tracing 相关模块

**配置层面**：
- SecurityConfig/ObservabilityConfig/ServerConfig 结构重构
- 阈值 key 命名空间分离（新增 count_* 阈值 key）
- gateway.yaml 示例更新

**基础设施**：
- 无新增外部依赖（限流 memory 存储、指标可选）
- OpenTelemetry 为可选集成

## Constraints

- 限流 storage 仅支持 memory（Redis 留待 v1.1+）
- TLS 默认关闭（生产建议反向代理），cert/key 文件为可选配置
- OpenTelemetry 为可选集成，默认关闭
- Prometheus 指标与 DESIGN 12.5 对齐
- backlog 修正遵循严格 TDD，P0 项优先
- 保持对 v0.1.0~v0.3.0 配置的向后兼容（新字段默认值，旧配置可运行）

## Stakeholders

- 网关使用者（应用程序开发者）——需要认证与限流保护
- 安全运维团队——需要 TLS/CORS/请求限制/优雅停机
- 可观测性团队——需要 Prometheus 指标与 OTel 追踪
- 安全合规团队——需要修复审计字段保证合规可信度

## Risk Areas

- capability: authentication — 认证配置错误导致网关不可用或未授权访问
- capability: rate-limiting — 限流误伤正常流量
- capability: tls — TLS 配置错误导致服务不可达
- capability: prometheus-metrics — /metrics 暴露敏感信息或影响性能
- capability: config-system — 阈值命名空间分离破坏现有配置
- capability: sse-streaming — SSE 分片重组引入流式延迟或协议错误

## NonGoals

- Redis 分布式限流（v1.1+）
- Provider failover（v1.1+）
- gRPC sidecar 检测器（v0.5.0）
- 多租户配置隔离（v1.2）
- 热重载配置（不支持，需重启）
- B-13~B-20 中部分 P2 项按切片可行性分批处理，不强制全部纳入本次

## Critical

- [ ] 非关键变更（默认）
- [x] 关键变更 — 涉及安全/金融/核心基础设施，需 L3/L4 锚定

## Risk Assessment

- **safety_critical**：true（涉及认证/授权/加密/数据保护）
- **financial**：false
- **cross_system**：false

## Anchoring

- **level**：L3
- **reference_changes**：2026-08-12-v0.3.0-streaming-audit, 2026-08-11-v0.2.0-pipeline-detectors, 2026-08-11-v0.1.0-framework-skeleton
- **anchor_implementations**：（无）

## Success Criteria

- [ ] API Key 认证启用时，无有效 Bearer token 的请求返回 401
- [ ] 限流超限时返回 429 并带 Retry-After 头
- [ ] TLS 启用时通过 HTTPS 访问成功
- [ ] 请求体超过 max_request_size 时返回 413
- [ ] CORS 启用时跨域请求通过预检
- [ ] SIGTERM 触发优雅停机，in-flight 请求完成，stop_timeout 内退出
- [ ] /metrics 端点按 metrics_enabled 开关返回 Prometheus 指标
- [ ] OTel 追踪按 tracing 配置采样并导出
- [ ] 敏感词检测 count 阈值独立生效，不再被 engine 错误覆盖（B-01 回归测试通过）
- [ ] PII 检测器配置（redaction_mode/entity_types）生效（B-02 回归测试通过）
- [ ] per-detector timeout 与 circuit_breaker 生效（B-04 回归测试通过）
- [ ] 流式 SSE 分片边界不漏检（B-03 回归测试通过）
- [ ] 流式审计 final_action/detectors/window_count 正确（B-05/B-06 回归测试通过）
- [ ] sync_timeout 强制生效（B-08 回归测试通过）
- [ ] 审计字段与 DESIGN 12.1 一致（B-09 回归测试通过）
- [ ] 全量测试通过（v0.1.0+v0.2.0+v0.3.0 回归 + v0.4.0 新测试），ruff/mypy 无错误
