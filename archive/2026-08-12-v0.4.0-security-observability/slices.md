# v0.4.0 Security & Observability — 切片执行计划

## Dependency Graph Summary

```
                     ┌─────────────────────────────┐
                     │  S1 config-system (基础)    │
                     └──────────────┬──────────────┘
        ┌──────────────┬────────────┼─────────────┬──────────────┐
        ▼              ▼            ▼             ▼              ▼
   ┌─────────┐   ┌─────────┐  ┌─────────┐  ┌──────────┐   ┌──────────┐
   │S2 认证   │   │S3 TLS/  │  │S4 指标/ │  │S6 SSE修正│   │S7 审计   │
   │ 限流     │   │ 请求/CORS│  │ OTel    │  │ (修正)   │   │ (修正)   │
   └────┬────┘   │ 停机     │  └────┬────┘  └────┬─────┘   └────┬─────┘
        │        └────┬────┘       │             │              │
        └─────────────┼────────────┴─────────────┴──────────────┘
                      ▼
            ┌──────────────────┐
            │ S5 fastapi-server│
            │ (集成中间件链)    │
            └──────────────────┘
```

**并行化说明**：
- 并行组 1（依赖 S1 完成后并行）：S2 认证限流、S3 TLS/请求/CORS/停机、S4 指标/OTel、S6 SSE 修正、S7 审计修正
- 并行组 2（依赖全部组1完成）：S5 fastapi-server 集成

## Slice Execution Plan

| # | 优先级 | 风险 | 预估工时 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|---------|--------|---------|---------|------|
| 1 | P0 | 🟡 Med | L | 基础 | TC-CFG-001~005 | SecurityConfig/ObservabilityConfig/ServerConfig 重构 + 阈值命名空间 + PII 命名 | 无 |
| 2 | P0 | 🟡 Med | M | 组1 | TC-AUTH-*, TC-RL-* | AuthMiddleware + TokenBucket 限流 | 1 |
| 3 | P1 | 🟢 Low | M | 组1 | TC-TLS-*, TC-RSL-*, TC-CORS-*, TC-GS-* | TLS/请求大小/CORS/优雅停机 | 1 |
| 4 | P1 | 🟢 Low | M | 组1 | TC-PROM-*, TC-OTEL-* | Prometheus 指标 + OTel 追踪 | 1 |
| 5 | P0 | 🟡 Med | L | 组2 | TC-FSA-* | 中间件链注册 + request_id 接线 + timeout/breaker 传递 | 1,2,3,4 |
| 6 | P0 | 🔴 High | L | 组1 | TC-SSE-* | SSE 分片重组 + 流式审计字段修正 + 上下文传播 | 1,5(接口) |
| 7 | P0 | 🟡 Med | M | 组1 | TC-AUDIT-* | 审计字段补齐 + sync_timeout 强制 + schema 统一 | 1,5(接口) |

## Rationale

### Slice 1: config-system（P0，基础）
- **依赖关系**：所有新能力依赖重构后的配置模型，必须最先完成。
- **风险分析**：重构 SecurityConfig/ObservabilityConfig 需保持向后兼容；阈值命名空间分离是 B-01 核心修正（高风险）。
- **工作量估算**：L（5 req / 5 SC，涉及 config/models.py、validators.py、loader.py、gateway.yaml）。

### Slice 2: authentication + rate-limiting（P0，组1）
- **依赖关系**：依赖 S1 的 AuthConfig/RateLimitConfig。
- **风险分析**：安全关键（fail-closed 认证 + 429 限流），涉及 middleware 新增。
- **工作量估算**：M（11 req / 13 SC）。

### Slice 3: TLS + request-size + CORS + graceful-shutdown（P1，组1）
- **依赖关系**：依赖 S1 的 TLSConfig/CORSConfig/ServerConfig。
- **风险分析**：低风险，标准实现。
- **工作量估算**：M（12 req / 12 SC）。

### Slice 4: prometheus-metrics + opentelemetry-tracing（P1，组1）
- **依赖关系**：依赖 S1 的 MetricsConfig/TracingConfig。
- **风险分析**：依赖 prometheus-client/opentelemetry 包安装；OTel 可选默认关闭。
- **工作量估算**：M（9 req / 11 SC）。

### Slice 5: fastapi-server 集成（P0，组2）
- **依赖关系**：依赖 S1~S4 全部完成；连接所有中间件到 create_app。
- **风险分析**：中间件顺序错误可能导致绕过认证（高风险）。
- **工作量估算**：L（8 req / 18 SC，含 circuit_breaker/factory.py）。

### Slice 6: sse-streaming 修正（P0，组1）
- **依赖关系**：依赖 S1（配置）+ S5 集成接口（流式审计入口）。
- **风险分析**：SSE 分片重组是检测正确性边界，chunk 拆分场景测试复杂（最高风险）。
- **工作量估算**：L（5 req / 15 SC）。

### Slice 7: audit-logger 修正（P0，组1）
- **依赖关系**：依赖 S1 + S5 集成接口。
- **风险分析**：审计 schema 变更需与 DESIGN 12.1 对齐，涉及 models.py 字段增改。
- **工作量估算**：M（6 req / 16 SC）。
