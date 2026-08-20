# Detector Readiness Fail-Safe 切片执行计划

## Dependency Graph Summary

```text
S1 配置与状态基础
 ├──> S2 初始化协调器与 fatal cleanup ──> S3 启动策略矩阵 ──> S4 Readiness ──> S5 业务准入
 │                                          │                         │
 │                                          └────────> S6 审计 <──────┘
 └────────────────────────────────────────────────────> S7 Metrics <──┘
```

仓库没有 `bin/stdd`，依赖图由 canonical specs 与 test-plan 手工构建；未发现循环依赖。

**并行化说明**：实现会串行执行以避免 `server/app.py`、状态注册表和审计接口的交叉冲突。完成 S3 后，S4 与 S6 理论可并行；S5 完成后执行 S7 的请求指标集成。

## Slice Execution Plan

| # | 名称 | 优先级 | 风险 | 工作量 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|---|---|---|---|---|---|---|---|
| S1 | 配置与状态基础 | P0 | 🟡 4/5 | L | — | CFG-601～603, DLS-001～004 | config required 校验；app-scoped 状态模型 | 无 |
| S2 | 初始化协调器与清理 | P0 | 🟡 5/5 | M | — | DF-601～603, RDP-001～002 | 四类统一初始化；required fatal cleanup | S1 |
| S3 | 启动策略矩阵 | P0 | 🟡 5/5 | M | — | RDP-003～005, FAST-601～602 | app state；严格/降级启动决策 | S2 |
| S4 | Detector-aware Readiness | P0/P1 | 🟡 5/5 | M | G1 | HEALTH-601～605 | app 隔离；并行有界 health；恢复与摘要 | S3 |
| S5 | 业务安全准入 | P0 | 🟡 5/5 | M | — | FAST-603～605 | Provider 前 input/output guard；专用 503；fail-open skip | S3/S4 |
| S6 | 生命周期与请求审计 | P0/P1 | 🟡 4/5 | L | G1 | DSV-001～003, AUDIT-601～604 | lifecycle/request audit、fatal flush、脱敏日志 | S2/S3 |
| S7 | Prometheus 降级信号 | P1/P2 | 🟢 3/5 | M | — | PROM-601～604 | up/failure/degraded 指标与 disabled no-op | S1/S5 |

## 五步分析

### 依赖图

- 零依赖：S1。
- 最长路径：S1 → S2 → S3 → S4 → S5 → S7。
- 关键共享接口：`DetectorStatusRegistry` 的快照契约，被 readiness、guard、audit、metrics 共同消费。

### 风险评分

- S2/S3/S4/S5 为安全准入或跨模块路径，风险 5。
- S1/S6 涉及公共配置/可观测契约，风险 4。
- S7 复用状态快照且不改变决策，风险 3。
- 经验约束：EXP-001 要求生命周期边界清理；EXP-007 要求保留 gRPC sync stub + off-thread。

### 工作量

- S1、S6 含 7 个 TC，按 L 处理但维持单一内聚目标。
- S2～S5、S7 各 3～5 个 TC，按 M 处理。

### 分组理由

- 配置/状态先建立唯一事实源，再接入初始化、readiness 与业务 guard。
- fatal cleanup 与 optional 启动策略拆开，便于分别证明“拒绝启动”和“保留诊断进程”。
- readiness 与业务 guard 分开测试，且 guard 必须独立于负载均衡器。
- 审计与指标分开，避免可观测代码掩盖核心安全决策。

### 并行建议

S4 与 S6 在 S3 后可独立推进，但当前环境采用串行 fallback；每个切片都执行独立 RED→GREEN→REFACTOR 和全量回归。

## Slice Verification Contract

每个切片必须满足：TC-ID 覆盖率 100%、新增测试数 > 0、目标产出真实存在、切片测试与全量回归通过，并把证据写入 `.stdd.yaml` 与 `phase-context.md`。
