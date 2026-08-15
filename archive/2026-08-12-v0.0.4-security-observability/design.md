# v0.4.0 Security & Observability — 技术设计

## Context

v0.1.0~v0.3.0 已完成框架、Pipeline 检测器、流式与审计。当前系统存在两类缺口：
1. **安全防护缺失**：无认证/限流/TLS/请求大小限制/CORS/优雅停机。
2. **可观测性缺失**：无 Prometheus 指标/OpenTelemetry 追踪，`/metrics` 为占位。

同时，对前三个版本的功能 Review（见 `backlog.md`）确认了 P0/P1 遗留缺陷：阈值命名空间冲突（B-01）、PII 命名不一致（B-02）、流式 SSE 分片漏检（B-03）、per-detector timeout/circuit_breaker 未传递（B-04）、流式审计字段失真（B-05~B-09）。

**技术栈**：Python 3.10+ / FastAPI / Pydantic v2 / httpx / structlog / pytest + pytest-asyncio / ruff / mypy (strict)
**依赖**：新增 Prometheus client (`prometheus-client`)；OTel 可选；认证/限流用纯 Python + 内存实现（无外部依赖）。

## Decisions

### 1. API Key 认证：依赖注入中间件（Fail-Closed）
**方案**：新建 `middleware/auth.py::AuthMiddleware(BaseHTTPMiddleware)`。从 `security.auth.api_keys` 配置（key/name 列表）读取合法 Bearer token。请求头 `Authorization: Bearer <key>` 匹配任一配置 key 则放行并注入 `request.state.api_key_name`；否则返回 401（OpenAI 兼容错误体）。
**为什么**：认证默认关闭（`enabled: false`），显式启用为 fail-closed，避免配置错误导致未授权访问。中间件顺序在 RequestID 之后、路由之前，确保所有业务端点均被保护。
**备选方案及排除原因**：
- 备选 A：FastAPI 依赖项（`Depends`）— 需逐端点注入，易漏；中间件统一保护更稳妥。
- 备选 B：`httpx`/反向代理层认证 — 增加部署复杂度；网关内建更通用。

### 2. 限流：内存 Token Bucket（429 + Retry-After）
**方案**：新建 `ratelimit/` 模块。`TokenBucket` 维护 per-key（`per: api_key`）或 per-IP（`per: ip`）桶，`rate`（每秒补充）与 `burst`（桶容量）。超限返回 429 + `Retry-After` 头 + OpenAI 兼容错误体。`storage: memory`（MVP），线程/事件循环安全（asyncio.Lock 或简单原子）。
**为什么**：DESIGN 11.3/34 明确 MVP 用内存存储，Redis 留待 v1.1+。token_bucket 支持突发（burst）更符合 LLM API 调用模式。
**备选方案及排除原因**：
- 备选 A：fixed window — 边界突刺问题，burst 不自然。
- 备选 B：Redis — v1.1+（多实例），增加运维依赖。

### 3. TLS：原生终止（可选，默认关闭）
**方案**：`security.tls.enabled/cert_file/key_file` 配置。`__main__.py` 中 `uvicorn.run(..., ssl_certfile=..., ssl_keyfile=...)`。
**为什么**：DESIGN 11.2/13.2。生产建议反向代理（如 Nginx/ALB）承担 TLS，但原生支持满足直接暴露场景。
**备选方案及排除原因**：
- 备选 A：仅依赖反向代理 — 失去直接部署能力。
- 备选 B：`TrustedHostMiddleware` — 与 TLS 无关，不解决传输加密。

### 4. 请求大小限制：内容长度校验（413）
**方案**：`security.max_request_size`（默认 10MB）。在认证中间件链中新增 `RequestSizeMiddleware`，校验 `Content-Length` 头（存在时）；对分块传输在读取 body 时限制。超限返回 413 + OpenAI 兼容错误体。
**为什么**：DESIGN 11.4。防止超大请求耗尽内存。
**备选方案及排除原因**：
- 备选 A：仅靠 `Content-Length` — 分块传输无该头，需兜底读取限制。

