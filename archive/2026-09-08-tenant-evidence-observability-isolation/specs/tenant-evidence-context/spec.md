# Capability: tenant-evidence-context
<!-- source_hash: 633fea4d7da37b99 -->
> Change: 2026-09-08-tenant-evidence-observability-isolation; status: Gate 2 review draft

## REQ-TEC-001 — 可信观测快照
Confidence: high

#### Scenario: SC-TEC-001 · high
- **GIVEN** 已认证 acme/globex 且具有 TenantPolicyContext
- **WHEN** 策略解析后构建观测快照
- **THEN** SHALL 创建 frozen TenantObservationContext v1.0，包含 scope=tenant、tenant_id 和 policy_id；身份必须同时匹配启动期租户与策略绑定。
- AND: 快照只含 contract_version、scope、tenant_id、policy_id；不含密钥、认证凭据名、配置对象或请求原文。
- AND: tenant_id 和 policy_id 复用既有 1–64 字符配置 ID 契约。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TEC-002 · high
- **GIVEN** 请求伪造 tenant Header/body、baggage 或日志同名字段
- **WHEN** 执行真实认证与策略解析
- **THEN** SHALL 仅以已认证上下文选择归属，忽略所有客户端归属声明。
- AND: 两个租户使用相同 X-Request-ID 也不合并上下文或审计归属。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TEC-003 · high
- **GIVEN** tenancy.enabled=true 且内部上下文缺失、身份未知或绑定冲突
- **WHEN** 进入安全检测或 Provider 调用前验证快照
- **THEN** SHALL 返回 OpenAI-compatible 503 tenant_policy_unavailable，且不调用插件或 Provider。
- AND: 诊断归属 unattributed，原因码 tenant_context_invalid；禁止 default、其他租户或全局策略回退。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

## REQ-TEC-002 — 阶段生命周期隔离
Confidence: medium

#### Scenario: SC-TEC-004 · high
- **GIVEN** 两个租户以屏障交错执行真实 HTTP 请求
- **WHEN** 分别走 sync-output、async-output、SSE buffer、sliding-window 和 post-audit/recall
- **THEN** SHALL 每条证据和后台诊断保留发起请求快照；共享 policy_id 时 tenant_id 仍不同。
- AND: 后台任务和生成器显式携带快照，不在执行时读取最近请求或重新解析全局默认值。
- AND: 每一运行路径分别参数化并断言真实调用、证据及输出，而非仅枚举阶段名称。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TEC-005 · high
- **GIVEN** 响应完成、异常、断连或取消，随后在同一执行环境处理其他请求
- **WHEN** 退出请求/后台观测作用域
- **THEN** SHALL 用 token/finally 恢复上下文且不吞掉取消；后续请求不继承前一租户。
- AND: 在 ASGI send/迭代结束前保留流式作用域；禁止仅围绕 BaseHTTPMiddleware.call_next 绑定。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TEC-006 · medium
- **GIVEN** tenancy 关闭、未认证请求和非请求生命周期事件
- **WHEN** 生成观测上下文
- **THEN** SHALL 分别使用 legacy、unattributed、system scope；只有已验证 policy 生命周期事件使用 policy scope。
- AND: legacy 的 tenant_id/policy_id 为 null，保留已有 TenantContext default 的认证契约，不将其误认为多租户 default。
- AND: 未认证请求维持现有 401，不引入归属查询。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md
