# v0.1.1 发布后加固与交付闭环 — 技术设计

## Context

项目已经发布 v0.1.0，并在提交 `33437bd` 完成 Detector Readiness Fail-Safe。当前功能回归为 862 passed / 1 skipped、覆盖率约 93%，但交付链仍有以下缺口：

- 仓库缺少 `bin/stdd` 及其 Python 包，上一变更的 canonical、结构索引和经验库步骤被跳过。
- 项目 `.stdd/config.d/project.yaml` 标记 2.9.3，技能文件为 2.9.5–2.9.6，且没有 `.stdd/version.yaml`。
- CI 只覆盖项目核心目录；示例插件测试目录与 SDK 严格类型检查不在门禁内。
- CI 覆盖率门槛为 80%，低于 v0.1.1 计划的 90%。
- Python 支持声明存在 3.10+、3.12+ 两种口径。
- Release、Dependabot、构建和文档已有未提交草稿，但未形成可复现验证。
- 安全披露、行为准则、远程 labels/milestones 和正式补丁发布尚未闭环。

本变更不修改网关 HTTP、配置或插件运行时契约；业务风险主要来自发布供应链、假绿门禁和外部发布状态。

## Decisions

### D1. 固定 vendoring STDD 官方 v2.9.5 CLI

**方案**：从官方仓库 `https://github.com/leonai42/stdd` 固定提交 `fd9df3104d3588eb145cc84ec551c1803e783c9e`，纳入 `bin/stdd`、`stdd/` Python 包、来源说明、文件哈希和 MIT 许可证。项目 `.stdd/version.yaml` 标记 CLI 版本、来源提交与项目 overlay 状态。

**为什么**：v2.9.5 与现有 2.9.x 技能和 canonical 布局相容；固定提交可离线运行并可审计。最新 v3.0.5 改变了流程语义，不适合在补丁发布中隐式升级。

**备选方案及排除原因**：

- 直接使用 v3.0.5：跨主版本升级，范围和回归面过大。
- 只写最小兼容脚本：会形成私有、不完整的第二套 CLI。
- 每次运行从网络下载：不可复现且扩大供应链风险。

### D2. 用临时兼容工作区补录已归档 change

**方案**：不移动 `archive/2026-08-19-detector-readiness-fail-safe`。验证程序在临时目录构造 CLI 预期的 `changes/<id>/canonical/` 布局，运行 canonical verify；结构 delta 从 `33437bd^..33437bd` 的真实文件列表生成，再由 CLI merge；最终确定性写回项目级 canonical 和 `.stdd/code-structure/`。

**为什么**：官方 v2.9.5 的 canonical/structure 命令只识别 `changes/`，直接对 archive 执行会失败；移动归档会破坏已提交历史语义。Git diff 比扫描 change 文档更能反映真实代码结构。

**备选方案及排除原因**：

- 将 archive 临时移回 changes：工作区风险高，且可能与当前 change 冲突。
- 修改官方 CLI 支持 archive：会破坏 vendored 源码的固定哈希。
- 跳过补录：无法完成优先级第 2 项。

### D3. 经验库只做真实生命周期推进

**方案**：初始化项目本地经验索引，补录“请求级 detector 过滤”“健康检查日志脱敏”“取消时 finally 释放本地资源”三个模式。先进入 discovered/verified；只有满足 occurrence 和 confidence 阈值的条目才 deposit/share。

**为什么**：上一报告明确记录了这些经验，但无 CLI 无法入库。人为伪造 occurrence 会污染后续自动复用。

**备选方案及排除原因**：

- 直接标记 shared：违反经验生命周期。
- 复制官方示例经验库：会把非本项目证据混入项目索引。

### D4. 项目代码全门禁，上游 vendored 代码做完整性门禁

**方案**：Ruff 覆盖 `src/`、`tests/`、`sdk/src/` 和两个示例插件的 `src/`、`tests/`；Mypy strict 覆盖 `src/` 与 `sdk/src/`。Vendored `stdd/` 保留上游原文，通过提交哈希、文件清单、官方选择测试和 CLI 冒烟验证。

**为什么**：自动格式化 vendored 代码会破坏固定来源；项目拥有的代码则应全部纳入一致质量标准。

**备选方案及排除原因**：

- 对整个 vendored 包执行项目 Ruff/Mypy 并批量修改：失去上游可比性。
- 保持当前 CI 范围：继续遗漏已发现的三个错误。

### D5. Python 支持为 3.10–3.12，3.12 为推荐发布版本

**方案**：`requires-python >=3.10` 保持不变；CI 覆盖 3.10/3.11/3.12；构建和发布 job 使用 3.12；AGENTS、README、CONTRIBUTING 与文档统一表述。

**为什么**：代码、Ruff、Mypy 与现有用户基线均以 3.10 为最低版本，直接改成 3.12+ 会制造不必要的兼容性破坏。

**备选方案及排除原因**：

- 仅支持 3.12+：与当前包元数据和公开测试版承诺冲突。
- 继续保留多种口径：用户无法判断真实支持范围。

### D6. 网关与 SDK 协调发布 0.1.1，但保持独立版本语义

