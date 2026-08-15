# performance-benchmark — 行为规格（Human View）

> 变更：2026-08-15-v1.0.0-production-ready | 置信度：medium

## Requirements

### REQ-BENCH-001: tests/benchmarks/bench_pipeline.py 存在且可运行（DESIGN 14.5 约定路径）

**SC-BENCH-001**（置信度 medium）— evidence: proposal.yaml -> what_changes C5; DESIGN.md 14.5

- GIVEN: tests/benchmarks/bench_pipeline.py
- WHEN: 执行 python -m tests.benchmarks.bench_pipeline --suite latency
- THEN: 脚本 SHALL 正常退出（exit 0）并输出延迟统计
- AND: 输出 SHALL 包含 P50/P95/P99 延迟（规则型 pipeline 配置）
- AND: 脚本 SHALL 使用标准库（time/statistics），无新增第三方依赖

### REQ-BENCH-002: 基准结果输出对照 DESIGN 14 章目标的报告

**SC-BENCH-002**（置信度 medium）— evidence: proposal.yaml -> success_criteria 5; DESIGN.md 14.1

- GIVEN: 基准运行完成
- WHEN: 检查报告输出
- THEN: 报告 SHALL 包含与 DESIGN 14 章目标的对照表（目标值 vs 实测值 vs 达标状态）
- AND: 未达标项 SHALL 有差异说明（不阻塞退出，作为发布评审依据）
- AND: 报告 SHALL 记录运行环境（Python 版本/OS）

### REQ-BENCH-003: 基准测试不设 CI 硬门槛

**SC-BENCH-003**（置信度 high）— evidence: proposal.yaml -> constraints; design.md D4

- GIVEN: CI pipeline 配置
- WHEN: 检查 CI 是否执行基准
- THEN: CI SHALL 不因基准数值未达标而失败（基准为手动/发布评审工具）
