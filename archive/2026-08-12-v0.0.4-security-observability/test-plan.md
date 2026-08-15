# v0.4.0 测试方案与详细案例

> 版本：v0.4.0（Security & Observability）
> 创建日期：2026-08-12
> 对应 Phase 2 Spec（12 capabilities / 90 scenarios）：
> - `specs/authentication/spec.yaml`（5 REQ / 7 SC）
> - `specs/rate-limiting/spec.yaml`（5 REQ / 6 SC）
> - `specs/tls/spec.yaml`（3 REQ / 3 SC）
> - `specs/request-size-limit/spec.yaml`（3 REQ / 3 SC）
> - `specs/cors/spec.yaml`（3 REQ / 3 SC）
> - `specs/graceful-shutdown/spec.yaml`（3 REQ / 3 SC）
> - `specs/prometheus-metrics/spec.yaml`（5 REQ / 6 SC）
> - `specs/opentelemetry-tracing/spec.yaml`（4 REQ / 5 SC）
> - `specs/config-system/spec.yaml`（5 REQ / 5 SC）
> - `specs/fastapi-server/spec.yaml`（8 REQ / 18 SC）
> - `specs/sse-streaming/spec.yaml`（5 REQ / 15 SC）
> - `specs/audit-logger/spec.yaml`（6 REQ / 16 SC）

## 一、测试策略

### 1.1 测试金字塔

v0.4.0 以单元测试为主（认证中间件、TokenBucket 限流、配置子模型、审计修正、SSE 分片重组、指标注册表），辅以集成测试（中间件链顺序、认证/限流/请求大小在真实路由上的行为、流式审计修正、`/metrics` 端点）。安全类（认证/限流）与 SSE 修正/审计修正为 P0，优先保证。可观测性（Prometheus/OTel）与 TLS/优雅停机依赖 uvicorn 运行，主要以单元 + 轻量集成（mock uvicorn 调用 / subprocess 信号）覆盖。

### 1.2 测试原则

- 严格 TDD：RED（写失败测试）→ GREEN（最小实现）→ REFACTOR
- 安全中间件以 `create_app` 级集成测试验证链顺序与 fail-closed 行为，不以孤立单元替代
- 限流用可控时钟（monkeypatch `time.monotonic`）验证补桶与突发，不依赖真实 sleep
- OTel 采样与 span 结构通过注入 mock TracerProvider / 内存 exporter 验证，不触发真实导出
- TLS 通过 mock `uvicorn.run` 校验 `ssl_certfile/ssl_keyfile` 传递，失败路径断言明确报错
- 优雅停机通过 subprocess 发送 SIGTERM 或调用 shutdown hook 验证 in-flight 完成与审计 flush
- 所有新增配置字段测试向后兼容（v0.1.0~v0.3.0 配置无需修改即可加载）

### 1.3 已有测试资产

| 测试文件 | 用例数 | 类型 | 覆盖范围 |
|----------|--------|------|----------|
| tests/unit/middleware/test_request_id.py | 7 | 单元 | RequestID 生成/使用客户端值/丢弃非法/注入 state |
| tests/unit/middleware/test_safety_headers_v2.py | 5 | 单元 | SafetyHeaders action/risk_level 响应头 |
| tests/unit/test_app.py | 3 | 单元 | create_app 构造/异常/无副作用 |
| tests/integration/test_chat.py | 6 | 集成 | 非流式 chat 转发/模型/错误/超时 |
| tests/integration/test_streaming.py | 13 | 集成 | 流式 SSE/窗口 block/后审计/审计写入 |
| tests/unit/streaming/test_sse.py | 4 | 单元 | SSE 事件格式（chunk/DONE/safety_block/safety_flag） |
| tests/unit/audit/test_logger.py | 6 | 单元 | 审计写入/明文开关/失败/禁用 |
| tests/unit/audit/test_models.py | 5 | 单元 | 审计模型字段/哈希/流式字段 |
| tests/unit/config/test_v3_audit.py | 7 | 单元 | audit/logging 配置解析 |
| tests/unit/config/test_v3_streaming.py | 8 | 单元 | streaming/output_detection 配置 |
| tests/unit/config/test_v2_validators.py | 22 | 单元 | 检测器配置/阈值校验 |

> 说明：v0.4.0 的认证、限流、TLS、请求大小、CORS、优雅停机、Prometheus、OTel 均为新增能力，对应测试全部「测试缺」；SSE 修正与审计修正部分建立在 `tests/integration/test_streaming.py`、`tests/unit/streaming/test_sse.py`、`tests/unit/audit/*` 既有资产之上，需补充修正断言。

## 二、详细测试案例

TC-ID 规则：`TC-<CAPABILITY缩写>-<NNN>`，全局唯一。缩写：AUTH / RL / TLS / RSL / CORS / GS / PROM / OTEL / CFG / FSA / SSE / AUDIT。每个 spec scenario 至少映射 1 个 TC。

### 功能 1：API Key 认证（authentication）

