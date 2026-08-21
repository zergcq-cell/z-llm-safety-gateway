# v0.1.1 发布后加固与交付闭环测试方案

> 版本：v0.1.1
> 创建日期：2026-08-20
> 对应 Phase 2 Spec：8 个 capability，共 23 Requirements / 31 Scenarios

## 一、测试策略

### 1.1 测试金字塔

- 单元/契约测试：验证版本、YAML、文档、CLI 参数、Release 条件和治理文件。
- 集成测试：运行 STDD CLI、构建分发包、干净安装、Compose 校验和完整质量门禁。
- E2E：Python 三版本远程 CI、Docker 健康冒烟、tag 驱动 GitHub Release。

### 1.2 测试原则

- 每个 Scenario 对应唯一 TC-ID；实现前先建立失败检查。
- 上游 vendored STDD 以固定提交和哈希验证，不做项目风格重写。
- 外部状态必须读取验证；没有权限或环境时记录 SKIPPED/BLOCKED，不伪造 PASS。
- Release dry-run 不能创建 tag 或 GitHub Release。
- 构建和安装使用临时目录，避免把产物混入源码提交。

### 1.3 已有测试资产

| 测试资产 | 当前规模 | 类型 | 覆盖范围 |
|----------|----------|------|----------|
| `tests/` + 两个示例插件 tests | 905 collected | 单元/集成 | 网关、SDK、插件、accuracy、发布契约 |
| `tests/benchmarks/bench_pipeline.py` | 2 suite | 基准 | 规则 pipeline 延迟与吞吐 |
| `.github/workflows/ci.yml` | 3 版本矩阵 | CI | Ruff/Mypy/pytest/coverage |
| 上游 STDD v2.9.5 tests | 选择执行 | 上游契约 | canonical/structure/experience/CLI |

## 二、详细测试案例

| ID | Capability / Scenario | P | Arrange / Act | Assert |
|----|-----------------------|---|---------------|--------|
| TC-STDD-001 | 固定可信来源 | P0 | 检查 provenance、MIT notice、固定提交 | 来源、tag、commit、许可证 SHALL 完整 |
| TC-STDD-002 | Vendored 文件完整性 | P0 | 对 `bin/stdd`、`stdd/` 计算清单哈希 | 文件 SHALL 与固定提交一致，项目 overlay 单独记录 |
| TC-STDD-003 | CLI 可运行 | P0 | 执行 `python bin/stdd --help` 与 `status` | 两命令 SHALL exit 0 且识别当前 change |
| TC-STDD-004 | Canonical 补录 | P0 | 临时镜像 archived change 并执行 canon verify | DC-HASH/DC-FIELD SHALL 通过且归档不被改写 |
| TC-STDD-005 | 结构索引补录 | P0 | 从 `33437bd` diff 生成 delta 并 merge 两次 | 首次 SHALL 合并；重复执行 SHALL 不产生重复模块记录 |
| TC-STDD-006 | 经验库补录 | P0 | add/list/stats 三个经验模式 | 条目 SHALL 可查询；不满足阈值时 SHALL NOT deposit/share |
| TC-REL-001 | 版本一致性 | P0 | 检查 gateway/SDK 元数据、模块版本、CHANGELOG | 本次发布版本 SHALL 均为 0.1.1 |
| TC-REL-002 | 构建产物 | P0 | 构建两个包并运行 metadata check | 2 wheel + 2 sdist SHALL 有效 |
| TC-REL-003 | 干净安装与入口 | P0 | 临时 venv 安装 wheel，运行三个 CLI `--help` | 安装和入口 SHALL exit 0 |
| TC-REL-004 | 依赖审计 | P0 | 对解析生产依赖执行 pip-audit | SHALL 无未豁免已知漏洞 |
| TC-REL-005 | Release dry-run 安全性 | P0 | workflow_dispatch dry-run / 本地等价验证 | SHALL 构建验证且 SHALL NOT 创建 Release |
| TC-REL-006 | Release notes 映射 | P0 | 从 CHANGELOG 提取 0.1.1 章节 | SHALL 非空、版本准确且无下一版本内容 |
| TC-REL-007 | Tag 驱动远程发布 | P0 | Gate 3 后 push main 与 v0.1.1 tag | 远程 CI SHALL 全绿且 Release SHALL 含四个产物 |
| TC-GOV-001 | 安全披露政策 | P0 | 检查 SECURITY.md 与 README 链接 | SHALL 含私有披露、响应时限、支持版本、禁用公开 0-day 细节 |
| TC-GOV-002 | 行为准则 | P2 | 检查 CODE_OF_CONDUCT.md | SHALL 为完整标准文本并含执行联系人/方式 |
| TC-GOV-003 | 贡献与反馈渠道 | P1 | 检查 CONTRIBUTING、模板、README、远程 labels/milestones | 文件与 GitHub 状态 SHALL 完整一致 |
| TC-GH-001 | 三版本矩阵 | P0 | 解析 CI workflow | SHALL 包含 3.10/3.11/3.12 |
| TC-GH-002 | 全项目质量范围 | P0 | 检查并执行 CI 等价 Ruff/Mypy/pytest | Ruff SHALL 含示例 tests；Mypy SHALL 含 SDK；coverage SHALL ≥90% |
| TC-GH-003 | Dependabot 范围 | P0 | 解析 dependabot.yml | SHALL 覆盖 root pip、SDK pip、GitHub Actions |
| TC-GH-004 | 远程 CI 真实性 | P0 | push 后读取 Actions 状态 | 三版本、build、audit SHALL 全绿 |
| TC-DOCS-001 | Python/版本口径 | P1 | 扫描 AGENTS、README、pyproject、docs | SHALL 统一为 Python 3.10–3.12、推荐 3.12、版本 0.1.1 |
| TC-DOCS-002 | Quick Start 实测 | P1 | 在干净环境按 README 安装、配置、启动、health | 命令 SHALL 可执行且文档无漂移 |
| TC-DOCS-003 | 导航与链接 | P1 | 检查本地 Markdown 链接与反馈入口 | SHALL 无断链并链接安全/贡献/行为准则 |
| TC-DEPL-001 | Compose 静态校验 | P0 | 对两个 Compose 执行 `docker compose config` | 两者 SHALL exit 0 |
| TC-DEPL-002 | 生产部署不变量 | P0 | 检查 replicas/resources/health/sidecar | 生产配置 SHALL 保留全部不变量 |
| TC-DEPL-003 | Docker 健康冒烟 | P1 | daemon 可用时启动最小配置并请求 health/ready | 容器 SHALL healthy；不可用时 SHALL 明确记录环境限制 |
| TC-SDK-001 | SDK 严格类型 | P0 | 执行 `mypy sdk/src` | SHALL exit 0，无 Any-return |
| TC-SDK-002 | SDK 行为与版本 | P0 | 执行 SDK 单元测试并检查 `__version__` | 测试 SHALL 通过且版本 SHALL 为 0.1.1 |
| TC-SDK-003 | SDK 独立构建安装 | P0 | 构建、安装 SDK wheel，运行 zlg-sdk | SHALL 不依赖网关包且入口可运行 |
| TC-BENCH-001 | 单 suite 报告真实性 | P1 | 分别运行 latency/throughput | 未运行指标 SHALL 显示“—”，不得伪造 0/PASS |
| TC-BENCH-002 | 发布基准可比性 | P1 | 运行 all 并与 v0.1.0 报告比较 | SHALL 记录环境和差异，基准不作为 CI 硬门槛 |

