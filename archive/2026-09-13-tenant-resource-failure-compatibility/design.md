# v0.3.0 租户资源、失败与兼容性隔离 — 技术设计

## Context

前三项租户变更已经建立可信身份、不可变运行时 bundle 以及租户观测上下文。当前 Flow runtime、Provider 调用、SSE 和 post-audit 仍缺少统一的租户资源预算与跨路径失败契约。本 change 只补齐资源和失败运行机制，不引入控制面或新的领域能力。

## Project Principle Check

| 原则 | 设计与验证 |
|---|---|
| Plugin / Flow；核心最小 | 资源租约、并发闸门、deadline 和失败分类属于核心运行机制；检测与策略仍由插件和 Flow 提供。通过核心模块无租户领域决策导入检查。 |
| 策略显式；失败不静默 | 配额、队列、超时、取消、资源耗尽和 Provider 故障均有显式配置及稳定 reason code；每种降级产生 audit/metric 信号。 |
| 边界透明；契约稳定 | 旧单租户路径保持原 HTTP/SSE/Provider 语义；租户模式新增拒绝只发生在资源边界，所有等待和内存占用有上限。 |
| 证据；数据保护 | 失败证据只携带受信任 tenant/policy 归属、资源类型和 reason code；不记录原文、密钥或请求体。 |

无原则偏离。主要取舍是优先使用进程内有界租约与请求 deadline，避免在本 change 引入分布式配额依赖。

## Decisions

### 1. 请求级不可变 ResourceBudget

每个已解析 tenant bundle 生成 `ResourceBudget` 快照，包含最大并发、队列深度、请求 deadline、流式连接和后台任务上限。快照随请求传播，禁止从客户端字段覆盖。

### 2. 租户闸门与有界队列

使用按租户分片的异步闸门；获取租约必须在 deadline 内完成，队列超限立即返回稳定的 `tenant_resource_exhausted`。释放在同步、异步、SSE、异常和取消路径执行。

### 3. 统一 FailureOutcome

将 timeout、cancelled、capacity_exhausted、initialization_failed、provider_unavailable、isolation_violation 归一为稳定分类，映射到兼容 HTTP/SSE 错误和最小观测事件。禁止跨租户或全局 bundle fallback。

### 4. Provider 与后台生命周期

Provider 调用继承请求 deadline，不允许无限重试；post-audit 和 recall 等后台任务只能消费原请求的冻结快照，并受租户后台预算约束。

### 5. 聚合验收

在 change 末尾建立跨前三项归档证据的验收矩阵，覆盖身份绑定、策略选择、证据归属、观测基数、资源隔离、失败语义和 legacy compatibility。

## Architecture

```text
trusted TenantContext
        │
        ▼
TenantPolicyBundle + ResourceBudget (frozen)
        │
        ├─ request gate ── Flow runtime ── Detector plugins
        │                         └──── Provider router
        ├─ SSE/buffer/post-audit (same snapshot, bounded lifetime)
        └─ evidence/log/metrics (tenant-safe failure projection)
```

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 租户饥饿或全局锁竞争 | 分片闸门、确定性屏障、最大队列和跨租户并发测试 |
| 取消后租约泄漏 | finally 释放、任务取消注入、active lease 归零断言 |
| Provider 重试放大 | 单 deadline、重试上限、失败零调用/单调用断言 |
| 长 SSE 占用容量 | 连接预算、idle/deadline、断开清理测试 |
| 旧行为回归 | legacy corpus、HTTP/SSE/Provider 精确 body 回归 |
