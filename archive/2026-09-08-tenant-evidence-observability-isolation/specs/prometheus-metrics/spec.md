# Capability: prometheus-metrics
<!-- source_hash: 945372e3f3467032 -->
> Change: 2026-09-08-tenant-evidence-observability-isolation; status: Gate 2 review draft

## REQ-TME-001 — 租户指标与计数语义
Confidence: medium

#### Scenario: SC-TME-001 · medium
- **GIVEN** metrics 启用且 tenant_ids 白名单为 acme
- **WHEN** acme、其他可信租户、legacy 和无归属请求产生日志/决策
- **THEN** SHALL 新增 safety_tenant_decisions_total{tenant_scope,tenant_id,direction,action} 和 safety_tenant_observability_events_total{tenant_scope,tenant_id,event}。
- AND: acme 使用 tenant/acme；其他可信租户使用 tenant_other/other；legacy、unattributed、policy、system 使用相应 scope 和固定 none。
- AND: 不新增 policy、model、request_id、Flow/node、API key 标签；policy 生命周期不扇出为租户指标。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TME-002 · high
- **GIVEN** 同一请求多个 Flow 节点、多个 SSE 窗口或 async pending/completed 审计
- **WHEN** 统计最终 input/output 安全决策
- **THEN** SHALL 每个实际最终方向决策计数一次；pending、窗口和持久化重试不得重复计数。
- AND: action 枚举 allow/block/flag/modify/error；direction 仅 input/output。
- AND: 未形成方向安全决策的 401/路由错误只产生诊断，不伪造 allow。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

## REQ-TME-002 — 基数与安全兼容
Confidence: medium

#### Scenario: SC-TME-003 · high
- **GIVEN** 白名单最多 32 个已配置租户，攻击者发送 10000 个不同请求字段
- **WHEN** 检查两个新指标 family 的所有 label tuples
- **THEN** SHALL 身份组合最多 37，决策 tuples 最多 370，诊断 tuples 最多 296。
- AND: event 固定八项：tenant_context_invalid、audit_sink_failed、tracing_unavailable、projection_sanitized、auth_rejected、policy_unavailable、background_failed、cancelled。
- AND: 每个 counter 的 total/created 样本合计最多 1332；诊断记录不递归产生诊断。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TME-004 · medium
- **GIVEN** 多租户请求产生任意 model/category/reason/error 和插件描述
- **WHEN** 更新现有 gateway/provider/detector/Flow 指标
- **THEN** SHALL 保留现有 metric 名称和 label schema，model 固定 redacted；自由文本映射固定 unknown，ID 仅允许启动期受限配置集合。
- AND: 动作、状态、direction 使用现有有限枚举；category、reason_code、error_type、field、detector_type 采用实现中固定允许值集合加 unknown。
- AND: Counter/Histogram 的 ID label 白名单取配置字典序前 256 项，其余归并 other；Gauge 仅接受完整预编译实体集合，不聚合实体，未知实体拒绝。
- AND: 不得将任意输入加入缓存；单租户旧指标行为保持兼容。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TME-005 · high
- **GIVEN** metrics 关闭或同进程创建两个不同配置 app
- **WHEN** 记录/导出事件
- **THEN** SHALL 禁用时不分配 label 状态；不同 app 的租户白名单和新增 registry 不相互覆盖。
- AND: 使用 app-scoped observation runtime 及显式注入，不能把租户配置保存在模块级最近 app 变量。
- AND: 现有全局 metrics/tracing API 的兼容调用保留，但多租户请求路径必须绑定其所属 app runtime。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md
