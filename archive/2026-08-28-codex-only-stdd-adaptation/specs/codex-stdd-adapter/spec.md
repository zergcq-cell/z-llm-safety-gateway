# Capability: codex-stdd-adapter

## ADDED Requirements

### REQ-CODEX-001：Codex 项目规则入口

项目 SHALL 以根目录 `AGENTS.md` 作为 Codex 项目级规则入口。

#### Scenario: SC-CODEX-001 项目规则可发现

- **GIVEN** Codex 从仓库根目录启动
- **WHEN** Codex 构建项目指令链
- **THEN** 项目 SHALL 提供根目录 `AGENTS.md`，并明确 STDD 强制门、六阶段流程和四项原则检查

### REQ-CODEX-002：项目级 STDD Skills

项目 SHALL 通过 `.agents/skills/` 暴露与 `.stdd/skills/` 一一对应的 Codex Skills，且正文保持单一来源。

#### Scenario: SC-CODEX-002 Skill 集合完整

- **GIVEN** `.stdd/skills/` 包含七个顶层阶段或升级 Skill
- **WHEN** 检查 `.agents/skills/` 的项目级 Skill 集合
- **THEN** 项目 SHALL 提供完全一致的七个 `stdd-*` Skill 目录
- **AND** 每个目录 SHALL 包含 `SKILL.md`

#### Scenario: SC-CODEX-003 Skill 入口有效且无正文复制

- **GIVEN** 一个 `.agents/skills/stdd-<name>/SKILL.md`
- **WHEN** 解析其 YAML frontmatter 和正文引用
- **THEN** 入口 SHALL 使用合法且匹配目录名的 `name` 与可区分的 `description`
- **AND** 入口 SHALL 引用存在的 `.stdd/skills/<name>.md`，且不复制完整阶段正文

### REQ-CODEX-003：Codex 原生权限说明

STDD 长程模式 SHALL 由 Codex 运行环境管理实际权限，不写入其他平台或用户级配置。

#### Scenario: SC-CODEX-004 长程授权不伪造平台权限

- **GIVEN** 用户在 Gate 2 后选择长程模式
- **WHEN** STDD 生成或读取长程授权说明
- **THEN** 项目 SHALL 不创建或要求 `.claude/settings.local.json`，也不修改 `~/.codex`
- **AND** 超出当前权限的操作 SHALL 显式失败或交由 Codex 运行时处理

### REQ-CODEX-004：非 Codex 活跃适配清理

项目 SHALL 不保留非 Codex 平台的活跃适配副本。

#### Scenario: SC-CODEX-005 旧平台目录不存在

- **GIVEN** 当前工作树完成 Codex-only 适配
- **WHEN** 枚举项目活跃平台配置
- **THEN** `.trae/skills/` 和 `.stdd/platforms/` 下非 Codex 快照 SHALL 不存在
- **AND** 历史 archive 和 vendored 上游来源 SHALL 保持不变