#### 案例 1.1 — 合法 Bearer token 放行并注入 api_key_name

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUTH-001 |
| **对应 Spec** | authentication/spec.yaml → SC-AUTH-001 |
| **优先级** | P0 |
| **预置条件** | security.auth.enabled=true，api_keys=[{key:'sk-a', name:'app-a'}] |
| **输入** | GET/POST 业务端点，携带 Authorization: Bearer sk-a |
| **预期结果** | 请求放行到路由；request.state.api_key_name == 'app-a' |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.2 — 未知 token 拒绝返回 401

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUTH-002 |
| **对应 Spec** | authentication/spec.yaml → SC-AUTH-002 |
| **优先级** | P0 |
| **预置条件** | security.auth.enabled=true，api_keys=[{key:'sk-a', name:'app-a'}] |
| **输入** | 请求携带 Authorization: Bearer sk-unknown |
| **预期结果** | 返回 HTTP 401 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.3 — 认证默认关闭时不校验 token

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUTH-003 |
| **对应 Spec** | authentication/spec.yaml → SC-AUTH-003 |
| **优先级** | P0 |
| **预置条件** | security.auth.enabled 未设置或 false（默认关闭） |
| **输入** | 无 Authorization 头访问端点 |
| **预期结果** | 请求被放行（认证关闭不校验） |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.4 — 显式启用 fail-closed：无凭据拒绝

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUTH-004 |
| **对应 Spec** | authentication/spec.yaml → SC-AUTH-004 |
| **优先级** | P0 |
| **预置条件** | security.auth.enabled=true |
| **输入** | 无 Authorization 头访问端点 |
| **预期结果** | 返回 401（fail-closed） |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.5 — 未授权响应为 OpenAI 兼容错误体且不泄露 key

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUTH-005 |
| **对应 Spec** | authentication/spec.yaml → SC-AUTH-005 |
| **优先级** | P0 |
| **预置条件** | 认证启用且 token 无效或缺失 |
| **输入** | 触发未授权判定 |
| **预期结果** | 401 + error 对象（type/message）；响应不含任何配置 api_key 明文 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.6 — 放行时注入 api_key_name 供下游读取

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUTH-006 |
| **对应 Spec** | authentication/spec.yaml → SC-AUTH-006 |
| **优先级** | P0 |
| **预置条件** | 认证启用且 token 匹配 name='app-a' 的 key |
| **输入** | 请求进入后续路由/审计 |
| **预期结果** | request.state.api_key_name == 'app-a'，审计可读取 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.7 — 中间件顺序：RequestID 之后、路由之前

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUTH-007 |
| **对应 Spec** | authentication/spec.yaml → SC-AUTH-007 |
| **优先级** | P0 |
| **预置条件** | 认证启用，请求到达网关 |
| **输入** | 请求经过中间件链 |
| **预期结果** | Auth 在 RequestID 之后、路由分发之前；所有业务端点均受保护 |
| **当前状态** | ❌ 测试缺 |

### 功能 2：限流（rate-limiting）

#### 案例 2.1 — 桶内仍有令牌时放行并消耗一个

| 字段 | 内容 |
|------|------|
| **ID** | TC-RL-001 |
| **对应 Spec** | rate-limiting/spec.yaml → SC-RL-001 |
| **优先级** | P0 |
| **预置条件** | rate=10、burst=20、per=api_key，该 api_key 桶内仍有令牌 |
| **输入** | 该 api_key 发起的请求 |
| **预期结果** | 放行并消耗一个令牌 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.2 — 桶令牌耗尽返回 429

| 字段 | 内容 |
|------|------|
| **ID** | TC-RL-002 |
| **对应 Spec** | rate-limiting/spec.yaml → SC-RL-002 |
| **优先级** | P0 |
| **预置条件** | 某 api_key 桶令牌已耗尽（持续超速） |
| **输入** | 后续请求到达 |
| **预期结果** | 拒绝并返回 429 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.3 — 配置读取 rate/burst/per/storage

| 字段 | 内容 |
|------|------|
| **ID** | TC-RL-003 |
| **对应 Spec** | rate-limiting/spec.yaml → SC-RL-003 |
| **优先级** | P0 |
| **预置条件** | security.rate_limit={rate:10, burst:20, per:api_key, storage:memory} |
| **输入** | 加载配置并初始化限流器 |
| **预期结果** | 使用对应参数；per 支持 api_key/ip；storage 仅 memory |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.4 — 超限响应带 Retry-After + OpenAI 错误体

| 字段 | 内容 |
|------|------|
| **ID** | TC-RL-004 |
| **对应 Spec** | rate-limiting/spec.yaml → SC-RL-004 |
| **优先级** | P0 |
| **预置条件** | 请求被判定超限 |
| **输入** | 生成拒绝响应 |
| **预期结果** | 429 + Retry-After 头 + OpenAI 兼容错误体 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.5 — memory 存储原子性（并发不超耗）

| 字段 | 内容 |
|------|------|
| **ID** | TC-RL-005 |
| **对应 Spec** | rate-limiting/spec.yaml → SC-RL-005 |
| **优先级** | P0 |
| **预置条件** | 多请求并发命中同一 api_key 桶 |
| **输入** | 并发读写令牌桶 |
| **预期结果** | 令牌消耗原子（asyncio.Lock），无超额/负值 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.6 — per=ip 按 IP 维度限流

| 字段 | 内容 |
|------|------|
| **ID** | TC-RL-006 |
| **对应 Spec** | rate-limiting/spec.yaml → SC-RL-006 |
| **优先级** | P0 |
| **预置条件** | per=ip，某 IP 已超限 |
| **输入** | 该 IP 的后续请求 |
| **预期结果** | 按 IP 判定超限返回 429 |
| **当前状态** | ❌ 测试缺 |

### 功能 3：TLS（tls）

#### 案例 3.1 — TLS 默认关闭以 HTTP 启动

| 字段 | 内容 |
|------|------|
| **ID** | TC-TLS-001 |
| **对应 Spec** | tls/spec.yaml → SC-TLS-001 |
| **优先级** | P1 |
| **预置条件** | 未设置 security.tls.enabled（或 enabled:false） |
| **输入** | 通过 __main__.py 启动（uvicorn.run） |
| **预期结果** | uvicorn 参数不含 ssl_certfile/ssl_keyfile；HTTP 正常响应；无 TLS 报错 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.2 — 启用 TLS 传递证书并 HTTPS 受理

| 字段 | 内容 |
|------|------|
| **ID** | TC-TLS-002 |
| **对应 Spec** | tls/spec.yaml → SC-TLS-002 |
| **优先级** | P1 |
| **预置条件** | security.tls.enabled=true + 有效 cert_file/key_file |
| **输入** | 通过 uvicorn.run 启动 |
| **预期结果** | ssl_certfile/ssl_keyfile 被传递；https://host:port 请求被受理 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.3 — 证书缺失拒绝启动且报明确错误

