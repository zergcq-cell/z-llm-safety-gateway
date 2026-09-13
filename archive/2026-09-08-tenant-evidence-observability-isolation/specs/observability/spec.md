# Capability: observability
<!-- source_hash: d69aa55daf52c756 -->
> Change: 2026-09-08-tenant-evidence-observability-isolation; status: Gate 2 review draft

## REQ-TOB-001 — 日志及 Trace 投影
Confidence: medium

#### Scenario: SC-TOB-001 · high
- **GIVEN** 已验证租户快照与 Flow/节点证据
- **WHEN** 生成网关管理的请求、安全决策、Provider、Flow/node 日志及 span
- **THEN** SHALL 通过统一安全投影附加 tenant.scope、tenant.id、tenant.policy_id；无值字段省略。
- AND: 日志采用 tenant_scope、tenant_id、tenant_policy_id 对应键；可信投影覆盖同名非可信字段。
- AND: Flow/Node 观测函数显式接受快照，第三方插件内部日志不承诺可强制隔离。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TOB-002 · medium
- **GIVEN** 请求 model、request_id、Header、baggage 或异常包含秘密和长字符串
- **WHEN** 网关观测事件被导出
- **THEN** SHALL 不将原文、密钥、原始异常、URL query 或客户端 baggage 导出为租户观测属性。
- AND: Trace span 名称不包含租户或客户端字段；请求/Provider model 在多租户模式投影为固定 redacted。
- AND: 自动 FastAPI instrumentation 的 Header 捕获必须关闭、URL query 必须脱敏；traceparent 仅用于链路连接，不用于身份。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TOB-003 · high
- **GIVEN** 嵌套 Flow、流式和后台任务交错运行
- **WHEN** 导出 spans 和结构化日志
- **THEN** SHALL 每个请求关联事件使用其显式快照，嵌套 Flow 延续相同归属。
- AND: 取消、正常结束与失败之后无残留 contextvars。
- AND: Span exporter、日志捕获夹具验证实际输出而非只验证调用参数。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

## REQ-TOB-002 — 观测故障策略
Confidence: high

#### Scenario: SC-TOB-004 · high
- **GIVEN** tracing 禁用、可选依赖缺失或 exporter 故障
- **WHEN** 初始化/导出观测
- **THEN** SHALL 保持禁用时 no-op；启用但不可用时产生稳定 tracing_unavailable 诊断，安全结果和 Provider 语义不变。
- AND: 沿用已有 best-effort tracing 政策；不得每次请求重复初始化或新建 exporter。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TOB-005 · high
- **GIVEN** 观测投影内部收到非法字段或不可序列化异常对象
- **WHEN** 执行安全投影
- **THEN** SHALL 使用固定 unknown/invalid 值或省略非法字段，并产生 projection_sanitized 诊断。
- AND: 不截取、哈希或缓存任意输入来创建身份/标签；异常对象不得进入诊断文本。
- AND: 网关管理的日志及 Trace 失败诊断路径都经过相同安全投影。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md
