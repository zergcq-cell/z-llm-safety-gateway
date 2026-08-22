# Phase Context — 2026-08-20-v0.1.1-release-hardening

## Phase 1: UNDERSTAND (completed 2026-08-20T22:29:12+08:00)

### 关键决策

- **需求边界**：完成 STDD、全项目质量、构建安全、Docker、治理和 v0.1.1 发布闭环；不新增网关业务能力。
- **优先级**：发布/供应链 P0，文档/容器 P1，行为准则 P2。
- **版本范围**：Python 3.10–3.12；gateway 与 SDK 本次协调发布 0.1.1。

### 用户关注点

- 用户要求严格按建议的 1→5 顺序完成，而不是只给评估建议。
- 用户明确选择 thorough 模式并确认 Gate 1。

### 产出物

- `proposal.yaml` / `proposal.md` — Gate 1 已确认。

## Phase 2: SPEC (completed 2026-08-20T22:38:45+08:00)

### 关键技术决策

- 固定 vendoring STDD 官方 v2.9.5 commit `fd9df3104d3588eb145cc84ec551c1803e783c9e`，保留 MIT notice 与哈希。
- 不改写 archive；用临时兼容工作区补跑 canonical，用 `33437bd` 真实 diff 补结构索引。
- 经验只按真实 occurrence/confidence 生命周期推进，不伪造 deposit/share。
- 项目拥有代码全部进入 Ruff/Mypy；vendored 上游代码走 provenance/哈希/上游选择测试。
- CI 分为三版本 quality、build、audit、release dry-run；coverage gate 90%。
- tag 是唯一公开发布入口，Gate 3 前不 push/tag/release。

### 经验触发

- EXP-001：生命周期资源清理由 app/init 边界管理；用于 STDD backfill 和 Docker cleanup 约束。
- EXP-007：保持既有同步 gRPC 模型；本 change 不触碰运行时架构。
- readiness change 三个待入库模式：请求级过滤、健康日志脱敏、取消时 finally 释放。

### 已知坑点

- 官方 v2.9.5 CLI 的 canonical/structure 命令只识别 `changes/`，必须使用临时兼容布局。
- 官方 v2.9.5 tag 的静态 `version.yaml` 仍显示 2.9.3；项目 provenance 必须同时记录 tag 与 commit，不能只信单一版本字段。
- 当前仅有 Python 3.10 本地 venv；3.11/3.12 主要由远程 CI 验证。
- Docker 客户端存在，但受限环境不能访问 Colima socket；运行冒烟需要最小权限提升。
- 本机没有 `gh`，远程 GitHub 状态可能需要浏览器会话、安装 CLI 或 API 凭据。

### 低置信度场景

- SC-DEPL-006：Docker daemon 和镜像网络可用性。
- SC-REL-007：GitHub 身份、tag push、Actions 和 Release 的真实外部状态。

### 产出物

- `design.md`
- `specs/*/{spec.yaml,agent_spec.yaml,spec.md}` — 8 capabilities / 23 requirements / 31 scenarios
- `test-plan.md` — 31 TC（P0 23 / P1 7 / P2 1）

## Phase 3: SLICE (completed 2026-08-20T23:04:08+08:00)

### 当前状态

Gate 2 已确认；按依赖关系形成 S1～S6 六个串行切片。用户确认 Phase 3～5 全自动长程模式；Gate 3 仍为强制人工确认点。

## Phase 4: BUILD (in progress)

### S1 STDD CLI/交付补录（completed 2026-08-20T23:18:40+08:00）

- **RED**：新增 6 个测试，覆盖 provenance/哈希/CLI、canonical、结构索引与经验库；初始因 CLI 和补录工具缺失而失败。
- **GREEN**：固定 vendoring 官方 v2.9.5 commit `fd9df3104d3588eb145cc84ec551c1803e783c9e`；新增项目 overlay `tools/stdd_backfill.py`，完成 canonical、结构和三个真实经验模式补录。
- **REFACTOR**：上游文件保持原字节；项目适配逻辑与 provenance、清单哈希、许可证分离；补录可幂等重复运行。
- **切片验证**：TC-STDD-001～006 全覆盖；定向 6 passed；Ruff passed；Mypy passed；全量回归 868 passed / 1 skipped。
- **真实性约束**：archive 未改写；经验保持 `discovered / occurrences=1 / confidence=0.5`，未伪造 deposit/share。

### 当前切片

### S2 全项目质量与 SDK（completed 2026-08-20T23:21:44+08:00）

- **RED**：新增 3 个发布契约测试；CI 示例测试目录、SDK Mypy 范围、90% 覆盖率和 SDK 0.1.1 契约按预期失败；另复现两个示例 import 与 SDK `Any` return 静态错误。
- **GREEN**：CI 矩阵覆盖 Python 3.10/3.11/3.12；Ruff 纳入两个示例 tests，Mypy 纳入 `sdk/src`，coverage gate 提升到 90%；SDK 元数据、模块版本和测试统一为 0.1.1。
- **REFACTOR**：SDK CLI handler 使用明确 `Callable[..., int]`，消除 Any-return；示例 import 仅做机械排序。
- **切片验证**：TC-GH-001～002、TC-SDK-001～002 全覆盖；定向 19 passed；Ruff passed；Mypy 84 files passed；CI 等价全量 871 passed / 1 skipped，coverage 92.85%。

### 当前切片

### S3 构建/审计/Release dry-run（completed 2026-08-21T07:29:56+08:00）

