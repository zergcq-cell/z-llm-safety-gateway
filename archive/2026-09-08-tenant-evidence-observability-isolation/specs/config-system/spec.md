# Capability: config-system
<!-- source_hash: 87ab2ca18a1c738a -->
> Change: 2026-09-08-tenant-evidence-observability-isolation; status: Gate 2 review draft

## REQ-TOC-001 — 配置契约与启动校验
Confidence: medium

#### Scenario: SC-TOC-001 · medium
- **GIVEN** 未提供新增配置或提供合法已配置租户列表
- **WHEN** 加载 observability.tenancy.metric_tenant_ids
- **THEN** SHALL 默认 []，最多 32 个唯一已声明租户 ID；tenancy 关闭时要求列表为空。
- AND: 新增子模型 extra=forbid，严格字符串列表，不接受重复、未知、超长或类型强制转换。
- AND: 不新增 metrics/audit/tracing 默认启用开关；沿用已有默认关闭设置。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TOC-002 · high
- **GIVEN** 配置非法或 tenant 名称与系统保留字同名
- **WHEN** 执行启动校验
- **THEN** SHALL 非法配置以固定 tenant_observability_config_invalid 失败，不回显输入；合法配置 ID 通过 scope 区分保留字。
- AND: tenant/other 与 tenant_other/other 不碰撞；不存在全局禁用保护的静默回退。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

## REQ-TOC-002 — 协议兼容与文档
Confidence: high

#### Scenario: SC-TOC-003 · high
- **GIVEN** 旧单租户示例及新的多租户观测示例
- **WHEN** 加载配置并通过真实 HTTP/SSE 请求运行
- **THEN** SHALL 保持旧 JSON/SSE/body/header 状态语义和 FlowEvidence v1.0；新增观测字段只进入管理员观测数据。
- AND: 不向 Provider Header/body/baggage 或客户端响应注入租户身份。
- AND: 示例包含白名单聚合、非秘密 ID、共享管理员 sinks、disabled 与写入失败策略说明。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md

#### Scenario: SC-TOC-004 · high
- **GIVEN** 第三项通过验证但第四项尚未交付
- **WHEN** 更新路线与交付文档
- **THEN** SHALL 仅在 Gate 3/Deliver 后将第三项标为 delivered，第四项及公共 v0.3.0 保持未完成。
- AND: 本次不更改包版本、不创建发布标签，不声称实现物理租户存储或访问授权隔离。
- Evidence: canonical/proposals/2026-09-08-tenant-evidence-observability-isolation.yaml#what_changes; design.md
