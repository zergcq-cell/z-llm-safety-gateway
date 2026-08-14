# cors — 行为规格（Human View）

> **变更**: 2026-08-12-v0.4.0-security-observability
> **Capability**: cors
> **创建时间**: 2026-08-12T16:00:00+08:00
> **置信度**: high

## 描述

提供**可选的 CORS 支持**。通过 `security.cors.enabled/origins` 配置，启用时在 `create_app` 接入 `starlette.middleware.cors.CORSMiddleware`。用于浏览器直连网关的场景，**默认关闭**。

> 设计依据：design Decision 5；DESIGN 11.6。

---

## Requirements

### REQ-CORS-001：CORS 默认关闭

**描述**：未配置 `security.cors.enabled` 时不接入 CORSMiddleware，不返回 CORS 响应头。

**置信度**: high

#### SC-CORS-001：CORS 未启用时不注册 CORSMiddleware

- **Given**: 配置未设置 `security.cors.enabled`（或显式 `enabled: false`）
- **When**: `create_app` 构建 FastAPI 应用
- **Then**: 应用 **SHALL** 不注册 CORSMiddleware，CORS 相关响应头不返回
- **And**:
  - 跨域浏览器请求 **SHALL** 按无 CORS 处理（浏览器端拦截预检/响应）

---

### REQ-CORS-002：启用时接入 CORSMiddleware 并按 origins 放行

**描述**：启用后接入 CORSMiddleware，允许配置的 origins 通过跨域预检。

**置信度**: high

#### SC-CORS-002：启用 CORS 后允许配置 origin 通过预检

- **Given**: 配置 `security.cors.enabled=true` 且 `security.cors.origins` 含 `https://app.example.com`
- **When**: `create_app` 构建 FastAPI 应用，且来自 app.example.com 的请求发起 CORS 预检（`OPTIONS`）
- **Then**: 应用 **SHALL** 接入 CORSMiddleware 并允许该 origin，返回相应 CORS 响应头（`Access-Control-Allow-Origin` 等）
- **And**:
  - 预检请求 **SHALL** 返回 200 并允许配置的 methods/headers
  - 配置的 origins 之外不被允许的跨域请求 **SHALL** 不获得 CORS 放行头

---

### REQ-CORS-003：CORS 配置不影响正常业务路由与安全中间件链

**描述**：启用 CORS 不改变业务处理逻辑，安全中间件链仍按序生效。

**置信度**: medium

#### SC-CORS-003：CORS 不影响同源业务请求与安全中间件

- **Given**: 启用 CORS 且网关运行正常
- **When**: 向网关发起同源业务请求（如 `POST /v1/chat/completions`）
- **Then**: 业务请求 **SHALL** 正常处理，不受 CORS 中间件影响
- **And**:
  - 认证/限流/请求大小等安全中间件 **SHALL** 依旧按序生效，不因 CORS 而绕过

---

## 验证检查点

| CP | Scenario | 描述 |
|----|----------|------|
| CP-1 | SC-CORS-001 | CORS 未启用时不注册 CORSMiddleware |
| CP-2 | SC-CORS-002 | 启用后允许配置 origin 通过预检 |
| CP-3 | SC-CORS-002 | 非配置 origin 不获得放行头 |
| CP-4 | SC-CORS-003 | CORS 不影响业务与安全中间件链 |
| CP-5 | -- | cors 完整测试套件通过 |
| CP-6 | -- | lint 与类型检查通过 |
