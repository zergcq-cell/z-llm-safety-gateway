# v0.2.1 独立版本发布热修复切片执行计划

## Dependency Graph Summary

CLI 依赖图未发现 capability 间的声明依赖或循环：

```text
detector-sdk ─────┐
project-docs ─────┼── zero dependency / no cycles
release-hardening ┘

实现语义顺序：
S1 版本角色校验 → S2 双版本产物 → S3 workflow/公开表面 → S4 完整验证
```

**并行化说明**：

- 机械依赖层面三个 Capability 均可并行，依赖链深度为 0。
- 实际修改共享版本表面且高风险；为保留逐片 RED→GREEN 证据，采用串行组 1–4。
- S1 是语义关键路径：先明确 Gateway tag 与 SDK 内部一致性的独立校验规则。
- TC-REL-015～017 需要 Gate 3 后的远程写入/查询，Phase 3–5 只验证其前置条件。

## Capability Risk and Effort

| Capability | 风险分 | 风险 | 工作量 | 依据 |
|------------|--------|------|--------|------|
| release-hardening | 5 | 🔴 High | L | 10 scenarios、跨 checker/workflow/build/GitHub；匹配高风险经验 EXP-2026-0004 |
| detector-sdk | 4 | 🔴 High | M | 独立包契约与误升版风险；跨 metadata/runtime/docs/install |
| project-docs | 3 | 🟡 Medium | M | 公开契约表面，匹配 EXP-2026-0005；需保护历史证据 |

## Slice Execution Plan

| # | 优先级 | 风险 | 工作量 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|--------|--------|---------|---------|------|
| S1 | P0 | 🔴 High | M | 组1 | TC-REL-008～011、TC-SDK-010 | 角色化校验器与完整负向 mutation 矩阵 | 无 |
| S2 | P0 | 🔴 High | M | 组2 | TC-REL-012～013、TC-SDK-010～011 | Gateway 0.2.1 / SDK 0.1.1 四产物和三个 CLI | S1 |
| S3 | P0/P1 | 🟡 Medium | M | 组3 | TC-REL-014、TC-SDK-012、TC-DOCS-008～010 | 安全 workflow 与角色化公开版本表面 | S2 |
| S4 | P0 | 🔴 High | M | 组4 | 全部本地 TC；TC-REL-015～017 前置 | checkpoint、全回归、失败模式与原则验证 | S1–S3 |

## Rationale

### Slice S1: Release verifier role separation（P0，先行）

- **依赖关系**：声明图无依赖，但后续 metadata、产物与文档都依赖版本角色定义，因此先行。
- **风险分析**：匹配 EXP-2026-0004；当前 v0.2.0 Release 的真实失败点就在 checker。正向测试必须同时具备 Gateway mismatch、SDK mismatch、notes mismatch 三类负向保护，避免通过“忽略 SDK”产生假绿。
- **工作量估算**：M；5 个 TC，主要修改一个测试文件和一个工具文件。
- **TDD 边界**：先在临时发布树写精确失败测试，再最小拆分 Gateway 与 SDK 校验，最后重构错误信息和 helper。

### Slice S2: Independent artifacts and CLI installation（P0，串行）

- **依赖关系**：依赖 S1 的角色校验；构建事实必须与 checker 的语义一致。
- **风险分析**：SDK 0.1.1 误升版会破坏稳定契约；组合安装可能暴露入口点或依赖耦合。
- **工作量估算**：M；4 个重叠 TC，涉及根/SDK metadata、runtime version 与构建安装测试。
- **TDD 边界**：先把期望切到 Gateway 0.2.1 / SDK 0.1.1 并新增三个 CLI 组合测试，再最小更新 Gateway 版本表面；SDK 版本不可修改。

### Slice S3: Workflow and role-based public surfaces（P0/P1，串行）

- **依赖关系**：依赖 S2 的真实版本组合，避免文档先行形成不可构建的声明。
- **风险分析**：workflow 仍是发布供应链高风险面；公开配置/文档匹配 EXP-2026-0005，且全局替换会误改 SDK 与历史证据。
- **工作量估算**：M；5 个 TC，跨 workflow、CHANGELOG、当前文档与契约测试。
- **TDD 边界**：先写按角色的契约断言，再逐路径更新；明确禁止改写 archive、旧 spec 或失败 v0.2.0 证据。

### Slice S4: Thorough local verification and Gate 3 evidence（P0，最终）

- **依赖关系**：依赖前三个实现切片全部完成。
- **风险分析**：匹配 EXP-2026-0006；Agent checkpoint 若引用虚假节点会使验证证据失效。远程发布还受 EXP-2026-0004 约束。
- **工作量估算**：M；无新产品行为，执行 AST/collect、定向与全量质量门、12 类失败模式和原则检查。
- **远程边界**：TC-REL-015～017 在本切片只验证可执行前置；Gate 3 后严格按 push main → 等三版本 CI → 新建/push v0.2.1 → 验证 Release 的顺序执行。

## Coverage Check

- Requirements：REQ-REL-005～007、REQ-SDK-009、REQ-DOCS-008，5/5 已覆盖。
- Scenarios / TC：16/16 已映射；其中 13 个 P0、3 个 P1。
- 循环依赖：无。
- P0 排序：高风险 checker 与 artifacts 优先；P1 文档与对应 P0 workflow 同切片执行。