| 字段 | 内容 |
|------|------|
| **ID** | TC-TLS-003 |
| **对应 Spec** | tls/spec.yaml → SC-TLS-003 |
| **优先级** | P1 |
| **预置条件** | enabled=true 但 cert_file/key_file 指向不存在文件 |
| **输入** | 通过 uvicorn.run 启动 |
| **预期结果** | 启动失败并报明确错误（含缺失文件路径）；NOT 静默降级 HTTP |
| **当前状态** | ❌ 测试缺 |

### 功能 4：请求大小限制（request-size-limit）

#### 案例 4.1 — 默认 10MB 且 Content-Length 超限返回 413

| 字段 | 内容 |
|------|------|
| **ID** | TC-RSL-001 |
| **对应 Spec** | request-size-limit/spec.yaml → SC-RSL-001 |
| **优先级** | P1 |
| **预置条件** | 未配置 max_request_size（默认 10MB） |
| **输入** | Content-Length > 10MB 的请求 |
| **预期结果** | 返回 413 + OpenAI 兼容错误体；不进入路由 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.2 — 分块传输读取阶段超限返回 413

| 字段 | 内容 |
|------|------|
| **ID** | TC-RSL-002 |
| **对应 Spec** | request-size-limit/spec.yaml → SC-RSL-002 |
| **优先级** | P1 |
| **预置条件** | max_request_size=10MB，Transfer-Encoding: chunked 无 Content-Length |
| **输入** | 读取 body 累计超过 max_request_size |
| **预期结果** | 中断返回 413；OpenAI 错误体；不继续读 body |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.3 — 限制内请求正常放行

| 字段 | 内容 |
|------|------|
| **ID** | TC-RSL-003 |
| **对应 Spec** | request-size-limit/spec.yaml → SC-RSL-003 |
| **优先级** | P1 |
| **预置条件** | 请求体在 max_request_size 内 |
| **输入** | 正常请求 |
| **预期结果** | 放行进入路由，无 413 |
| **当前状态** | ❌ 测试缺 |

### 功能 5：CORS（cors）

#### 案例 5.1 — CORS 默认关闭不注册中间件

| 字段 | 内容 |
|------|------|
| **ID** | TC-CORS-001 |
| **对应 Spec** | cors/spec.yaml → SC-CORS-001 |
| **优先级** | P1 |
| **预置条件** | 未设置 security.cors.enabled（或 false） |
| **输入** | create_app 构建应用 |
| **预期结果** | 不注册 CORSMiddleware，不返回 CORS 响应头 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.2 — 启用 CORS 按 origins 放行预检

| 字段 | 内容 |
|------|------|
| **ID** | TC-CORS-002 |
| **对应 Spec** | cors/spec.yaml → SC-CORS-002 |
| **优先级** | P1 |
| **预置条件** | enabled=true，origins 含 'https://app.example.com' |
| **输入** | 来自 app.example.com 的 OPTIONS 预检 |
| **预期结果** | 返回 Access-Control-Allow-Origin 等头；预检 200；非允许 origin 不放行 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.3 — CORS 不影响业务路由与安全链

| 字段 | 内容 |
|------|------|
| **ID** | TC-CORS-003 |
| **对应 Spec** | cors/spec.yaml → SC-CORS-003 |
| **优先级** | P1 |
| **预置条件** | 启用 CORS，网关运行正常 |
| **输入** | 同源业务请求 POST /v1/chat/completions |
| **预期结果** | 正常处理；认证/限流/请求大小仍按序生效 |
| **当前状态** | ❌ 测试缺 |

### 功能 6：优雅停机（graceful-shutdown）

#### 案例 6.1 — SIGTERM 等待 in-flight 完成并以 0 退出

| 字段 | 内容 |
|------|------|
| **ID** | TC-GS-001 |
| **对应 Spec** | graceful-shutdown/spec.yaml → SC-GS-001 |
| **优先级** | P1 |
| **预置条件** | 网关运行且有 in-flight 请求 |
| **输入** | 发送 SIGTERM |
| **预期结果** | 停止新连接，等待 in-flight 完成（≤stop_timeout），退出码 0 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.2 — stop_timeout 默认 30s 且超时强退

| 字段 | 内容 |
|------|------|
| **ID** | TC-GS-002 |
| **对应 Spec** | graceful-shutdown/spec.yaml → SC-GS-002 |
| **优先级** | P1 |
| **预置条件** | stop_timeout 未配置（默认 30s）或显式值，请求超时未完成 |
| **输入** | SIGTERM 后等待超过 stop_timeout |
| **预期结果** | 超时后强制退出，不再无限等待 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.3 — 停机冲刷审计日志并释放资源

| 字段 | 内容 |
|------|------|
| **ID** | TC-GS-003 |
| **对应 Spec** | graceful-shutdown/spec.yaml → SC-GS-003 |
| **优先级** | P1 |
| **预置条件** | SIGTERM 且 in-flight 已完成 |
| **输入** | 执行停机收尾 |
| **预期结果** | 审计日志 flush；资源释放；文档说明 stop_timeout < Docker stop_grace_period |
| **当前状态** | ❌ 测试缺 |

### 功能 7：Prometheus 指标（prometheus-metrics）

#### 案例 7.1 — /metrics 开启返回 Prometheus 文本格式

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROM-001 |
| **对应 Spec** | prometheus-metrics/spec.yaml → SC-PROM-001 |
| **优先级** | P1 |
| **预置条件** | observability.metrics.enabled=true，已注册 /metrics |
| **输入** | GET /metrics |
| **预期结果** | 200 + text/plain; version=0.0.4 文本格式，含全部注册指标系列 |
| **当前状态** | ❌ 测试缺 |

#### 案例 7.2 — /metrics 关闭返回 404

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROM-002 |
| **对应 Spec** | prometheus-metrics/spec.yaml → SC-PROM-002 |
| **优先级** | P1 |
| **预置条件** | observability.metrics.enabled=false（默认） |
| **输入** | GET /metrics |
| **预期结果** | 404；不初始化指标注册表 |
| **当前状态** | ❌ 测试缺 |

