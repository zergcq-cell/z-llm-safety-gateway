# v0.2.2 发布可复现性测试报告

> 测试日期：2026-08-26
> 测试环境：macOS Darwin 25.6.0 arm64；Python 3.10.20 / 3.12；pytest 9.1.1
> 被测版本：`c8daffcef87326c377aa4abd945a46a6455da1eb` 加本 change 未提交工作树
> 结论范围：本地 Verify 完成；Gate 3 后远程发布验收尚未执行

## 一、总体概况

| 指标 | Python 3.10 | Python 3.12 |
|------|-------------|-------------|
| 收集总数 | 1066 | 1066 |
| 通过 | 1065 | 1065 |
| 失败 | 0 | 0 |
| 跳过 | 1 | 1 |
| 有效通过率 | 100% | 100% |
| 最终结果 | ✅ | ✅（22.28 秒） |

- Python 3.11：本机无可用解释器，未伪造本地结果；由 Gate 3 后同 SHA GitHub CI 矩阵验证。
- Coverage：5521 statements，368 missed，项目源码行覆盖率 **93%**，达到配置的 90% 目标。
- Ruff：通过。
- Mypy：99 个源码文件通过，0 issues；仅提示既有 `torch.*` override 未使用。
- `git diff --check`：通过。
- YAML：CI、Release、STDD canonical/metadata 和经验索引共 14 个文件解析通过。
- E2E：项目配置为 disabled；本 change 的远程 E2E 被拆为 Gate 3 后三个显式 checkpoint。

### 1.1 覆盖率诊断

本 change 进入 Gateway runtime 的唯一源码变化是
`src/z_llm_safety_gateway/__init__.py` 的版本号，覆盖率为 100%。新增的发布校验器位于
`tools/release_checks.py`，由 50 个 release 契约用例中的纯函数、mutation、CLI 和构建用例覆盖；
工具目录不在项目源码 coverage 统计范围内。全项目源码覆盖率为 93%，未发现与本 change
相关的低覆盖阻塞项。

## 二、质量门与构建结果

| 检查 | 结果 | 证据摘要 |
|------|------|----------|
| Python 3.10 全量回归 | ✅ | 1065 passed, 1 skipped |
| Python 3.12 全量回归 | ✅ | 1065 passed, 1 skipped |
| Python 3.11 | ⏳ 待远程 | 本机无解释器；CI matrix 已包含 3.11 |
| Coverage | ✅ | 93%，高于 90% 目标 |
| Ruff | ✅ | All checks passed |
| Mypy | ✅ | 99 source files，0 issues |
| release lock 安装 | ✅ | Python 3.12 使用 `--require-hashes` 安装成功 |
| 四产物构建 | ✅ | Gateway 0.2.2 + SDK 0.1.1 的 wheel/sdist 共四个 |
| Twine / metadata | ✅ | 四产物全部校验通过 |
| Agent checkpoints | ✅ / ⏳ | 19 个本地 node 通过；3 个远程 checkpoint 待 Deliver |

本地四产物验证使用同一完整 hash lock 和 `build --no-isolation`。Python 3.12 wheel smoke
使用隔离 venv 并强制重装被测 wheel，避免外层环境已有同版本包导致 CLI 入口未生成而产生假结论。

## 三、功能与测试覆盖对照

| Capability | TC | 本地结果 | 远程结果 | 结论 |
|------------|---:|----------|----------|------|
| release-hardening | 8 | 7 PASS | TC-REL-025 待远程 | 无覆盖真空 |
| github-setup | 4 | 3 PASS | TC-GH-011 待远程 | 无覆盖真空 |
| project-docs | 3 | 3 PASS | 不适用 | 完成 |
| **合计** | **15** | **13 PASS** | **2 待远程** | **15/15 有自动化映射** |

### 3.1 本地 checkpoint

- 15 个 TC 与 15 个 Agent checkpoint 一一对应。
- 19 个本地 pytest nodes 均通过 AST 定位、`pytest --collect-only` 和实际执行。
- 元契约会实际收集并运行本地 node，不再只验证函数名存在。
- 三个远程动作均由 `tools/verify_remote_release.sh` 实现，模式为 `pre-tag`、
  `annotations`、`release`；shell 语法、参数契约和失败分支已在本地验证。

### 3.2 Gate 3 后远程 checkpoint

以下项目在本报告中严格标为 **待远程**，不得计为 PASS：