**方案**：网关与 SDK 的 pyproject、模块 `__version__` 和测试均更新为 0.1.1。SDK 因 CLI 类型修复和独立构建验证参与本次补丁发布；未来版本不要求与网关同步。

**为什么**：SDK 当前 pyproject 已为 0.1.0，模块版本草稿也在向 0.1.0 对齐；本次确有 SDK 代码修复，因此补丁升级合理。

**备选方案及排除原因**：

- SDK 保持 0.1.0：发布资产包含代码变化但版本不变。
- 恢复 SDK 1.0.0：与首次公开测试版的现有包元数据和用户改动相冲突。

### D7. CI 分层为质量矩阵、构建、依赖审计和发布 dry-run

**方案**：

- quality matrix：Python 3.10/3.11/3.12，Ruff、Mypy、pytest，coverage gate 90%。
- build：Python 3.12 构建 gateway/SDK wheel+sdist，执行 metadata 检查与干净环境入口冒烟。
- audit：`pip-audit` 扫描网关和 SDK 解析依赖，任何未豁免漏洞失败。
- release dry-run：手动触发只构建、验证版本和 CHANGELOG，不创建 Release。

**为什么**：将跨版本正确性、构建可用性和安全审计分开，可定位失败且避免每个矩阵重复构建。

**备选方案及排除原因**：

- 所有工作放进矩阵 job：重复且难以定位。
- 只做本地检查：无法证明 GitHub runner 上的三版本兼容性。

### D8. Release workflow 以 tag 为唯一公开发布入口

**方案**：`workflow_dispatch` 支持 dry-run；只有 `refs/tags/v*` 且版本、CHANGELOG、产物一致时才执行 `gh release create`。Gate 3 前不 push tag。发布后验证 CI、Release 页面和四个分发产物。

**为什么**：防止手动测试误创建公开 Release，并保持 tag、版本和发布说明的一一对应。

**备选方案及排除原因**：

- push main 自动发布：容易产生非版本化公开产物。
- 本地直接调用 `gh release create`：绕过可审计 workflow。

### D9. 依赖审计默认零已知漏洞

**方案**：`pip-audit` 对解析后的生产依赖执行扫描；任何漏洞均失败。若确需豁免，必须在仓库记录漏洞 ID、理由、影响范围和到期日。

**为什么**：安全网关应采用比“只阻止高危”更清晰且可自动执行的默认策略。

### D10. Compose 静态校验必做，运行冒烟按环境能力执行

**方案**：开发和生产 Compose 都执行 `docker compose config`；Docker daemon 可访问时启动最小配置并验证 `/health` 与 `/ready`，完成后正常停止。若 daemon 确实不可用，必须记录外部环境限制，不能把静态校验冒充运行成功。

**为什么**：静态校验可稳定自动化，运行冒烟提供更强证据，但依赖本机 Colima/Docker 权限与镜像网络。

### D11. 治理文件使用标准文本并验证远程仓库状态

**方案**：新增项目安全披露政策和 Contributor Covenant，更新 CONTRIBUTING/README 导航，验证 Issue/PR 模板、labels、v0.1.1/v0.2.0 milestones。远程写操作只在 Gate 3 后执行。

**为什么**：文件存在不等于远程协作入口可用；补丁发布需要同时验证仓库内契约和 GitHub 状态。

## Architecture

```text
官方 STDD v2.9.5 固定提交
        │ 审查 + 哈希 + MIT notice
        ▼
bin/stdd + stdd/ ──► CLI smoke / upstream selection tests
        │
        ├──► 临时兼容工作区 ──► canonical verify ──► canonical/ 索引
        ├──► git diff 33437bd ──► structure delta ──► .stdd/code-structure/
        └──► 经验补录 ──► .stdd/experiences/（真实生命周期）

项目改动
  ├──► quality matrix 3.10/3.11/3.12 ──► Ruff + Mypy + pytest/cov≥90
  ├──► build job ──► gateway + SDK wheel/sdist ──► clean-install smoke
  ├──► audit job ──► pip-audit
  ├──► compose validation ──► optional runtime health smoke
  └──► release dry-run ──► Gate 3 ──► commit/tag push ──► GitHub Release
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 固定的 STDD v2.9.5 后续落后 | 记录 provenance；未来单独 STDD upgrade change，不在补丁中自动升级 |
| 官方 CLI 对 archive 支持有限 | 临时兼容工作区 + 确定性导入，不修改归档或 vendored 源码 |
| vendoring 增加仓库体积 | 仅纳入运行所需包和许可证；不纳入完整上游仓库历史 |
| CI 扩展增加耗时 | 构建/审计与版本矩阵分层，避免重复工作 |
| coverage 90% 在多版本上波动 | 使用同一测试集和 source scope；低于门槛即暴露真实回归 |
| Docker daemon/镜像网络不可用 | 静态校验必做；运行限制如实记录，不伪造 PASS |
| GitHub 凭据不足 | Gate 3 后再请求最小必要授权；本地产物与 tag 准备不受影响 |
| tag/Release 难以撤回 | 发布前验证版本、CHANGELOG、产物哈希和 dry-run；tag 后只允许补充说明，不重写 |
| SDK 与网关同步版本被误解为永久绑定 | 文档明确“本次协调发布，未来独立演进” |
