# v1.0.0 Production Ready — 技术设计

> 变更：2026-08-15-v1.0.0-production-ready
> 模式：thorough

## Context

项目已完成 v0.1.0~v0.5.1 五个功能阶段：FastAPI 网关、pipeline 检测引擎、5 个内置检测器、流式与审计、安全可观测、插件生态。现状：

- 测试：796 用例，覆盖率 93%（> DESIGN 17 章 80% 目标）
- 代码质量：ruff / mypy 全绿
- 文档：README 7 行占位，docs/ 有 3 份插件文档（v0.5.1）
- 部署：Dockerfile + 单副本 docker-compose.yml（开发版）
- 开源：pyproject 声明 Apache-2.0，但无 LICENSE 文件；无 CI / CONTRIBUTING / 模板
- 性能：DESIGN 14 章定义目标，从未基准验证
- 准确性：检测器功能测试覆盖，无准确率（accuracy）验证

v1.0.0 是首个稳定发布版本，目标是补齐"Production Ready"所需的工程化资产，**不改变任何运行时行为**。

## Decisions

### D1. 文档体系：docs/ 统一指南 + README 作为入口

**方案**：`docs/` 下 7 份指南（getting-started / configuration / api-spec / deployment + 已有 plugin-development / grpc-integration / commercial-plugin），README 扩写为项目门面并链接到 docs/。

**为什么**：docs/ 集中管理避免根目录散乱；README 承担"30 秒了解项目"角色，深度内容放 docs/。与 DESIGN 16 章 Project Structure 一致。

**备选**：
- 单文件 ALL.md：不利于维护与导航 → 排除
- 只扩 README 不建 docs/：信息过载，且插件文档已在 docs/ → 排除

### D2. LICENSE：Apache 2.0 官方全文

**方案**：将 Apache License 2.0 官方全文放入根目录 `LICENSE`。

**为什么**：DESIGN 19.1 决策 + pyproject.toml `license = "Apache-2.0"` 已声明；开源仓库必须包含许可证全文才能合规分发。取官方标准文本（apache.org/licenses/LICENSE-2.0），不修改。

### D3. Accuracy 测试：固定样本集 + 阈值断言，覆盖 4 规则型检测器

**方案**：
- `tests/accuracy/samples/<detector>.yaml`：每个检测器的固定正/负样本（≥20 条/检测器，公开来源、离线可复现）
- `tests/accuracy/test_accuracy.py`：加载样本 → 运行检测器 → 断言 准确率 ≥ 0.9、误报率 ≤ 0.1
- 覆盖 4 个规则型检测器：prompt_injection / pii_redaction / sensitive_words / secret_leak
- toxicity（ML）：标注 `@pytest.mark.skipif`（模型环境不可用时跳过），提供 mock 冒烟路径

**为什么**：规则型检测器确定性可离线复现；ML 检测器 accuracy 依赖模型权重，CI 环境不可保证下载。准确率 ≥0.9 为保守阈值，用于**回归保护**（防止优化破坏既有行为），不作为发布硬门槛（样本有限，准确率绝对值为参考）。

**备选**：
- 使用外部公开基准集（如 harmful prompts 数据集）：体积大、需网络、不可离线复现 → 排除
- 每检测器仅正样本：无法验证误报 → 排除

### D4. 性能基准：标准库脚本 + 目标对照报告，不设 CI 门槛

**方案**：
- `tests/benchmarks/bench_pipeline.py`（DESIGN 14.5 约定路径）：用 `time.perf_counter` + `statistics` 度量 pipeline 端到端延迟（规则型配置），输出 Markdown 报告对照 DESIGN 14 章目标表
- 命令行：`python -m tests.benchmarks.bench_pipeline --suite all|latency|throughput`
- 结果写入 `tests/benchmarks/results/<date>.md`；未达标项记录差异与建议

**为什么**：DESIGN 14.5 已约定脚本路径与命令格式；标准库避免新依赖；结果作为发布评审依据。

**备选**：
- pytest-benchmark 插件：新增 dev 依赖；本地机器差异大，基准值不可跨机比较 → 排除
- CI 中硬性断言：机器性能差异导致 flaky → 排除（记录为 constraint）

### D5. 生产部署配置：docker-compose.prod.yml

**方案**：新增 `docker-compose.prod.yml`：
- gateway 服务：`deploy.replicas: 2`、`deploy.resources.limits`（cpu/memory）、healthcheck（复用开发版）、`restart: unless-stopped`
- gRPC sidecar 示例服务（基于示例镜像构建说明）
- 环境变量配置（OPENAI_API_KEY 等）
- 使用 `docker compose -f docker-compose.prod.yml config` 校验

**为什么**：DESIGN 13 章部署要求（多副本 + 资源限制 + 健康检查）；compose 是 MVP 阶段最贴近用户的部署方式（K8s Helm 属 v1.1 路线图，non-goal）。

**备选**：
- 修改现有 docker-compose.yml：破坏开发体验（dev 与 prod 混用）→ 排除，新增独立文件

### D6. CI：GitHub Actions workflow（ruff + mypy + pytest + coverage）

**方案**：`.github/workflows/ci.yml`：
- 触发：push / pull_request
- 矩阵：Python 3.10 / 3.11
- 步骤：install（含 sdk 路径）→ ruff → mypy → pytest（coverage ≥ 80% gate）→ accuracy（可选）
- 本地以等价命令验证 CI 内容；真实仓库 push 由用户执行（non-goal）

**为什么**：GitHub Actions 为 GitHub 原生 CI（DESIGN 19.2 贡献模型为 GitHub PR 流程）；coverage gate 80% 与 DESIGN 17 章一致。

**备选**：无（GitHub 生态下 Actions 是默认且唯一合理选择）

## Architecture

```
v1.0.0 交付物结构
├── LICENSE                        (D2)
├── README.md                      (D1 扩写：入口 + 导航)
├── docs/
│   ├── getting-started.md         (D1)
│   ├── configuration.md           (D1)
│   ├── api-spec.md                (D1)
│   ├── deployment.md              (D1)
│   └── (已有 3 份插件文档)
├── tests/
│   ├── accuracy/                  (D3)
│   │   ├── samples/<detector>.yaml
│   │   └── test_accuracy.py
│   └── benchmarks/                (D4)
│       ├── bench_pipeline.py
│       └── results/
├── docker-compose.prod.yml        (D5)
└── .github/                       (D6)
    ├── workflows/ci.yml
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
CONTRIBUTING.md                     (D6)
```

验证闭环：
- accuracy：固定样本 → 检测器 → 准确率断言（回归保护）
- benchmark：pipeline 运行 → 延迟/吞吐统计 → DESIGN 14 对照报告
- CI：push/PR → ruff+mypy+pytest+coverage → 质量门槛
- compose：`docker compose config` 校验结构；单副本冒烟

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 基准不达 DESIGN 14 目标（规则 P50<5ms 等） | 报告对照表 + 差异记录；目标为评审依据非 CI 门槛；可提交后续优化变更 |
| accuracy 样本选择偏差 | 样本固定公开 + 阈值保守（≥0.9）+ 只验证回归 |
| CI 无真实仓库无法在线验证 | 本地等价命令全绿 + README 提供 act 说明 |
| 生产 compose 无容器环境验证受限 | `docker compose config` 校验 + 单副本本地冒烟 |
| 文档漂移（与实现不一致） | 文档中的命令/配置在构建时逐条实测（agent_spec CP 验证） |