#### 案例 7.3 — Gateway 指标（requests/duration/blocks/flags/gauge）

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROM-003 |
| **对应 Spec** | prometheus-metrics/spec.yaml → SC-PROM-003 |
| **优先级** | P1 |
| **预置条件** | metrics.enabled=true，处理经检测请求（input，action=block） |
| **输入** | 请求处理 |
| **预期结果** | requests_total 递增（direction/action/model 标签）；duration 直方图；blocks_total/flags_total 递增；active_connections/streaming_active gauge 反映连接数 |
| **当前状态** | ❌ 测试缺 |

#### 案例 7.4 — Detector 指标（duration/results/errors/circuit state）

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROM-004 |
| **对应 Spec** | prometheus-metrics/spec.yaml → SC-PROM-004 |
| **优先级** | P1 |
| **预置条件** | metrics.enabled=true，pipeline 运行检测器（block 一次 + 异常一次） |
| **输入** | 检测器执行 |
| **预期结果** | duration 直方图、results_total、errors_total 递增；circuit_breaker_state gauge（0/1/2） |
| **当前状态** | ❌ 测试缺 |

#### 案例 7.5 — Provider 指标（requests/duration/errors）

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROM-005 |
| **对应 Spec** | prometheus-metrics/spec.yaml → SC-PROM-005 |
| **优先级** | P1 |
| **预置条件** | metrics.enabled=true，路由到 openai/gpt-4，调用一次 + 错误一次 |
| **输入** | 上游 provider 调用 |
| **预期结果** | requests_total/duration 直方图/errors_total 递增（provider/model 标签） |
| **当前状态** | ❌ 测试缺 |

#### 案例 7.6 — Recall 指标（recalls_total，不含原文）

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROM-006 |
| **对应 Spec** | prometheus-metrics/spec.yaml → SC-PROM-006 |
| **优先级** | P1 |
| **预置条件** | metrics.enabled=true，一次后审计触发召回（pii/high） |
| **输入** | PostAuditRunner 完成召回 |
| **预期结果** | recalls_total 递增（category/risk_level 标签）；不含敏感原文 |
| **当前状态** | ❌ 测试缺 |

### 功能 8：OpenTelemetry 追踪（opentelemetry-tracing）

#### 案例 8.1 — 默认关闭不初始化 TracerProvider

| 字段 | 内容 |
|------|------|
| **ID** | TC-OTEL-001 |
| **对应 Spec** | opentelemetry-tracing/spec.yaml → SC-OTEL-001 |
| **优先级** | P1 |
| **预置条件** | observability.tracing.enabled 未配置或 false |
| **输入** | 网关启动并处理请求 |
| **预期结果** | 不初始化 TracerProvider/导出；不产生 span |
| **当前状态** | ❌ 测试缺 |

#### 案例 8.2 — enabled=true 初始化 TracerProvider + OTLP exporter

| 字段 | 内容 |
|------|------|
| **ID** | TC-OTEL-002 |
| **对应 Spec** | opentelemetry-tracing/spec.yaml → SC-OTEL-002 |
| **优先级** | P1 |
| **预置条件** | enabled=true，exporter=otlp，endpoint=http://otel-collector:4317 |
| **输入** | 网关启动 |
| **预期结果** | 初始化全局 TracerProvider + OTLP exporter；FastAPI 自动 instrumentation 接入 |
| **当前状态** | ❌ 测试缺 |

#### 案例 8.3 — sample_rate 控制采样比例

| 字段 | 内容 |
|------|------|
| **ID** | TC-OTEL-003 |
| **对应 Spec** | opentelemetry-tracing/spec.yaml → SC-OTEL-003 |
| **优先级** | P1 |
| **预置条件** | sample_rate=0.1 |
| **输入** | 处理请求并决定是否创建追踪 |
| **预期结果** | 约 10% 采样；未采样不导出；默认 0.1 |
| **当前状态** | ❌ 测试缺 |

#### 案例 8.4 — 嵌套 span 树与属性

| 字段 | 内容 |
|------|------|
| **ID** | TC-OTEL-004 |
| **对应 Spec** | opentelemetry-tracing/spec.yaml → SC-OTEL-004 |
| **优先级** | P1 |
| **预置条件** | enabled=true，处理含检测与 provider 调用请求 |
| **输入** | 请求经过 gateway.request/auth/pipeline/detector/provider/audit 各阶段 |
| **预期结果** | gateway.request 为根的嵌套 span 树；detector/provider span 携带对应属性 |
| **当前状态** | ❌ 测试缺 |

#### 案例 8.5 — W3C TraceContext 延续与传播

| 字段 | 内容 |
|------|------|
| **ID** | TC-OTEL-005 |
| **对应 Spec** | opentelemetry-tracing/spec.yaml → SC-OTEL-005 |
| **优先级** | P2 |
| **预置条件** | 客户端携带 traceparent/tracestate |
| **输入** | 网关处理该请求 |
| **预期结果** | 延续客户端 context 为子 span 并响应传播 traceparent；无 context 时新建根 trace |
| **当前状态** | ❌ 测试缺 |

### 功能 9：配置系统（config-system）

#### 案例 9.1 — SecurityConfig 类型化子模型 + 时长解析 + 向后兼容

| 字段 | 内容 |
|------|------|
| **ID** | TC-CFG-001 |
| **对应 Spec** | config-system/spec.yaml → SC-CFG-001 |
| **优先级** | P0 |
| **预置条件** | 含 security.auth/tls/rate_limit/cors/request_id/max_request_size/timeout 配置 |
| **输入** | GatewayConfig 加载 |
| **预期结果** | 解析为类型化子模型；'120s'/'5s' 时长解析；新字段有默认值，旧配置可加载 |
| **当前状态** | ❌ 测试缺 |

#### 案例 9.2 — ServerConfig 补 workers 与 stop_timeout

