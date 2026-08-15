# Proposal: v1.0.0 Production Ready

> 变更：2026-08-15-v1.0.0-production-ready
> 模式建议：thorough（复杂度评分 11/17，见下）
> 前置：v0.1.0 ~ v0.5.1 全部完成（五个功能阶段 + 尾项）

## Why — 问题与动机

DESIGN.md 第 18 章 Roadmap 的五个功能阶段（v0.1.0~v0.5.0）已全部完成，但 **v1.0.0 Production Ready 的交付物尚未启动**：

- 缺少生产级文档体系（README 仅 7 行占位，无 Getting Started / 配置 / API / 部署指南）
- 无 LICENSE 文件（DESIGN 19.1 声明 Apache 2.0，但仓库没有许可证全文，开源合规缺口）
- 无准确性测试（检测器准确率未验证）
- 无性能基准（DESIGN 14 章目标从未对照验证）
- Docker Compose 仅单副本开发版，无生产配置
- 无 CI / CONTRIBUTING / issue/PR 模板（无法对外协作）

v1.0.0 是首个稳定发布版本，需要**可验证的完成标准**：文档让新用户 30 分钟上手、基准证明满足性能目标、生产 compose 可一键部署、CI 保证质量门槛。

## What Changes — 变更清单

| # | 类型 | 变更 |
|---|------|------|
| C1 | new | Apache 2.0 `LICENSE` 全文（对齐 DESIGN 19.1 与 pyproject 声明） |
| C2 | modified | README 扩写为完整项目门面（介绍/特性/快速开始/配置示例/文档导航/许可） |
| C3 | new | `docs/` 新增 4 份指南：getting-started、configuration、api-spec、deployment（与已有 3 份插件文档构成完整体系） |
| C4 | new | `tests/accuracy/` 检测器准确性测试：5 个内置检测器各 ≥20 正/负样本，准确率阈值可断言 |
| C5 | new | `tests/benchmarks/bench_pipeline.py` 性能基准（DESIGN 14.5 约定路径），输出对照 14 章目标报告 |
| C6 | new | `docker-compose.prod.yml` 生产配置：多副本、资源限制、健康检查、gRPC sidecar 示例 |
| C7 | new | GitHub 建设：`.github/workflows/ci.yml`（ruff+mypy+pytest+coverage）、CONTRIBUTING.md、issue/PR 模板 |
| C8 | new | 定义并记录 v1.0.0 Definition of Done 清单（随 proposal/test-report 交付） |

## Capabilities

| 类型 | Capability | 说明 |
|------|------------|------|
| new | `project-docs` | LICENSE、README、docs/ 四份指南 |
| new | `accuracy-testing` | 内置检测器准确性测试套件 |
| new | `performance-benchmark` | 基准脚本 + DESIGN 14 目标对照 |
| new | `production-deployment` | docker-compose.prod.yml |
| new | `github-setup` | CI、CONTRIBUTING、模板 |

## Impact

| 维度 | 影响 |
|------|------|
| 代码 | 新增测试/基准脚本（tests/accuracy/、tests/benchmarks/）；无运行时代码修改 |
| 配置 | 新增 docker-compose.prod.yml；现有 config/ 不变 |
| 基础设施 | 新增 .github/ CI 配置；真实 GitHub 仓库 push 由用户后续执行 |
| 文档 | README 扩写 + docs/ 新增 4 份指南 |

## Constraints / 约束

- 性能基准在本地机运行，结果用于发布评审，不设 CI 硬门槛（环境差异大）
- accuracy 样本集固定内置，可离线复现
- CI 文件仓库内就绪；真实远程仓库由用户决定，不阻塞
- 不引入新运行时依赖

## Risk Areas

| 风险 | 缓解 |
|------|------|
| 基准可能不达 DESIGN 14 目标 | 输出对照表 + 差异记录，作为发布评审依据而非 CI 门槛 |
| accuracy 样本偏差导致虚高 | 公开固定样本 + 保守阈值（≥0.9），只验证回归 |
| CI 无真实仓库无法在线验证 | 本地等价命令验证 + act 说明 |
| 生产 compose 无容器环境 | docker compose config 校验 + 单副本冒烟 |

## Non-Goals（明确不做）

- 不实现新功能（检测器/协议/安全特性）
- 不修改既有运行时行为（配置 schema、API 兼容 v0.5.x）
- 不含 v1.1+ 路线图内容（K8s Helm、Redis 限流、provider failover、mTLS 等）
- 不执行真实 GitHub 发布操作（push/PR/release 由用户执行）

## Success Criteria（可验证）

1. `LICENSE` 为 Apache License 2.0 全文
2. README 覆盖：介绍、特性、快速开始、配置示例、文档导航、许可
3. `docs/` 含 getting-started/configuration/api-spec/deployment 四份指南，与实现一致
4. `tests/accuracy/` 覆盖 5 个内置检测器，各 ≥20 正/负样本，准确率断言 ≥0.9，全绿
5. `bench_pipeline.py` 可运行，输出对照 DESIGN 14 章目标报告（达标或记录差异）
6. `docker-compose.prod.yml` 通过 `docker compose config` 校验，含 ≥2 副本、资源限制、健康检查、sidecar
7. `.github/workflows/ci.yml` 存在，本地等价命令全绿
8. CONTRIBUTING.md、issue/PR 模板存在
9. v1.0.0 DoD 清单逐项可勾选

## 复杂度评分与模式建议

| 维度 | 得分 |
|------|------|
| 预估文件数（20+） | 3 |
| 预估行数（1500+） | 3 |
| Capability 数（5） | 2 |
| 风险等级（文档/基准/部署，无安全） | 2 |
| 数据/API（accuracy 样本、benchmark） | 1 |
| 安全（无） | 0 |
| **总分** | **11 / 17** |

**模式建议：thorough**（8+ 分）。大型变更，需完整切片计划与验证。

---

⚠️ **待确认**：
1. 范围与边界是否准确（特别是 Non-Goals 中的"不做新功能/不改运行时行为"）？
2. Success Criteria 是否可验证？
3. 模式是否同意 thorough？

**确认后进入 Phase 2: SPEC**（生成能力规格 + 测试方案 + 切片计划）。
