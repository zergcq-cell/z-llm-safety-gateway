# config-system — 行为规格（Human View）

> Capability: config-system
> Change: 2026-08-12-v0.4.0-security-observability
> 置信度：high

## 概述

重构配置系统以支撑 v0.4.0 全部新安全能力与可观测能力，并修复前版本遗留的阈值命名空间冲突与 PII 命名不一致问题。

## Requirements

### REQ-CFG-001 — SecurityConfig 类型化子模型重构

**Given** 一份包含 `security.auth`、`security.tls`、`security.rate_limit`、`security.cors`、`security.request_id`、`security.max_request_size` 的配置

**When** `GatewayConfig` 加载该配置

**Then** 该配置 SHALL 被解析为类型化的 `AuthConfig`/`TLSConfig`/`RateLimitConfig`/`CORSConfig`/`RequestIDConfig` 实例

**And**
- `security.timeout` SHALL 解析 `"120s"`/`"5s"` 字符串形式的 `upstream` 与 `detector` 超时
- 全部新字段 SHALL 有默认值，旧 v0.1.0~v0.3.0 配置无需修改即可加载

### REQ-CFG-002 — ServerConfig 补 workers 与 stop_timeout

**Given** `server` 配置含 `workers` 与 `stop_timeout`

**When** `GatewayConfig` 加载该配置

**Then** `server.workers` 与 `server.stop_timeout` SHALL 被解析，默认 `workers=1`、`stop_timeout='30s'`

### REQ-CFG-003 — ObservabilityConfig 嵌套子模型

**Given** `observability` 配置含 `metrics.enabled/endpoint` 与 `tracing.enabled/exporter/endpoint/sample_rate`

**When** `GatewayConfig` 加载该配置

**Then** `observability` SHALL 解析为 `MetricsConfig`/`TracingConfig` 子模型

**And**
- `tracing.exporter` SHALL 支持 `"otlp"`，`sample_rate` 默认 0.1
- `metrics.endpoint` 默认 `/metrics`

### REQ-CFG-004 — 阈值命名空间分离

**Given** `sensitive_words` 检测器 config 含 `count_block_threshold=3`、`count_flag_threshold=1`

**When** 配置校验运行

**Then** 配置校验 SHALL 独立校验 count 阈值（`count_block > count_flag`）与 confidence 阈值

**And**
- count 阈值 SHALL 与 confidence 阈值（`block_threshold`/`flag_threshold`）互不混淆
- 旧的 `block_threshold`/`flag_threshold` 若仍用于 confidence 语义 SHALL 保持可用

### REQ-CFG-005 — PII 命名统一

**Given** 配置引用名为 `pii_redaction` 的检测器

**When** `PIIDetector.name` 与注册表/校验器比对

**Then** `PIIDetector.name` SHALL 等于 `"pii_redaction"`

**And** engine 按 `detector.name` 查找配置 SHALL 命中 `pii_redaction` 的配置

## 验证检查点

| CP | 对应 Scenario | 验证动作 |
|----|--------------|----------|
| CP-1 | SC-CFG-001 | 新配置加载 + SecurityConfig 类型化断言 |
| CP-2 | SC-CFG-001 | TimeConfig 时长解析 |
| CP-3 | SC-CFG-002 | ServerConfig workers/stop_timeout |
| CP-4 | SC-CFG-003 | ObservabilityConfig 嵌套解析 |
| CP-5 | SC-CFG-004 | 阈值命名空间校验 |
| CP-6 | SC-CFG-005 | PII 命名统一 |
| CP-7 | SC-CFG-001~005 | 旧配置向后兼容 |
| CP-8 | — | ruff + mypy |

## Evidence

- REQ-CFG-001~003: proposal C1/C2; design Decision 9/10
- REQ-CFG-004: proposal C3; design Decision 11; DESIGN 5.3.1; backlog B-01
- REQ-CFG-005: proposal C4; design Decision 12; backlog B-02
