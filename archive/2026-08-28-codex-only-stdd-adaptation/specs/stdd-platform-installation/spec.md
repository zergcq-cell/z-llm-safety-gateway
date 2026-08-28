# Capability: stdd-platform-installation

## MODIFIED Requirements

### REQ-STDD-001：Vendored CLI 来源完整性

Codex-only 项目适配 SHALL 不修改固定来源的 `bin/stdd`、`stdd/` 或其 SHA-256 manifest。

#### Scenario: SC-STDD-001 上游 manifest 保持有效

- **GIVEN** 项目固定了 STDD v2.9.5 的上游 commit 和文件 hash
- **WHEN** 执行 vendored manifest 契约测试
- **THEN** 所有 vendored 文件 SHALL 与 manifest 完全一致
- **AND** 项目 SHALL 不以更新 hash 的方式掩盖本地 fork

### REQ-STDD-002：活跃 overlay 文档一致

项目活跃 STDD 文档和 Skill SHALL 只指导 Codex，不宣告其他平台为当前项目入口。

#### Scenario: SC-STDD-002 活跃说明不包含旧平台配置

- **GIVEN** 历史 archive 与 vendored CLI 被排除在项目 overlay 扫描之外
- **WHEN** 扫描 `AGENTS.md`、`STDD.md`、`.stdd/skills/` 和 `.stdd/templates/`
- **THEN** 活跃说明 SHALL 不包含 Claude Code、Trae、WorkBuddy、Cursor 或 OpenCode 配置步骤
- **AND** Codex 的 `AGENTS.md`、`.agents/skills/` 和运行时权限边界 SHALL 明确

### REQ-STDD-003：质量门与可恢复性

Codex-only 适配 SHALL 通过项目质量门，且删除的旧平台文件可由 Git 历史恢复。

#### Scenario: SC-STDD-003 完整验证通过

- **GIVEN** Codex-only 配置、测试和文档变更完成
- **WHEN** 执行 Skill 结构校验、STDD 契约测试、Ruff、Mypy 和完整 pytest
- **THEN** 所有强制检查 SHALL 通过
- **AND** Git diff SHALL 只包含已批准范围
