# Codex-only STDD 本地适配设计调整说明

> 原始基线：Gate 1 proposal、Phase 2 `design.md` / specs / test-plan
> 调整来源：Gate 2 设计决策与 Phase 5 三路并行审查

## 调整汇总

| # | 调整类型 | 严重程度 | 调整阶段 | 影响 TC | 用户已知 |
|---|---------|---------|---------|---------|---------|
| 1 | CLI 安装目标改为项目 overlay | Major | Phase 2 | TC-CODEX-001～006 | 是，Gate 2 已确认 |
| 2 | upgrade 增加 Codex overlay 事务边界 | Major | Phase 5 | TC-CODEX-002、007 | Gate 3 待确认 |
| 3 | TC-ID 去重并使用组合质量 checkpoint | Major | Phase 5 | TC-CODEX-006～008 | Gate 3 待确认 |

## 调整 1：保持 vendored CLI，不实现 `stdd install codex`

- **原始设计**：Gate 1 proposal 要求 `stdd install codex` 成功，并让非 Codex 平台安装失败。
- **调整内容**：保留上游 v2.9.5 CLI 和 SHA-256 manifest；在项目内预置七个 `.agents/skills` 薄入口，删除活跃非 Codex 副本。
- **调整原因**：修改固定上游快照会使来源声明失真。项目 overlay 能满足 Codex-only 开发环境，同时保持供应链证据。
- **影响范围**：Codex 入口、STDD overlay、TC-CODEX-001～006；不影响 Gateway/SDK runtime。
- **原则影响**：四项原则均加强，无偏离；Gate 2 已明确批准此取舍。

## 调整 2：upgrade 必须保护并原子恢复 Codex overlay

- **原始设计**：上游 upgrade 说明会直接覆盖静态资源，只备份 `.stdd`。
- **调整内容**：先下载到 staging；Codex 定制文件只合并上游通用变化；备份/恢复同时覆盖 `.stdd` 与 `.agents/skills`，并删除失败过程中新增的入口。
- **调整原因**：首轮并行审查发现升级后可能重新出现旧平台说明，第二轮又发现 wrapper 不在回滚集合。
- **影响范围**：`.stdd/skills/upgrade.md`、TC-CODEX-002/007。
- **原则影响**：显式失败、契约稳定和证据完整性得到加强，无原则偏离。

## 调整 3：全仓唯一 TC-ID 与组合质量门

- **原始设计**：新场景复用了既有 `TC-STDD-001～003`，完整质量门被简化为单个 pytest 命令。
- **调整内容**：改为 `TC-CODEX-006～008`；完整质量门使用 `set -euo pipefail` 组合 checkpoint，覆盖 validator、release pytest、Ruff、Mypy 和 diff check。
- **调整原因**：重复 ID 会造成追溯假绿，单个 pytest 不能证明完整质量门。
- **影响范围**：test-plan、slices、agent spec、测试 docstring 和追溯报告。
- **原则影响**：让每项安全决定有真实 checkpoint 证据，无原则偏离。

## 结论

三个调整均已在当前设计边界内解决，不要求重新进入 Phase 2 或重做 Gateway 代码。ADJ-001 已由 Gate 2 批准；ADJ-002/003 随本报告提交 Gate 3 确认。
