# v0.3.0 里程碑范围定义与 Roadmap 统一测试报告

> 测试日期：2026-08-30
> 测试环境：Linux 7.0.0-30-generic x86_64；Python 3.10.21 / 3.11.16 / 3.12.14；pytest 9.1.1
> 被测基线：`0c3b876` + 当前授权工作区 diff

## 一、总体概况

| 指标 | 数值 |
|------|------|
| 主质量门用例 | 1091（含 1 skipped） |
| 通过 | 1090 |
| 失败 | 0 |
| 跳过 | 1 |
| 通过率 | 100%（按已执行用例） |
| 执行耗时 | 79.15 秒 |
| 运行时覆盖率 | 93.34%（门槛 90%） |

### 1.1 覆盖率诊断（仅变更文件）

本 change 只修改 Markdown 和文档契约测试，没有运行时源码变更；pytest-cov 的目标是
`src/z_llm_safety_gateway`，因此变更文件行/分支覆盖率不适用。完整运行时覆盖率 93.34%，无新增
低覆盖运行时文件。

## 二、按模块统计

| 测试模块 | 用例数 | 通过 | 失败 | 跳过 | 说明 |
|----------|--------|------|------|------|------|
| Documentation contract | 22 | 22 | 0 | 0 | 12 个新 TC 及既有文档契约 |
| Canonical agent checkpoints | 8 actions / 12 targets | 全部 | 0 | 0 | 两份 agent spec 均实际执行 |
| 主质量门（含 examples） | 1091 | 1090 | 0 | 1 | coverage 93.34% |
| Python 3.10 矩阵 | 1085 | 1084 | 0 | 1 | coverage 93.34% |
| Python 3.11 矩阵 | 1085 | 1084 | 0 | 1 | coverage 92.47% |
| Python 3.12 矩阵 | 1085 | 1084 | 0 | 1 | coverage 93.34% |

## 三、E2E 测试结果

项目配置 `quality.e2e.enabled: false`，本 documentation change 不改变运行时用户路径，因此 E2E
按配置跳过，不作为 Gate 3 缺口。

## 四、失败项详细分析

最终质量门无失败。Python 3.10 首次无插桩矩阵曾在 `TC-PE-003` 报告 1162 req/s，命中既有
EXP-2026-0011 的共享宿主微基准假失败模式。没有修改性能规格或门槛；改用项目正式 coverage
同构命令后 1084 passed / 1 skipped，且该用例按自身契约在插桩环境不比较无插桩吞吐基线。

## 五、功能/测试覆盖对照

| 功能模块 | 涉及文件 | 测试覆盖 | 缺失测试 |
|----------|----------|----------|----------|
| Roadmap 权威与版本语义 | `DESIGN.md`、`AGENTS.md` | TC-RMAP-001–004 | 无 |
| v0.3.0 范围、拆分与候选分类 | `DESIGN.md` | TC-RMAP-005–008 | 无 |
| 次级文档一致性 | `README.md`、`CHANGELOG.md`、`AGENTS.md` | TC-DOCS-014–015、017 | 无 |
| 产品与历史边界 | 文档契约测试 | TC-DOCS-016、TC-RMAP-008 | 无 |

## 五-B、多路并行 Review 结果

### Review 迭代历史

| 轮次 | C | H | M | L | 状态 |
|------|---|---|---|---|------|
| 1 | 0 | 1 | 7 | 4 | 自动修复并复审 |
| 2 | 0 | 1 | 4 | 4 | 自动修复归档生命周期与边界门 |
| 3 | 0 | 0 | 1 | 0 | 唯一 M 收窄历史路径后定向复核通过 |
| 最终 | 0 | 0 | 0 | 0 | 通过 |

### Review 已修复问题

| # | 严重性 | 问题 | 状态 |
|---|--------|------|------|
| 1 | H | 活跃源码旧 `v0.3.0` 标签未被当前 Roadmap 分类 | 已分类并由 TC-RMAP-007 验证 |
| 2 | H | checkpoint 元测试在 Phase 6 归档后必然失败 | 支持 `changes/` / `archive/` 恰一定位 |
| 3 | M | Git diff 边界遗漏未跟踪文件 | 改用 `git status --porcelain=v1` |
| 4 | M | 历史保护只有字符串存在性、范围一度过宽 | 限定 10 个既有历史路径并持久验证 |
| 5 | M | 分类只校验 category，未校验 Roadmap meaning | 三列精确映射，延后项不得承诺版本 |
| 6 | M | design adjustment capability 名称错误 | 统一为 `project-docs` |