| 字段 | 内容 |
|------|------|
| **ID** | TC-CFG-002 |
| **对应 Spec** | config-system/spec.yaml → SC-CFG-002 |
| **优先级** | P0 |
| **预置条件** | server 配置含 workers 与 stop_timeout |
| **输入** | GatewayConfig 加载 |
| **预期结果** | 解析 workers/stop_timeout；默认 workers=1、stop_timeout='30s' |
| **当前状态** | ❌ 测试缺 |

#### 案例 9.3 — ObservabilityConfig 嵌套 Metrics/Tracing 子模型

| 字段 | 内容 |
|------|------|
| **ID** | TC-CFG-003 |
| **对应 Spec** | config-system/spec.yaml → SC-CFG-003 |
| **优先级** | P0 |
| **预置条件** | observability 含 metrics 与 tracing 配置 |
| **输入** | GatewayConfig 加载 |
| **预期结果** | 解析为 MetricsConfig/TracingConfig；exporter 支持 otlp；sample_rate 默认 0.1；metrics.endpoint 默认 '/metrics' |
| **当前状态** | ❌ 测试缺 |

#### 案例 9.4 — count 与 confidence 阈值命名空间分离

| 字段 | 内容 |
|------|------|
| **ID** | TC-CFG-004 |
| **对应 Spec** | config-system/spec.yaml → SC-CFG-004 |
| **优先级** | P1 |
| **预置条件** | sensitive_words 配置含 count_block_threshold=3、count_flag_threshold=1 |
| **输入** | 配置校验运行 |
| **预期结果** | count（block>flag）与 confidence 阈值独立校验，互不混淆；旧 block/flag_threshold 仍可用 |
| **当前状态** | ❌ 测试缺 |

#### 案例 9.5 — PII 检测器命名统一 pii_redaction

| 字段 | 内容 |
|------|------|
| **ID** | TC-CFG-005 |
| **对应 Spec** | config-system/spec.yaml → SC-CFG-005 |
| **优先级** | P1 |
| **预置条件** | 配置引用 pii_redaction 检测器 |
| **输入** | PIIDetector.name 与注册表/校验器比对 |
| **预期结果** | PIIDetector.name == 'pii_redaction'；engine 按 name 命中配置 |
| **当前状态** | ❌ 测试缺 |

### 功能 10：FastAPI 服务器中间件与集成（fastapi-server）

#### 案例 10.1 — 安全中间件链顺序（RequestID→Auth→RateLimit→RequestSize→SafetyHeaders）

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-001 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-001 |
| **优先级** | P0 |
| **预置条件** | 安全配置已加载，auth/rate_limit/request_size 均启用 |
| **输入** | create_app(config_path) |
| **预期结果** | 注册中间件链外层→内层为 RequestID→Auth→RateLimit→RequestSize→SafetyHeaders |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.2 — request_id.header/generate 接线（合法头沿用）

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-002 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-002 |
| **优先级** | P0 |
| **预置条件** | security.request_id.header='X-Request-ID'，generate=true |
| **输入** | 客户端携带合法 X-Request-ID |
| **预期结果** | 沿用客户端值并注入响应头；非法/超长/含控制字符的丢弃并生成 UUID v4 |
| **当前状态** | ✅ 部分覆盖（tests/unit/middleware/test_request_id.py） |

#### 案例 10.3 — request_id.generate 生成 UUID v4 并存入 state

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-003 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-003 |
| **优先级** | P0 |
| **预置条件** | generate=true 且客户端未带 X-Request-ID |
| **输入** | 请求到达网关 |
| **预期结果** | 生成 UUID v4 注入响应头；存入 request.state.request_id |
| **当前状态** | ✅ 部分覆盖（tests/unit/middleware/test_request_id.py） |

#### 案例 10.4 — _extract_detector_configs 注入显式 timeout_seconds

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-004 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-004 |
| **优先级** | P1 |
| **预置条件** | 检测器显式 timeout='10s'，全局 security.timeout.detector='5s' |
| **输入** | _extract_detector_configs 处理该检测器 |
| **预期结果** | config 注入 timeout_seconds=10（显式优先） |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.5 — timeout 缺失回退全局默认

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-005 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-005 |
| **优先级** | P1 |
| **预置条件** | 检测器未配置 timeout，全局 '5s' |
| **输入** | _extract_detector_configs 处理 |
| **预期结果** | 注入 timeout_seconds=5 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.6 — 配置 circuit_breaker 时注入实例

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-006 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-006 |
| **优先级** | P1 |
| **预置条件** | 检测器配置 circuit_breaker（enabled/failure_threshold/recovery_timeout/fallback_action） |
| **输入** | _extract_detector_configs 处理 |
| **预期结果** | 注入 build_circuit_breaker 构建的实例；未配置则不注入 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.7 — build_circuit_breaker 解析 recovery_timeout

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-007 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-007 |
| **优先级** | P1 |
| **预置条件** | CircuitBreakerConfig recovery_timeout='30s' |
| **输入** | build_circuit_breaker(config) |
| **预期结果** | 解析为秒并返回配置化 CircuitBreaker；failure_threshold/fallback_action 传递 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.8 — 认证集成：合法 token 放行并注入 api_key_name

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-008 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-008 |
| **优先级** | P0 |
| **预置条件** | auth.enabled=true 且配置合法 key |
| **输入** | 请求携带 Authorization: Bearer <合法 key> |
| **预期结果** | 放行进入后续中间件与路由；request.state.api_key_name 注入 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.9 — 认证集成：无效 token 返回 401 OpenAI 错误体

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-009 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-009 |
| **优先级** | P0 |
| **预置条件** | auth.enabled=true |
| **输入** | 无/无效 Bearer token |
| **预期结果** | 401 + OpenAI 错误体（type: invalid_request_error） |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.10 — 认证集成：默认关闭放行

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-010 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-010 |
| **优先级** | P0 |
| **预置条件** | auth.enabled=false（默认） |
| **输入** | 任意请求 |
| **预期结果** | 放行，不校验 token |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.11 — 限流集成：超限 429 + Retry-After

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-011 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-011 |
| **优先级** | P0 |
| **预置条件** | rate_limit.enabled=true，rate/burst 已配置 |
| **输入** | 同一 key 超过 burst 连续请求 |
| **预期结果** | 429 + Retry-After；错误体 type: rate_limit_error, code: rate_limit_exceeded；per 维度隔离；storage 仅 memory |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.12 — 限流集成：未超限放行

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-012 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-012 |
| **优先级** | P0 |
| **预置条件** | rate_limit.enabled=true 且未超限 |
| **输入** | 请求到达网关 |
| **预期结果** | 放行进入路由 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.13 — 请求大小集成：超限 413

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-013 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-013 |
| **优先级** | P1 |
| **预置条件** | max_request_size=10MB（默认） |
| **输入** | Content-Length 超限（或分块读取超限） |
| **预期结果** | 413 + OpenAI 兼容错误体 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.14 — 请求大小集成：限制内放行

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-014 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-014 |
| **优先级** | P1 |
| **预置条件** | max_request_size=10MB |
| **输入** | Content-Length 在限制内 |
| **预期结果** | 放行进入后续处理 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.15 — CORS 集成：预检放行

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-015 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-015 |
| **优先级** | P1 |
| **预置条件** | cors.enabled=true，origins 已配置 |
| **输入** | 浏览器跨域 OPTIONS 预检 |
| **预期结果** | 通过 CORSMiddleware 返回允许的 CORS 响应头 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.16 — CORS 集成：默认关闭不注册

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-016 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-016 |
| **优先级** | P1 |
| **预置条件** | cors.enabled=false（默认） |
| **输入** | create_app 构建应用 |
| **预期结果** | 不注册 CORSMiddleware，不添加 CORS 响应头 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.17 — TLS 集成：原生终止接线

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-017 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-017 |
| **优先级** | P1 |
| **预置条件** | tls.enabled=true 且 cert_file/key_file 已配置 |
| **输入** | uvicorn.run(ssl_certfile=..., ssl_keyfile=...) 启动 |
| **预期结果** | 原生 TLS 终止接受 HTTPS 请求 |
| **当前状态** | ❌ 测试缺 |

