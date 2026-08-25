# v0.2.2 发布可复现性切片执行计划

## Dependency Graph Summary

CLI 依赖图：3 个 capability、0 条边、0 个循环；`github-setup`、`project-docs`、
`release-hardening` 均为零依赖节点。实现层为避免两个切片同时修改 Release workflow，增加一条
手工集成依赖：最终 workflow 集成在锁、校验器与版本 notes 就绪后执行。

```text
S1 Release lock / Node 24 ─┐
S2 Validator / evidence ───┼──► S4 Draft-first workflow integration
S3 Versions / docs ────────┘
```

**并行化说明**：

- 并行组 1：S1、S2、S3 在 capability 图上均无依赖。
- 本次由单一工作区串行执行 S1 → S2 → S3，以避免共享测试文件冲突；不改变依赖结论。
- 并行组 2：S4 依赖 S1～S3 的稳定输入、校验器与 release notes。

## Slice Execution Plan

| # | 优先级 | 风险 | 工作量 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|--------|--------|---------|---------|------|
| S1 | P0 | 高（5/5） | M | 1 | TC-REL-018、TC-GH-008、TC-GH-009 | `requirements/release-tools.*`、Action SHA allowlist、Dependabot/维护契约 | 无 |
| S2 | P0/P1 | 高（5/5） | M | 1 | TC-REL-021～TC-REL-025 | `tools/release_checks.py` 的 exact payload/ref/absence/evidence 纯边界与远程检查点 | 无 |
| S3 | P0/P1 | 中（3/5） | M | 1 | TC-DOCS-011～TC-DOCS-013 | Gateway 0.2.2 / SDK 0.1.1 表面、兼容矩阵、真实路线图和隔离 notes | 无 |
| S4 | P0/P1 | 高（5/5） | M | 2 | TC-REL-019、TC-REL-020、TC-GH-010、TC-GH-011 | release workflow 的 hash install、no-isolation、draft-first、最小权限、evidence artifact 与本地 checkpoint | S1、S2、S3 |

## Rationale

### S1：Release lock 与 Node 24 Action 锚点

- **依赖关系**：无；为下游 workflow 提供受控工具输入和官方 Action 锚点。
- **风险分析**：Action major 变化与传递依赖漂移均影响跨系统供应链；命中 EXP-2026-0004 的完整质量门风险。
- **工作量估算**：3 个 TC，涉及 requirements、两个 workflows、Dependabot 与契约测试，为 M。

### S2：Release 校验器与 evidence

- **依赖关系**：纯确定性判断与网络采集分离，可独立于 workflow 先实现；S4 负责接线。
- **风险分析**：错误分类可能把认证/网络失败误当作不存在，或公开错误资产；命中 EXP-2026-0015、EXP-2026-0016。
- **工作量估算**：5 个 TC，集中在工具模块和测试 fixture；远程 TC 仅建立交付检查点，为 M。

### S3：Gateway/SDK 版本与路线图

- **依赖关系**：无；S4 创建 Release 前需要稳定的 0.2.2 notes 和四资产名称。
- **风险分析**：最大风险是全仓替换误改 SDK/历史；角色化表面和负向契约可控，为中风险。
- **工作量估算**：3 个 TC、多个文档/metadata 表面，为 M。

### S4：Draft-first workflow 集成

- **依赖关系**：消费 S1 lock/Action pins、S2 校验器与 S3 notes/version；位于关键路径末端。
- **风险分析**：公开状态机、权限、digest 和 evidence 顺序错误会产生不可逆发布影响；命中 EXP-2026-0004、0014～0016。
- **工作量估算**：4 个 TC，但需要 workflow、构建、checkpoint 与全量集成验证，为 M。

## Phase 3 Principle Check

1. **Plugin / Flow**：切片只修改发布基础设施、工具与文档，不进入插件、Flow 或 runtime 核心。
2. **显式策略 / 失败**：S2/S4 独立覆盖 absence、draft、publish、evidence 失败路径，无静默 fallback。
3. **透明边界 / 契约**：S1/S3/S4 保持四资产、Gateway/SDK 独立版本和全部运行时边界。
4. **证据 / 数据**：S2 先定义白名单 evidence，S4 再接线，确保记录公开元数据且保留期有界。

**原则取舍或偏离**：无。
