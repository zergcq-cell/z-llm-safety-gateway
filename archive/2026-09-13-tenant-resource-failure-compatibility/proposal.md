# v0.3.0 租户资源、失败与兼容性隔离

## Why

租户身份、策略解析和观测隔离已经完成，但资源使用、并发争用和跨路径失败行为仍缺少统一租户边界。高负载或租户级故障可能影响其他租户。本 change 完成 v0.3.0 的第四项基础能力。

## What Changes

- 增加租户级容量、并发、队列和资源生命周期契约。
- 统一请求、Flow、Detector、Provider、SSE、buffer 和 post-audit 的资源边界。
- 建立资源耗尽、超时、取消、初始化失败、Provider 不可用和隔离异常的稳定失败矩阵。
- 禁止静默跨租户回退、上下文泄漏和状态污染，保持旧单租户及协议兼容。
- 增加 v0.3.0 四项变更的聚合验收矩阵和交付证据。

## Capabilities

### New Capabilities

- **tenant-resource-isolation**：租户级并发、容量、队列和资源生命周期隔离。
- **tenant-failure-matrix**：统一、显式、可观测的租户失败、超时、取消和降级契约。
- **v0.3-aggregate-acceptance**：身份、策略、证据、观测、资源和兼容性的联合验收。

### Modified Capabilities

- **flow-runtime**：在租户资源上下文中执行，同时保持 Flow 核心租户中立。
- **provider-proxy**：在租户资源和失败策略约束下执行 Provider 调用。
- **streaming-and-post-audit**：SSE、buffer、post-audit 和异步路径遵循同一资源快照与失败语义。
- **legacy-compatibility**：未启用租户功能的旧配置和单租户调用路径保持兼容。

## Impact

**代码层面**：配置模型、租户运行时、Flow runtime、Provider router、请求中间件、流式处理、post-audit、健康检查及对应测试。

**配置层面**：新增可选且有上限的资源与失败策略配置；旧配置无需迁移。

**基础设施**：增加确定性并发、容量、跨租户隔离、三版本兼容和整体验收测试；不引入外部服务。

## Constraints

- 严格执行 STDD 与 RED→GREEN→REFACTOR。
- 所有上限、超时、降级和失败代码必须显式、有界、可观测。
- 保持包版本 v0.2.2，直到 v0.3.0 完成。

## Stakeholders

- 网关部署者与运维人员
- 多租户应用开发者
- 安全策略与合规审计人员
- Provider 和 Detector 插件维护者
- 现有单租户用户

## Risk Areas

- **tenant-resource-isolation**：共享资源错误设计导致跨租户饥饿或泄漏；使用快照、有界队列和释放测试缓解。
- **tenant-failure-matrix**：路径间失败语义不一致；使用统一 reason code 和全路径矩阵缓解。
- **provider-proxy**：超时、取消和重试放大资源占用；使用 deadline、取消传播和重试上限缓解。
- **legacy-compatibility**：新配置改变旧协议；使用旧配置和 HTTP/SSE/Provider 回归缓解。

## NonGoals

- 租户数据库、缓存、控制面 API、热更新或物理日志分库。
- 新 Provider、Detector、OAuth、多模态或其他产品能力。
- 发布 v0.3.0、创建 tag 或推送 GitHub。

## Critical

- [x] 关键变更：涉及资源隔离、失败边界和安全可用性。

## Risk Assessment

- **safety_critical**：true
- **financial**：false
- **cross_system**：true

## Anchoring

- **level**：L3
- **reference_changes**：2026-08-30-tenant-identity-config-contract, 2026-09-01-tenant-flow-policy-resolution, 2026-09-08-tenant-evidence-observability-isolation

## Project Principle Check

1. **Plugin / Flow**：资源隔离、生命周期和失败处理属于核心运行机制；租户安全领域行为仍由插件提供，执行组合仍由 Flow 决定。
2. **显式策略 / 失败**：配额、队列、超时、取消、资源耗尽和降级动作均配置化、可观测，并使用稳定失败代码。
3. **透明边界 / 稳定契约**：保留旧单租户、HTTP、SSE、Provider 和错误响应语义；资源成本设置明确上限。
4. **证据 / 数据保护**：资源拒绝、失败和降级记录最小租户归属与策略证据，不记录原始内容、密钥或无界标签。

**原则取舍或偏离**：无。

## Success Criteria

- [x] 任一租户达到资源上限时，仅该租户受到稳定、可观测的拒绝或排队结果，其他租户仍可运行。
- [x] 同步、异步、SSE、buffer、post-audit 和 Provider 调用均遵循同一租户资源快照。
- [x] 超时、取消、初始化失败、Provider 不可用和资源耗尽均命中明确失败矩阵，无静默跨租户 fallback。
- [x] 旧单租户配置和既有 HTTP/SSE/Provider 协议回归通过。
- [x] 通过跨租户隔离、失败模式、资源有界性、隐私、Ruff、mypy 和完整测试质量门。
- [x] v0.3.0 四项变更的聚合验收矩阵全部通过，文档和归档证据一致。
