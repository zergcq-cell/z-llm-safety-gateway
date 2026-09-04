# v0.3.0 租户级 Flow 与安全策略解析

<!-- source_hash: 0d857b441ddffb86 -->
<!-- generated_at: 2026-09-01T22:02:54.486834 -->
<!-- canonical: canonical/proposals/2026-09-01-tenant-flow-policy-resolution.yaml -->

## Why

v0.3.0 已建立可信租户身份与配置契约，但当前所有租户仍共享同一套全局 Flow、 Detector 配置、阈值、词表和 Provider 路由。网关虽然能够识别租户，却尚不能保证 不同租户按各自安全策略执行，也不能阻止模型路由越出租户允许的 Provider 范围。


## What Changes

- 扩展租户配置，使租户显式引用经过启动期验证的 Flow、Detector、策略和 Provider 路由配置
- 建立由可信 TenantContext 驱动的不可变请求级租户策略快照
- 按租户解析 input/output Flow、节点策略、Detector 参数、阈值和词表
- 将 Provider 选择限制在租户允许的路由范围内，禁止客户端输入越权切换租户策略
- 启动期拒绝未知、重复、悬空和冲突引用；运行期拒绝缺失策略和越权路由，不静默回退
- 预编译租户策略关系，使请求期解析为有界查找且并发请求互不污染
- 保持旧单租户 YAML、Flow、HTTP/SSE 和 Provider 协议行为兼容，并更新 v0.3.0 roadmap 状态

### New Capabilities

- **tenant-policy-resolution**：从可信租户身份解析不可变、有界且非秘密的请求级 Flow、安全策略和 Provider 路由快照

### Modified Capabilities

- **tenant-config-contract**：从 identity-only 声明演进为显式、可验证的租户策略引用契约
- **default-detector-flow**：支持请求级 Flow、Detector 参数、阈值、词表和节点策略选择
- **provider-proxy**：在租户允许的路由范围内选择 Provider，禁止跨租户或全局静默回退
- **config-system**：在启动期验证并预编译全部租户策略关系，同时保留单租户兼容入口

## Success Criteria

- [ ] 两个租户可以在同一 Gateway 中解析为不同的 input/output Flow、Detector 参数、阈值、词表和 Provider 路由
- [ ] 相同 model 值可以依据可信租户身份在各自允许的路由域内选择不同 Provider
- [ ] 客户端 Header、body 或 model 输入不能覆盖可信租户身份或选择其他租户策略
- [ ] 未知、重复、悬空和冲突策略引用在启动期以稳定、脱敏的原因失败
- [ ] 运行期缺失策略、无匹配 Provider 或越权路由不会回退到其他租户或全局配置
- [ ] 并发租户请求使用彼此独立、不可变的策略快照，不发生跨租户污染
- [ ] 请求期解析使用启动期预编译的有界查找，不执行无界配置扫描
- [ ] 原有单租户 YAML、Flow、HTTP、SSE 和 Provider 行为保持兼容
- [ ] 新增单元、集成和失败路径测试；全量 pytest、ruff、mypy 通过且覆盖率不下降
- [ ] 不提前实现后续 evidence/observability 和 resource/failure/aggregate changes 的能力