### 已知限制与后续项

活跃 runtime docstrings/comments 以及两个 legacy config tests 仍保留内部实现时期的 `v0.3.0`
标签。本 change 的授权范围不包含运行时代码；它们已被明确分类并作为迁移期 guardrail 监测，
不代表公开 v0.3.0 已交付。建议在独立 STDD cleanup change 或首个 v0.3.0 实施 change 中清理，
届时同步更新该迁移期契约。

## 六、设计调整说明

Phase 5 新增 1 项 minor `boundary_discovery`：将活跃源码/legacy 测试中的旧内部版本标签纳入
当前分类与验证，但不越权修改运行时代码；无需重新 Spec 或 Build。详见
[`design-adjustments.md`](design-adjustments.md)。

## 七、十二类失败模式检查

| 类别 | 结论与证据 | 状态 |
|------|------------|------|
| (a) 幻觉路径 | Markdown 链接、checkpoint targets、历史路径均实际解析/收集 | 通过 |
| (b) 范围蔓延 | tracked 产品 diff 仅 5 个授权文件；runtime/config/API/version 无变化 | 通过 |
| (c) 级联错误 | 无异常或运行时改动；全量与多版本回归通过 | 通过 |
| (d) 设计偏离 | 1 项 minor 边界发现已记录，无静默偏离 | 通过 |
| (e) 工具误用 | 使用项目 CLI、pytest、Ruff、Mypy 与只读 Git 检查 | 通过 |
| (f) 运行时行为偏差 | 无运行时 diff；1090 项主质量门通过 | 通过 |
| (g) 管线断链 | DESIGN→README/CHANGELOG/AGENTS 与 8 个 checkpoints 全部连通 | 通过 |
| (h) 内容质量偏差 | 版本分类三列精确校验，旧标签显式说明 | 通过 |
| (i) 指令遗漏 | Phase 1–5、三轮 review、全量门和 Gate 约束均执行 | 通过 |
| (j) 覆盖真空 | 12/12 TC 唯一且可收集，两个 capability 均有验证 | 通过 |
| (k) 契约断层 | 权威/次级文档、历史与产品边界均有持久契约 | 通过 |
| (l) 锚定不足 | L2 锚定到既有 archive、canonical、merged specs 与 Release Notes | 通过 |

## 七-B、经验库更新

本次无新增经验；复用 EXP-2026-0011（宿主微基准）、EXP-2026-0019（发布状态不可压平）和
EXP-2026-0022（TC-ID/checkpoint 真实性）。经验库总计 24 条。

## 七-C、项目原则复核

| 原则 | 实际结果与证据 | 状态 |
|------|---------------|------|
| Plugin / Flow；核心最小 | 仅文档治理和契约测试，无 plugin、Flow 或 core 运行时改动 | 通过 |
| 策略显式；失败不静默 | 规划状态、进入/完成条件、延期语义、旧标签限制均显式记录 | 通过 |
| 边界透明；契约稳定 | 单一权威 Roadmap；runtime/config/API/version 与历史证据受边界门保护 | 通过 |
| 决策有证据；数据默认保护 | 12 TC、8 checkpoints 和发布证据可审计；不新增数据收集 | 通过 |

原则取舍：仅 DA-001 所述授权边界取舍；无原则偏离。

## 八、结论

Phase 5 质量门通过，可提交 Gate 3。该 change 只定义和统一公开 v0.3.0 Roadmap，不交付、
部署或发布多租户运行时能力。Gate 3 确认前不进入 Deliver，也不执行 Git 交付。

| 信号源 | 状态 | 备注 |
|--------|------|------|
| 单元/集成测试 | 通过 | 1090 passed / 1 skipped |
| E2E | N/A | 配置禁用；本 change 无运行时路径 |
| Lint | 通过 | Ruff |
| 类型检查 | 通过 | Mypy 99 source files |
| 多版本测试 | 通过 | Python 3.10 / 3.11 / 3.12 |
| 覆盖率 | 通过 | 主质量门 93.34%，门槛 90% |
| 十二类失败模式 | 通过 | 12/12 已检查，0 未解决 |

### Phase 6 交付后复验补充

归档合并暴露 DA-002：累积式 `specs/project-docs/spec.md` 不能同时被正常追加并要求 Git 完全
干净。契约已改为验证既有 REQ-DOCS-011/012/013 的语义保留，不可变历史路径仍使用 Git
status 保护。该修正不改变 Gate 3 已确认的产品范围；交付后质量门结果记录在 `.stdd.yaml`。
