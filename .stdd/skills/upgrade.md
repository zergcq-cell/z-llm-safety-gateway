---
name: stdd-upgrade
description: "STDD 技能层升级 — 同步项目 .stdd/ 快照与全局技能版本，无需 Python CLI"
stdd_version: "2.9.5"
---
# STDD Upgrade — 技能层版本同步

## 阶段目标

无需 Python CLI，通过 AI 对话将项目的 `.stdd/` 静态资源同步到与当前技能一致的最新版本。解决 GitHub Issue #5 报告的版本漂移问题。

## 前置条件

- 项目已初始化 STDD（存在 `.stdd/` 目录）
- 网络可访问 GitHub（`https://raw.githubusercontent.com/leonai42/stdd/master/`）

## 执行流程

### Step 1: 版本检查

1. 读取项目 `.stdd/version.yaml`
2. 显示当前项目版本和技能版本
3. 如果项目版本 >= 技能版本：提示"项目已是最新版本"，询问是否仍要强制同步
4. 如果项目版本 < 技能版本：确认升级

### Step 2: Codex overlay 检测

检查项目级 Codex 入口是否完整：

- 根目录 `AGENTS.md` 存在并声明 STDD 强制门和项目原则
- `.agents/skills/stdd-<phase>/SKILL.md` 覆盖全部顶层 `.stdd/skills/<phase>.md`
- 每个入口包含合法 frontmatter，并引用对应的单一正文源文件

任何入口缺失、重复正文或引用失效都必须显式报告，不得以空集合通过。

### Step 3: 备份当前版本

1. 创建备份目录：`.stdd/backup/<old_version>-<timestamp>/`
2. 复制当前 `.stdd/skills/`、`.stdd/templates/`、`.stdd/config.d/`、`.stdd/version.yaml` 到备份目录
3. 备份 `.agents/skills/` 到同一备份目录，并记录同步前入口集合；空集合也必须显式记录

### Step 4: 同步静态资源

先把 GitHub raw 文件拉取到 `.stdd/upgrade-staging/<new_version>/`，校验完整性后再同步。以下 Codex 项目 overlay 文件不得直接被上游版本覆盖：

- `.stdd/skills/spec.md`
- `.stdd/skills/upgrade.md`
- `.stdd/templates/long-range-auth.md`

对这三个文件只合并上游通用流程变化，并保留 Codex 权限边界、薄入口与单平台策略。其他静态资源可以从暂存目录同步到项目 `.stdd/`：

**技能文件**（拉取自 `.stdd/skills/`）：
- `understand.md`、`spec.md`、`slice.md`、`build.md`、`verify.md`、`deliver.md`
- `_shared/confirm-gate.md`、`_shared/version-check.md`、`_shared/mode-selection.md`、`_shared/long-range-auth.md`
- `upgrade.md`

**配置文件**（拉取自 `.stdd/config.d/`）：
- `gates.yaml`、`quality.yaml`、`long_range.yaml`、`lite.yaml`、`experience.yaml`
- `project.yaml`：**特殊处理** — 覆盖时保留 `project` 和 `paths` 字段的原有值

**模板文件**（拉取自 `.stdd/templates/` 和 `.stdd/templates/canonical/`）

**GitHub Raw URL 模式**：
```
https://raw.githubusercontent.com/leonai42/stdd/master/.stdd/skills/<filename>
https://raw.githubusercontent.com/leonai42/stdd/master/.stdd/config.d/<filename>
https://raw.githubusercontent.com/leonai42/stdd/master/.stdd/templates/<filename>
https://raw.githubusercontent.com/leonai42/stdd/master/.stdd/templates/canonical/<filename>
```

### Step 5: 更新版本标记

更新 `.stdd/version.yaml`：
```yaml
stdd_version: "<new_version>"
upgraded_at: "<current_iso_timestamp>"
```

### Step 6: 同步 Codex Skill 薄入口

对 `.stdd/skills/` 下每个顶层阶段文件同步项目入口：

1. 目标路径为 `.agents/skills/stdd-<phase>/SKILL.md`
2. 入口只包含 `name`、`description` frontmatter 和读取 `../../../.stdd/skills/<phase>.md` 的强制路由
3. 不复制阶段正文，不写用户级 Codex 配置，不修改 vendored CLI 或来源 manifest
4. 运行 Codex Skill validator 和项目契约测试；任何失败必须显式报告
5. 如果同步、合并或验证失败，原子恢复 Step 3 的 `.stdd/` 资源并恢复 `.agents/skills/`，同时精确删除同步中新出现的多余入口；保留失败日志，不得留下部分升级状态
6. 验证成功并完成一次性切换后清理暂存目录；失败回滚完成后也清理暂存目录

### Step 7: 输出升级摘要

```
✅ STDD 升级完成
  项目版本: <old_version> → <new_version>
  同步文件: <N> 个
  同步入口: .agents/skills/stdd-*/SKILL.md
  备份位置: .stdd/backup/<old_version>-<timestamp>/
```

## 错误处理

| 场景 | 处理 |
|------|------|
| GitHub raw 不可达（超时/403） | 提示网络错误，提供手动下载 URL：`https://github.com/leonai42/stdd` |
| `.stdd/` 目录不存在 | 提示"当前项目未初始化 STDD，请先运行 stdd init" |
| 项目已锁定 | 提示"项目已锁定在版本 X.X.X，使用 stdd upgrade --unlock 解锁后再升级" |

## 产出物

- 更新后的 `.stdd/skills/`、`.stdd/templates/`、`.stdd/config.d/`
- `.stdd/version.yaml`（版本号和时间戳更新）
- `.stdd/backup/<old_version>-<timestamp>/`（升级前备份）
- 同步后的 Codex Skill 薄入口

## 质量检查

完成前确认：
- [ ] 所有拉取的文件成功写入
- [ ] `.stdd/version.yaml` 版本号正确更新
- [ ] 备份目录包含升级前的文件快照
- [ ] Codex Skill 入口 frontmatter 合法且引用目标存在
- [ ] Codex Skill 入口未复制完整阶段正文
