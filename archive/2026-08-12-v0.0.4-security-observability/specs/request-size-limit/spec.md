# request-size-limit — 行为规格（Human View）

> **变更**: 2026-08-12-v0.4.0-security-observability
> **Capability**: request-size-limit
> **创建时间**: 2026-08-12T16:00:00+08:00
> **置信度**: high

## 描述

提供**请求大小限制**能力。通过 `security.max_request_size`（默认 10MB）配置，在认证中间件链中新增 `RequestSizeMiddleware`：当存在 `Content-Length` 头时校验之；对分块传输（无该头）在读取 body 阶段限制。超限返回 **HTTP 413** + OpenAI 兼容错误体，防止超大请求耗尽内存。

> 设计依据：design Decision 4；DESIGN 11.4。

---

## Requirements

### REQ-RSL-001：max_request_size 默认 10MB，Content-Length 超限返回 413

**描述**：`security.max_request_size` 默认 10MB，`Content-Length` 超限时返回 413 + OpenAI 兼容错误体。

**置信度**: high

#### SC-RSL-001：Content-Length 超限返回 413

- **Given**: 未显式配置 `security.max_request_size`（使用默认 10MB）
- **When**: `RequestSizeMiddleware` 收到 `Content-Length` 大于 10MB 的请求
- **Then**: 该请求 **SHALL** 被拒绝并返回 HTTP 413
- **And**:
  - 错误响应体 **SHALL** 为 OpenAI 兼容错误（`error.type` / `error.message`）
  - 被拒的超限请求体 **SHALL** 不会进入后续路由处理

---

### REQ-RSL-002：分块传输在读取 body 阶段限制，超限返回 413

**描述**：对无 `Content-Length` 的分块传输，在读取 body 时累计限制，超限返回 413。

**置信度**: high

#### SC-RSL-002：分块传输读取 body 超限返回 413

- **Given**: `security.max_request_size` 设为 10MB，且请求为分块传输（`Transfer-Encoding: chunked`，无 `Content-Length`）
- **When**: `RequestSizeMiddleware` 读取 body 的过程中累计字节数超过 `max_request_size`
- **Then**: 请求 **SHALL** 被中断并返回 HTTP 413
- **And**:
  - 响应体 **SHALL** 为 OpenAI 兼容错误
  - 超限后 **SHALL NOT** 继续读取完整请求体以避免内存耗尽

---

### REQ-RSL-003：未超限请求正常放行

**描述**：请求体大小在限制内的请求正常进入后续处理。

**置信度**: high

#### SC-RSL-003：未超限请求放行

- **Given**: 一份请求体大小不超过 `security.max_request_size` 的合法请求
- **When**: `RequestSizeMiddleware` 校验该请求
- **Then**: 该请求 **SHALL** 被放行并进入后续路由处理
- **And**:
  - 响应 **SHALL** 正常返回，不出现 413 错误

---

## 验证检查点

| CP | Scenario | 描述 |
|----|----------|------|
| CP-1 | SC-RSL-001 | Content-Length 超限返回 413 |
| CP-2 | SC-RSL-002 | 分块传输读取 body 超限返回 413 |
| CP-3 | SC-RSL-003 | 未超限请求正常放行 |
| CP-4 | -- | request-size-limit 完整测试套件通过 |
| CP-5 | -- | lint 与类型检查通过 |
