# v0.2.1 独立版本发布热修复

<!-- source_hash: fa3cdb212ab550a2 -->
<!-- generated_at: 2026-08-23T22:44:17.589817 -->
<!-- canonical: canonical/proposals/2026-08-23-v0.2.1-release-version-hotfix.yaml -->

## Why

v0.2.0 已确认采用 Gateway 0.2.0 与 Detector SDK 0.1.1 的独立版本组合，但 tools/release_checks.py 仍把 Gateway 和 SDK 的四个版本声明放入同一集合，并强制全部 等于发布 tag。main 的 Python 3.10/3.11/3.12 CI 全绿后，v0.2.0 Release workflow 因此在版本校验阶段失败，未构建产物或创建 GitHub Release。


## What Changes

- 发布校验器分别验证 Gateway 发布版本和 SDK 独立版本：Gateway 元数据与运行时版本必须匹配 tag，SDK 元数据与运行时版本必须彼此一致
- 保持版本错配为显式硬失败，并新增 Gateway tag 错配、SDK 内部错配、缺失或空 CHANGELOG 的负向测试
- 将 Gateway 元数据、CHANGELOG、README、配置与部署版本口径提升至 0.2.1；Detector SDK 保持 0.1.1
- 验证 Gateway 0.2.1 与 SDK 0.1.1 的两个 wheel、两个 sdist、产物 metadata、干净安装及三个 CLI 入口
- 保持 Release workflow 的 dry-run 不发布、tag push 才发布及 quality/build/audit 全部门依赖；消除默认版本口径漂移
- Gate 3 后先推送 main 并等待三版本 CI，再创建全新 v0.2.1 tag 和 GitHub Release；保留 v0.2.0 tag 与失败运行记录

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- **release-hardening**：支持 Gateway 与 SDK 独立版本，同时保持 tag、CHANGELOG、产物、审计和发布失败门严格可验证
- **detector-sdk**：明确 SDK 0.1.1 可随 Gateway 0.2.1 构建交付，SDK 包与运行时版本仍必须内部一致
- **project-docs**：同步 Gateway 0.2.1 / SDK 0.1.1 双版本口径及 v0.2.0 失败发布后的补丁说明

## Impact

**代码层面**：

- 预计修改发布校验器、发布契约测试和 Release workflow，约 8–20 个文件、50–200 行实现与测试。
- 更新 Gateway 包版本、运行时版本、CHANGELOG、README、部署示例及相应版本断言。

**配置层面**：

- 不修改 Gateway 运行时 YAML schema 或默认 Flow；仅更新示例文件中的发布版本注释。
- Release workflow 的手动验证输入不再保留过时默认版本。

**基础设施**：

- 不新增基础设施；继续使用现有 GitHub Actions quality、build、audit、release jobs。
- Deliver 阶段新增 `v0.2.1` tag 和 GitHub Release，不触碰 `v0.2.0` tag。

## Constraints

- 严格遵循 STDD 与 RED → GREEN → REFACTOR，发布校验修复必须先有可观察失败测试。
- 不得删除、移动、强推或覆盖远程 `v0.2.0` tag。
- Detector SDK 版本保持 `0.1.1`，公开接口、导入路径、生命周期与产物名称不变。
- Gateway tag 错配、SDK 内部错配和 CHANGELOG 缺失必须继续硬失败，不得降级为 warning。
- GitHub Release 只能由经 Gate 3 批准且远程三版本 CI 全绿的新 tag 驱动。
- 不得修改 Flow、HTTP/SSE、Provider、gRPC proto 或 legacy YAML 运行时契约。

## Stakeholders

- Gateway 发布维护者与仓库管理员。
- Detector SDK 与第三方插件开发者。
- 从 GitHub Release 安装 Gateway 或 SDK 的用户。
- 供应链、安全审计与 CI 维护人员。

## Risk Areas

- capability: **release-hardening** — 拆分版本校验可能错误放行 Gateway tag 错配或任意 SDK 漂移；分别建立 Gateway tag、Gateway runtime、SDK metadata/runtime 和 CHANGELOG 的正负向契约测试。
- capability: **release-hardening** — 发布修复可能诱导删除或移动已公开 `v0.2.0` tag；把 tag 不可变性列为硬约束和远程验收项，只允许创建 `v0.2.1`。
- capability: **detector-sdk** — 同一 GitHub Release 中包含旧版本 SDK 产物可能造成版本含义不清；CHANGELOG、README、产物 metadata 与测试均明确 Gateway `0.2.1` / SDK `0.1.1` 独立版本组合。
- capability: **release-hardening** — dry-run 或失败 job 可能意外创建不完整 Release；保留 tag-only release condition 及 quality/build/audit needs，失败时 release job 必须 skipped。