#### 案例 10.18 — 优雅停机集成：SIGTERM 等待 + flush + 退出码 0

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-018 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-018 |
| **优先级** | P1 |
| **预置条件** | server.stop_timeout=30s（默认） |
| **输入** | 进程收到 SIGTERM |
| **预期结果** | 等待 in-flight 完成（≤stop_timeout）；flush 审计日志；退出码 0；stop_timeout < Docker stop_grace_period |
| **当前状态** | ❌ 测试缺 |

### 功能 11：流式 SSE 分片重组与审计字段修正（sse-streaming）

#### 案例 11.1 — SSEBuffer 跨 chunk 重组完整事件

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-001 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-001 |
| **优先级** | P0 |
| **预置条件** | provider 按网络分片 yield，单个 `data:{json}\n\n` 拆散到两个 chunk |
| **输入** | SSEBuffer 接收第一段后补齐第二段 `\n\n` |
| **预期结果** | 在 `\n\n` 边界重组完整事件并解析 delta；字节不丢不重；delta 进入窗口检测 |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.2 — 单 chunk 多事件按序产出

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-002 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-002 |
| **优先级** | P0 |
| **预置条件** | 单 chunk 含多个 `\n\n` 分隔的完整事件 |
| **输入** | SSEBuffer 处理该 chunk |
| **预期结果** | 一次性产出全部完整事件，按原始顺序交付；以 `\n\n` 为界 |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.3 — 结束 flush 残留内容避免漏检

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-003 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-003 |
| **优先级** | P0 |
| **预置条件** | 流接近结束，缓冲区残留未以 `\n\n` 结尾的不完整事件 |
| **输入** | stream_forward 迭代完毕进入结束处理 |
| **预期结果** | 结束 flush 残留并解析；完整 JSON 负载仍检测透传；`[DONE]` 透传不抛异常 |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.4 — 非 data 事件跨 chunk 原样透传

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-004 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-004 |
| **优先级** | P0 |
| **预置条件** | 流出现 `event: safety_block`、`data: [DONE]`，被拆分或混在 chunk |
| **输入** | SSEBuffer 处理 |
| **预期结果** | 按 `\n\n` 切分并原样透传非 data 事件，不改类型/负载 |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.5 — 输出侧 output_action/output_risk_level 独立维护与聚合

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-005 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-005 |
| **优先级** | P0 |
| **预置条件** | 滑动窗口模式，逐个窗口输出检测 |
| **输入** | 每个窗口产生 PipelineResult |
| **预期结果** | 独立维护 output_action（allow<flag<modify<block 升序聚合）与 output_risk_level（最高风险） |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.6 — 窗口 block 置 output_action=block 并停止透传

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-006 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-006 |
| **优先级** | P0 |
| **预置条件** | 某窗口 final_action==block |
| **输入** | handler 发出 safety_block 并停止透传 |
| **预期结果** | output_action=block，risk_level 取阻断窗口；审计记录 final_action=block 及 blocked_by/category/confidence/reason |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.7 — 流式审计使用输出侧而非输入侧 action

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-007 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-007 |
| **优先级** | P0 |
| **预置条件** | 输入侧 safety_action 与输出侧结果不同 |
| **输入** | 构建流式输出审计条目 |
| **预期结果** | 审计用输出侧 output_action/output_risk_level；输出阻断而输入 allow 时记录 block |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.8 — 后审计 detector_results 写入审计（不再恒空）

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-008 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-008 |
| **优先级** | P0 |
| **预置条件** | PostAuditRunner.run() 深检产生 detector_results |
| **输入** | 写入流式输出审计条目 |
| **预期结果** | detectors 数组含完整检测器结果；post_audit 保留 effective_action/original_action/risk_level |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.9 — window_count 以实际窗口数填充

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-009 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-009 |
| **优先级** | P0 |
| **预置条件** | 滑动窗口模式，逐窗口检测 |
| **输入** | 消费并检测完整窗口 |
| **预期结果** | window_count == 实际检测窗口数；仅对 streaming=True 有效 |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.10 — PostAuditRunner 透传 request_id

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-010 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-010 |
| **优先级** | P0 |
| **预置条件** | 后置审计触发，请求持有非空 request_id |
| **输入** | PostAuditRunner.run(content, request_id=..., language=...) |
| **预期结果** | 接收并透传 request_id；DetectionContext.request_id == 当前请求 id |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.11 — 复用输入侧 language（不重测）

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-011 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-011 |
| **优先级** | P0 |
| **预置条件** | 输入侧已检测 language |
| **输入** | handler 为滑动窗口与后置审计构建 DetectionContext |
| **预期结果** | 写入输入侧 language，不重新检测 |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.12 — 流式审计 language 取输入侧

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-012 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-012 |
| **优先级** | P1 |
| **预置条件** | 流式输出审计条目构建时有输入侧 language |
| **输入** | 写入 AuditEntry |
| **预期结果** | language 用输入侧；未检测时保持 None 不产生伪值 |
| **当前状态** | ❌ 测试缺 |

