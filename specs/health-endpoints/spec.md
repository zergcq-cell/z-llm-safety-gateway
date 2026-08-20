# Capability: health-endpoints

> liveness (`/health`)、readiness (`/ready`)、metrics 占位端点 (`/metrics`)

## ADDED Requirements

### Requirement: REQ-001 - Liveness Probe

GET /health 是 liveness 探针，返回 HTTP 200 和 JSON body `{"status": "healthy"}`，不检查任何依赖。

#### Scenario: SC-001 - Liveness 探针正常返回

- **GIVEN** FastAPI 服务器已启动并监听
- **WHEN** 客户端发送 GET /health 请求
- **THEN** 服务器 SHALL 返回 HTTP 200
- **AND** 响应 body SHALL 为 JSON `{"status": "healthy"}`
- **AND** 响应 Content-Type SHALL 为 application/json
- **AND** liveness 探针 SHALL NOT 检查任何外部依赖（provider、数据库等）

---

### Requirement: REQ-002 - Readiness Probe (Ready)

GET /ready 是 readiness 探针，当服务器就绪（配置已加载、provider 客户端已初始化）时返回 HTTP 200 和 JSON body `{"status": "ready"}`。

#### Scenario: SC-002 - 服务器就绪时 readiness 探针返回 ready

- **GIVEN** 服务器配置已加载完成
- **AND** provider 客户端已初始化
- **WHEN** 客户端发送 GET /ready 请求
- **THEN** 服务器 SHALL 返回 HTTP 200
- **AND** 响应 body SHALL 为 JSON `{"status": "ready"}`
- **AND** 响应 Content-Type SHALL 为 application/json

---

### Requirement: REQ-003 - Readiness Probe (Not Ready)

GET /ready 在服务器未就绪时返回 HTTP 503 和 JSON body `{"status": "not_ready"}`。

#### Scenario: SC-003 - 服务器未就绪时 readiness 探针返回 not_ready

- **GIVEN** 服务器配置尚未加载完成或 provider 客户端尚未初始化
- **WHEN** 客户端发送 GET /ready 请求
- **THEN** 服务器 SHALL 返回 HTTP 503
- **AND** 响应 body SHALL 为 JSON `{"status": "not_ready"}`
- **AND** 响应 Content-Type SHALL 为 application/json

---

### Requirement: REQ-004 - Metrics Endpoint Content Type

GET /metrics 返回 HTTP 200 和 text/plain 内容类型（Prometheus 格式占位）。

#### Scenario: SC-004 - Metrics 端点返回 text/plain

- **GIVEN** FastAPI 服务器已启动并监听
- **WHEN** 客户端发送 GET /metrics 请求
- **THEN** 服务器 SHALL 返回 HTTP 200
- **AND** 响应 Content-Type SHALL 为 text/plain; charset=utf-8

---

### Requirement: REQ-005 - Metrics Placeholder Body

Phase 1 中 `/metrics` 响应 body 为 `# z LLM Safety Gateway metrics placeholder\n`（占位文本，Phase 4 实现完整指标）。

#### Scenario: SC-005 - Metrics 占位响应 body

- **GIVEN** FastAPI 服务器已启动并监听（Phase 1）
- **WHEN** 客户端发送 GET /metrics 请求
- **THEN** 响应 body SHALL 为 `# z LLM Safety Gateway metrics placeholder\n`
- **AND** Phase 1 SHALL NOT 实现实际 Prometheus 指标采集

---

### Requirement: REQ-006 - Health Endpoints No Authentication

健康检查端点不需要认证（即使在 Phase 4 启用认证后仍然如此）。

#### Scenario: SC-006 - 健康检查端点无认证可访问

- **GIVEN** FastAPI 服务器已启动
- **AND** 请求未携带任何认证凭据（无 Authorization 头、无 API key）
- **WHEN** 客户端分别发送 GET /health、GET /ready、GET /metrics 请求
- **THEN** 服务器 SHALL 返回正常响应（不返回 401 Unauthorized）
- **AND** /health SHALL 返回 HTTP 200
- **AND** /ready SHALL 返回 HTTP 200 或 503（取决于就绪状态）
- **AND** /metrics SHALL 返回 HTTP 200

---

### Requirement: REQ-007 - Health Endpoints Include X-Request-ID

所有健康检查端点响应包含 X-Request-ID 头。

#### Scenario: SC-007 - /health 响应包含 X-Request-ID

- **GIVEN** FastAPI 服务器已启动并注册了 RequestID 中间件
- **WHEN** 客户端发送 GET /health 请求（未携带 X-Request-ID 头）
- **THEN** 响应 SHALL 包含 X-Request-ID 头
- **AND** X-Request-ID 值 SHALL 为 UUID v4 格式

#### Scenario: SC-008 - /ready 响应包含 X-Request-ID

- **GIVEN** FastAPI 服务器已启动并注册了 RequestID 中间件
- **WHEN** 客户端发送 GET /ready 请求（未携带 X-Request-ID 头）
- **THEN** 响应 SHALL 包含 X-Request-ID 头
- **AND** X-Request-ID 值 SHALL 为 UUID v4 格式

#### Scenario: SC-009 - /metrics 响应包含 X-Request-ID

- **GIVEN** FastAPI 服务器已启动并注册了 RequestID 中间件
- **WHEN** 客户端发送 GET /metrics 请求（未携带 X-Request-ID 头）
- **THEN** 响应 SHALL 包含 X-Request-ID 头
- **AND** X-Request-ID 值 SHALL 为 UUID v4 格式
# 2026-08-20 合并：Detector-aware Readiness

> 来源：`2026-08-19-detector-readiness-fail-safe`

- `REQ-HEALTH-601`：`/health` 保持纯 liveness；`/ready` 使用 app-scoped detector 状态。
- `REQ-HEALTH-602`：健康检查并行、有界、脱敏，并支持后续恢复。

required/fail-closed 故障返回 503 not-ready；仅 fail-open 故障返回 200 ready、
`degraded: true`。摘要包含确定排序的 detector issues 与稳定 reason code。
