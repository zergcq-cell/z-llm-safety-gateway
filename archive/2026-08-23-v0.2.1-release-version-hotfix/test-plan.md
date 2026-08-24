# v0.2.1 独立版本发布热修复测试方案与详细案例

> 版本：Gateway 0.2.1 / Detector SDK 0.1.1
> 创建日期：2026-08-23
> 对应 Phase 2 Spec：`release-hardening`、`detector-sdk`、`project-docs`

## 一、测试策略

### 1.1 测试金字塔

- **单元/契约层（约 70%）**：临时发布树 mutation、版本角色、CHANGELOG 截止、workflow
  YAML、文档版本角色。无网络、快速、确定性。
- **构建/安装层（约 20%）**：真实构建两个 wheel 与两个 sdist，解析 Metadata，Twine
  检查，在干净环境执行三个 CLI，并单独验证 SDK 无 Gateway 安装。
- **远程发布层（约 10%）**：Gate 3 后验证 main 三版本 CI、tag 指向、Release jobs、四个
  assets、notes 和 `v0.2.0` tag 不可变性。

### 1.2 测试原则

- 严格 RED → GREEN → REFACTOR；先复现当前 `found ['0.1.1', '0.2.0']` 失败。
- 正向独立版本用例必须配套 Gateway、SDK、CHANGELOG 三组负向 mutation，防止“直接忽略 SDK”的假绿。
- 版本断言按 Gateway、SDK、历史证据三类路径维护，不执行全仓库字符串替换。
- tag 之前完成本地全套质量门并等待 main 同一 SHA 的三版本 CI；失败即停止。
- Agent checkpoint 必须通过 AST/collect 证明真实节点存在，且只引用归档后仍存在的 `tests/` 路径（EXP-0006）。
- Release job 必须继续依赖 quality/build/audit（EXP-0004）；公开文档由自动化契约反向校验（EXP-0005）。
- 远程写操作只允许创建新的 `v0.2.1`；不得删除、移动或覆盖 `v0.2.0`。

### 1.3 已有测试资产

| 测试文件或证据 | 当前用例/状态 | 类型 | 覆盖范围 |
|----------------|---------------|------|----------|
| `tests/unit/release/test_release_contract.py` | 7 functions | 单元 + 构建 | 版本、CHANGELOG、四产物、SDK 安装、workflow |
| `tests/unit/release/test_documentation_contract.py` | 7 functions | 文档契约 | Gateway/SDK 版本表面、链接、插件文档 |
| `tests/unit/release/test_sdk_release_contract.py` | 1 function | SDK 契约 | SDK metadata/runtime 0.1.1 |
| `tests/unit/release/test_ci_contract.py` | 4 functions | Workflow 契约 | Python 矩阵、quality 命令和 coverage gate |
| 完整本地回归基线 | 1011 passed / 1 skipped | 回归 | Gateway、Flow、HTTP/SSE、SDK、gRPC、YAML |
| main CI run `32644631428` | 3.10/3.11/3.12 success | 远程 | v0.2.0 提交完整质量矩阵 |
| Release run `32644725425` | quality/audit pass；build fail；release skipped | 远程失败锚点 | 精确复现独立版本校验缺陷 |

## 二、详细测试案例

### 2.1 release-hardening

