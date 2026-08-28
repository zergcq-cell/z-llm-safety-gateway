# Codex-only STDD 本地适配 - 技术设计

## Context

项目已通过根目录 `AGENTS.md` 向 Codex 提供项目规则，但 STDD 阶段 Skill 目前仅以
`.stdd/skills/*.md` 的通用源文件和 Trae/Claude Code/WorkBuddy 平台副本存在。Codex 官方
项目级 Skill 发现路径为 `.agents/skills/<name>/SKILL.md`。

`bin/stdd` 与 `stdd/` 是从上游 STDD v2.9.5 vendored 的固定快照，受
`stdd-v2.9.5.sha256` 和来源契约测试保护。本变更属于项目 overlay 配置，不应通过修改
vendored CLI 伪装成未修改的上游版本。

## Project Principle Check

| 原则 | 本设计如何满足 | 风险或取舍 | 验证方式 |
|------|---------------|-----------|---------|
| Plugin / Flow；核心最小 | 仅修改开发工具 overlay，不进入网关运行时核心 | 不适用于领域插件与 Flow | 路径范围测试与 Git diff 审查 |
| 策略显式；失败不静默 | Codex 是唯一活跃适配；非 Codex 副本必须不存在 | vendored CLI 仍保留上游通用命令，但明确不属于项目 overlay | 目录、文档和 manifest 契约测试 |
| 边界透明；契约稳定 | 保持 Gateway、SDK 和上游 STDD CLI 契约不变 | 原 proposal 中 `stdd install codex` 改为项目级预置适配 | 上游 hash manifest 与完整回归 |
| 决策有证据；数据默认保护 | 结构、frontmatter、引用和移除范围均可由测试复核 | 不采集用户数据，不写用户级 Codex 配置 | pytest、Skill validator、diff 审查 |

## Decisions

### 1. 使用 Codex 项目 overlay，不 fork vendored STDD CLI

**方案**：保持 `bin/stdd`、`stdd/` 和 `stdd-v2.9.5.sha256` 不变；Codex 适配只落在
`AGENTS.md`、`.agents/skills/`、`.stdd/skills/` 和项目模板/文档中。

**为什么**：现有来源测试要求 vendored 文件与固定上游 commit 完全一致。项目环境适配不应
破坏这条供应链证据。

**备选方案及排除原因**：

- 修改 `stdd install` 增加 Codex：会使 vendored manifest 与来源声明失真。
- 更新 manifest 后继续声称上游原版：证据不准确，违反显式失败与可审计原则。

### 2. 使用薄 Skill 入口引用单一正文

**方案**：为七个 STDD Skill 创建 `.agents/skills/stdd-<phase>/SKILL.md`。入口仅包含 Codex
可发现的 frontmatter 和读取对应 `.stdd/skills/<phase>.md` 的强制路由，正文仍只有一份。

**为什么**：既符合 Codex Skill 目录约定，又避免复制整个阶段说明造成版本漂移。

**备选方案及排除原因**：

- 复制完整正文：更新 `.stdd/skills` 时容易遗漏第二份副本。
- Git symlink：在 Windows、归档和部分分发环境中可移植性较弱。
- 重排 `.stdd/skills` 为目录：会扩大变更并破坏现有 STDD 工具假设。

### 3. 项目活跃配置只保留 Codex

**方案**：删除 `.trae/skills/` 和 `.stdd/platforms/` 下的非 Codex 平台快照；更新
`AGENTS.md`、`STDD.md`、`.stdd/skills/spec.md`、`.stdd/skills/upgrade.md` 与
`.stdd/templates/long-range-auth.md` 中的活跃平台说明。

**为什么**：这些文件是当前项目配置副本，而不是不可变的历史证据。删除后可由 Git 历史恢复。

**备选方案及排除原因**：

- 仅忽略旧目录：仍会被维护者误认为受支持入口。
- 删除 archive 中历史文字：会改写已完成 change 的审计证据。

### 4. Codex 权限由运行环境管理

**方案**：长程模式只记录用户流程授权和允许的操作类别，不创建 `.claude/settings.local.json`，
也不写 `~/.codex`。超出当前环境权限的操作按 Codex 运行时机制显式失败或请求用户处理。

**为什么**：Codex 没有与 Claude Code 项目权限文件等价的受支持仓库配置；伪造权限文件既无效
也可能造成错误安全预期。

### 5. 用项目契约测试验证适配

**方案**：新增 `tests/unit/stdd/test_codex_adapter.py`，验证入口集合、frontmatter、正文引用、
非 Codex 路径清理、Codex 原生长程说明和活跃文档一致性；复用现有 vendored manifest 测试。

**为什么**：配置存在不等于 Codex 可消费，必须对目录和内容契约进行可执行验证。

## Architecture

```text
Codex session
  ├─ reads repository AGENTS.md
  └─ discovers .agents/skills/stdd-*/SKILL.md
       └─ routes to .stdd/skills/<phase>.md
            ├─ reads .stdd/config.d/*.yaml
            ├─ reads .stdd/templates/*
            └─ invokes unchanged bin/stdd / stdd package
```

`archive/`、历史 release notes 和 vendored CLI 保持不可变；只有项目活跃 overlay 收敛为 Codex。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 薄入口引用路径错误 | 对每个 Skill 解析目标路径并验证文件存在、版本一致 |
| Codex 只在新 session 扫描 Skill | 用结构测试验证；交付说明提示重新打开 session 做发现验证 |
| 删除旧平台文件影响旧工具用户 | 用户已明确选择 Codex-only；删除范围可由 Git 恢复并在交付记录列明 |
| vendored CLI 帮助仍显示旧平台 | 明确界定为上游通用 CLI，不作为项目活跃配置；manifest 测试禁止静默 fork |
| 长程权限不再自动写配置 | 保留用户预授权与降级规则，由 Codex 运行时执行实际权限控制 |
