# Phase Context — v0.2.1 独立版本发布热修复

## Phase 1: UNDERSTAND (completed 2026-08-23T22:19:44+08:00)

- 用户确认 proposal 并选择 `thorough` 模式。
- 目标：修复 Gateway/SDK 独立版本发布校验，通过新 `v0.2.1` 恢复 Release。
- 硬边界：SDK 保持 0.1.1；不删除、移动或覆盖 v0.2.0；不修改运行时/Flow/API/YAML。
- Gate 1：approved。

## Phase 2: SPEC (completed 2026-08-23T22:51:26+08:00)

### 结构化输入

- Modified Capabilities：`release-hardening`、`detector-sdk`、`project-docs`。
- What Changes：6 项；Success Criteria：9 项。
- Impact：发布校验器、发布测试、workflow、Gateway 版本与角色化文档表面。

### L3 真实锚点

- `2026-08-20-v0.1.1-release-hardening`：quality/build/audit needs、四产物、tag-only
  publish、公开 tag 不重写。
- `2026-08-22-v0.2.0-flow-foundation`：Gateway 0.2.0 / SDK 0.1.1 独立版本决定、
  1011-test 本地基线与失败 Release 真实证据。
- v0.2.0 remote tag object：`dae034025cc7f68d13ef7b9b3ba3f1b1eca35411`。
- v0.2.0 peeled commit：`d67d573b0e38691707e70e64a7ec1a431ca1f545`。
- Release run `32644725425`：quality 3.10/3.11/3.12 与 audit success；build version
  validation failure；release skipped。

### 经验库交叉检查

- `EXP-2026-0004`：tag 发布必须依赖同一提交的完整质量矩阵。已进入 REQ-REL-007、
  SC-REL-014～016。
- `EXP-2026-0006`：Agent checkpoint 必须引用真实且归档后仍可定位的 test node。已要求
  Build 阶段 AST + collect 验证，并只引用 `tests/` 节点。
- `EXP-2026-0005`：公开配置/文档表面必须由契约测试反向校验。已进入 REQ-DOCS-008
  与 TC-DOCS-008～010。

### 锁定设计决策

1. tag 仅约束 Gateway package/runtime；SDK package/runtime 必须内部一致但无需等于 tag。
2. 版本失败矩阵使用临时发布树 mutation，不修改真实工作树。
3. 不重写 v0.2.0，使用全新 v0.2.1。
4. Release 仍交付 Gateway 0.2.1 / SDK 0.1.1 的 2 wheel + 2 sdist。
5. workflow_dispatch version 必填且移除静态 default；tag 使用 `github.ref_name`。
6. 文档按 Gateway、SDK、双版本与历史证据四类路径更新，禁止全局替换。
7. mismatch 继续硬失败；不 fallback、不复用旧 artifact、不上传半成品。
8. 本地单元/构建/完整回归与远程 CI/Release 分层验证。

### Project Principle Check

1. Plugin / Flow：发布逻辑保持在 tools/workflow，不进入核心；Flow 与插件无变化。
2. 显式策略 / 失败：四类版本角色与 CHANGELOG 分别验证，任一失败非零且 Release skipped。
3. 透明边界 / 稳定契约：Gateway 补丁升级，SDK 0.1.1 与所有运行时边界保持稳定。
4. 证据 / 数据保护：tag/commit/jobs/artifacts/notes 构成证据；只读取公开版本，不采集 secrets。

原则取舍：保留失败 v0.2.0 tag 以维护公开 tag 不可变性，通过 v0.2.1 恢复发布。

### 产出与指标

- `design.md`：8 个设计决策、架构/发布时序、L3 freedom evaluation、风险表。
- Canonical code specs：3；Agent specs：3；Human specs：3。
- Requirements：5；Scenarios：16；Checkpoints：16；TC Cases：16。
- Confidence：high 13 / medium 3 / low 0。
- Priority：P0 13 / P1 3 / P2 0。

### 自动审查

- 需求覆盖：6/6 What Changes、3/3 Capabilities、9/9 Success Criteria 均已覆盖。
- Scenario：5/5 Requirements 至少一个 Scenario；16/16 使用 GIVEN/WHEN/THEN/AND；
  THEN 全含 SHALL；AND 均不超过 5。