| ID | 对应 Spec | 优先级 | 预置条件（Arrange） | 输入（Act） | 预期结果（Assert） | 当前状态 |
|----|-----------|--------|--------------------|-----------|---------------------|----------|
| TC-REL-008 | SC-REL-008 | P0 | 临时树 Gateway 0.2.1、SDK 0.1.1、非空 0.2.1 notes | `verify_version("v0.2.1")` | 返回成功；SDK 不要求等于 tag | ❌ 新增 |
| TC-REL-009 | SC-REL-009 | P0 | 分别 mutation Gateway package/runtime 为非 0.2.1 | 执行版本校验 | 每个 mutation 均抛 gateway mismatch，非零退出 | ❌ 新增参数化 |
| TC-REL-010 | SC-REL-010 | P0 | SDK package/runtime 取不同值 | 执行合法 Gateway tag 校验 | 抛 SDK mismatch，不静默选值 | ❌ 新增 |
| TC-REL-011 | SC-REL-011 | P0 | 0.2.1 notes 缺失、空、与 0.2.0/0.1.1 相邻 | 校验并提取 notes | 缺失/空失败；有效输出只含 0.2.1 | ⚠️ 扩展现有 |
| TC-REL-012 | SC-REL-012 | P0 | 根版本 0.2.1、SDK 0.1.1、可用 build backend | 构建两项目并解析 4 个 artifacts | 2 wheel + 2 sdist；名称/版本集合精确；metadata 有效 | ⚠️ 更新现有 |
| TC-REL-013 | SC-REL-013 | P0 | 已构建两个 wheel 与两个干净环境 | 组合安装运行 3 CLI；SDK 单独安装 | 所有命令退出 0，SDK 不依赖 Gateway | ⚠️ 扩展现有 |
| TC-REL-014 | SC-REL-014 | P0 | 解析 `release.yml` | 检查 dispatch input、version source、condition、needs | 无静态 default；manual 不发布；tag 使用 ref；needs 三门 | ⚠️ 更新现有 |
| TC-REL-015 | SC-REL-015 | P0 | Gate 3 批准、发布提交本地全绿 | push main 并查询同 SHA CI | 三个 Python job 全绿后才创建 tag；失败则停止 | ❌ Deliver 远程 |
| TC-REL-016 | SC-REL-016 | P0 | 新 annotated v0.2.1 指向已验证 SHA | push tag，等待 workflow，读取 Release | 四 jobs 成功；4 assets；精确 notes；tag verified | ❌ Deliver 远程 |
| TC-REL-017 | SC-REL-017 | P0 | 基线 object `dae034…`、commit `d67d573…` | v0.2.1 前后 `git ls-remote` | 两个 v0.2.0 值不变；无 v0.2.0 Release 伪造 | ❌ Deliver 远程 |

### 2.2 detector-sdk

| ID | 对应 Spec | 优先级 | 预置条件（Arrange） | 输入（Act） | 预期结果（Assert） | 当前状态 |
|----|-----------|--------|--------------------|-----------|---------------------|----------|
| TC-SDK-010 | SC-SDK-010 | P0 | Gateway 元数据更新为 0.2.1 | 读取 SDK pyproject/runtime 并执行发布校验 | 两处 SDK 均为 0.1.1；内部错配阻断 | ⚠️ 扩展现有 |
| TC-SDK-011 | SC-SDK-011 | P0 | SDK wheel/sdist 与无 Gateway 干净环境 | 检查 metadata、安装、运行 `zlg-sdk --help` | 两产物为 0.1.1；安装与入口成功 | ✅ 已有，纳入组合回归 |
| TC-SDK-012 | SC-SDK-012 | P1 | SDK README、CLI、plugin docs、example pyprojects | 扫描 wheel 名称、URL 和双版本说明 | 所有 SDK 发布引用为 0.1.1；无 SDK 0.2.1 宣传 | ⚠️ 扩展现有 |

### 2.3 project-docs

| ID | 对应 Spec | 优先级 | 预置条件（Arrange） | 输入（Act） | 预期结果（Assert） | 当前状态 |
|----|-----------|--------|--------------------|-----------|---------------------|----------|
| TC-DOCS-008 | SC-DOCS-008 | P1 | Gateway 当前公开文档、配置注释、Compose | 扫描 Gateway 版本与 Python 口径 | 当前版本全部为 0.2.1；历史/归档不改；Python 口径不变 | ⚠️ 更新现有 |
| TC-DOCS-009 | SC-DOCS-009 | P1 | SDK 与插件当前文档和示例依赖 | 扫描 SDK 与双版本表面 | SDK 0.1.1；双版本说明为 Gateway 0.2.1 / SDK 0.1.1 | ⚠️ 更新现有 |
| TC-DOCS-010 | SC-DOCS-010 | P0 | 相邻 CHANGELOG 0.2.1/0.2.0/0.1.1 | 提取 v0.2.1 notes | 说明热修复与 SDK 0.1.1；不串节；不声称 v0.2.0 Release 成功 | ❌ 新增/更新 |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 构建/集成 | 远程 E2E | 状态 |
|----------|---------|-----------|----------|------|
| Gateway/SDK 独立版本校验 | 临时树正负矩阵 | CLI 调用真实 checker | Release build first step | 🟡 待实现 |
| CHANGELOG notes | 缺失/空/相邻章节 | release notes 文件 | GitHub Release notes | 🟡 待实现 |
| 四产物 metadata | Metadata 断言 | 真实 wheel/sdist + Twine | Release assets 4/4 | 🟡 部分已有 |
| SDK 独立兼容 | package/runtime/docs 契约 | 无 Gateway 安装 | SDK asset 下载验证 | 🟡 部分已有 |
| Workflow 发布策略 | YAML 结构断言 | manual dry-run | tag push + needs | 🟡 部分已有 |
| 文档双版本口径 | Markdown/config 扫描 | 本地链接/示例解析 | Release notes/assets | 🟡 待更新 |
| Tag 不可变 | 本地约束检查 | tag 创建前 SHA 对照 | `ls-remote` 前后对照 | 🔴 Deliver 验证 |
| 运行时兼容 | 全量 pytest | Flow/HTTP/SSE/gRPC 集成 | main CI 三版本 | 🟢 基线存在 |

