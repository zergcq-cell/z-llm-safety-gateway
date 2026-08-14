# v0.4.0 Security & Observability 任务清单

## 1. config-system（P0）

- [ ] 1.1 重构 SecurityConfig：AuthConfig/TLSConfig/RateLimitConfig/CORSConfig/RequestIDConfig/TimeoutConfig 子模型 + max_request_size
- [ ] 1.2 统一时长解析（'120s'/'5s'），TimeoutConfig upstream/detector 分离
- [ ] 1.3 ServerConfig 补 workers/stop_timeout
- [ ] 1.4 ObservabilityConfig 重构为 MetricsConfig/TracingConfig 嵌套子模型
- [ ] 1.5 阈值命名空间分离：count_block_threshold/count_flag_threshold（B-01）
- [ ] 1.6 PII 命名统一 pii_redaction（B-02）
- [ ] 1.7 _validate_thresholds 区分 count/confidence 阈值校验（B-20）
- [ ] 1.8 更新 gateway.yaml 示例配置

## 2. authentication + rate-limiting（P0）

- [ ] 2.1 新建 middleware/auth.py AuthMiddleware（Bearer token，401 fail-closed，注入 api_key_name）
- [ ] 2.2 新建 ratelimit/ TokenBucket（per api_key/ip，429 + Retry-After）
- [ ] 2.3 新建 middleware/rate_limit.py RateLimitMiddleware

## 3. TLS + request-size + CORS + graceful-shutdown（P1）

- [ ] 3.1 TLS 集成：__main__.py uvicorn ssl_certfile/ssl_keyfile
- [ ] 3.2 新建 middleware/request_size.py RequestSizeMiddleware（413）
- [ ] 3.3 CORS 集成：create_app 接入 CORSMiddleware
- [ ] 3.4 优雅停机：__main__.py SIGTERM + stop_timeout

## 4. prometheus-metrics + opentelemetry-tracing（P1）

- [ ] 4.1 添加 prometheus-client 依赖
- [ ] 4.2 新建 observability/metrics.py（gateway/detector/provider/recall 指标）
- [ ] 4.3 /metrics 端点按 metrics_enabled 控制
- [ ] 4.4 可选 OTel 集成（默认关闭，exporter otlp）

## 5. fastapi-server 集成（P0）

- [ ] 5.1 中间件链注册：RequestID→Auth→RateLimit→RequestSize→SafetyHeaders
- [ ] 5.2 request_id.header/generate 配置接线到 RequestIDMiddleware（B-12）
- [ ] 5.3 新建 circuit_breaker/factory.py build_circuit_breaker（B-04）
- [ ] 5.4 _extract_detector_configs 注入 timeout_seconds 与 CircuitBreaker 实例（B-04）

## 6. sse-streaming 修正（P0）

- [ ] 6.1 SSEBuffer 分片行缓冲重组（B-03）
- [ ] 6.2 输出侧 output_action/output_risk_level 单独维护（B-05）
- [ ] 6.3 后审计 detector_results + window_count 写入审计（B-06）
- [ ] 6.4 PostAuditRunner/handler 透传 request_id 与 language（B-07）

## 7. audit-logger 修正（P0）

- [ ] 7.1 补齐 total_duration_ms 赋值（B-09）
- [ ] 7.2 提取 user_id（B-09）
- [ ] 7.3 DetectorAuditRecord 填 duration_ms/error + 增 applied 字段（B-09）
- [ ] 7.4 统一 post_audit schema（result/category/risk_level）（B-09）
- [ ] 7.5 同步输出检测加 asyncio.wait_for 强制 sync_timeout（B-08）

## 8. 测试与验证

- [ ] 8.1 每个切片 RED→GREEN→REFACTOR（90 个 TC）
- [ ] 8.2 全量 pytest 通过（v0.1.0+v0.2.0+v0.3.0 回归 + v0.4.0 新增）
- [ ] 8.3 ruff check 无错误
- [ ] 8.4 mypy strict 无错误
- [ ] 8.5 测试覆盖率报告

<!--
优先级说明：
- P0：阻塞性任务，完成前无法进入下一阶段（切片 1/2/5/6/7）
- P1：重要任务（切片 3/4）
- 依赖标注：切片 2/3/4/6/7 依赖切片 1；切片 5 依赖切片 1-4
-->
