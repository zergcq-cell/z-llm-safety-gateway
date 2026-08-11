# Capability: request-id

> 请求 ID 生成（UUID v4）或从客户端 X-Request-ID 头传播，所有响应注入 X-Request-ID 和 X-Safety-Action: allow

## ADDED Requirements

### Requirement: REQ-001 - Generate UUID v4 When Absent

如果请求中不存在 X-Request-ID 头，网关 SHALL 生成 UUID v4 作为请求 ID。

#### Scenario: SC-001 - 请求未携带 X-Request-ID 时生成 UUID v4

- **GIVEN** 客户端发送的请求未携带 X-Request-ID 头
- **WHEN** RequestID 中间件处理该请求
- **THEN** 网关 SHALL 生成 UUID v4 作为请求 ID
- **AND** 生成的 UUID v4 SHALL 符合 36 字符格式 xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx

---

### Requirement: REQ-002 - Use Client-Provided ID When Valid

如果请求中存在合法的 X-Request-ID 头，网关 SHALL 使用客户端提供的值。

#### Scenario: SC-002 - 客户端提供合法 ID 时传播客户端值

- **GIVEN** 客户端发送的请求携带 X-Request-ID 头
- **AND** 头值匹配正则 ^[a-zA-Z0-9_-]{1,128}$
- **WHEN** RequestID 中间件处理该请求
- **THEN** 网关 SHALL 使用客户端提供的 X-Request-ID 值作为请求 ID
- **AND** 网关 SHALL NOT 重新生成 UUID v4

---

### Requirement: REQ-003 - Sanitize Invalid Client-Provided IDs

客户端提供的 ID 经过消毒：必须匹配 ^[a-zA-Z0-9_-]{1,128}$，不合法的 ID 被丢弃并重新生成 UUID v4。

#### Scenario: SC-003 - 非法 ID 被丢弃并重新生成 UUID v4

- **GIVEN** 客户端发送的请求携带 X-Request-ID 头
- **AND** 头值不匹配正则 ^[a-zA-Z0-9_-]{1,128}$（如包含特殊字符、超过 128 字符）
- **WHEN** RequestID 中间件处理该请求
- **THEN** 网关 SHALL 丢弃客户端提供的无效 ID
- **AND** 网关 SHALL 生成新的 UUID v4 作为请求 ID
- **AND** 此行为 SHALL 防止 log injection（换行/控制字符破坏 JSONL）
- **AND** 此行为 SHALL 防止 header injection

#### Scenario: SC-004 - 空 ID 被丢弃并重新生成 UUID v4

- **GIVEN** 客户端发送的请求携带 X-Request-ID 头
- **AND** 头值为空字符串
- **WHEN** RequestID 中间件处理该请求
- **THEN** 网关 SHALL 丢弃空 ID 并生成新的 UUID v4

---

### Requirement: REQ-004 - Response Includes X-Request-ID

所有响应 SHALL 包含 X-Request-ID 头，值为该请求的请求 ID。

#### Scenario: SC-005 - 生成 ID 时响应包含 X-Request-ID

- **GIVEN** 客户端发送请求（未携带 X-Request-ID 头）
- **WHEN** 服务器处理请求并返回响应
- **THEN** 响应 SHALL 包含 X-Request-ID 头
- **AND** X-Request-ID 头值 SHALL 为网关生成的 UUID v4

#### Scenario: SC-006 - 传播 ID 时响应包含 X-Request-ID

- **GIVEN** 客户端发送请求（携带合法的 X-Request-ID: my-req-123）
- **WHEN** 服务器处理请求并返回响应
- **THEN** 响应 SHALL 包含 X-Request-ID 头
- **AND** X-Request-ID 头值 SHALL 为 my-req-123（客户端提供的值）

---

### Requirement: REQ-005 - Response Includes X-Safety-Action: allow

所有响应 SHALL 包含 X-Safety-Action 头，值为 "allow"（Phase 1 无检测，始终为 allow）。

#### Scenario: SC-007 - Phase 1 所有响应包含 X-Safety-Action: allow

- **GIVEN** Phase 1 环境下服务器已启动
- **WHEN** 客户端发送任意请求
- **THEN** 响应 SHALL 包含 X-Safety-Action 头
- **AND** X-Safety-Action 头值 SHALL 为 "allow"
- **AND** Phase 1 中 SHALL NOT 执行任何安全检测

---

### Requirement: REQ-006 - No X-Safety-Risk-Level When Allow

当 action 为 "allow" 时，响应 SHALL NOT 包含 X-Safety-Risk-Level 头。

#### Scenario: SC-008 - allow 时不包含 X-Safety-Risk-Level

- **GIVEN** Phase 1 环境下服务器已启动
- **AND** 响应的 X-Safety-Action 为 "allow"
- **WHEN** 服务器返回响应
- **THEN** 响应 SHALL NOT 包含 X-Safety-Risk-Level 头

---

### Requirement: REQ-007 - Request ID Stored in request.state

请求 ID 存储在 request.state.request_id 供下游使用。

#### Scenario: SC-009 - request.state.request_id 包含请求 ID

- **GIVEN** RequestID 中间件已处理请求并确定请求 ID
- **WHEN** 路由处理函数或下游中间件访问 request.state
- **THEN** request.state.request_id SHALL 包含该请求的请求 ID 值
- **AND** request.state.request_id SHALL 为字符串类型
- **AND** 下游组件 SHALL 能通过 request.state.request_id 获取请求 ID 用于日志和追踪

---

### Requirement: REQ-008 - UUID v4 Format

UUID v4 格式：36 字符，格式为 xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx。

#### Scenario: SC-010 - 生成的 UUID v4 符合标准格式

- **GIVEN** 客户端请求未携带 X-Request-ID 头
- **WHEN** 网关生成请求 ID
- **THEN** 生成的 ID SHALL 为 UUID v4 格式
- **AND** ID SHALL 为 36 字符长度
- **AND** ID SHALL 匹配正则 ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$
- **AND** ID 第 14 位 SHALL 为 '4'（表示 UUID 版本 4）
- **AND** ID 第 19 位 SHALL 为 '8'、'9'、'a' 或 'b'（RFC 4122 变体）