1. `pre-tag`：同 SHA main CI 和 dry-run 成功后、创建 tag 前，确认 v0.2.2 Release API
   明确 404 且远程 tag 不存在。
2. `annotations`：main push、workflow_dispatch、tag push 三类 run 全绿，且所有 check-run
   annotations 不含 Node.js 20 / node20 回退信号。
3. `release`：下载 distributions 与 evidence，按本地产物字节逐名称复算 SHA-256，验证
   public Release、四资产、peeled HEAD、evidence 逐字重建，以及 v0.2.0/v0.2.1 远程基线不变。

## 四、多路技术评审

Step 0 已完成三轮、每轮三路只读审查：代码/失败边界、测试/配置、锚定/项目原则。
下表按去重后的问题组记录；同一问题被多路发现时只计一次。

| 轮次 | 发现 | 处理 | 轮次结论 |
|------|-----:|------|----------|
| 1 | 4 组 | 补齐 pre-tag 时序证据、Phase 文档数据、checkpoint collect/execute、声明与动作边界 | 继续复审 |
| 2 | 6 组 | 修复 Bash 假绿、digest 本地字节绑定、URL/时间关联、wheel smoke 隔离和历史状态表述 | 继续 mutation 复审 |
| 3 | 0 个未解决项 | 定向复跑、完整回归和原则交叉验证 | ✅ 通过 |

最终 Critical/High 未解决项为 0；Medium/Low 未解决项为 0。远程 GitHub 行为不是已知缺陷，
而是按设计保留到 Gate 3 后、按时序执行的验收项。

### 4.1 已修复的关键问题

| 问题 | 修复结果 |
|------|----------|
| Bash process substitution 不传播远程查询失败 | 改为普通文件输入并校验非空、格式与退出状态 |
| command substitution 中前置失败被后续成功覆盖 | 强制查询/校验成为最后一个显式失败命令，并增加 PATH stub 负向测试 |
| Release digest 只验证格式 | 按文件名与本地 `dist/*` 字节的 SHA-256 比较，增加错误与互换 mutation |
| 发布终态倒推 dry-run absence | 新增 tag 前 `pre-tag` checkpoint（ADJ-003） |
| Evidence 关联不够精确 | 增加 repository/run URL、Release URL 和 RFC3339 UTC 时间验证 |
| checkpoint 只做 AST 存在性检查 | 增加 collect-only 与实际执行 |
| 嵌套 smoke venv 受外层同版本包影响 | 使用 `--force-reinstall` 验证 wheel 与 CLI 入口 |
| v0.2.0/v0.2.1/v0.2.2 历史状态被压平 | 分别描述 tag、workflow、draft/public Release 状态（ADJ-002） |

## 五、十二类失败模式检查

| 类别 | 结果 | 结论 |
|------|------|------|
| (a) 幻觉行为 | ✅ 本地 PASS | 路径、CLI flags、Action allowlist 与 API 字段均存在；官方远程行为由后续 run 验收 |
| (b) 范围蔓延 | ✅ PASS | 实际文件数超过 proposal 的粗略估算，但全部映射到已批准 capability；无 runtime 语义扩张 |
| (c) 级联错误 | ✅ PASS | 只有明确 404 表示 absence；认证、限流、网络、5xx、空结果和无效 JSON 均失败关闭 |
| (d) 上下文丢失 | ✅ PASS | 最终实现与 proposal/design/spec 一致；3 项轻量调整已显式记录并收口 |
| (e) 工具误用 | ✅ PASS | 确定性判断集中在 Python 校验器，远程采集集中在有界 shell 脚本 |
| (f) 运行时行为偏差 | ⏳ 待远程 | 本地契约通过；真实 GitHub 三事件路径必须在 Deliver 验收 |
| (g) 管线断链 | ✅ 本地 PASS | 构建→draft→验证→publish→evidence 链完整；pre-tag 时序缺口已修复 |
| (h) 内容质量偏差 | ✅ PASS | checkpoint 数、测试计数和三个版本的发布历史表述已校正 |
| (i) 指令衰减 | ✅ PASS | 强制 checkpoint 现有 AST、collect-only 和真实执行三层自动化证据 |
| (j) 覆盖真空 | ✅ PASS | 三个 capability 自动化覆盖均高于 50%，无零覆盖 capability |
| (k) 契约断层 | ✅ PASS | TC/SC/CP、workflow/CLI flags、artifact/evidence 字段均对齐 |
| (l) 锚定缺失 | ✅ 本地 PASS / ⏳ 远程待验 | L3 历史 change、实现锚点和本地 tag objects 可追溯；远程不变性待 Deliver |

