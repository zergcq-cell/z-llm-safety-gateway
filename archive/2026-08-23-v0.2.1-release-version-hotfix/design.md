# v0.2.1 独立版本发布热修复 - 技术设计

## Context

Gateway `v0.2.0` 的实现与本地质量门已经完成，Gateway 包版本为 `0.2.0`，独立
Detector SDK 保持 `0.1.1`。提交 `d67d573b0e38691707e70e64a7ec1a431ca1f545`
在远程 CI 的 Python 3.10、3.11、3.12 矩阵全部通过，之后创建并推送了 annotated
tag `v0.2.0`。

Release workflow run `32644725425` 的 quality 三版本和 dependency audit 均通过，但
build job 在 `Validate version and release notes` 失败：

```text
ValueError: version mismatch: expected 0.2.0, found ['0.1.1', '0.2.0']
```

根因位于 `tools/release_checks.py::verify_version`：它将 Gateway package/runtime 与 SDK
package/runtime 的四个声明合并为一个集合，再要求集合只能包含 tag 版本。这与
`DESIGN.md` 决策 30“Detector SDK 独立版本”及已确认的 v0.2.0 双版本边界冲突。

远程不可变基线：

- `refs/tags/v0.2.0` annotated tag object：`dae034025cc7f68d13ef7b9b3ba3f1b1eca35411`
- `refs/tags/v0.2.0^{}` peeled commit：`d67d573b0e38691707e70e64a7ec1a431ca1f545`
- GitHub Release：未创建；release job 因 build failure 正确 skipped

本热修复只调整发布契约、发布元数据与文档口径，不修改 Gateway 运行时、Flow、Detector
SDK API、HTTP/SSE、Provider、gRPC proto 或 YAML 配置语义。

## Project Principle Check

| 原则 | 本设计如何满足 | 风险或取舍 | 验证方式 |
|------|---------------|-----------|---------|
| Plugin / Flow；核心最小 | 发布版本判断保留在 `tools/` 与 GitHub workflow，不进入 Gateway 核心；插件与 Flow 无变化 | 本 change 不扩展运行时能力 | import/diff 审查确认 `src/**/flow`、detector API 和 pipeline 行为未改变 |
| 策略显式；失败不静默 | Gateway tag、Gateway runtime、SDK package/runtime、CHANGELOG 分别验证；任一不一致继续非零失败 | SDK 不必等于 tag，但必须内部一致并由发布测试锁定为 0.1.1 | 正向独立版本测试与四类负向 mutation 测试；失败 build 时 release job skipped |
| 边界透明；契约稳定 | Gateway 仅补丁升级为 0.2.1；SDK 仍是 0.1.1；HTTP/SSE/Provider/Flow/gRPC/YAML 不变 | GitHub Release 同时包含不同版本的两个包，需要明确文档 | 产物 metadata 集合、SDK 独立安装、文档版本契约及完整回归 |
| 决策有证据；数据默认保护 | tag object、commit、CI jobs、artifact metadata、release notes 和 assets 构成证据链 | 保留 v0.2.0 失败记录而非“清理”历史 | `git ls-remote`、`gh run/release view`、Twine/Metadata 检查；不读取或输出 secrets |

**原则取舍**：保留一个未对应 GitHub Release 的 `v0.2.0` tag 会形成可见的失败发布记录，
但避免重写公开 tag。项目既有 `release-hardening` Agent spec 明确规定“公开 tag 不重写，
发布问题以新补丁修复”，因此选择 `v0.2.1` 是稳定契约优先于版本序列美观。

## Decisions

### 1. 发布 tag 只约束 Gateway 版本

**方案**：保留 `verify_version(version: str) -> None` 外部调用方式。内部将声明拆为两个
有名字的集合：

- Gateway：根 `pyproject.toml` 的 `version` 与 Gateway `__version__`，两者都必须等于
  去除可选 `v` 前缀后的 tag 版本。
- SDK：`sdk/pyproject.toml` 的 `version` 与 SDK `__version__`，两者必须彼此相等，但不
  要求等于 Gateway tag。

之后提取并验证当前 Gateway 版本的非空 CHANGELOG 章节。错误消息包含固定角色
`gateway` 或 `SDK` 与公开版本字符串，不包含路径外的动态数据或 secrets。

**为什么**：Git tag 表示 Gateway 发布版本；SDK 是同仓库中的独立包，允许在 Gateway
发布中重复附带未变化的稳定 SDK 产物。保持现有函数签名可避免 workflow 与调用方迁移。

**备选方案及排除原因**：

- 同步把 SDK 提升到 0.2.1：没有 SDK API/实现变化，会制造虚假版本语义，并违背已确认边界。
- 完全跳过 SDK 检查：可能构建 package/runtime 版本不一致的 SDK，弱化供应链门禁。
- 要求命令行额外传 `--sdk-version`：可以显式锁定，但每次 Gateway 补丁都需手动同步
  workflow 输入，增加另一处易漂移事实源；SDK 预期版本由发布契约测试和 CHANGELOG 锁定即可。

### 2. 使用临时发布树测试所有失败路径

