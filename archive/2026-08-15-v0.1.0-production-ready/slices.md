# v1.0.0 切片计划

> 变更：2026-08-15-v1.0.0-production-ready
> 日期：2026-08-15
> 模式：thorough / 顺序执行（零依赖，可并行但顺序更稳）

## 依赖图分析

- **零依赖节点**：全部 5 个 capability（project-docs / accuracy-testing / performance-benchmark / production-deployment / github-setup）均无相互依赖
- **依赖链深度**：1（无链）
- **关键路径**：无（无下游依赖）

## 风险评分

| Capability | 经验风险 | 复杂度风险 | 变更类型 | 总分 | 级别 |
|------------|----------|-----------|----------|------|------|
| project-docs | 0 | 0 | new | 1 | 🟢 低 |
| accuracy-testing | 0 | 1（样本偏差） | new | 2 | 🟢 中 |
| performance-benchmark | 0 | 1（环境差异） | new | 2 | 🟢 中 |
| production-deployment | 0 | 1（无容器） | new | 2 | 🟢 中 |
| github-setup | 0 | 0 | new | 1 | 🟢 低 |

## 切片列表

| 切片 | Capability | 内容 | 工作量 | TC | 并行组 |
|------|-----------|------|--------|-----|--------|
| 1 | project-docs | LICENSE 全文 + README 扩写 | M | TC-DOCS-001/002 | 1 |
| 2 | project-docs | docs/ 四份指南 + DoD 清单 | L | TC-DOCS-003/004 | 1 |
| 3 | accuracy-testing | 样本集 ×4 + 断言测试 | M | TC-ACC-001/002/003 | 1 |
| 4 | performance-benchmark | 基准脚本 + 目标对照报告 | M | TC-BENCH-001/002/003 | 1 |
| 5 | production-deployment | docker-compose.prod.yml | S | TC-DEPL-001/002/003 | 1 |
| 6 | github-setup | CI + CONTRIBUTING + 模板 | M | TC-GH-001/002/003 | 1 |

## 排序

拓扑：全零依赖 → 按 P0 TC 密度排序（Slice 1/3/6 含最多 P0），顺序执行：

1. Slice 1（LICENSE + README）— P0: 2
2. Slice 2（docs/ 指南 + DoD）— P0: 1
3. Slice 3（accuracy 测试）— P0: 2
4. Slice 4（benchmark）— P0: 1
5. Slice 5（compose prod）— P0: 1
6. Slice 6（github-setup）— P0: 2

## 并行化建议

全部零依赖，但单一执行上下文下顺序执行（每个切片独立验证后继续），避免上下文切换成本。
