# opentelemetry-tracing — 行为规格（Human View）

> **变更**: 2026-08-12-v0.4.0-security-observability
> **Capability**: opentelemetry-tracing
> **创建时间**: 2026-08-12T16:30:00+08:00
> **置信度**: high
> **依据**: design Decision 8；DESIGN 12.6；proposal O2

## 描述

可选的分布式追踪集成，通过 OpenTelemetry 对网关请求进行自动埋点。由 `observability.tracing.enabled/exporter/endpoint/sample_rate` 配置控制，默认关闭以避免为默认用户引入重依赖；MVP 支持 `exporter: otlp`，可扩展 jaeger/zipkin。

---

## 需求

### REQ-OTEL-001: OpenTelemetry 追踪为可选集成，默认关闭

**描述**: `observability.tracing.enabled` 默认 `false`，未启用时不加载任何 OTel 追踪依赖与导出。

**置信度**: high

#### SC-OTEL-001: 默认关闭时不初始化追踪

- **Given**: `observability.tracing.enabled` 未配置或为 `false`
- **When**: 网关启动并处理请求
- **Then**: 网关 **SHALL NOT** 初始化 TracerProvider，也 **SHALL NOT** 加载/生效任何追踪导出
- **And**:
  - 默认关闭 **SHALL** 保证不引入 OTel 重依赖（opentelemetry-api/sdk 及 instrumentation）
  - 默认路径下请求 **SHALL** 不产生 span 且不向外部导出

---

### REQ-OTEL-002: 启用时初始化 TracerProvider 并按 exporter 导出

**描述**: `tracing.enabled=true` 时初始化全局 TracerProvider，MVP 支持 `exporter: otlp`。

**置信度**: high

#### SC-OTEL-002: exporter=otlp 时初始化并导出

- **Given**: `observability.tracing.enabled=true`，`exporter=otlp`，`endpoint=http://otel-collector:4317`
- **When**: 网关启动
- **Then**: 网关 **SHALL** 使用 opentelemetry-sdk 初始化全局 TracerProvider，并配置 OTLP exporter 指向 `endpoint`
- **And**:
  - exporter 取值 **SHALL** 支持 `otlp`，可扩展 jaeger/zipkin
  - FastAPI 自动 instrumentation（opentelemetry-instrumentation-fastapi）**SHALL** 被接入以自动埋点

---

### REQ-OTEL-003: sample_rate 控制采样比例

**描述**: `sample_rate` 决定被采样的请求比例，默认 `0.1`。

**置信度**: high

#### SC-OTEL-003: 按 sample_rate 采样

- **Given**: `observability.tracing.sample_rate=0.1`
- **When**: 网关处理请求并决定是否创建追踪
- **Then**: 网关 **SHALL** 按约 10% 的请求比例采样创建追踪（比例由 `sample_rate` 决定）
- **And**:
  - `sample_rate` 默认 **SHALL** 为 0.1
  - 采样 **SHALL** 通过 Sampler 实现，未采样请求 **SHALL NOT** 被导出

---

### REQ-OTEL-004: 生成与传播标准 span 结构及属性

**描述**: 生成符合 DESIGN 12.6 的嵌套 span 树，并通过 W3C TraceContext 传播。

**置信度**: high

#### SC-OTEL-004: 生成嵌套 span 树并携带属性

- **Given**: `tracing.enabled=true`，网关处理一个包含检测与 provider 调用的请求
- **When**: 请求经过 `gateway.request` / `auth` / `pipeline.input` / `detector.*` / `provider.call` / `pipeline.output` / `audit.post` 等阶段
- **Then**: 网关 **SHALL** 生成以 `gateway.request` 为根的嵌套 span 树，根 span 携带 `request_id`/`model`/`direction` 属性
- **And**:
  - detector span **SHALL** 携带 `detector_name`/`confidence`/`action` 属性
  - `provider.call` span **SHALL** 携带 `provider`/`model`/`streaming` 属性
  - 各 span **SHALL** 记录相应 duration 信息

#### SC-OTEL-005: 尊重并延续客户端 trace context

- **Given**: 客户端请求携带 W3C `traceparent`/`tracestate` 头（trace context 已存在）
- **When**: 网关处理该请求
- **Then**: 网关 **SHALL** 尊重并延续客户端提供的 trace context（作为子 span 挂载），并通过响应传播 `traceparent`
- **And**:
  - trace 上下文传播 **SHALL** 遵循 W3C TraceContext 规范（`traceparent`/`tracestate`）
  - 无客户端 context 时网关 **SHALL** 创建新的根 trace

---

## 验证检查点

| CP | Scenario | 描述 |
|----|----------|------|
| CP-1 | SC-OTEL-001 | enabled=false 时不初始化、不导出 |
| CP-2 | SC-OTEL-002 | enabled=true + exporter=otlp 时初始化并导出 |
| CP-3 | SC-OTEL-003 | sample_rate 采样比例正确 |
| CP-4 | SC-OTEL-004 | span 结构、属性与嵌套正确 |
| CP-5 | SC-OTEL-005 | W3C trace context 传播与延续正确 |
| CP-6 | -- | opentelemetry-tracing 全量单元测试通过 |
| CP-7 | -- | ruff / mypy 无错误 |
