# Codex-only STDD 本地适配测试方案

> 版本：configuration change 2026-08-28
> 创建日期：2026-08-28
> 对应 Phase 2 Spec：`codex-stdd-adapter/spec.md`、`stdd-platform-installation/spec.md`

## 一、测试策略

### 1.1 测试金字塔

以快速配置契约测试为主：单元层验证文件集合、frontmatter、正文路由和禁用路径；集成层执行
真实 STDD CLI manifest 契约和完整项目质量门；Codex 新 session 的发现行为作为交付冒烟。

### 1.2 测试原则

- 每个 Scenario 至少对应一个稳定、可执行的 checkpoint；文件契约使用 pytest 节点，完整质量门使用失败即停止的组合命令并在测试报告留证。
- 对目录和文件集合做精确比较，空集合不得通过。
- 活跃 overlay 扫描明确排除 archive、发布历史和 vendored CLI，避免改写历史证据。
- 先写失败测试，再实施配置变更；删除范围必须可由 Git diff 审计。

### 1.3 已有测试资产

| 测试文件 | 用例数 | 类型 | 覆盖范围 |
|----------|--------|------|----------|
| `tests/unit/stdd/test_cli_recovery.py` | 3 | 单元/契约 | 上游来源、manifest、CLI help/status |
| `tests/unit/stdd/test_agent_spec_checkpoints.py` | 多项 | 契约 | Agent checkpoint 文件和测试节点真实性 |
| `tests/unit/release/test_documentation_contract.py` | 多项 | 文档契约 | 活跃文档一致性和发布事实 |

## 二、详细测试案例

### 功能 1：Codex 项目级适配

#### 案例 1.1 — 项目规则可发现

| 字段 | 内容 |
|------|------|
| **ID** | TC-CODEX-001 |
| **对应 Spec** | codex-stdd-adapter/spec.md → Scenario: SC-CODEX-001 |
| **优先级** | P0 |
| **预置条件** | 从仓库根读取项目配置 |
| **输入** | 解析 `AGENTS.md` |
| **预期结果** | 文件存在并包含 STDD Gate、六阶段和四项原则入口 |
| **当前状态** | ✅ 已覆盖 |

#### 案例 1.2 — Skill 集合完整

| 字段 | 内容 |
|------|------|
| **ID** | TC-CODEX-002 |
| **对应 Spec** | codex-stdd-adapter/spec.md → Scenario: SC-CODEX-002 |
| **优先级** | P0 |
| **预置条件** | `.stdd/skills` 包含七个顶层 Skill |
| **输入** | 枚举 `.agents/skills` |
| **预期结果** | 七个名称精确一致且每个目录都有 `SKILL.md` |
| **当前状态** | ✅ 已覆盖 |

#### 案例 1.3 — Skill 入口合法

| 字段 | 内容 |
|------|------|
| **ID** | TC-CODEX-003 |
| **对应 Spec** | codex-stdd-adapter/spec.md → Scenario: SC-CODEX-003 |
| **优先级** | P0 |
| **预置条件** | Codex Skill 薄入口已生成 |
| **输入** | 解析 frontmatter 和正文引用 |
| **预期结果** | 名称合法、引用目标存在且没有复制完整正文 |
| **当前状态** | ✅ 已覆盖 |

#### 案例 1.4 — Codex 原生权限边界

| 字段 | 内容 |
|------|------|
| **ID** | TC-CODEX-004 |
| **对应 Spec** | codex-stdd-adapter/spec.md → Scenario: SC-CODEX-004 |
| **优先级** | P0 |
| **预置条件** | 长程模式模板与 Phase 2 Skill 存在 |
| **输入** | 扫描权限配置说明 |
| **预期结果** | 不要求其他平台权限文件或用户级 Codex 写入，运行时边界明确 |
| **当前状态** | ✅ 已覆盖 |

#### 案例 1.5 — 非 Codex 适配清理

