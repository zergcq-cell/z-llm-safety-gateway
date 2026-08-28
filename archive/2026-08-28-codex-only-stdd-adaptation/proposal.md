# Codex-only STDD 本地适配

<!-- canonical: canonical/proposals/2026-08-28-codex-only-stdd-adaptation.yaml | source_hash: 3d1ba5b9372e2607 -->

## Why

当前仓库同时保留 Trae、Claude Code、WorkBuddy、Cursor 和 OpenCode 等平台适配，
但当前开发环境只使用 Codex。重复的平台副本容易产生版本漂移，而本地 STDD 安装器尚未
提供 Codex 原生的 `.agents/skills/` 目标。

## What Changes

- 保留根目录 `AGENTS.md` 作为 Codex 项目级规则入口。
- 以 `.agents/skills/<skill-name>/SKILL.md` 提供 Codex 项目级 STDD Skills，并复用
  `.stdd/skills/` 的单一权威内容。
- 删除 `.trae/skills/` 及 `.stdd/platforms/` 下非 Codex 平台适配副本。
- 将本项目 STDD 安装器收敛为 Codex 目标，旧平台请求明确失败。
- 更新相应测试和 STDD 使用文档。

## Capabilities

### New Capabilities

- **codex-stdd-adapter**：Codex 可从项目级 `.agents/skills/` 原生发现并加载 STDD 阶段 Skills。

### Modified Capabilities

- **stdd-platform-installation**：本项目的 STDD 平台安装目标从多平台收敛为 Codex-only。

## Impact

**代码层面**：

- STDD 平台安装器及其测试，预计涉及 3–8 个逻辑文件。

**配置层面**：

- 新增 `.agents/skills/`；移除 `.trae/skills/` 和非 Codex 平台快照；同步项目说明。

**基础设施**：

- 不修改 `~/.codex` 全局配置，不新增外部服务或凭据。

## Constraints

- 遵循 Codex 官方的 `AGENTS.md` 和 `.agents/skills/<name>/SKILL.md` 发现约定。
- `.stdd/skills/` 保持为 STDD 流程内容的单一权威来源，避免复制后漂移。
- 不改变 STDD 六阶段、三道 Gate、TDD 或四项项目原则。
- 删除内容均为 Git 跟踪文件，可通过版本历史恢复。

## Stakeholders

- 使用 Codex 开发本项目的维护者。
- 维护本项目内嵌 STDD 工具链的贡献者。

## Risk Areas

- capability: codex-stdd-adapter — Codex Skill 目录或 frontmatter 不正确会导致 Skill 无法发现；使用官方目录约定和 Skill validator 验证。
- capability: stdd-platform-installation — 收窄平台契约会让旧平台安装命令失效；通过帮助信息、非零退出和测试显式表达。
- capability: codex-stdd-adapter — 符号链接在部分打包或平台上可能丢失；在 Spec 阶段确认 Git、Codex 扫描和分发契约。

## NonGoals

- 不修改网关运行时、API、Provider、Flow、Pipeline、检测器或 SDK 行为。
- 不修改用户级 `~/.codex` 配置或其他项目。
- 不在本 change 中重写产品 roadmap；roadmap 盘点另行记录。

## Critical

- [x] 非关键变更（默认）
- [ ] 关键变更 — 涉及安全/金融/核心基础设施，需 L3/L4 锚定

## Risk Assessment

- **safety_critical**：false
- **financial**：false
- **cross_system**：false

## Anchoring

- **level**：L1
- **reference_changes**：无
- **anchor_implementations**：`AGENTS.md`、`.stdd/skills/`、`stdd/cli/commands/install.py`

## Project Principle Check

1. **Plugin / Flow**：仅修改开发工具适配，不涉及领域能力、Flow 组合或运行时核心。
2. **显式策略 / 失败**：Codex 是唯一支持目标；旧平台请求必须明确失败，不做静默兼容。
3. **透明边界 / 稳定契约**：有意收窄的是本地 STDD 安装器的平台契约；网关和 SDK 契约保持不变。
4. **证据 / 数据保护**：不收集用户内容或敏感数据；通过测试、validator 和 STDD 报告保留验证证据。

**原则取舍或偏离**：无。

## Success Criteria

- [ ] Codex 能从根目录 `AGENTS.md` 和项目级 `.agents/skills/` 加载 STDD 规则与 Skills。
- [ ] `python bin/stdd install codex --dry-run` 成功并显示 `.agents/skills/` 目标。
- [ ] 非 Codex 平台不再作为本项目支持目标，相关请求明确返回失败。
- [ ] 仓库不再包含 `.trae/skills/` 或其他非 Codex 平台适配副本。
- [ ] Codex Skills 通过结构校验，且不会复制出第二份易漂移的 STDD 正文。
- [ ] STDD CLI、Ruff、Mypy 和完整测试通过。