### 5. CORS：`starlette` CORSMiddleware
**方案**：`security.cors.enabled/origins` 配置。启用时在 `create_app` 接入 `starlette.middleware.cors.CORSMiddleware`。
**为什么**：DESIGN 11.6。浏览器直连网关场景必需，默认关闭。
**备选方案及排除原因**：无（标准做法）。

### 6. 优雅停机：SIGTERM + stop_timeout
**方案**：`server.stop_timeout`（默认 30s）配置。`__main__.py` 使用 `uvicorn.run`（`graceful_shutdown` 由 uvicorn 处理），并注册 SIGTERM handler。文档明确 `stop_timeout < Docker stop_grace_period`。
**为什么**：DESIGN 13.4/37。确保 in-flight 请求完成、审计日志 flush。
**备选方案及排除原因**：uvicorn 内建 graceful shutdown，无需自研。

### 7. Prometheus 指标：prometheus-client + /metrics
**方案**：新增依赖 `prometheus-client`。新建 `observability/metrics.py`，定义指标注册表与计数器：请求总数/按 action/按端点、检测器调用次数/耗时/失败、provider 调用/错误、recall 计数。`/metrics` 端点由 `observability.metrics.enabled` 控制，接入 `prometheus_client.generate_latest()`。
**为什么**：DESIGN 12.5 定义 15+ 指标，`/metrics` 是 Prometheus 抓取标准接口。
**备选方案及排除原因**：自研计数器 — prometheus-client 成熟且零运维。

### 8. OpenTelemetry 追踪：可选集成（默认关闭）
**方案**：`observability.tracing.enabled/exporter/sample_rate` 配置。启用时通过 `opentelemetry-api/sdk` + `opentelemetry-instrumentation-fastapi` 自动埋点。为控制依赖，MVP 支持 `exporter: otlp`，可扩展 jaeger/zipkin。
**为什么**：DESIGN 12.6。可选集成避免为默认用户引入重依赖。
**备选方案及排除原因**：手动埋点 — 工作量大；自动 instrumentation 更标准。

### 9. SecurityConfig 重构：类型化子模型
**方案**：`SecurityConfig` 拆分为 `AuthConfig`/`TLSConfig`/`RateLimitConfig`/`CORSConfig`/`RequestIDConfig`/`TimeoutConfig`，补 `max_request_size`。`TimeoutConfig` 提供统一时长解析（`"120s"`/`"5s"`），字段 `upstream`/`detector`。`ServerConfig` 补 `workers`/`stop_timeout`。
**为什么**：DESIGN 10.2/11.5。消除文档与实现分歧，v0.4.0 全部安全能力依赖此配置树。
**备选方案及排除原因**：保留扁平 dict — 无法类型校验。

### 10. ObservabilityConfig 重构：嵌套子模型
**方案**：`MetricsConfig`（enabled/endpoint）/`TracingConfig`（enabled/exporter/endpoint/sample_rate）。
**为什么**：DESIGN 10.2。扁平布尔无法表达 endpoint/exporter/sampling。
**备选方案及排除原因**：无（对齐 DESIGN）。

### 11. 阈值命名空间分离（B-01）
**方案**：count 阈值用 `count_block_threshold`/`count_flag_threshold`（int），confidence 阈值用 `block_threshold`/`flag_threshold`（float）。`SensitiveWordsDetector` 移除内部 action 决策，只输出 `match_count` 证据 + 归一化 confidence（`min(count/count_block_threshold, 1.0)`），由 engine 统一决策。详见 DESIGN.md 5.3.1。
**为什么**：消除 count-int 被误读为 confidence-float 的错误阻断/放行。
**备选方案及排除原因**：让 engine 感知 match_count — 复杂且破坏通用接口；命名空间分离最简。