- Traceability：16 个 Scenario、16 个 Agent checkpoint、16 个 TC-ID 一一对应且全局唯一。
- 文档一致性：Gateway 0.2.1 / SDK 0.1.1 口径一致；设计引用的三个现有路径均存在。
- 自动修复 3 项：增加 SDK mismatch 负向防假绿；锁定 annotated/peeled 两个 tag 基线；
  增加 combined-wheel 三 CLI checkpoint。

### STDD 2.9.5 工具兼容记录

- `canon generate --type spec` 当前实现忽略 `gen_type` 并只生成 proposal；Capability Human
  View 依 Canonical YAML 手动渲染，Canonical 仍为唯一事实源。
- generator 会遗漏 proposal 的 Impact/Risk/Principle/Mode 章节；已从 Canonical 补回，
  source hash 保持一致，`canon verify` 2/2 通过。
- 以上为 STDD 工具兼容处理，不改变本 change 产品设计。

### 当前状态

- Phase 2 文档已就绪，L3 anchoring 通过。
- Gate 2：用户已于 `2026-08-23T22:51:26+08:00` 明确确认。
- 用户选择全自动长程模式；一次性具体操作授权仍等待「确认全部」，授权前不进入 Phase 3。
- `stdd gate approve --gate 2` 因 CLI 2.9.5 对 `phases` 路径重复解析，误报 Gate 1 未确认；
  已按用户真实确认同步 `confirmed_at`、legacy gates 与 `phases.spec` 状态，未跳过门禁。

## Phase 3–5 长程授权（confirmed 2026-08-24T22:47:19+08:00）

- 用户回复「确认全部」，授权 Phase 3–5 连续自动执行，最大 10 轮，同一问题连续自动修复
  3 次失败时降级暂停。
- 已授权 change/source/test/workflow/docs 文件写入、pytest/Ruff/Mypy/build/Twine、项目脚本、
  必要网络读取与 Git 只读操作。
- Phase 3–5 不 commit、tag、push；不删除、移动或覆盖 v0.2.0。
- 当前平台为 Codex managed permissions，不修改 `.claude/settings.local.json` 或全局权限。
- Gate 3 仍为强制人工确认门。

## Phase 3: SLICE (completed 2026-08-24T22:55:00+08:00)

- STDD version check：项目与 Slice Skill 均为 2.9.5，且项目 locked；无版本漂移。
- dependency graph：`detector-sdk`、`project-docs`、`release-hardening` 均为 zero-dependency，
  cycles 为空。
- 风险评分：release-hardening 5（High）、detector-sdk 4（High）、project-docs 3
  （Medium）。
- 划分 4 个串行垂直切片：S1 版本角色校验；S2 双版本产物/CLI；S3 workflow/公开表面；
  S4 thorough 本地验证与 Gate 3 证据。
- 覆盖检查：5/5 Requirements、16/16 Scenarios/TC；13 个 P0、3 个 P1；无循环依赖。
- TC-REL-015～017 明确保留到 Gate 3 后 Deliver；Phase 3–5 不执行远程写入。
- 自动进入 Phase 4 BUILD，active slice 为 S1。

## Phase 4: BUILD (in progress)

### S1 — Release verifier role separation (completed 2026-08-24T22:58:57+08:00)

- RED：4 个新测试函数、6 个 collected cases 全部失败，精确复现 Gateway/SDK 被错误要求
  同版本以及通用错误信息掩盖具体角色的问题。
- GREEN：`tools/release_checks.py` 先校验 Gateway package/runtime 等于 tag，再独立校验 SDK
  package/runtime 内部一致，最后校验目标 CHANGELOG notes。
- REFACTOR：保留小型 `verify_version()` 接口，错误顺序与角色明确；未引入不必要抽象。
- 切片验证：TC 5/5；发布契约 13 passed；Ruff 与 diff check 通过；全量回归 1017 passed /
  1 skipped。
- 环境证据：沙箱禁止绑定 `127.0.0.1:0` 导致 13 个 gRPC setup errors；授权本机回环后
  同一套件全部通过，确认不是产品回归。
- 经验提醒：EXP-2026-0004（发布完整质量链）；经验库尚无 verified/settled 条目，因此正式
  自动加载数为 0。

### S2 — Independent artifacts and CLI installation (completed 2026-08-24T23:03:32+08:00)

- RED：构建 metadata 与组合环境 runtime 断言均检测到 Gateway 仍为 0.2.0；SDK 独立安装
  用例继续通过。
