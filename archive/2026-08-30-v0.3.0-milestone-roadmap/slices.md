# v0.3.0 里程碑范围定义与 Roadmap 统一切片执行计划

## Dependency Graph Summary

CLI dependency graph：2 个零依赖 Capability、0 条边、0 个循环。实现层增加“次级文档依赖
权威 Roadmap”的顺序约束。

```text
milestone-scope-governance ──> S1 权威范围与分类 ──┐
                                                   ├─> S3 边界与全量回归
project-docs ─────────────────> S2 次级文档同步 ───┘
                                  ^
                                  └── 依赖 S1 的稳定摘要
```

**并行化说明**：

- CLI 认为两个 Capability 均可并行。
- 实际执行不并行修改同一个文档契约测试文件；S1 先稳定 DESIGN 语义，S2 再同步次级表面。
- S3 依赖 S1、S2 完成。

## Slice Execution Plan

| # | 优先级 | 风险 | 工作量 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|--------|--------|---------|---------|------|
| S1 | P0 | 高（4/5） | M | 1 | TC-RMAP-001/003/005/006/007 | DESIGN 权威范围、候选分类、AGENTS 版本语义与 RED/GREEN 契约 | 无 |
| S2 | P0/P1 | 中（3/5） | M | 2 | TC-RMAP-002/004/008、TC-DOCS-014/015 | README/CHANGELOG 有界摘要、历史保护与次级一致性 | S1 |
| S3 | P0/P1 | 中（3/5） | S | 3 | TC-DOCS-016/017 | 产品契约负向边界、helper 重构、checkpoint 与全量质量门 | S1、S2 |

## Rationale

### S1：权威范围与候选分类（P0，关键路径）

- **依赖关系**：无；它定义所有次级文档消费的规范文本。
- **风险分析**：8 个 milestone Scenario 中有 5 个进入本切片，且命中 EXP-2026-0019 的
  高风险发布事实模式；AGENTS 与 DESIGN 跨两个当前表面，因此风险 4/5。
- **工作量估算**：5 个 TC，修改测试、DESIGN、AGENTS 三个文件，为 M。

### S2：次级文档同步与历史保护（P0/P1，依赖 S1）

- **依赖关系**：README 和 CHANGELOG 必须引用 S1 已稳定的主题、状态与锚点。
- **风险分析**：历史引用不可批量改写，且次级表面可能形成第二路线图；现有 release contract
  提供部分保护，风险 3/5。
- **工作量估算**：5 个 TC，修改测试、README、CHANGELOG，为 M。

### S3：产品边界与全量回归（P0/P1，最终汇合）

- **依赖关系**：需要 S1/S2 的完整 diff 才能验证允许路径和产品表面未变化。
- **风险分析**：命中 EXP-2026-0022 的 checkpoint/TC-ID 假覆盖风险；通过 AST、collect-only
  和 agent action 交叉核对，风险 3/5。
- **工作量估算**：2 个 TC，加一次 helper 重构与全量质量门，为 S。
