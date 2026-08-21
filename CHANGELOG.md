# Changelog

本项目的所有显著变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

**版本策略**：`v0.0.x` = 内部开发阶段（不公开发布） · `v0.x.y` = 公开测试版（API 可能变化） · `v1.0.0` = GA 正式版（API 稳定）。

## [Unreleased]

暂无。

## [0.1.1] - 2026-08-21

### 安全与可靠性

- 检测器就绪状态改为 fail-safe：必需检测器不可用时拒绝流量，并保持健康日志脱敏。
- 修复请求取消路径中的检测器资源释放，避免容量泄漏。

### 工程与发布

- CI 扩展至 Python 3.10、3.11、3.12，并将覆盖率门槛提升到 90%。
- Ruff 门禁覆盖 Detector SDK 与两个示例插件；Mypy 覆盖网关、SDK 与发布工具，
  SDK 同步发布 0.1.1。
- 增加 Dependabot、生产依赖 `pip-audit`、四产物构建和干净安装验证。
- Release workflow 支持安全 dry-run；仅 `v*` tag push 可以创建 GitHub Release。
- 恢复固定来源的 STDD v2.9.5 CLI，并补录 canonical、代码结构与真实经验模式。

## [0.1.0] - 2026-08-15

### 首个公开测试版

- 透明 LLM 代理：OpenAI 兼容 `/v1/chat/completions`、`/v1/models`，路由到 OpenAI / Azure / OpenAI 兼容提供商（如 Ollama）
- 5 个内置检测器：prompt injection、PII 脱敏、toxicity（ML）、敏感词、密钥泄露 — 并行执行 + 可配置阈值
- 流式安全：SSE 代理 + 滑动窗口检测 + 事后深度审计（post-audit）+ 召回信号（SSE/webhook）
- 插件生态：in-process 插件（entry points）、gRPC sidecar 检测器（任意语言）、官方 `z-llm-safety-gateway-sdk`、`zlg` 插件 CLI
- 安全：API Key 认证、限流、TLS 终止、请求大小限制、CORS、熔断器、per-detector 超时、fail-open/fail-closed
- 可观测性：Prometheus 指标、OpenTelemetry 追踪、JSONL 审计日志（含脱敏）
- 生产部署：Docker 镜像、生产 Compose（多副本 + 健康检查 + sidecar）
- 质量：802 tests、92% 覆盖率、ruff/mypy clean、规则流水线 P50 0.2ms、单实例 ~6600 req/s
- 文档：getting-started / configuration / api-spec / deployment / plugin-development / grpc-integration / commercial-plugin

## [0.0.6] - 2026-08-15

### 生产就绪（内部阶段，git 历史中曾标记为 v1.0.0）

- 全套用户文档与 Apache 2.0 LICENSE
- 检测器精度测试（accuracy tests）与性能基准（benchmarks）
- 生产 Docker Compose 配置（多副本、资源限制、健康检查、sidecar）
- GitHub CI 流水线（ruff + mypy + pytest 覆盖率门限）

## [0.0.5] - 2026-08-14

### 插件生态

- gRPC sidecar 支持：protobuf 契约、gRPC 客户端、生命周期管理
- 插件加载器：entry points + gRPC 发现、健康检查
- Detector SDK：独立包、基础类、测试工具、CLI 脚手架（`zlg-sdk new`）
- 插件 CLI：list / info / test / check-connection
- 示例插件：Python in-process、Python gRPC、Go gRPC
- 插件文档：检测器开发指南、gRPC 集成指南、商业化指南

## [0.0.4] - 2026-08-14

### 安全与可观测性

- API Key 认证（Bearer token 校验）
- 限流：每 API Key / IP 令牌桶，429 + Retry-After
- 请求大小限制
- 超时控制：上游 Provider + 检测器超时
- CORS（可选、可配置）
- TLS 原生终止
- Prometheus 指标：gateway / detector / provider / recall
- OpenTelemetry 追踪（可选、可配置采样）
- 优雅关闭（SIGTERM，完成 in-flight 请求）

## [0.0.3] - 2026-08-12

### 流式与审计

- SSE 流式透明代理
- 滑动窗口检测（字符级窗口、可配置大小/重叠）
- 流内存管理：最大响应大小、block/truncate 策略
- 事后审计：流结束后全响应深度检测
- 召回机制：SSE 事件 + 可选 webhook 召回信号
- 非流式输出检测（sync/async 可配置）
- JSONL 审计日志（每日轮转）+ stdout 结构化输出
- 日志脱敏：API Key、认证头

## [0.0.2] - 2026-08-11

### 流水线与检测器

- Pipeline 引擎：并行执行、block 短路、结果聚合、优先级排序
- DetectionResult 模型：阈值驱动动作、风险等级、置信度
- 检测器基类：抽象接口、DetectionContext、生命周期（init/health/shutdown）
- 检测器注册表：内置 + entry point 发现
- 5 个 MVP 检测器：Prompt Injection、PII 脱敏、Toxicity、敏感词、密钥泄露
- 检测器配置：per-detector 阈值、on_error 策略、优先级
- ML 模型管理：下载、缓存、离线模式
- 语言检测：langdetect 集成、上下文传播
- 熔断器：外部 / LLM-as-Judge 检测器
- Block 响应格式：OpenAI 兼容错误 + safety 扩展字段

## [0.0.1] - 2026-08-11

### 框架骨架

- FastAPI 服务：OpenAI 兼容端点（`/v1/chat/completions`）
- 配置系统：YAML 加载、Pydantic v2 校验、env 覆盖、校验规则
- Provider 代理：请求转发到 OpenAI、响应返回
- 内容提取器：从 messages 数组提取文本、修改写回
- Docker 配置：Dockerfile + 基础 docker-compose.yml
- 健康端点：`/health`、`/ready`、`/metrics`
- Request ID：生成、传播、响应头