**方案**：发布校验器单元测试在 `tmp_path` 构造最小 Gateway/SDK metadata、两个
`__init__.py` 和 CHANGELOG，并通过 `monkeypatch` 将 `tools.release_checks.ROOT` 指向临时树。
测试分别 mutation Gateway package、Gateway runtime、SDK package/runtime、CHANGELOG
缺失与空章节；每个 mutation 必须观察明确 `ValueError`。

**为什么**：不修改真实工作树即可证明每个版本角色被独立验证，测试无网络且确定性强。

**备选方案及排除原因**：

- 只对子函数 mock 返回值：无法证明文件字段名、路径和正则读取仍正确。
- 在真实仓库临时改版本再恢复：污染工作树，失败时可能遗留错误发布元数据。
- 只运行 `verify --version v0.2.1` 正向测试：无法防止修复变成“忽略 SDK”的假绿。

### 3. 通过 v0.2.1 恢复发布，不重写 v0.2.0

**方案**：把远程 `v0.2.0` tag object 与 peeled commit 固定为上述 L3 基线。热修复完成并
通过 Gate 3 后：

1. 创建发布提交，将 Gateway 更新为 `0.2.1`、SDK 保持 `0.1.1`。
2. 推送 `main`，等待该提交的 Python 3.10/3.11/3.12 CI 全绿。
3. 创建新的 annotated `v0.2.1`，再次确认其指向同一验证提交。
4. 推送 `v0.2.1`，等待 Release workflow quality/build/audit/release 全绿。
5. 验证 GitHub Release notes 与四个 assets；再次读取 `v0.2.0` object ID 确认未变化。

**为什么**：不可变 tag 是发布消费者、缓存、SBOM 和审计系统的稳定锚点。

**备选方案及排除原因**：

- 删除并重建 `v0.2.0`：已公开 tag 会改变对象，破坏可复现性和既有规范。
- force-push `v0.2.0`：比删除重建更隐蔽，明确禁止。
- 手工在失败 tag 上创建 Release：绕过 checked-in workflow 的 build/audit/quality 证据链。

### 4. 四产物允许两个独立版本，但每个包内部必须一致

**方案**：构建仍执行根项目与 `sdk/` 项目，必须产生恰好两个 wheel 和两个 sdist。产物
metadata 集合必须精确为：

```text
z-llm-safety-gateway      0.2.1
z-llm-safety-gateway-sdk  0.1.1
```

Twine 检查四个产物。干净环境同时安装两个 wheel，并执行 `z-safety-gateway --help`、
`zlg --help`、`zlg-sdk --help`。SDK 另在无 Gateway 包的环境执行独立安装测试。

**为什么**：同一 Release 可以承载独立版本的协同产物，但不能接受缺失、重复、错误名字或
metadata 漂移。

**备选方案及排除原因**：

- v0.2.1 Release 不附 SDK：会改变既有四产物交付契约和插件安装入口。
- 复制 v0.1.1 Release 的旧 SDK asset：绕过当前提交的重建、Twine 与安装验证。

### 5. workflow_dispatch 不保存会漂移的版本默认值

**方案**：保留 `workflow_dispatch.inputs.version.required: true`，移除静态 `default`。
手动 dry-run 必须显式输入要验证的 Gateway 版本。tag push 仍使用 `github.ref_name`。
Release job 继续满足：

- 仅 `push` 且 `refs/tags/v*` 执行；
- `needs: [quality, build, audit]`；
- 任何前置 job 失败时 skipped；
- workflow_dispatch 永不创建 tag 或 Release。

**为什么**：静态 default 已从 0.1.1 漂移；要求显式输入比每个补丁人工更新默认值更可靠。

**备选方案及排除原因**：

- 将 default 更新为 0.2.1：本次可用，但下次发布会再次过期。
- 自动读取 pyproject 作为 UI default：GitHub Actions 输入 schema 不支持动态默认值。

### 6. 文档按产品角色更新，不做全局字符串替换

**方案**：版本表面分三类：

- Gateway 表面：根 metadata/runtime、README current source、getting-started、API、deployment、
  config comments、Compose image 更新为 `0.2.1`。
- SDK 表面：SDK metadata/runtime、SDK README wheel、CLI template、示例插件依赖保持 `0.1.1`。
- 双版本表面：plugin/grpc/commercial docs 与 CHANGELOG 明确 Gateway `0.2.1` / SDK `0.1.1`。

历史 CHANGELOG、archive、spec 锚点与 `PLAN_v0.1.1.md` 不修改。

**为什么**：角色化映射避免把历史证据或 SDK 下载 URL 误改为不存在的 0.2.1 SDK。

**备选方案及排除原因**：

- 全仓库替换 `0.2.0` 或 `0.1.1`：会改写历史与 SDK 契约。
- 只改 pyproject：用户文档、Compose image 与发布契约继续漂移。

### 7. 发布失败保持可见且不产生半成品