#### 案例 11.13 — 无输出检测器时透明透传（无回归）

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-013 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-013 |
| **优先级** | P0 |
| **预置条件** | has_detection=False |
| **输入** | 发起流式请求 |
| **预期结果** | 逐 chunk 转发 + `[DONE]`；不执行重组/窗口/后审计，与修正前一致 |
| **当前状态** | ✅ 部分覆盖（tests/integration/test_streaming.py） |

#### 案例 11.14 — buffer 模式行为保持（无回归）

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-014 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-014 |
| **优先级** | P1 |
| **预置条件** | streaming.mode=buffer 且配置输出检测器 |
| **输入** | 缓冲模式全量检测并回放 |
| **预期结果** | 保持既有行为（block 或回放 + [DONE]）；window_count/SSEBuffer 重组仅作用于滑动窗口 |
| **当前状态** | ✅ 部分覆盖（tests/integration/test_streaming.py buffer 用例） |

#### 案例 11.15 — 流式 Provider 错误路径（无回归）

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-015 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-SSE-015 |
| **优先级** | P1 |
| **预置条件** | provider 流中抛 ProviderError |
| **输入** | 滑动窗口捕获异常并发出 error + [DONE] |
| **预期结果** | 输出 error + [DONE]；审计 final_action/risk_level 反映实际；detector_results/window_count 缺失时为空/None 不伪造 |
| **当前状态** | ✅ 部分覆盖（tests/integration/test_streaming.py provider error 用例） |

### 功能 12：审计日志修正（audit-logger）

#### 案例 12.1 — input 条目 total_duration_ms 实测赋值

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-001 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-001 |
| **优先级** | P0 |
| **预置条件** | 非流式 chat 请求，审计启用，走输入 pipeline 并转发 provider |
| **输入** | 构建 input 审计条目 |
| **预期结果** | total_duration_ms 为实测耗时（≥0），非占位 0 |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.2 — output 条目 total_duration_ms 实测赋值

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-002 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-002 |
| **优先级** | P0 |
| **预置条件** | 非流式 chat 请求，输出 pipeline 完成并返回响应 |
| **输入** | 构建 output 审计条目 |
| **预期结果** | total_duration_ms 为响应处理耗时，排除 provider 延迟 |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.3 — JSONL 中 total_duration_ms 不再恒 0

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-003 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-003 |
| **优先级** | P0 |
| **预置条件** | 审计条目序列化为 JSONL |
| **输入** | 输出 audit.log 的 total_duration_ms 字段 |
| **预期结果** | total_duration_ms 已正确赋值（非 0） |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.4 — user_id 取自请求体 user 字段

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-004 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-004 |
| **优先级** | P0 |
| **预置条件** | chat 请求体含顶层 'user'='user_001' |
| **输入** | 构建 input/output 审计条目 |
| **预期结果** | user_id == 'user_001' |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.5 — 无 user 字段时 user_id 为 null

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-005 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-005 |
| **优先级** | P0 |
| **预置条件** | chat 请求体无顶层 'user' |
| **输入** | 构建审计条目 |
| **预期结果** | user_id == null（不伪造） |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.6 — DetectorAuditRecord.duration_ms 取实测值

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-006 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-006 |
| **优先级** | P0 |
| **预置条件** | 检测器成功执行并返回含 duration_ms 的 DetectionResult |
| **输入** | _build_audit_entry 写入 detectors 数组 |
| **预期结果** | duration_ms 取实测值，非默认 0.0 |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.7 — DetectorAuditRecord.error 取异常信息

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-007 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-007 |
| **优先级** | P0 |
| **预置条件** | 检测器异常并返回带 error 的 DetectionResult |
| **输入** | _build_audit_entry 写入 detectors 数组 |
| **预期结果** | error 取异常信息（非 null）；成功时为 null |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.8 — post_audit 字典统一 schema（result/category/risk_level）

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-008 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-008 |
| **优先级** | P0 |
| **预置条件** | 流式滑动窗口，post-audit 已执行 |
| **输入** | 构建 output 审计 post_audit 字典 |
| **预期结果** | {'executed':true,'result':effective_action,'category':...,'risk_level':...} |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.9 — post_audit 不再使用 effective_action/original_action 键名

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-009 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-009 |
| **优先级** | P0 |
| **预置条件** | 流式 post-audit 执行后构建字典 |
| **输入** | 检查 post_audit 键名 |
| **预期结果** | 统一用 result，不再用 effective_action/original_action |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.10 — post-audit 跳过时 post_audit={'executed':false}

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-010 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-010 |
| **优先级** | P0 |
| **预置条件** | buffer 模式或 post_audit=false |
| **输入** | 构建 output 审计 post_audit 字典 |
| **预期结果** | {'executed':false}（不含 result/category/risk_level） |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.11 — DetectorAuditRecord 新增可选 applied 字段

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-011 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-011 |
| **优先级** | P0 |
| **预置条件** | audit/models.py 的 DetectorAuditRecord |
| **输入** | 定义审计记录字段 |
| **预期结果** | 新增可选 applied（bool，默认缺省/None），向后兼容既有序列化 |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.12 — 流式 modify 降级为 flag 且 applied=false

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-012 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-012 |
| **优先级** | P0 |
| **预置条件** | 流式 post-audit 某检测器 action='modify'（响应已发出无法应用） |
| **输入** | 构建 DetectorAuditRecord |
| **预期结果** | 记录 action='flag' 且 applied=false |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.13 — 同步 modify 已应用记录 applied=true

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-013 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-013 |
| **优先级** | P0 |
| **预置条件** | 输入侧/非流式同步 modify 已写回 |
| **输入** | 构建 DetectorAuditRecord |
| **预期结果** | action='modify' 且 applied=true（或省略 applied） |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.14 — 同步输出检测加 asyncio.wait_for(sync_timeout)

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-014 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-014 |
| **优先级** | P0 |
| **预置条件** | 非流式同步输出检测，检测器已配置且 engine 可用 |
| **输入** | engine.run(output_detectors, [context], configs) |
| **预期结果** | 调用被 asyncio.wait_for(..., timeout=sync_timeout) 包裹；超时停止等待 |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.15 — sync_timeout 超时按 on_error 策略处理

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-015 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-015 |
| **优先级** | P0 |
| **预置条件** | asyncio.wait_for 触发 TimeoutError |
| **输入** | 处理输出检测超时 |
| **预期结果** | 未完成检测器按 on_error（fail_open 跳过 / fail_closed 视为 block）；已完成结果正常聚合 |
| **当前状态** | ❌ 测试缺 |