- GREEN：仅将根 `pyproject.toml` 与 Gateway `__version__` 提升为 0.2.1；SDK package/runtime
  保持 0.1.1。四产物 metadata 与组合版本断言转绿。
- REFACTOR：提取测试虚拟环境 helper；组合环境只复用已安装依赖，wheel 自身仍从临时构建
  目录安装并验证，SDK 独立环境保持无 Gateway。
- 切片验证：TC 4/4；新增 1 个测试；release/SDK 定向 26 passed；Ruff 与 diff check 通过；
  全量回归 1018 passed / 1 skipped。

### S3 — Workflow and role-based public surfaces (completed 2026-08-24T23:06:57+08:00)

- RED：7 个定向 cases 中 5 个失败，分别锁定缺失 0.2.1 notes、workflow 静态默认、Gateway
  当前文档 0.2.0 与插件双版本旧口径；SDK 0.1.1 两项保护持续通过。
- GREEN：新增精确 v0.2.1 CHANGELOG 章节并记录 v0.2.0 Release 失败事实；移除 dispatch
  静态默认；按角色更新 Gateway 当前 README/docs/config 表面，保留 SDK 0.1.1 URL/metadata。
- REFACTOR：workflow 测试按 step 名称查找，避免依赖脆弱数组位置；新增 SDK 0.2.1 禁止
  宣传断言。未执行全仓库版本替换，Flow Foundation 0.2.0 历史说明保持不变。
- 切片验证：TC 5/5；新增 1 个测试；release/docs 契约 42 passed；Ruff、release checker
  和 diff check 通过；全量回归 1019 passed / 1 skipped。
- 经验提醒：公开表面契约遵循 EXP-2026-0005；workflow 三门依赖继续遵循 EXP-2026-0004。

### S4 — Thorough local prerequisites (completed 2026-08-24T23:10:40+08:00)

- RED：新增 hotfix Agent checkpoint 合同后，预期目标计数先检测到解析不完整；确认 Agent
  action 同时包含 file-only 与 `file::function` 两种 pytest target。
- GREEN/REFACTOR：使用 shell-token 解析遍历 3 份 Canonical Agent specs，21 个本地 pytest
  targets 全部存在；保留归档旧 change 的既有合同。
- 切片验证：16/16 TC 均有映射；13 个本地 TC 已执行，TC-REL-015～017 明确为 Deliver
  pending；55 个 release/SDK/STDD cases 可 collect；全量回归 1020 passed / 1 skipped。
- release checker `verify v0.2.1` 与精确 notes 提取成功；无 placeholder 或 0 覆盖切片。
- Phase 4 四个切片全部完成，自动进入 Phase 5 VERIFY iteration 1/10。

## Phase 5: VERIFY (in progress)

- STDD version check：项目与 Verify Skill 均为 2.9.5；无漂移。
- CLI bridge：项目实际入口 `.venv/bin/python -m stdd --help` 返回 0。
- 上下文预算：已发生会话压缩，但 `phase-context.md` 与 `.stdd.yaml` 新鲜且完整；长程模式
  继续，无需重置。

### Verify iteration 1 (Gate 3 ready 2026-08-24T23:42:18+08:00)

- Step 0 Review：三轮；最终 code/test-config/docs-skills 均为 C0 H0 M0 L0。修复 Compose
  0.2.1、archive fallback、精确 workflow/artifact/assertions、SDK 文档覆盖、Release JSON
  validator 与 explicit 404。
- Step 1：1027 passed / 1 skipped；coverage 93.33%；Ruff clean；Mypy 99 files clean；
  Gateway 0.2.1 / SDK 0.1.1 四产物 build + Twine 全绿。
- Step 2：22 个 tracked diff 文件逐项通过范围、死代码、命名、错误处理、安全和契约审查。
- Step 3：12/12 失败模式全量执行，无未修复命中；四原则逐项通过。
- Step 3.5：新增 EXP-0014～0016，复用 EXP-0004～0006；经验库总计 16。
- Step 4：设计调整 0；无需 re-spec/re-build。
- Step 5：`test-report.md` 已生成；TC 16/16 mapped，13 local PASS，3 Deliver pending。
- 本地 clean venv 因 bundled Python 强制注入 tool site-packages 而诚实标记 SKIPPED；Gate 3
  后在 tag 前增加 `workflow_dispatch(version=0.2.1)` 作为补偿性硬门。
- Gate 3：pending；Phase 3–5 未 commit、tag、push，v0.2.0 refs 保持不变。
