# v0.1.1 发布后加固与交付闭环

## Why

v0.1.0 的功能与自动化测试已达到公开测试版水平，但 STDD CLI 缺失导致交付校验不完整，CI 未覆盖示例测试与 SDK 严格类型检查，版本支持口径、构建、依赖安全、容器部署、发布自动化和开源治理仍缺少完整验证证据。

在进入 v0.2.0 功能开发前，应先形成可复现、可审计、可发布的 v0.1.1 基线，避免把工具链和发布债务带入下一轮安全功能开发。

## What Changes

- 恢复与项目 STDD 静态资源兼容且来源可验证的 `bin/stdd`
- 补跑上一变更跳过的 canonical verify、structure merge 和经验库步骤
- 扩大全仓 Ruff/Mypy 门禁并修复示例测试与 SDK 的现有问题
- 统一 Python 3.10–3.12 支持口径并将 CI 覆盖率门槛提高到 90%
- 验证三版本 CI、构建产物、干净安装、依赖安全、Compose 与 Release dry-run
- 补齐安全和社区治理文件、反馈入口及发布文档
- 收敛现有 v0.1.1 改动，通过 Gate 3 后提交、标记并验证远程发布

## Capabilities

### New Capabilities

- **stdd-toolchain-recovery**：恢复 STDD CLI，并使 canonical、结构与经验库交付步骤可执行
- **release-hardening**：提供构建、安装、安全、容器和发布自动化的可复现验证
- **open-source-governance**：提供安全披露、行为准则、贡献和反馈治理契约

### Modified Capabilities

- **github-setup**：扩展 CI 矩阵、质量门禁和 Release workflow
- **project-docs**：统一版本、安装、反馈和发布说明
- **production-deployment**：验证开发与生产 Compose 配置和健康检查
- **detector-sdk**：纳入 SDK 类型检查、测试、构建和版本契约
- **performance-benchmark**：复核并记录可比较的发布基准结果

## Impact

**代码层面**：
- STDD CLI、SDK CLI 类型边界、示例测试格式和验证脚本
- 预计涉及 20 个以上文件、200–1000 行增量或调整

**配置层面**：
- CI、Release、Dependabot、Python 支持口径、覆盖率门槛和 Compose 验证

**基础设施**：
- GitHub Actions、GitHub Release、依赖审计、构建与容器冒烟

## Constraints

- 遵守 Understand、Spec、Verify 三道强制确认门以及 RED→GREEN→REFACTOR
- 保留并审计用户现有未提交改动，不覆盖或丢弃其内容
- 恢复的 STDD CLI 必须具有可验证来源，不执行未经审查的远程脚本
- Python 支持范围统一为 3.10、3.11、3.12；3.12 为推荐运行版本
- Docker 运行时冒烟以本机 Docker 可用为前提；静态 Compose 校验为必做项
- 不在日志、配置、构建产物或发布记录中写入真实密钥
- 远程 push、tag 和 GitHub Release 仅在 Gate 3 通过后执行

## Stakeholders

- 网关部署与运维人员
- 检测器 SDK 和插件开发者
- 项目维护者与外部贡献者
- 依赖网关安全能力的应用团队

## Risk Areas

- **stdd-toolchain-recovery** — 错误或不可信的 CLI 可能破坏 canonical 数据或供应链；固定来源与版本，先离线审查，再以只读命令和临时副本验证
- **github-setup** — 门禁范围或版本矩阵错误可能产生假绿、假红或显著延长 CI；先建立失败基线，再逐项扩展并在三个 Python 版本验证
- **release-hardening** — tag 与公开 Release 会产生外部可见且难以撤回的状态；先 dry-run、检查版本一致性和产物，再在 Gate 3 后发布
- **detector-sdk** — SDK 与网关版本或类型契约不一致会破坏第三方插件开发体验；执行独立测试、类型检查和安装冒烟
- **project-docs** — 文档与实际配置、安装或发布状态可能不一致；按文档从干净环境执行命令并核对链接与配置模型

## NonGoals

- 新增检测器、Provider 或网关业务功能
- 发布 PyPI 包或推送 Docker Registry 镜像
- 实现 v0.2.0 路线图项目
- 对公共 HTTP、配置或插件 API 做不兼容变更

## Critical

- [ ] 非关键变更
- [x] 关键变更 — 涉及发布与供应链基础设施，采用 L3 锚定

## Risk Assessment

- **safety_critical**：false
- **financial**：false
- **cross_system**：true

## Anchoring

- **level**：L3
- **reference_changes**：`2026-08-15-v0.1.0-production-ready`、`2026-08-19-detector-readiness-fail-safe`
- **anchor_implementations**：无

## Success Criteria

- [ ] `bin/stdd --help` 与 `status` 可运行，上一变更跳过的 Phase 6 本地步骤全部完成
- [ ] 全仓 Ruff 与 Mypy 检查无错误
- [ ] 至少 862 个测试通过，跳过项有理由，源代码总覆盖率不低于 90%
- [ ] Python 3.10、3.11、3.12 的 CI 全部通过
- [ ] gateway 和 SDK 的 wheel/sdist 可构建、可在干净环境安装且入口命令可运行
- [ ] 依赖审计不存在未处置的高危漏洞
- [ ] 两个 Compose 文件静态校验通过，Docker 可用时健康冒烟通过
- [ ] Release workflow dry-run 能正确关联 tag、CHANGELOG 和全部构建产物
- [ ] SECURITY、行为准则、贡献指南、模板和反馈入口完整且链接有效
- [ ] 工作区改动全部收敛为可审计提交
- [ ] Gate 3 通过后创建 `v0.1.1` tag，并验证远程 CI 与 GitHub Release