## 三、测试执行矩阵

| 功能模块 | 单元/契约 | 集成 | E2E | 状态 |
|----------|-----------|------|-----|------|
| STDD CLI 恢复 | 哈希/版本 | CLI + backfill | — | 🟢 本地完成 |
| 质量门禁 | workflow 契约 | 本地等价命令 | GitHub Actions | 🟡 本地完成，远程待 Gate 3 |
| 构建与审计 | 元数据 | wheel 安装/pip-audit | CI build/audit | 🟡 本地完成，远程待 Gate 3 |
| 文档与治理 | 文件/链接 | Quick Start | GitHub labels/milestones | 🟡 本地完成，远程待 Gate 3 |
| Compose | YAML 不变量 | compose config | 双副本 + sidecar health/ready | 🟢 完成并清理 |
| SDK | 单元/mypy | wheel 安装 | CI 3 版本 | 🟡 本地完成，远程待 Gate 3 |
| Benchmark | render 单测 | 本地基准 | 发布报告 | 🟢 完成 |
| Release | workflow 契约 | 本地等价 dry-run | tag + Release | 🟡 本地完成，远程待 Gate 3 |

## 四、回归风险矩阵

| 风险区域 | v0.1.1 改动 | 已有回归保护 | 风险等级 |
|----------|-------------|-------------|---------|
| 网关运行时 | 无预期业务改动 | 862 tests / 93% coverage | 🟢 |
| STDD 工具链 | 新增 vendored CLI 与索引 | 上游选择测试 + 新 CLI 契约 | 🔴 |
| CI | 范围、矩阵、门槛扩大 | 本地等价命令 | 🟡 |
| SDK | 类型修复、版本、构建 | SDK 单元测试 | 🟡 |
| Release | 新 workflow/tag/公开 Release | dry-run + 版本契约 | 🔴 |
| Docker | 配置实测 | 既有 compose 结构 | 🟡 |
| 文档治理 | 新增/同步 | 链接和内容契约 | 🟢 |

## 五、建议补充顺序

1. **P0**：TC-STDD-001～006、TC-REL-001～007、TC-GOV-001、TC-GH-001～004、TC-DEPL-001～002、TC-SDK-001～003。
2. **P1**：TC-GOV-003、TC-DOCS-001～003、TC-DEPL-003、TC-BENCH-001～002。
3. **P2**：TC-GOV-002。
