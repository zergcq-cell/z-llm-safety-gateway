# v0.3.0 租户证据与可观测性隔离
<!-- source_hash: ba75cb168978c03e -->

## Why
可信租户身份和策略运行时已交付，但 AuditEntry 缺少租户归属，Flow 指标和 Trace 尚无统一租户观测上下文。
实施 DESIGN.md 公共 v0.3.0 路线第三项，确保普通、流式及后台安全决策的证据不会串租户。

## What Changes
- 建立可信且跨请求隔离的观测快照
- 将租户及策略归属贯穿审计、日志和 Trace
- 为指标设定租户明细及基数边界
- 明确身份异常、观测失败和脱敏行为
- 补充真实请求链测试、配置约束和兼容文档

## Capabilities

### New Capabilities
- **tenant-evidence-context**：可信、不可变且跨异步阶段隔离的租户观测上下文

### Modified Capabilities
- **audit-logger**：审计归属、租户证据与持久化失败可观测
- **observability**：安全日志和 Trace 的租户归属与脱敏
- **prometheus-metrics**：有限基数的租户指标及现有指标安全投影
- **config-system**：租户观测配置约束、兼容行为与示例

## Impact

**代码层面**：tenancy、middleware、pipeline、routes、streaming、post_audit、audit、observability、app 装配及对应测试，预计 20–35 文件。

**配置层面**：新增观测配置约束及示例；旧配置无需迁移。

**基础设施**：无需新增基础设施，复用现有 JSONL、Prometheus、OTel。

## Constraints

- 严格 STDD 与 RED→GREEN→REFACTOR；Gate 2/3 独立确认。
- 只消费可信身份，禁止客户端 Header、body、baggage 覆写。
- 不改变 Provider 协议、安全决策或默认内容保留策略。

## Stakeholders

- 网关维护者
- 多租户平台与安全运维
- 观测数据消费者

## NonGoals

- 租户容量、配额、并发公平性及第四项整体验收
- 租户数据库、控制面、热更新、物理日志分库或租户查询 API
- 发布 v0.3.0、改制品版本或创建发布标签

## Risk Areas

- capability: tenant-evidence-context — 并发及后台任务串租户；缓解：不可变快照、显式传递、上下文清理及真实并发测试
- capability: prometheus-metrics — 高基数或秘密泄漏；缓解：配置白名单、有限枚举及对抗性基数测试
- capability: audit-logger — 错误归属或持久化失败静默；缓解：稳定诊断事件、故障注入与安全投影

## Critical
- [x] 关键变更：涉及可信租户归属和数据保护。

## Risk Assessment
- safety_critical: true
- financial: false
- cross_system: false

## Anchoring
- level: L3
- reference_changes: 2026-08-22-v0.2.0-flow-foundation, 2026-08-30-tenant-identity-config-contract, 2026-09-01-tenant-flow-policy-resolution

## Project Principle Check

1. **plugin_flow**：只扩展上下文、证据与观测运行机制；领域判断仍在插件、组合仍由 Flow 决定。
2. **explicit_policy_failure**：身份缺失、上下文冲突、写入失败和指标归并都有明确行为与稳定原因码。
3. **transparent_contracts**：保持 HTTP/SSE 和单租户行为；采用增量审计字段及独立租户指标，身份传播和指标基数有界。
4. **evidence_data_protection**：可信租户/策略快照关联 Flow/节点证据；默认不记录原文和认证秘密，不从客户端字段推导租户。

**原则取舍或偏离**：指标明细与基数限制之间的取舍由 Phase 2 明确；不偏离四项原则。

## Success Criteria

- [ ] 跨租户并发和后台任务的证据归属正确。
- [ ] 伪造身份无法污染审计、日志、Trace 或指标。
- [ ] 认证秘密、原文和原始异常不进入新增观测字段。
- [ ] 租户指标及请求驱动指标维度有明确可验证的上限。
- [ ] 单租户与上游 HTTP/SSE 协议兼容测试通过。
