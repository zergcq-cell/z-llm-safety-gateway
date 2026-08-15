# authentication - 行为规格（Human View）

> **Change**: 2026-08-12-v0.4.0-security-observability
> **Capability**: authentication
> **Created**: 2026-08-12T16:00:00+08:00
> **Confidence**: high

## Description

API Key 认证能力：`AuthMiddleware` 从 `security.auth.api_keys`（key/name 列表）读取合法 Bearer token，请求头 `Authorization: Bearer <key>` 匹配任一配置 key 则放行并注入 `request.state.api_key_name`，否则返回 401（OpenAI 兼容错误体）。认证默认关闭，显式启用为 fail-closed，避免配置错误导致未授权访问。中间件顺序位于 RequestID 之后、路由之前，确保所有业务端点均被保护。

---

## Requirements

### REQ-AUTH-001: 从 security.auth.api_keys 校验 Bearer token

**Description**: AuthMiddleware 从 `security.auth.api_keys`（key/name 列表）校验 Bearer token，匹配任一配置 key 则放行，否则拒绝。

**Confidence**: high

#### SC-AUTH-001: 合法 Bearer token 被放行

- **Given**: `security.auth.enabled=true` 且 `api_keys=[{key:'sk-a', name:'app-a'}]`
- **When**: 请求携带 `Authorization: Bearer sk-a` 访问业务端点
- **Then**: AuthMiddleware **SHALL** 校验 Bearer token 匹配任一配置 key 并放行请求到路由
- **And**:
  - 请求 **SHALL** 被注入 `request.state.api_key_name='app-a'`

#### SC-AUTH-002: 未知 Bearer token 返回 401

- **Given**: `security.auth.enabled=true` 且 `api_keys=[{key:'sk-a', name:'app-a'}]`
- **When**: 请求携带 `Authorization: Bearer sk-unknown`（不在 api_keys 中）
- **Then**: AuthMiddleware **SHALL** 拒绝该请求并返回 401

---

### REQ-AUTH-002: 默认关闭，显式启用为 fail-closed

**Description**: 认证默认关闭（`enabled: false`）；显式启用后为 fail-closed，无凭据请求默认拒绝。

**Confidence**: high

#### SC-AUTH-003: 认证关闭时无 Authorization 头放行

- **Given**: `security.auth.enabled` 未设置或为 false（默认关闭）
- **When**: 请求未携带任何 Authorization 头访问端点
- **Then**: AuthMiddleware **SHALL** 放行请求（认证关闭时不校验 token）

#### SC-AUTH-004: 显式启用后无凭据请求返回 401

- **Given**: `security.auth.enabled=true`（显式启用）
- **When**: 请求未携带 Authorization 头访问端点
- **Then**: AuthMiddleware **SHALL** 拒绝该请求并返回 401（fail-closed：无凭据默认拒绝）

---

### REQ-AUTH-003: 401 OpenAI 兼容错误体

**Description**: 未授权响应返回 HTTP 401，错误体为 OpenAI 兼容格式，且不泄露配置的 api_key。

**Confidence**: high

#### SC-AUTH-005: 无效或缺失 token 返回 OpenAI 兼容 401

- **Given**: 认证启用且请求的 token 无效或缺失
- **When**: AuthMiddleware 判定未授权
- **Then**: 响应 **SHALL** 返回 HTTP 401 且错误体为 OpenAI 兼容格式
- **And**:
  - 错误体 **SHALL** 包含 error 对象（含 type 与 message 字段）
  - 响应 **SHALL NOT** 泄露任何配置的 api_key 值

---

### REQ-AUTH-004: 放行时注入 request.state.api_key_name

**Description**: 校验通过后，将匹配到的 key 对应的 name 注入 `request.state.api_key_name`，供后续中间件与审计使用。

**Confidence**: high

#### SC-AUTH-006: api_key_name 被注入 state

- **Given**: 认证启用且 Bearer token 匹配 `api_keys` 中 `name='app-a'` 的 key
- **When**: 请求进入后续路由/审计处理
- **Then**: `request.state.api_key_name` **SHALL** 等于 'app-a'
- **And**:
  - 后续中间件与审计日志 **SHALL** 可读取 `request.state.api_key_name`

---

### REQ-AUTH-005: 中间件顺序（RequestID 之后、路由之前）

**Description**: AuthMiddleware 位于 RequestIDMiddleware 之后、路由分发之前，确保所有业务端点均被认证保护。

**Confidence**: high

#### SC-AUTH-007: 认证在所有业务端点分发前执行

- **Given**: 认证启用且请求到达网关
- **When**: 请求经过中间件链
- **Then**: AuthMiddleware **SHALL** 在 RequestIDMiddleware 之后、路由分发之前执行
- **And**:
  - 所有业务端点（chat/streaming 等）**SHALL** 均被认证保护

---

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-AUTH-001 | 合法 Bearer token 被放行 |
| CP-2 | SC-AUTH-002 | 未知 Bearer token 返回 401 |
| CP-3 | SC-AUTH-003 | 认证关闭时无 Authorization 头放行 |
| CP-4 | SC-AUTH-004 | 显式启用后无凭据请求返回 401（fail-closed） |
| CP-5 | SC-AUTH-005 | 401 错误体为 OpenAI 兼容格式且不泄露 api_key |
| CP-6 | SC-AUTH-006 | request.state.api_key_name 被注入 |
| CP-7 | SC-AUTH-007 | 中间件顺序正确（RequestID 之后、路由之前） |
| CP-8 | -- | ruff lint 通过 |
| CP-9 | -- | mypy 类型检查通过 |
