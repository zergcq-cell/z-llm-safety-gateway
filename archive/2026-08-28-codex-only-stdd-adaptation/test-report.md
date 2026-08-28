# Codex-only STDD 本地适配测试报告

> 测试日期：2026-08-28
> 测试环境：Linux 7.0.0-30-generic x86_64；Python 3.10.21 / 3.11.16 / 3.12.14；pytest 9.1.1
> 被测基线：`3f358ec` + 当前工作树

## 一、总体概况

主质量门（Python 3.12）完整包含 `tests/` 与两个 example plugin 测试目录。

| 指标 | 数值 |
|------|------|
| 测试用例总数 | 1074 |
| 通过 | 1073 |
| 失败 | 0 |
| 跳过 | 1 |
| 通过率 | 100%（排除 skip） |
| 执行耗时 | 69.52 秒 |

### 1.1 覆盖率诊断

- Gateway 总覆盖率：**93.33%**，通过 90% release 门。
- 本 change 不修改 Gateway/SDK runtime 源码；新增内容为配置、文档、Skill 入口和契约测试，因此没有需要单独诊断的变更源码覆盖率。

## 二、质量门结果

| 检查 | 结果 | 证据摘要 |
|------|------|---------|
| Codex 适配契约 | ✅ | 9 passed（含既有 CLI provenance/manifest/help） |
| Codex Skill validator | ✅ | 7/7 valid |
| Release pytest + coverage | ✅ | 1073 passed, 1 skipped；93.33% |
| Ruff | ✅ | All checks passed |
| Mypy | ✅ | 99 source files，0 issues |
| STDD CLI bridge | ✅ | `bin/stdd --help`、status、validate 成功 |
| Vendored 来源边界 | ✅ | `bin/stdd`、`stdd/`、manifest 无 diff；hash 契约通过 |
| Diff 检查 | ✅ | `git diff --check` 通过，无 Gateway/SDK runtime diff |
| E2E | N/A | `quality.e2e.enabled: false` |

## 三、多 Python 版本结果

| Python | 结果 | 说明 |
|--------|------|------|
| 3.10.21 | ✅ | 1073 passed, 1 skipped；93.33% |
| 3.11.16 | ⚠️ | 1072 passed, 1 failed, 1 skipped；93.33% |
| 3.12.14 | ✅ | 1073 passed, 1 skipped；93.33% |

Python 3.11 唯一失败为既有 `TC-RL-005`：测试要求 50 个并发消费只能使用初始 burst=5，但 bucket 配置 `rate=1000/s`，执行期间补充了一个 token，实际成功 6 次。该测试/实现均不在本 change diff 中，Python 3.10/3.12 同轮通过；按 Verify 规则将多版本失败单列给 Gate 3 决策，不在纯配置 change 中静默修改运行时代码。

首次使用 `uv run --isolated` 的诊断执行还出现 wheel 子 venv 无法继承临时依赖 overlay；改用真实临时 venv 后 wheel 冒烟在 3.10/3.11 均通过，确认这是验证环境建模问题而非产品失败。

## 四、功能/测试覆盖对照

| TC | 场景 | Checkpoint | 结果 |
|----|------|------------|------|
| TC-CODEX-001 | 项目规则可发现 | `test_codex_project_instructions_are_canonical` | ✅ |
| TC-CODEX-002 | Skill 集合完整 | `test_codex_skill_wrappers_match_core_skills` | ✅ |
| TC-CODEX-003 | Skill 入口合法 | `test_codex_skill_wrappers_have_valid_frontmatter` | ✅ |
| TC-CODEX-004 | Codex 原生权限边界 | `test_codex_long_range_guidance_is_platform_native` | ✅ |
| TC-CODEX-005 | 非 Codex 适配清理 | `test_non_codex_project_adapters_are_absent` | ✅ |
| TC-CODEX-006 | Vendored manifest 完整 | `test_vendored_manifest_matches_upstream` | ✅ |
| TC-CODEX-007 | 活跃 overlay 文档一致 | `test_active_stdd_docs_are_codex_only` | ✅ |
| TC-CODEX-008 | 完整质量门 | agent spec 的失败即停止组合 checkpoint | ✅ |

