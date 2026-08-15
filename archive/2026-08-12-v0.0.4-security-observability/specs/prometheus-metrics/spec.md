# prometheus-metrics — 行为规格（Human View）

> **变更**: 2026-08-12-v0.4.0-security-observability
> **Capability**: prometheus-metrics
> **创建时间**: 2026-08-12T16:00:00+08:00
> **置信度**: high
> **依据**: design Decision 7；DESIGN 12.5；proposal O1

## 描述

通过 `prometheus-client` 暴露 Prometheus 格式的网关可观测指标。`/metrics` 端点由 `observability.metrics.enabled` 控制，覆盖 gateway / detector / provider / recall 四类指标，与 DESIGN 12.5 定义的 15+ 指标对齐。

---

## 需求

### REQ-PROM-001: /metrics 端点由 observability.metrics.enabled 控制

**描述**: `/metrics` 端点由 `observability.metrics.enabled` 控制，开启时返回 Prometheus 文本格式指标。

**置信度**: high

#### SC-PROM-001: 开启时 /metrics 返回 Prometheus 格式

- **Given**: `observability.metrics.enabled=true`，网关已启动并注册了 `/metrics` 路由
- **When**: 客户端以 GET 请求 `/metrics`
- **Then**: 网关 **SHALL** 返回 HTTP 200，响应体为 `prometheus_client.generate_latest()` 生成的 Prometheus 文本格式指标
- **And**:
  - 响应 Content-Type **SHALL** 为 `text/plain; version=0.0.4; charset=utf-8`
  - 响应 **SHALL** 包含本 capability 定义的全部已注册指标系列

#### SC-PROM-002: 关闭时 /metrics 不可用

- **Given**: `observability.metrics.enabled=false`
- **When**: 客户端以 GET 请求 `/metrics`
- **Then**: 网关 **SHALL NOT** 暴露 Prometheus 指标（返回 404）
- **And**:
  - 未启用时 **SHALL NOT** 初始化指标注册表，避免指标采集开销
  - 该开关 **SHALL** 默认关闭，需显式启用

---

### REQ-PROM-002: 暴露 Gateway 指标

**描述**: 暴露 gateway 级指标：请求总数、处理时长、阻断数、标记数、活跃连接数。

**置信度**: high

#### SC-PROM-003: 请求处理时 gateway 指标计数与标签

- **Given**: `metrics.enabled=true`，网关已注册 gateway 指标
- **When**: 网关处理一个经过检测的请求（方向为 input/output，得到 action=block）
- **Then**: 网关 **SHALL** 递增 `safety_gateway_requests_total`，并携带 `direction`/`action`/`model` 标签
- **And**:
  - 网关 **SHALL** 记录 `safety_gateway_request_duration_seconds` 直方图（标签 `direction`/`model`）
  - 阻断请求 **SHALL** 递增 `safety_gateway_blocks_total`（标签 `direction`/`category`/`detector_name`）
  - 标记请求 **SHALL** 递增 `safety_gateway_flags_total`（标签 `direction`/`category`/`detector_name`）
  - `safety_gateway_active_connections` 与 `safety_gateway_streaming_active` 为 gauge，**SHALL** 反映当前连接数

---

### REQ-PROM-003: 暴露 Detector 指标

**描述**: 暴露检测器级指标：耗时、结果、错误、熔断器状态。

**置信度**: high

#### SC-PROM-004: 检测器执行时指标计数

- **Given**: `metrics.enabled=true`，pipeline 运行 `prompt_injection` 等检测器
- **When**: 检测器完成一次执行（结果为 block，随后又发生一次异常）
- **Then**: 网关 **SHALL** 记录 `safety_detector_duration_seconds` 直方图（标签 `detector_name`/`direction`）
- **And**:
  - 检测结果 **SHALL** 递增 `safety_detector_results_total`（标签 `detector_name`/`action`）
  - 检测异常 **SHALL** 递增 `safety_detector_errors_total`（标签 `detector_name`/`error_type`）
  - `safety_detector_circuit_breaker_state` gauge（标签 `detector_name`）**SHALL** 反映熔断器状态（0=closed,1=open,2=half-open）

---

### REQ-PROM-004: 暴露 Provider 指标

**描述**: 暴露 provider 级指标：请求总数、耗时、错误数。

**置信度**: high

#### SC-PROM-005: provider 调用时指标计数

- **Given**: `metrics.enabled=true`，provider 路由到 openai 模型 `gpt-4`
- **When**: 网关调用上游 provider 一次并发生一次错误
- **Then**: 网关 **SHALL** 递增 `safety_provider_requests_total`（标签 `provider`/`model`）
- **And**:
  - 网关 **SHALL** 记录 `safety_provider_duration_seconds` 直方图（标签 `provider`/`model`）
  - provider 错误 **SHALL** 递增 `safety_provider_errors_total`（标签 `provider`/`error_type`）

---

### REQ-PROM-005: 暴露 Recall 指标

**描述**: 暴露后审计召回计数指标。

**置信度**: high

#### SC-PROM-006: 后审计召回时计数

- **Given**: `metrics.enabled=true`，一次后审计触发召回（category=pii，risk_level=high）
- **When**: PostAuditRunner 完成一次召回记录
- **Then**: 网关 **SHALL** 递增 `safety_recalls_total`（标签 `category`/`risk_level`）
- **And**:
  - 指标 **SHALL** 仅记录召回次数，不包含敏感原文内容
  - 该计数 **SHALL** 与 audit logger 的召回记录语义一致（DESIGN 12.5）

---

## 验证检查点

| CP | Scenario | 描述 |
|----|----------|------|
| CP-1 | SC-PROM-001 | metrics.enabled=true 时 /metrics 返回 200 + Prometheus 格式 |
| CP-2 | SC-PROM-002 | metrics.enabled=false 时 /metrics 返回 404 |
| CP-3 | SC-PROM-003 | gateway 指标计数与标签正确 |
| CP-4 | SC-PROM-004 | detector 指标计数正确 |
| CP-5 | SC-PROM-005 | provider 指标计数正确 |
| CP-6 | SC-PROM-006 | recall 指标计数正确 |
| CP-7 | -- | prometheus-metrics 全量单元测试通过 |
| CP-8 | -- | ruff / mypy 无错误 |
