# v0.1.1 — 发布后加固计划（Post-Release Hardening）

> **制定日期**: 2026-08-15
> **背景**: v0.1.0 已作为第一个公开测试版发布（802 tests / 92% coverage / ruff+mypy clean）。
> **状态说明**: 上述数字与下表中的 802 tests 是 2026-08-15 制定计划时的基线；
> 当前验收结果以本次 STDD change 的 `test-report.md` 为准。
> 在进入 v0.2.0 新功能开发前，先做一轮"发布后加固"，把工程质量补到能让真实用户放心使用的程度。
> **执行方式**: 本计划中的文档 / CI / 配置类改动为低风险小改动，可直接实施；
> 涉及代码逻辑或依赖升级的功能性改动，按 STDD 流程（/stdd-understand）启动变更。
> **验收口径**: 每个任务完成 = 改动落地 + 相关测试/检查通过 + 文档同步。

---

## 第一批：工程基础设施（P0，约 2-3 天）

| # | 任务 | 内容 | 验收标准 |
|---|------|------|----------|
| 1.1 | CI 矩阵扩展 | `.github/workflows/ci.yml` 覆盖项目声明的 Python 3.10–3.12 | CI 在 3.10/3.11/3.12 三版本全绿 |
| 1.2 | 本地质量门禁复跑 | 全新 venv（Python 3.10）安装 `-e .[dev,grpc]`，复跑 pytest + coverage + ruff + mypy strict | 802 tests passed、coverage ≥90%、lint/type 全净 |
| 1.3 | Wheel 构建验证 | `python -m build` / hatchling 构建并安装验证 | wheel 可构建、可安装、入口命令可用 |
| 1.4 | 依赖安全扫描 | 本地 `pip-audit` 全量扫描；启用 GitHub Dependabot（actions + pip） | 无高危漏洞；Dependabot 配置落地 |
| 1.5 | Release 自动化 | 新增 `release.yml`：tag 触发 → 构建 wheel/sdist → 生成 GitHub Release 与变更说明 | 打 `v0.1.1` tag 可自动发布（dry-run 验证） |
| 1.6 | CHANGELOG.md | 建立 CHANGELOG，回填 v0.0.1–v0.1.0 各阶段摘要 | 文件存在、历史完整、格式规范（Keep a Changelog） |

## 第二批：质量验证（P1，约 2-3 天）

| # | 任务 | 内容 | 验收标准 |
|---|------|------|----------|
| 2.1 | Quick Start 实测 | 干净环境按 README 从零跑通：安装 → 配置 → 启动 → health → chat 冒烟 | 全流程无文档偏差；发现的问题回写文档 |
| 2.2 | 文档一致性核对 | README ↔ `docs/*` ↔ DESIGN.md 的版本号、命令、配置项、链接逐一核对 | 无过期版本号/失效链接/矛盾配置 |
| 2.3 | Docker 配置验证 | 本机（如有 Docker）验证 `docker-compose.yml` 与 `docker-compose.prod.yml` 可正常启动与健康检查 | 两个 compose 均能启动并通过 /health |
| 2.4 | SDK 覆盖确认 | 确认 CI 对 `sdk/` 的测试覆盖（当前经 `PYTHONPATH=sdk/src` 由 tests/unit/sdk 覆盖）；如有缺口补充 SDK 独立测试 | SDK 关键 API（base/result/modification/context/cli）均有测试 |
| 2.5 | 精度回归 | 重跑 `tests/accuracy` 与 `tests/benchmarks`，确认与发布数据一致 | 4 个规则检测器 ≥90%；benchmark 与 v0.1.0 数据可比 |

## 第三批：开源治理（P2，约 1-2 天）

| # | 任务 | 内容 | 验收标准 |
|---|------|------|----------|
| 3.1 | SECURITY.md | 安全漏洞报告流程（私有披露、响应时限、修复流程） | 文件存在并链接进 README |
| 3.2 | CODE_OF_CONDUCT.md | 贡献者行为准则 | 文件存在并链接进 README |
| 3.3 | CONTRIBUTING.md 校对 | 按文档实测开发流程（clone → 安装 → 测试 → lint），修正偏差 | 新人可按文档独立跑通 |
| 3.4 | 仓库治理设置 | issue 标签、里程碑（v0.1.1 / v0.2.0）、PR 模板核对 | 标签/里程碑就绪，模板可用 |
| 3.5 | 反馈渠道确认 | issue 模板（bug/feature）可用性检查；评估是否开启 GitHub Discussions | 反馈渠道明确并在 README 可见 |

## 完成定义（Definition of Done）

- [ ] 第一批 6 项全部落地，CI 三版本全绿
- [ ] 第二批 5 项验证完成，发现的文档/代码问题已修复或登记
- [ ] 第三批 5 项治理文件就绪
- [ ] 全部改动合并 main，打 `v0.1.1` 补丁发布（含 CHANGELOG + Release notes）
- [ ] 将本计划标记完成，归档到 `archive/`

## 后续（v0.2.0，走 STDD）

按 DESIGN §18 路线图推进（用户后续确认优先级）：新检测器（jailbreak/hallucination）→ Provider 故障转移 → Redis 分布式限流 → K8s Helm Chart → sidecar mTLS。
每个变更经 `/stdd-understand` 启动。