#### 案例 12.16 — sync_timeout 默认 5s

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUDIT-016 |
| **对应 Spec** | audit-logger/spec.yaml → SC-AUDIT-016 |
| **优先级** | P1 |
| **预置条件** | sync_timeout 未显式配置 |
| **输入** | 计算同步输出检测 pipeline 级超时 |
| **预期结果** | sync_timeout 使用默认 5s |
| **当前状态** | ❌ 测试缺 |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 集成测试 | E2E | 状态 |
|----------|---------|----------|-----|------|
| API Key 认证 | ✅ | ✅ | ❌ | 🟡 |
| 内存 Token Bucket 限流 | ✅ | ✅ | ❌ | 🟡 |
| TLS 原生终止 | ✅ | ❌ | ❌ | 🟡 |
| 请求大小限制 | ✅ | ✅ | ❌ | 🟡 |
| CORS | ✅ | ✅ | ❌ | 🟡 |
| 优雅停机 | ✅ | ❌ | ❌ | 🟡 |
| Prometheus 指标 | ✅ | ✅ | ❌ | 🟡 |
| OpenTelemetry 追踪 | ✅ | ❌ | ❌ | 🟡 |
| 配置系统子模型 | ✅ | ❌ | ❌ | 🟢 |
| FastAPI 中间件链集成 | ✅ | ✅ | ❌ | 🟡 |
| SSE 分片重组修正 | ✅ | ✅ | ❌ | 🟡 |
| 流式/审计字段修正 | ✅ | ✅ | ❌ | 🟡 |

> 说明：所有功能模块测试均为新增（❌ 测试缺）或基于既有资产补充断言；状态以「待补充」为主，配置系统因有 v2/v3 配置测试资产基线为 🟢。

## 四、回归风险矩阵

| 风险区域 | v0.4.0 改动 | 已有回归保护 | 风险等级 |
|----------|-------------|-------------|---------|
| app.py / create_app | 注册安全中间件链（Auth/RateLimit/RequestSize/CORS） | tests/unit/test_app.py、tests/integration/test_chat.py | 🔴 |
| config/models.py | SecurityConfig/ObservabilityConfig/ServerConfig 重构 | config v2/v3 测试 | 🟡 |
| config/validators.py | 阈值命名空间分离、pii_redaction 改名 | test_v2_validators.py | 🟡 |
| routes/chat.py | 认证/限流/请求大小接入 + 审计 total_duration/user_id 修正 | test_chat.py、test_streaming.py | 🔴 |
| streaming/handler.py | SSE 分片重组、输出侧审计字段、window_count | test_streaming.py、test_sse.py | 🔴 |
| streaming/sse.py | SSEBuffer 重组 | test_sse.py | 🟡 |
| audit/models.py | DetectorAuditRecord.applied、post_audit schema | test_models.py | 🟡 |
| audit/logger.py | total_duration_ms 赋值（无 schema 破坏） | test_logger.py | 🟢 |
| providers/base.py | provider 指标埋点 | test_openai.py、test_stream_forward.py | 🟢 |
| circuit_breaker | build_circuit_breaker 工厂、timeout 注入 | test_breaker.py | 🟡 |
| pipeline/engine.py | 复用（无改动） | 现有 pipeline 测试 | 🟢 |

## 五、建议补充顺序

1. **第一优先**（部署前必补，P0）：
   - 认证：TC-AUTH-001~007、TC-FSA-008/009/010
   - 限流：TC-RL-001~006、TC-FSA-011/012
   - 中间件链：TC-FSA-001
   - SSE 修正：TC-SSE-001~011、TC-SSE-013
   - 审计修正：TC-AUDIT-001~015
   - 配置接线：TC-CFG-001/002/003
2. **第二优先**（部署后尽快补，P1）：
   - TLS：TC-TLS-001~003、TC-FSA-017
   - 请求大小：TC-RSL-001~003、TC-FSA-013/014
   - CORS：TC-CORS-001~003、TC-FSA-015/016
   - 优雅停机：TC-GS-001~003、TC-FSA-018
   - Prometheus：TC-PROM-001~006
   - OTel：TC-OTEL-001~004
   - 检测器配置注入：TC-FSA-004~007
   - 配置：TC-CFG-004/005、TC-AUDIT-016、TC-SSE-012/014/015
3. **第三优先**（后续补，P2）：
   - TC-OTEL-005（W3C TraceContext 传播）