## 四、回归风险矩阵

| 风险区域 | v0.2.1 改动 | 已有回归保护 | 风险等级 |
|----------|-------------|-------------|---------|
| `tools/release_checks.py` | 版本角色拆分 | release contract + 临时树 mutation | 🔴 高 |
| `.github/workflows/release.yml` | manual input 去静态默认，保持 gates | workflow YAML 契约 + remote run | 🔴 高 |
| Gateway metadata/runtime | 0.2.0 → 0.2.1 | package/runtime/changelog/build metadata | 🟠 中 |
| Detector SDK | 代码不改，锁定 0.1.1 | SDK unit、release、独立安装 | 🔴 高（误改影响大） |
| CHANGELOG/Release notes | 新增 0.2.1 章节 | 精确提取与相邻截止 | 🟠 中 |
| 文档/Compose/config comments | Gateway 版本更新、SDK 不变 | documentation/deployment contracts | 🟠 中 |
| Gateway runtime/Flow/API | 无计划改动 | 1011-test 完整回归、三版本 CI | 🟢 低 |
| 远程 tag/Release | 新建 v0.2.1，保留 v0.2.0 | SHA baseline + GitHub API evidence | 🔴 高 |

## 五、建议补充与执行顺序

1. **第一优先（P0，13 cases）**：TC-REL-008～017、TC-SDK-010～011、TC-DOCS-010。
   先完成 checker RED/GREEN，再更新版本/产物，最后在 Gate 3 后执行三个远程 TC。
2. **第二优先（P1，3 cases）**：TC-SDK-012、TC-DOCS-008～009。版本实现转绿后同步
   文档角色映射，禁止全局替换。
3. **第三优先（P2）**：无。本热修复的全部 Scenario 都是发布所需门禁。

## 六、质量命令与停止条件

### 本地门

```text
.venv/bin/ruff check src/ tests/ sdk/src/ tools/ examples/plugins/python-inprocess/src examples/plugins/python-inprocess/tests examples/plugins/python-grpc/src examples/plugins/python-grpc/tests
.venv/bin/mypy src/ sdk/src tools/
PYTHONPATH=sdk/src:examples/plugins/python-inprocess/src:examples/plugins/python-grpc/src OPENAI_API_KEY=sk-test .venv/bin/pytest tests/ examples/plugins/python-inprocess/tests examples/plugins/python-grpc/tests --cov=src/z_llm_safety_gateway --cov-fail-under=90 -q
```

### 远程门

- main CI：Python 3.10、3.11、3.12 全部 success。
- Release：quality/build/audit/release 全部 success，assets 4/4。
- `v0.2.0` refs 必须保持 `dae034…` / `d67d573…`。

### 停止条件

- 任一版本或 artifact metadata 不一致：停止，不创建 tag。
- main 任一 Python job 失败：停止，不创建/推送 tag。
- tag 已推送后的 Release 失败：保留该 tag，不移动；另开补丁修复。
- 发现 SDK API、Flow、HTTP/SSE、Provider、gRPC 或 YAML 行为变化：视为范围偏离，记录
  `design-adjustments.md` 并回到相应 Gate。
