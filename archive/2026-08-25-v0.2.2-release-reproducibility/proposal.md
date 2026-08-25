# v0.2.2 发布可复现性与证据闭环

<!-- source_hash: 4e3e8720400f68be -->
<!-- generated_at: 2026-08-25T20:52:33.061629 -->
<!-- canonical: canonical/proposals/2026-08-25-v0.2.2-release-reproducibility.yaml -->

## Why

v0.2.1 已修复 Gateway 与 Detector SDK 独立版本发布问题，但现有 GitHub Actions 仍产生 Node.js 20 弃用告警，发布工具采用浮动安装，公开 Release 在精确验证前创建， 且发布后证据与项目路线图尚未形成自动、机器可读的一致闭环。

## What Changes

- 将 GitHub Actions 升级到经验证的 Node 24-compatible 版本并固定完整 commit SHA
- 增加受版本控制的 release constraints，固定构建与依赖审计工具版本
- 将 tag 发布改为 draft-first，仅在 quality、build、audit 和精确验证全部通过后公开
- 扩展发布校验器以验证 notes、四资产、SHA-256 digest、发布状态和 peeled tag SHA
- 生成仅含公开元数据且有界保留的 release-evidence Actions artifact 与 Job Summary
- 将 Gateway 更新到 0.2.2，SDK 保持 0.1.1，并同步实际版本历史、路线图和兼容矩阵

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- **release-hardening**：固化可复现工具链、draft-first 发布、确定性发布审计和证据输出
- **github-setup**：使用 Node 24-compatible 且完整 SHA 固定的 Actions，并维持最小权限
- **project-docs**：同步 v0.2.x 实际历史、后续路线图及 Gateway/SDK 独立版本兼容口径

## Impact

**代码层面**：

- 修改 `tools/release_checks.py` 及发布契约测试。
- 预计涉及 12–20 个文件、200–450 行实现与测试调整。

**配置层面**：

- 修改 GitHub CI/Release workflows、Dependabot，并新增 release constraints。

**基础设施**：

- 仅使用现有 GitHub Actions、workflow artifacts 与 GitHub Release，不新增外部服务。

## Constraints

- 保持四个且仅四个公开分发资产；release evidence 只能作为 Actions artifact。
- `workflow_dispatch` 永不创建 tag 或 Release。
- draft 验证失败时 workflow 必须失败且 Release 保持非公开；不得删除或移动 tag。
- `v0.2.0` 与 `v0.2.1` 的 tag、peeled commit 和 Release 状态保持不可变。
- Gateway 更新到 `0.2.2`，Detector SDK 保持 `0.1.1` 且 API 不变。
- 不修改 Flow、Pipeline、HTTP/SSE、Provider、gRPC 或 YAML 运行时行为。
- evidence 只记录公开元数据并配置明确保留期，不得记录 token、secret 或用户内容。
- Actions 目标版本须在 Spec 阶段核对官方来源和 Node 24 运行时后锁定。

## Stakeholders

- Gateway 发布维护者与仓库管理员。
- Detector SDK 与第三方插件开发者。
- 使用 GitHub Release 产物的部署和安全审计人员。

## Risk Areas

- capability: **github-setup** — Actions major 升级可能改变 artifact、运行时或权限语义；核对官方来源，使用完整 SHA 固定，并覆盖 CI、dry-run、tag 三种触发模式。
- capability: **release-hardening** — draft-first 状态机错误可能公开未验证 Release 或遗留无法诊断的草稿；默认非公开，任一校验失败硬失败，保留诊断并提供显式人工处置步骤。
- capability: **release-hardening** — GitHub API digest、404 或认证失败可能被错误归类为验证成功；要求显式字段和 HTTP 状态，缺失、认证、网络与服务错误全部硬失败。
- capability: **project-docs** — 路线图更新可能范围蔓延或改写历史事实；只同步已发布事实、兼容矩阵和下一版本边界，不重构产品路线图。

## NonGoals

- K8s、Redis、新 Provider、UI 或新检测器。
- PyPI 或 Docker Registry 发布。
- SBOM、Sigstore、SLSA attestation 或制品签名。
- Detector SDK 升版或 API 变化。
- 大规模重写 DESIGN。
- 修改、删除、移动或覆盖任何既有公开 tag。

## Critical

- [ ] 非关键变更
- [x] 关键变更 — 涉及 GitHub Actions、公开 tag、draft/public Release 状态和跨包供应链证据。

## Risk Assessment

- **safety_critical**：false
- **financial**：false
- **cross_system**：true

## Anchoring

- **level**：L3
- **reference_changes**：`2026-08-20-v0.1.1-release-hardening`、`2026-08-23-v0.2.1-release-version-hotfix`
- **anchor_implementations**：`.github/workflows/release.yml`、`tools/release_checks.py`、`tests/unit/release/test_release_contract.py`

## Project Principle Check

1. **Plugin / Flow**：仅修改发布基础设施和文档，不新增领域能力，不改变 Flow 组合或运行时核心。
2. **显式策略 / 失败**：draft、digest、远程 API、权限和发布失败均有显式状态与硬失败，不设置静默 fallback。
3. **透明边界 / 稳定契约**：保持四个公开分发资产、SDK 0.1.1 和所有运行时边界；新增发布检查成本有界。
4. **证据 / 数据保护**：evidence 只包含公开版本、commit、run ID、资产 digest 和结论，配置有界保留且不收集用户内容或 secrets。

**原则取舍或偏离**：无。

## Success Criteria

- [ ] CI、dry-run 和 tag release 不再产生 Node.js 20 弃用告警
- [ ] 所有外部 Actions 固定到已验证的完整 commit SHA
- [ ] 构建与审计工具由受控 constraints 固定，三种发布路径使用同一版本集合
- [ ] workflow_dispatch(version=0.2.2) 完成全部验证且不创建公开 Release
- [ ] tag 发布先创建 draft，只有 quality、build、audit 和精确验证全部通过后才公开
- [ ] Release 精确包含 Gateway 0.2.2 与 SDK 0.1.1 的两个 wheel和两个 sdist
- [ ] 校验器验证 tag、notes、资产集合、SHA-256 digest、draft/prerelease 状态和 peeled SHA
- [ ] 远程不存在检查只接受明确 404，认证、网络和 API 错误全部硬失败
- [ ] evidence artifact 内容完整、无敏感数据并配置明确保留期
- [ ] DESIGN 与公开文档准确描述 v0.2.0、v0.2.1、v0.2.2 和后续 v0.3.0
- [ ] 全量测试、Ruff、Mypy、覆盖率及 Python 3.10/3.11/3.12 CI 全部通过
- [ ] v0.2.0 与 v0.2.1 的远程引用和 Release 状态完全不变

## Complexity & Mode

- 复杂度评分：14/17（preliminary）。
- 执行模式：`thorough`。
- 自动审查：完整性、清晰度、范围三项通过；发现 4 项潜在歧义并全部自动修复，未解决项 0。