- **RED**：新增 6 个交付契约测试；复现网关 0.1.0、四产物版本不一致、SDK 模板错误依赖 1.x、Release YAML 无法解析及缺少安全 dry-run。
- **GREEN**：gateway/SDK 统一 0.1.1；补充非空 CHANGELOG；Release workflow 拆分 build/audit/release，手动运行只验证，tag push 才发布；Dependabot 覆盖三类依赖。
- **REFACTOR**：发布版本与说明提取集中到 `tools/release_checks.py`；SDK 脚手架和示例插件依赖修正为 `>=0.1.1,<0.2`；SDK 明确未来独立版本语义。
- **构建证据**：2 wheel + 2 sdist；Twine 4/4 passed；临时干净环境安装 gateway/SDK，`z-safety-gateway`、`zlg`、`zlg-sdk` 3/3 passed，`pip check` passed。
- **审计证据**：对干净安装解析出的锁定生产依赖执行 pip-audit，排除本地包自身及非运行时 pip/setuptools 构建工具；No known vulnerabilities found，无豁免。
- **切片验证**：TC-REL-001～006、TC-GH-003、TC-SDK-003 全覆盖；定向 25 passed；Ruff/Mypy passed；全量 877 passed / 1 skipped，coverage 92.85%。

### 当前切片

### S4 Compose/Benchmark（completed 2026-08-21T07:39:55+08:00）

- **RED**：新增 5 个部署/基准契约测试；复现生产镜像仍为 0.1.0、sidecar 没有实际 endpoint 配置，以及 benchmark 报告逻辑与重型运行模块耦合。
- **GREEN**：生产镜像更新为 0.1.1；新增 `config/gateway.prod.yaml`，将 `acme_guard` 明确连至 `acme-guard:50051`；两份 Compose config 通过。
- **REFACTOR**：报告渲染拆至轻量 `tools/benchmark_report.py`；修复 benchmark 直接执行时的仓库根路径；单 suite 使用“—”，all suite 自动生成 v0.1.0 比较表。
- **容器证据**：Docker 29.7.2 / server 29.5.2；实际构建并启动 gateway，容器 healthy，`/health` healthy，`/ready` ready/degraded=false/2 detectors healthy；随后删除容器和网络，确认无遗留容器。
- **基准证据**：latency/throughput/all 均实际运行；最终 P50 0.12ms、P95 0.13ms、P99 0.16ms、7920 req/s；对 v0.1.0 差异为 -6.1%/-6.2%/+3.5%/-1.3%，仅作建议性证据。
- **切片验证**：TC-DEPL-001～003、TC-BENCH-001～002 全覆盖；定向 5 passed；Ruff/Mypy passed；全量 882 passed / 1 skipped，coverage 92.85%。

### 当前切片

### S5 文档与治理（local complete 2026-08-21T09:16:57+08:00）

- **RED**：新增 6 个治理/文档契约测试，初始全部失败；确认缺少 SECURITY/CODE_OF_CONDUCT、README 没有治理入口、公开文档仍为 v0.1.0、Quick Start 漂移及本地断链。
- **GREEN**：新增安全披露政策和完整 Contributor Covenant 2.1；统一 README/CONTRIBUTING/模板/docs/config 为 v0.1.1 与 Python 3.10–3.12（推荐 3.12）；修复 SDK 错误 `DetectorBase` 示例和 1.x 依赖范围。
- **REFACTOR**：活跃 Markdown 链接/锚点检查自动化；README Quick Start 缩减为可复现的源码安装、启动、health/ready 流程。
- **Quick Start 证据**：全新临时环境源码 editable 安装 0.1.1，启动 8080，`/health` healthy、`/ready` ready/degraded=false，随后优雅关闭。
- **远程只读证据**：默认 labels 存在，但 `dependencies` 缺失；milestones 为空；GitHub private vulnerability reporting 为 disabled。按 Gate 约束未写远程，动作已记录到 `github-governance-checkpoint.md`。
- **切片验证**：本地 TC-GOV-001～003、TC-DOCS-001～003 契约 6 passed；Ruff/Mypy passed；全量 888 passed / 1 skipped，coverage 92.85%。TC-GOV-003 的远程最终断言保留到 Gate 3 后。

### 当前切片

S6 Phase 5 全量验证：重跑所有门禁、审查完整 diff、执行 L3 锚定与 12 类失败模式检查，生成 test-report/design-adjustments 后提交 Gate 3。

### S6 Phase 5 Verify（local complete / Gate 3 pending 2026-08-21）

- **三路评审**：代码/安全、测试/配置、文档/Skills 全部完成；发现的 Release 质量断链、生产 gRPC runtime 缺失、stale checkpoints、Compose 竞态/端口/密钥、配置文档漂移和安装渠道问题均已修复。
- **最终回归**：主测试集 + 两个示例插件测试集 904 passed / 1 skipped；coverage 92.85%；Ruff passed；Mypy 88 source files / 0 issues。
- **构建与审计**：gateway/SDK 共 2 wheels + 2 sdists，Twine 4/4；三个 CLI 入口通过；pip-audit 无已知漏洞。
- **生产冒烟**：仓库内 sidecar 镜像实际构建；sidecar healthy；8080/8081 两个 gateway 副本均 healthy/ready，3/3 detectors healthy，degraded=false；容器、网络和卷已清理。
- **失败模式/L3**：a-k 全量检查通过；上游 Verify 的第 12 类缺失以独立 `(l) anchor_missing` 检查完成；两个 L3 reference changes 均存在，8 项调整已记录。
- **经验库**：新增 EXP-2026-0004～0007，全部保持 discovered / occurrences=1，未 verify/deposit/share。
- **远程待办**：TC-GOV-003、TC-GH-004、TC-REL-007 保留到 Gate 3 后；Gate 3 前未 push、tag、release 或写 GitHub 治理状态。