### 12. PII 命名统一（B-02）
**方案**：`PIIDetector.name` 由 `pii_detector` 改为 `pii_redaction`。
**为什么**：与 registry/validator/DESIGN 对齐，修复配置丢失。
**备选方案及排除原因**：改 registry 为 `pii_detector` — 与 DESIGN/validator 文档不一致。

### 13. per-detector timeout/circuit_breaker 传递（B-04）
**方案**：`_extract_detector_configs` 注入 `timeout_seconds`（解析 `det.timeout` 或回退全局 `security.timeout.detector`）与 `CircuitBreaker` 实例。新增 `circuit_breaker/factory.py::build_circuit_breaker(CircuitBreakerConfig) -> CircuitBreaker`，解析 `recovery_timeout` 字符串。统一 engine 读取的 key 为 `timeout_seconds`。
**为什么**：修复 dead config，使超时与熔断真正生效。
**备选方案及排除原因**：无（对齐 engine 现有接口）。

### 14. 流式 SSE 分片重组（B-03）
**方案**：`streaming/sse.py` 新增 `SSEBuffer`，按 `\n\n` 边界缓存不完整事件，跨 chunk 拼接后再交给 `_extract_delta_text`。
**为什么**：`aiter_text()` 不保证 SSE 事件完整落在单个 chunk，分片导致漏检。
**备选方案及排除原因**：禁用 `aiter_text` 逐行读取 — httpx 流式 API 限制；缓冲重组最通用。

### 15. 流式审计字段修正（B-05~B-09）
**方案**：
- 输出侧单独维护 `output_action`/`output_risk_level`（sliding_window 从 handler 状态取）。
- 将后审计 `detector_results` 与 `window_count` 写入审计条目；`handler.process_chunk` 累加窗口计数。
- `PostAuditRunner.run()` 与 handler 透传 `request_id` 与输入侧 `language`。
- 同步输出检测加 `asyncio.wait_for(engine.run(...), timeout=sync_timeout)`。
- 补齐 `total_duration_ms`/`user_id`/`duration_ms`/`error`；统一 `post_audit` schema；`DetectorAuditRecord` 增 `applied` 字段。
**为什么**：审计日志是合规追溯唯一依据，必须如实反映输出侧结果。
**备选方案及排除原因**：无（对齐 DESIGN 12.1）。

## Architecture

```
Client ──► RequestID ──► [Auth] ──► [RateLimit] ──► [RequestSize] ──► Route
              │                                                    │
              └──────────── CORS / TLS / Graceful Shutdown ────────┘
                                                                     │
                                              ┌──────────────────────┤
                                              ▼                      ▼
                                        chat/streaming           health/metrics
                                              │
                                    [Pipeline Engine + Detectors]
                                              │
                                    [Post-Audit / Audit Logger / Recall]
                                              │
                                    [Prometheus Metrics / OTel Trace]
```

中间件链（Starlette 顺序，外层先处理请求、后处理响应）：
1. `RequestIDMiddleware`（最外层，响应最后写 X-Request-ID）
2. `AuthMiddleware`（401 保护）
3. `RateLimitMiddleware`（429 保护）
4. `RequestSizeMiddleware`（413 保护）
5. `SafetyHeadersMiddleware`（最内层，先处理响应写 X-Safety-Action）

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 认证配置错误导致网关不可用或未授权访问 | 默认关闭；显式启用 fail-closed；401 兼容错误体 |
| 限流误伤正常流量 | 可配 rate/burst；per api_key/ip 灵活维度 |
| TLS 配置错误导致服务不可达 | 默认关闭；示例配置 + 启动校验 |
| /metrics 暴露敏感信息或影响性能 | metrics_enabled 开关；指标不含敏感内容 |
| 阈值命名空间分离破坏现有配置 | count key 新增而非复用；迁移文档 |
| SSE 分片重组引入延迟或协议错误 | 行缓冲重组；严格 chunk 边界测试 |
| OTel 重依赖影响默认用户 | 可选集成，默认关闭 |
| 中间件顺序错误导致绕过认证 | 测试固定中间件注册顺序；认证在路由前 |