## NonGoals

- 不删除、移动、覆盖或重新触发 `v0.2.0` tag。
- 不提升 Detector SDK 版本，不改变 SDK 契约。
- 不修改 Flow Runtime、Detector pipeline、HTTP/SSE、Provider 或 YAML 行为。
- 不新增 PyPI 发布、Docker Registry 发布或签名基础设施。
- 不实现 Kubernetes、Redis、新 Provider、UI 或新检测器。
- 不顺带升级 GitHub Actions major 版本；Node.js 20 弃用提示另行处理。

## Critical

- [ ] 非关键变更
- [x] 关键变更 — 涉及公开 tag、跨包版本和 GitHub Release 供应链。

## Risk Assessment

- **safety_critical**：false
- **financial**：false
- **cross_system**：true

## Anchoring

- **level**：L3
- **reference_changes**：
  - `2026-08-20-v0.1.1-release-hardening`
  - `2026-08-22-v0.2.0-flow-foundation`
- **anchor_implementations**：`tools/release_checks.py`、`.github/workflows/release.yml`、`tests/unit/release/test_release_contract.py`

## Project Principle Check

1. **Plugin / Flow**：本变更只修复发布工具与版本元数据，不引入领域能力、不改变 Flow 组合，也不把发布策略放入 Gateway 运行时核心。
2. **显式策略 / 失败**：Gateway tag、Gateway runtime、SDK metadata/runtime 与 CHANGELOG 的验证职责分别显式；任一错配都以稳定非零退出阻断 build，失败 release job 不运行。
3. **透明边界 / 稳定契约**：Gateway 以补丁版本恢复发布，Detector SDK 保持独立 `0.1.1` 契约；HTTP、SSE、Provider、Flow、gRPC proto 与 legacy YAML 均不改变，发布检查成本有界。
4. **证据 / 数据保护**：GitHub Actions job、产物 metadata、tag commit 与 Release assets 构成可审计证据；检查器只读取公开版本字符串和 CHANGELOG，不采集内容、密钥或其他敏感数据。

**原则取舍或偏离**：保留没有 GitHub Release 的 `v0.2.0` tag 及失败运行记录，以遵守公开 tag 不可变原则；通过 `v0.2.1` 补丁恢复发布。该取舍已由用户确认，不构成原则偏离。

## Success Criteria

- [ ] 发布校验器接受 Gateway 0.2.1 / SDK 0.1.1，且 Gateway 包元数据与运行时版本均精确匹配 v0.2.1 tag
- [ ] Gateway tag 错配、Gateway metadata/runtime 错配、SDK metadata/runtime 错配、缺失或空 0.2.1 CHANGELOG 均返回非零状态
- [ ] 构建生成 Gateway 0.2.1 与 SDK 0.1.1 的两个 wheel 和两个 sdist，四个产物 metadata 检查通过
- [ ] 干净环境同时安装两个 wheel 后，z-safety-gateway、zlg、zlg-sdk 三个入口均成功运行
- [ ] workflow_dispatch 只执行验证且不创建 tag 或 GitHub Release；tag push 仍依赖 quality、build、audit 全绿
- [ ] 本地全量 pytest、Ruff、Mypy、coverage 和发布契约通过；远程 Python 3.10、3.11、3.12 CI 全部通过
- [ ] Gate 3 后全新 v0.2.1 tag 指向经验证提交，并创建包含四个验证产物及精确 0.2.1 notes 的 GitHub Release
- [ ] 远程 v0.2.0 tag 的 object ID 保持不变，且不创建伪造的 v0.2.0 Release
- [ ] Flow、HTTP/SSE、Provider、Detector SDK API、gRPC proto、PipelineEngine 与 legacy YAML 回归无变化

## Complexity & Mode

复杂度评分：13/17。

| 维度 | 得分 |
|------|------|
| 预估文件数（8–20） | 2 |
| 预估行数（50–200） | 1 |
| Capability 数（3） | 1 |
| 风险等级（高） | 4 |
| 发布 API / 产物契约 | 2 |
| 供应链安全 | 3 |

执行模式：**thorough**。使用完整 Spec、Slice、严格 RED → GREEN → REFACTOR、全量失败模式检查和三道强制 Gate。