## 六、设计调整

三项调整均已 resolved，无需重新 Spec 或重新 Build：

- **ADJ-001**：lock 生成命令增加 `--allow-unsafe --strip-extras`，让固定的 pip 本身进入 hash lock。
- **ADJ-002**：分别描述 v0.2.0 tag/失败 workflow、v0.2.1 成功 Release 与 v0.2.2 release candidate。
- **ADJ-003**：新增 tag 前时序证据，不能用发布后的 public 终态倒推 dry-run 阶段未发布。

详见 [design-adjustments.md](design-adjustments.md)。

## 七、经验库更新

### 7.1 本次新增

| ID | 模式 | 严重性 |
|----|------|--------|
| EXP-2026-0017 | Bash 命令/进程替换可能吞掉强制远程查询失败 | high |
| EXP-2026-0018 | digest 必须按文件名绑定本地产物字节 | high |
| EXP-2026-0019 | tag、workflow、draft 与成功 Release 必须分别描述 | high |
| EXP-2026-0020 | 时序契约必须在状态改变前采集证据 | high |

### 7.2 本次复用

- EXP-2026-0004：发布链路不能缺少显式转换/验证步骤。
- EXP-2026-0006：Agent checkpoint 必须可定位、可收集、可执行。
- EXP-2026-0014：本地 dependency-reuse smoke 不能冒充可信 clean install。
- EXP-2026-0015：远程错误必须结构化分类并失败关闭。
- EXP-2026-0016：Release notes、资产、ref 与 evidence 必须精确验证。

经验库当前总计 20 条；本次新增 4 条、重点复用 5 条。

## 八、项目原则复核

| 原则 | 实际结果与证据 | 状态 |
|------|---------------|------|
| Plugin / Flow；核心最小 | runtime 仅版本声明变化；无 Flow、Pipeline、Provider、Detector SDK API 或插件行为修改 | ✅ |
| 策略显式；失败不静默 | 404→private draft→exact verify→publish→public recheck；所有非明确状态硬失败且不自动删 tag/draft | ✅ |
| 边界透明；契约稳定 | HTTP/API/YAML/SDK 兼容不变；Gateway 0.2.2 与 SDK 0.1.1 独立；Release assets 精确四个 | ✅ 本地；远程事件待验 |
| 决策有证据；数据默认保护 | schema v1 字段白名单、稳定排序、notes hash、资产 digest、90 天 artifact；不记录 token、用户内容或 actor email | ✅ 本地；远程 artifact 待验 |

原则取舍：失败 private draft 保留供诊断并由维护者显式处置，不自动清理。该取舍已在设计中公开，
没有静默原则偏离，也没有新增敏感数据收集。

## 九、结论与 Gate 3 建议

本地 Verify 质量门全部通过，未发现阻止进入 Deliver 的代码、测试、配置、文档或原则问题。
建议批准 Gate 3，但批准不等于发布成功：Deliver 仍须按顺序完成 push main、同 SHA CI、dry-run、
pre-tag absence、annotated tag、tag workflow、annotations 和 Release/evidence 复验。任一远程状态不明确
都必须立即停止，不创建或移动 tag，不公开未经验证的 draft。

| 信号源 | 状态 | 备注 |
|--------|------|------|
| 单元/集成测试 | ✅ | Python 3.10 / 3.12 均为 1065 passed, 1 skipped |
| Python 3.11 | ⏳ | Gate 3 后 CI 待验 |
| Coverage | ✅ | 93% |
| Ruff / Mypy | ✅ | 0 lint errors；99 source files 0 type issues |
| 构建 / Twine | ✅ | Gateway 0.2.2 + SDK 0.1.1 四产物 |
| 13 个本地 TC | ✅ | 全部通过 |
| 2 个远程 TC | ⏳ | TC-GH-011、TC-REL-025 |
| 19 个本地 nodes | ✅ | AST + collect-only + execute |
| 3 个远程 checkpoints | ⏳ | pre-tag、annotations、release |
| 十二类失败模式 | ✅ / ⏳ | 本地均闭合；(f) 与 (l) 的远程部分待验 |
| Gate 3 | ⏳ | 等待用户明确确认 |
