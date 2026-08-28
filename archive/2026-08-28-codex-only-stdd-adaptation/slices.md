# Codex-only STDD 本地适配切片

## 依赖图

`codex-stdd-adapter` 与 `stdd-platform-installation` 均无规格级前置依赖。实现上采用两个串行切片，先建立可执行的 Codex 入口契约，再收敛活跃文档和质量门，避免文档测试在入口未落地时产生混杂失败。

## S1 — Codex 项目入口与旧适配清理

- **优先级**：P0
- **依赖**：无
- **覆盖场景**：SC-CODEX-001～005、SC-STDD-001
- **测试映射**：TC-CODEX-001～006；其中 TC-CODEX-006 复用 vendored manifest 测试节点
- **RED 证据**：新增五个 pytest 节点必须在实现前因入口缺失、旧路径存在或旧权限说明而失败
- **GREEN 边界**：只修改项目 overlay；不得修改 `bin/stdd`、`stdd/`、manifest 或运行时网关代码
- **原则检查**：薄入口保持核心最小；路径与权限策略显式；上游契约稳定；删除和引用都有测试证据

## S2 — 活跃 overlay 一致性与完整质量门

- **优先级**：P1
- **依赖**：S1
- **覆盖场景**：SC-STDD-002～003
- **测试映射**：TC-CODEX-007～008
- **RED 证据**：新增活跃文档扫描必须先因旧平台入口文字而失败
- **GREEN 边界**：只更新活跃项目说明，排除 archive、历史 release notes 和 vendored CLI
- **原则检查**：平台策略单一且显式；历史与上游边界透明；全量质量门保留可复核证据

## 验收顺序

`S1 RED → S1 GREEN/REFACTOR → S1 回归 → S2 RED → S2 GREEN/REFACTOR → 全量验证 → Gate 3`