`stdd diff` 的静态扫描仅识别 Python 测试函数，因此显示 7/8；TC-CODEX-008 是已实际执行并留证的组合 checkpoint，不把单个无关 pytest 节点伪装为质量门覆盖。

## 五、多路并行 Review 结果

三名只读 reviewer 分别检查实现边界、测试/配置、文档/Skills，共进行最多三轮复核。

| 轮次 | 原始 C/H/M/L | 处理结果 |
|------|--------------|---------|
| 1 | 0 / 6 / 7 / 1（含跨 reviewer 重复项） | 修正 schema、TC-ID、切片证据、upgrade、文档与 checkpoint |
| 2 | 0 / 2 / 5 / 0（含重复项） | 补齐 `.agents/skills` 回滚、全目录扫描与 pending 状态 |
| 3 | 0 / 2 / 0 / 0（同一过宽测试规则的重复报告） | 改为上下文敏感 slash 命令正则；定向 9/9 通过 |

最终未解析的实现 finding：**0**。首轮 Low（薄入口可能容纳冲突正文）也通过正文精确等值断言解决。

## 六、十二类失败模式检查

| 类别 | 检查与结论 | 最终状态 |
|------|------------|---------|
| (a) 幻觉行为 | 所有 Skill 引用目标、配置路径、CLI 命令均实测存在 | ✅ |
| (b) 范围蔓延 | diff 限于批准的开发 overlay、测试、报告和经验；无 runtime diff | ✅ |
| (c) 级联错误 | 新增测试/说明无异常吞噬；组合门使用失败即停止 | ✅ |
| (d) 上下文丢失 | proposal→Gate 2 设计变化已写 ADJ-001 | ✅ |
| (e) 工具误用 | 文件修改经 patch；validator/CLI 使用项目声明工具 | ✅ |
| (f) 运行时偏差 | status 实测显示“全自动长程模式”；错误 schema 已修复 | ✅ |
| (g) 管线断链 | wrapper→core Skill 链路逐项验证；upgrade 回滚闭环，新增 EXP-2026-0021 | ✅ |
| (h) 内容质量 | 活跃 Skills/templates 全目录扫描；命令和 12 类口径一致 | ✅ |
| (i) 指令衰减 | 三道 Gate、完整原则检查和三路 review 均实际执行 | ✅ |
| (j) 覆盖真空 | 两个 capability 均有自动化 checkpoint，8/8 有证据 | ✅ |
| (k) 契约断层 | TC-ID 全仓去重且 checkpoint 映射一致，新增 EXP-2026-0022 | ✅ |
| (l) 锚定缺失 | L1 锚点为官方 Codex 文档、上游 manifest 和既有契约，均可达 | ✅ |

## 七、设计调整与经验

- 设计调整：3 项，均已解决；详见 [design-adjustments.md](design-adjustments.md)。
- 新增经验：EXP-2026-0021（升级事务回滚面）、EXP-2026-0022（TC-ID 全局唯一）。
- 复用经验：EXP-2026-0005、EXP-2026-0006、EXP-2026-0017。
- 经验库总计：22 条。

## 八、项目原则复核

| 原则 | 实际结果与证据 | 状态 |
|------|---------------|------|
| Plugin / Flow；核心最小 | 只新增项目 Skill overlay，未修改 Gateway/SDK/Flow runtime | ✅ |
| 策略显式；失败不静默 | Codex 是唯一活跃适配；组合门、upgrade 回滚和运行时拒绝均显式 | ✅ |
| 边界透明；契约稳定 | vendored hash 与 CLI 保持原样；thin wrapper 单一正文；偏差正式记录 | ✅ |
| 决策有证据；数据默认保护 | 8/8 TC 有 checkpoint；无用户数据处理，不写用户级 Codex 配置 | ✅ |

原则取舍：ADJ-001 以项目 overlay 替代 CLI fork，已获 Gate 2 批准；没有静默偏离。

## 九、结论

本次 Codex-only 配置 change 的主质量门全部通过，可以进入 Gate 3。唯一待用户知情决策的是与本 change 无关的 Python 3.11 既有令牌桶时序测试失败；整体多版本执行通过率高于 99.9%，未触发长程模式低于 95% 的降级条件。建议 Gate 3 接受本 change，并把 `TC-RL-005` 稳定性作为独立 STDD change 处理。
