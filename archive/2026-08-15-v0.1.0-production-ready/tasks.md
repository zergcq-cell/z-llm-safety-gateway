# v1.0.0 任务清单

> 变更：2026-08-15-v1.0.0-production-ready
> 执行模式：thorough / 全自动长程

## Slice 1: LICENSE + README（project-docs）

- [ ] 1.1 创建根目录 LICENSE（Apache 2.0 全文）→ TC-DOCS-001
- [ ] 1.2 扩写 README.md（介绍/特性/快速开始/配置示例/文档导航/许可）→ TC-DOCS-002
- [ ] 1.3 验证：README 中命令可执行；LICENSE 与 pyproject 一致

## Slice 2: docs/ 指南 + DoD（project-docs）

- [ ] 2.1 docs/getting-started.md（安装/最小配置/启动/curl 冒烟）→ TC-DOCS-003
- [ ] 2.2 docs/configuration.md（全部配置区块 + 示例）
- [ ] 2.3 docs/api-spec.md（/v1/chat/completions + 健康/指标端点）
- [ ] 2.4 docs/deployment.md（docker 部署/生产建议/sidecar/故障排查）
- [ ] 2.5 逐条实测指南中命令（防漂移）
- [ ] 2.6 DoD 清单写入 proposal/test-report → TC-DOCS-004

## Slice 3: accuracy 测试（accuracy-testing）

- [ ] 3.1 tests/accuracy/samples/ 样本集 ×4 检测器（≥20 正/负/检测器）→ TC-ACC-001
- [ ] 3.2 tests/accuracy/test_accuracy.py（准确率 ≥0.9、误报率 ≤0.1）→ TC-ACC-002
- [ ] 3.3 toxicity skipif 标注 → TC-ACC-003
- [ ] 3.4 验证：pytest tests/accuracy 全绿

## Slice 4: benchmark（performance-benchmark）

- [ ] 4.1 tests/benchmarks/bench_pipeline.py（延迟统计，标准库）→ TC-BENCH-001
- [ ] 4.2 DESIGN 14 目标对照报告输出 → TC-BENCH-002
- [ ] 4.3 确认 CI 不设基准门槛 → TC-BENCH-003
- [ ] 4.4 运行基准并记录结果

## Slice 5: 生产部署（production-deployment）

- [ ] 5.1 docker-compose.prod.yml（replicas≥2/资源限制/healthcheck/restart）→ TC-DEPL-001
- [ ] 5.2 sidecar 示例服务集成 → TC-DEPL-002
- [ ] 5.3 docker compose config 校验（或降级）→ TC-DEPL-003
- [ ] 5.4 单副本冒烟（Docker 可用时）

## Slice 6: github-setup

- [ ] 6.1 .github/workflows/ci.yml（3.10/3.11 矩阵 + ruff/mypy/pytest + coverage ≥80%）→ TC-GH-001
- [ ] 6.2 本地等价命令全绿 → TC-GH-002
- [ ] 6.3 CONTRIBUTING.md → TC-GH-003
- [ ] 6.4 .github/ISSUE_TEMPLATE/ + PULL_REQUEST_TEMPLATE.md

## 验证（Phase 5）

- [ ] 全量测试回归（无回归）
- [ ] ruff / mypy 全绿
- [ ] 技术评审 + 设计调整记录
- [ ] test-report.md 生成（含 DoD 清单勾选）
