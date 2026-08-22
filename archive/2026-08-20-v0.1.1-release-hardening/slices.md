# v0.1.1 切片执行计划

## Dependency Graph Summary

```text
S1 STDD CLI/交付补录
  └──► S2 全项目质量与 SDK
         └──► S3 构建/审计/Release dry-run
                └──► S4 Compose/Benchmark 验证
                       └──► S5 文档与治理
                              └──► S6 全量验证与 Gate 3 交付检查点
```

由于用户要求严格按优先级 1→5 顺序完成，本 change 不并行写入相互关联的工作区文件。文档链接检查与远程状态只在相应上游产物稳定后执行。

## Slice Execution Plan

| # | 优先级 | 风险 | 工作量 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|--------|--------|---------|---------|------|
| S1 | P0 | 🟡 High | L | — | TC-STDD-001～006 | 固定恢复 CLI，补 canonical/structure/experience | 无 |
| S2 | P0 | 🟡 High | M | — | TC-GH-001～002, TC-SDK-001～002 | 扩大全项目门禁并清零现有问题 | S1 |
| S3 | P0 | 🟡 High | L | — | TC-REL-001～006, TC-GH-003, TC-SDK-003 | 版本、构建、安装、audit、dry-run | S2 |
| S4 | P0/P1 | 🟢 Medium | M | — | TC-DEPL-001～003, TC-BENCH-001～002 | Compose 和性能发布验证 | S3 |
| S5 | P0/P1/P2 | 🟢 Medium | L | — | TC-GOV-001～003, TC-DOCS-001～003 | 治理、Quick Start、链接与远程准备 | S4 |
| S6 | P0 | 🟡 High | M | — | TC-GH-004, TC-REL-007 | 全量 Phase 5；远程动作锁定到 Gate 3 后 | S5 |

## Rationale

### S1：STDD CLI 与交付补录

- **依赖关系**：恢复 CLI 是后续 canonical、结构、经验和 change 状态验证的基础。
- **风险分析**：外部供应链 + vendored 源码 + archive 兼容，风险 5/5。
- **工作量**：6 TC、多目录、需要临时兼容工作区，L。

### S2：全项目质量与 SDK

- **依赖关系**：在构建发布产物前必须先保证代码与类型门禁干净。
- **风险分析**：CI 假绿与 SDK 契约，风险 4/5。
- **工作量**：4 TC、少量代码/配置修复，M。

### S3：构建、安全审计与 Release dry-run

- **依赖关系**：依赖 S2 全绿；产物稳定后才能做 Compose/文档安装实测。
- **风险分析**：构建供应链与发布条件，风险 5/5。
- **工作量**：8 TC、workflow/构建/临时安装，L。

### S4：Compose 与 Benchmark

- **依赖关系**：使用 S3 的版本和构建状态作为发布基线。
- **风险分析**：Docker 外部环境与机器性能差异，风险 3/5。
- **工作量**：5 TC，M。

### S5：治理与文档

- **依赖关系**：Quick Start 和版本文档必须引用已验证的构建、配置和入口。
- **风险分析**：主要为一致性与远程仓库状态，风险 3/5。
- **工作量**：6 TC、多文档和 GitHub 元数据，L。

### S6：全量验证与交付检查点

- **依赖关系**：汇总全部本地产物后才能进入 Gate 3。
- **风险分析**：tag/Release 是外部不可轻易撤回状态，风险 5/5。
- **工作量**：本地 Phase 5 为 M；TC-GH-004/TC-REL-007 的实际远程动作在 Gate 3 后 Phase 6 执行。
