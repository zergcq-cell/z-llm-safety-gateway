# Capability: fastapi-server — 行为规格（Human View）

> 变更：`2026-08-12-v0.4.0-security-observability`
> Capability：fastapi-server（认证/限流/TLS/CORS/请求限制/优雅停机集成、request_id 配置接线、per-detector timeout/circuit_breaker 注入）
> 整体置信度：high
> 关联能力：config-system（配置模型）、authentication、rate-limiting、request-size-limit、cors、graceful-shutdown、tls

---

## 1. 概述

本 capability 负责 FastAPI 应用工厂 `create_app` 的安全与可观测接线。核心是把 v0.4.0 新增的安全中间件（认证、限流、请求大小限制、CORS、TLS、优雅停机）以正确的顺序挂载到中间件链，并把 `security.request_id` 配置接线到 `RequestIDMiddleware`、把 per-detector 的 `timeout_seconds` 与 `CircuitBreaker` 实例注入 `_extract_detector_configs`。

依据 `design.md` 的 Architecture 中间件链顺序：**RequestID → Auth → RateLimit → RequestSize → SafetyHeaders**（外层先处理请求、后处理响应）。

---

## 2. 需求与场景

### REQ-FSA-001 — 中间件链注册顺序

`create_app` 按 RequestID→Auth→RateLimit→RequestSize→SafetyHeaders 的链顺序注册安全中间件。

- **SC-FSA-001（high）**
  - *Given*：安全配置加载通过，且 auth/rate_limit/request_size 均启用。
  - *When*：调用 `create_app(config_path)`。
  - *Then*：app 注册全部安全中间件，生效链顺序（外层→内层）为 RequestID→Auth→RateLimit→RequestSize→SafetyHeaders。
  - *And*：RequestID 最外层（响应最后写 X-Request-ID）；SafetyHeaders 最内层（先处理响应写 X-Safety-Action）；Auth 在 RateLimit 之前，确保所有业务端点先过认证；RateLimit 在 Auth 之后、RequestSize 之前。

### REQ-FSA-002 — request_id 配置接线

`security.request_id.header/generate` 配置接线到 `RequestIDMiddleware`。

- **SC-FSA-002（high）**：header='X-Request-ID' 且 generate=true 时，合法客户端头被采用并回写响应头；非法/超长（>128 字符）/含换行控制字符的头被丢弃并生成 UUID v4。
- **SC-FSA-003（high）**：generate=true 且客户端未带头时，生成 UUID v4 并注入响应头，同时写入 `request.state.request_id` 供下游审计/追踪。

### REQ-FSA-003 — per-detector timeout/circuit_breaker 注入

`_extract_detector_configs` 注入 `timeout_seconds` 与 `CircuitBreaker` 实例；新增 `circuit_breaker/factory.py::build_circuit_breaker`。

- **SC-FSA-004（high）**：显式 `timeout`（如 '10s'）注入 `timeout_seconds=10`，覆盖全局默认 5s；统一 key 为 `timeout_seconds`。
- **SC-FSA-005（high）**：未配置 timeout 时回退全局 `security.timeout.detector`（默认 5s）。
- **SC-FSA-006（high）**：配置了 `circuit_breaker` 的检测器注入由工厂构建的 `CircuitBreaker` 实例；未配置则不注入。
- **SC-FSA-007（high）**：`build_circuit_breaker` 解析 `recovery_timeout`（'30s'→30 秒），并正确传递 `failure_threshold`/`fallback_action`。

### REQ-FSA-004 — 认证集成（fail-closed）

- **SC-FSA-008（high）**：启用时合法 Bearer token 放行，并注入 `request.state.api_key_name`。
- **SC-FSA-009（high）**：启用时缺失/无效 token 返回 401，错误体为 OpenAI 兼容格式（type: invalid_request_error）。
- **SC-FSA-010（high）**：禁用（默认）时不校验、直接放行。

### REQ-FSA-005 — 限流集成（429 + Retry-After）

- **SC-FSA-011（high）**：超限返回 429 + Retry-After + OpenAI 兼容错误体（rate_limit_error / rate_limit_exceeded）；按 per（api_key|ip）维度隔离；storage 仅 memory（Redis 留待 v1.1+）。
- **SC-FSA-012（high）**：未超限时放行。

### REQ-FSA-006 — 请求大小限制（413）

- **SC-FSA-013（high）**：Content-Length（或分块读取）超 `max_request_size`（默认 10MB）返回 413，OpenAI 兼容错误体。
- **SC-FSA-014（high）**：限制内放行。

### REQ-FSA-007 — CORS 集成

- **SC-FSA-015（high）**：启用时跨域预检返回允许的 CORS 头。
- **SC-FSA-016（high）**：禁用（默认）时不注册 CORSMiddleware。

### REQ-FSA-008 — TLS 与优雅停机集成

- **SC-FSA-017（high）**：TLS 启用时以原生 TLS 终止接受 HTTPS 请求。
- **SC-FSA-018（high）**：收到 SIGTERM 后停止接收新连接、等待 in-flight 请求（至多 `server.stop_timeout`=30s），完成/超时后冲刷审计日志并以退出码 0 退出；`stop_timeout` 须小于 Docker `stop_grace_period`。

---

## 3. 场景统计

- **需求数**：8（REQ-FSA-001 ~ REQ-FSA-008）
- **场景数**：18（SC-FSA-001 ~ SC-FSA-018）
- 置信度：全部为 high

## 4. 证据来源

- `design.md`：Architecture 中间件链顺序；Decision 1/2/3/4/5/6/9/13
- `DESIGN.md`：11.1 Authentication、11.2 TLS、11.3 Rate Limiting、11.4 Request Size Limit、11.5 Timeout Control、11.6 CORS、11.7 Request ID、5.8 Circuit Breaker、13.4 Graceful Shutdown
- `proposal.yaml`：S1~S6、C1、C5、C6
- `src/z_llm_safety_gateway/app.py::create_app`、`middleware/request_id.py`
