# Capability: audit-logger
<!-- source_hash: 5bf8e13e75d3d446 -->
> Change: 2026-09-08-tenant-evidence-observability-isolation; status: Gate 2 review draft

## REQ-TAU-001 — 租户审计证据与兼容
Confidence: medium

#### Scenario: SC-TAU-001 · high
- **GIVEN** 包含 allow/block/flag/modify、降级或安全不可用的 input/output 决策
- **WHEN** 构建并写入 AuditEntry
- **THEN** SHALL 在新增可选 tenant_context 字段中记录可信观测快照，并保留现有 Flow/节点/插件版本/有效策略证据。
- AND: FlowEvidence v1.0 schema 不变；归属写在 AuditEntry 外层，避免破坏 extra=forbid 消费者。
- AND: 旧 AuditEntry JSON 无该字段仍可读取，单租户默认序列化不增加该字段。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TAU-002 · high
- **GIVEN** 后台异步输出、流式审计与 recall，含多个合并 SSE event
- **WHEN** 最终记录或发出后台诊断
- **THEN** SHALL 使用发起请求快照，保持现有 request_id、Flow execution_id 与归属关联。
- AND: 失败或取消诊断不得复制另一个请求的归属或原文。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TAU-003 · medium
- **GIVEN** 多个租户共用策略，策略私有 detector 发生状态变化
- **WHEN** 写入 DetectorLifecycleEvent
- **THEN** SHALL 记录 scope=policy 和可信 policy_id，tenant_id=null，保持原有顶层 policy_id。
- AND: 不伪造请求归属，不向每个租户重复发出事件。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

## REQ-TAU-002 — 安全投影与写入失败
Confidence: medium

#### Scenario: SC-TAU-004 · high
- **GIVEN** 审计原文默认关闭，并植入 API Key、Provider key、异常文本和伪造归属
- **WHEN** 序列化租户审计 envelope
- **THEN** SHALL 归属字段仅来自可信快照；新增元数据不泄露秘密，默认不记录 content。
- AND: store_content=true 的现有显式内容政策保留；它不授权把内容写入日志、Trace 或指标。
- AND: 新增归属 JSON UTF-8 增量上限 512 bytes，不复制租户配置；现有 Flow evidence size 预算仍成立。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TAU-005 · high
- **GIVEN** file/stdout 单独或共同失败、无可用 sink 或初始化失败
- **WHEN** 记录有/无 FlowEvidence 的租户审计
- **THEN** SHALL 标记 entry.evidence_persisted=false，并保持原有不因审计 sink 失败改变安全结果的行为。
- AND: 如有 FlowEvidence，返回值和 entry 内的 evidence_persisted 一致。
- AND: 发出稳定 audit_sink_failed 诊断，不包含路径、原始异常或原文；诊断 sink 再失败不递归。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TAU-006 · medium
- **GIVEN** audit.enabled=false 或审计投影收到非法归属
- **WHEN** 尝试记录
- **THEN** SHALL 分别显式跳过写入，或以 unattributed 记录 tenant_context_invalid 诊断并拒绝伪造的归属。
- AND: 审计关闭不禁用其他已启用观测通道；非法归属不补写为已知租户。
- AND: 禁用设置通过启动时固定事件可见，不逐请求产生禁用日志。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md