| 字段 | 内容 |
|------|------|
| **ID** | TC-CODEX-005 |
| **对应 Spec** | codex-stdd-adapter/spec.md → Scenario: SC-CODEX-005 |
| **优先级** | P0 |
| **预置条件** | Codex-only 适配完成 |
| **输入** | 枚举活跃平台目录 |
| **预期结果** | Trae 与其他非 Codex 项目适配副本不存在 |
| **当前状态** | ✅ 已覆盖 |

### 功能 2：STDD overlay 与上游边界

#### 案例 2.1 — Vendored manifest 完整

| 字段 | 内容 |
|------|------|
| **ID** | TC-CODEX-006 |
| **对应 Spec** | stdd-platform-installation/spec.md → Scenario: SC-STDD-001 |
| **优先级** | P0 |
| **预置条件** | 固定来源 manifest 存在 |
| **输入** | 执行现有 manifest 契约测试 |
| **预期结果** | 所有 vendored 文件 hash 完全一致 |
| **当前状态** | ✅ 已覆盖 |

#### 案例 2.2 — 活跃 overlay 文档一致

| 字段 | 内容 |
|------|------|
| **ID** | TC-CODEX-007 |
| **对应 Spec** | stdd-platform-installation/spec.md → Scenario: SC-STDD-002 |
| **优先级** | P1 |
| **预置条件** | 排除 archive 和 vendored CLI |
| **输入** | 扫描项目活跃 STDD overlay 文档 |
| **预期结果** | 只描述 Codex 项目入口和权限边界 |
| **当前状态** | ✅ 已覆盖 |

#### 案例 2.3 — 完整质量门

| 字段 | 内容 |
|------|------|
| **ID** | TC-CODEX-008 |
| **对应 Spec** | stdd-platform-installation/spec.md → Scenario: SC-STDD-003 |
| **优先级** | P1 |
| **预置条件** | 全部配置、测试和文档修改完成 |
| **输入** | 执行 Skill validator、Ruff、Mypy、pytest 和 diff 检查 |
| **预期结果** | 所有强制检查通过且无范围外改动 |
| **当前状态** | ✅ 已覆盖（Phase 5 checkpoint） |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 集成测试 | E2E/冒烟 | 状态 |
|----------|----------|----------|-----------|------|
| Codex 项目规则入口 | 文件内容契约 | — | 新 session 指令发现 | 🟢 |
| Codex Skills | 集合/frontmatter/引用 | Skill validator | 新 session Skill 发现 | 🟢 |
| 非 Codex 清理 | 路径不存在契约 | Git diff 审查 | — | 🟢 |
| Vendored CLI 边界 | manifest 契约 | CLI help/status | — | 🟢 |
| 项目质量门 | Ruff/Mypy | 完整 pytest/coverage | — | 🟢 |

## 四、回归风险矩阵

| 风险区域 | 本次改动 | 已有回归保护 | 风险等级 |
|----------|----------|--------------|----------|
| `.agents/skills` | 新增七个薄入口 | 新增集合、frontmatter、引用测试 | 中 |
| `.stdd/skills` 与模板 | 移除旧平台权限说明 | 新增活跃文档扫描 | 中 |
| `.trae` / `.stdd/platforms` | 删除非 Codex 副本 | 精确路径测试 + Git 恢复 | 中 |
| `bin/stdd` / `stdd/` | 不应修改 | SHA-256 manifest 测试 | 高 |
| Gateway/SDK runtime | 无计划改动 | 完整测试、Ruff、Mypy、覆盖率 | 低 |

## 五、建议补充顺序

1. **第一优先**：先完成全部 P0 案例，锁定 Codex overlay 和上游边界。
2. **第二优先**：再完成全部 P1 案例，验证文档一致性与全量回归。
3. **第三优先**：交付后从新 Codex session 验证 Skill 实际发现，并记录结果。