**方案**：发布校验继续位于 build 的第一个产品步骤；失败时构建、CLI 安装、artifact 上传
均 skipped。因为 release job 依赖 build，所以不能创建 GitHub Release。错误只呈现版本角色
与值；不做自动 fallback、不复用旧 artifact、不自动修改版本。

**为什么**：失败必须显式，且不可为了可用性绕过供应链完整性。

**备选方案及排除原因**：

- mismatch 时 warning 并继续：会发布错误产物。
- 自动把 SDK 版本视为 Gateway 版本：掩盖 metadata/runtime 漂移。
- 失败后上传部分 artifacts：会形成不可验证的半成品。

### 8. 测试与远程验收分层

**方案**：

- 单元层：临时发布树的版本角色与错误矩阵、CHANGELOG 精确提取、workflow YAML 结构、文档
  角色映射。
- 构建层：真实 Gateway/SDK wheel+sdist、Metadata/Twine、干净安装和 CLI。
- 回归层：完整 pytest+coverage、Ruff、Mypy，覆盖 Flow/HTTP/SSE/SDK/gRPC/YAML。
- 远程层：main CI 三版本、tag Release workflow、assets、notes、不可变 v0.2.0 object。

Agent checkpoint 使用计划中的精确 pytest node；Build 阶段创建测试后必须通过 AST 和
`pytest --collect-only` 验证节点存在，归档后 checkpoint 通过 `tests/` 节点而非 change 路径。

**为什么**：落实 EXP-0004 的完整质量依赖、EXP-0006 的真实 checkpoint，以及 EXP-0005
的文档契约反向校验。

**备选方案及排除原因**：

- 仅本地测试：无法证明 GitHub 权限、tag event、artifact 和 Release 行为。
- 仅远程重试：当前 tag commit 不含修复，且远程失败定位成本高。

## Architecture

```text
workflow input
  ├─ tag push: github.ref_name = v0.2.1
  └─ dry-run: explicit inputs.version
                  │
                  ▼
       tools/release_checks.py verify
         ├─ normalize v-prefix
         ├─ Gateway package ─┐
         ├─ Gateway runtime ─┴─ both == 0.2.1
         ├─ SDK package ─────┐
         ├─ SDK runtime ─────┴─ both equal each other (0.1.1)
         └─ CHANGELOG [0.2.1] exists and non-empty
                  │
          mismatch│success
          ┌───────┴──────────────┐
          ▼                      ▼
   build fails            build four artifacts
   release skipped         ├─ Twine/Metadata
                           ├─ clean install + 3 CLIs
                           └─ upload artifact bundle
                                      │
                   quality + build + audit all success
                                      │
                                      ▼
                           tag-only GitHub Release
                           ├─ exact 0.2.1 notes
                           └─ 4 verified assets
```

发布顺序：

```text
local Gate 3 approved
  → push main
  → wait CI(3.10, 3.11, 3.12)
  → create/push new v0.2.1
  → wait Release quality/build/audit/release
  → verify notes/assets/tag
  → assert v0.2.0 object unchanged
```

## L3 Anchoring Assessment

### Reference patterns

1. `2026-08-20-v0.1.1-release-hardening`
   - 复用 tag-only publish、quality/build/audit needs、四产物、干净安装和“公开 tag 不重写”模式。
2. `2026-08-22-v0.2.0-flow-foundation`
   - 复用 Gateway `0.2.0` / SDK `0.1.1` 独立版本决策、完整本地质量基线及失败 Release 真实证据。

### Freedom evaluation

- Gateway tag 约束对象：已锁定为 Gateway metadata/runtime。
- SDK 约束：已锁定为 package/runtime 内部一致且本 release 保持 0.1.1。
- CHANGELOG、artifact 集合、CLI、workflow needs、tag 不可变与远程顺序：均有 SHALL 规格。
- 剩余实现自由仅限 helper 命名、错误文本措辞和测试 fixture 内部组织，不影响公共行为。

最低要求为 critical L3；proposal 已提供两个历史 change 和三个当前实现锚点，判定 **L3 通过**。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| SDK 校验被过度放宽 | package/runtime 成对严格相等；真实产物与发布测试锁定 0.1.1；负向 mutation 测试 |
| Gateway tag 与 metadata/runtime 只验证部分字段 | 根 metadata、模块 runtime 两处都必须精确等于 normalized tag |
| CHANGELOG 提取串入相邻版本 | 沿用非贪婪、以相邻 `## [` 截止的提取器并测试 0.2.1/0.2.0 隔离 |
| 手动 dry-run 意外发布 | release job 保持 push+tag condition，并由 YAML 契约测试锁定 |
| v0.2.0 被误删或移动 | 记录 tag object/peeled commit；所有远程写操作只允许新 v0.2.1；Deliver 后复查 |
| 同一 Release 的双版本让用户困惑 | CHANGELOG、README、plugin docs、asset metadata 明确角色，不改 SDK 下载链接 |
| 新 tag 再次在远程失败 | tag 前先运行本地四产物/完整质量门并等待 main 三版本 CI；失败则不创建 tag |
| GitHub Actions Node 20 弃用提示 | 明确排除本 change；另行升级 action major，避免热修复范围蔓延 |
