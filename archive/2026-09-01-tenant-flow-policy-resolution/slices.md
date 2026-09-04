# v0.3.0 租户级 Flow 与安全策略解析切片执行计划

## Dependency Graph Summary

CLI 报告 5 个 nodes、0 edges、5 个 zero-dependency、0 cycles。Canonical specs 当前没有机器可读
Capability dependency 字段，因此必须使用 design/architecture 的人工依赖审查补充真实实现顺序：

```text
S1 policy schema + identity refs
        │
        ▼
S2 Flow/capability/provider/source validation
        │
        ▼
S3 trusted resolver + safe Context
        │
        ├───────────────┐
        ▼               ▼
S4 Flow bundles     S5 tenant Router/models
        └───────┬───────┘
                ▼
S6 all-path request snapshot
                │
                ▼
S7 production integration/docs/acceptance
```

**并行化说明**：

- 形式并行组 1：S4、S5 在 S3 后逻辑可并行。
- 实际执行顺序：S4 后 S5；二者都会触及 `app.py` 和 private bundle contract，单 agent 顺序执行可减少冲突。
- S6、S7 位于关键路径，必须等待上游全部完成。

最长依赖深度为 6；关键路径为 S1→S2→S3→S4/S5→S6→S7。

## 五步分析摘要

| Capability | CLI 依赖 | 人工依赖 | 风险分 | 风险 | TC 数 | 工作量 |
|------------|----------|----------|--------|------|-------|--------|
| tenant-config-contract | zero | 基础节点 | 5 | 高 | 7 | L，拆为 S1/S2 |
| tenant-policy-resolution | zero | 依赖 config contract | 5 | 高 | 6 | L，拆为 S3/S6 |
| default-detector-flow | zero | 依赖 resolver | 5 | 高 | 5 | M，S4 + S6 |
| provider-proxy | zero | 依赖 resolver | 4 | 高 | 5 | M，S5 |
| config-system | zero | 依赖全部 runtime | 5 | 高 | 4 | M，S7 |

风险依据：EXP-2026-0001/0002/0005/0008/0009/0022/0023/0025 均命中高严重度；所有
Capabilities 都是跨模块或修改既有接口。tenant-policy-resolution 另有 6 Scenarios，增加复杂度分。

## Slice Execution Plan

| # | 优先级 | 风险 | 工作量 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|--------|--------|---------|----------|------|
| S1 | P0/P1 | 高 | M | — | TCC-008/009/010/014 | strict policy models、policy_id、bounds、legacy identity boundary | 无 |
| S2 | P0 | 高 | M | — | TCC-011/012/013 | Flow/binding/routing/models/source cross validation | S1 |
| S3 | P0/P1 | 高 | M | — | TPR-001/002/003/004/006 | safe Context、private bundle、O(1) resolver、503/legacy | S2 |
| S4 | P0/P1 | 高 | M | 组1 | DDF-008/009/011/012 | per-policy engine/detectors/status/result policy + core boundary | S3 |
| S5 | P0/P1 | 高 | M | 组1 | PROXY-013～017 | bounded Router view、route miss、防伪、models Provider、adapter reuse | S3（顺序在 S4 后） |
| S6 | P0 | 高 | M | — | TPR-005, DDF-010 | snapshot 贯穿 input/sync/async/SSE/buffer/post-audit | S4、S5 |
| S7 | P0/P1 | 高 | M | — | CFG-704～707 | YAML→create_app→HTTP/SSE/Provider、secrets、legacy、docs | S6 |

## Rationale

### S1：Policy schema 与基础引用

- **依赖关系**：所有 resolver/runtime 都消费该 contract，必须先行。
- **风险分析**：Pydantic coercion/extra handling 和 prior identity-only spec 容易产生静默兼容错误；EXP-2026-0025 要求按运行时归一化验证。
- **工作量估算**：4 TC，涉及 models/validators/legacy tests，M。

### S2：跨注册表与双来源验证

- **依赖关系**：需要 S1 typed policies，输出是 S3 可安全编译的前置保证。
- **风险分析**：Flow 嵌套、binding identity、Provider refs 和 raw source presence 跨 3 个模块；错误必须稳定且脱敏。
- **工作量估算**：3 个参数化矩阵 TC，覆盖大量失败分支，M。

### S3：Trusted resolver 与 safe Context

- **依赖关系**：只接受 S2 已验证配置；为 S4/S5 提供唯一 request selection contract。
- **风险分析**：安全边界；缺 Context/bundle 必须 503 且无 fallback，untrusted hints 不参与解析。
- **工作量估算**：5 TC，新增 tenancy module 并接 route boundary，M。

### S4：Flow runtime bundles

- **依赖关系**：依赖 resolver contract；与 S5 逻辑可并行但共享 app assembly。
- **风险分析**：EXP-2026-0001/0009；同名 Detector、独立 status、result policy 和 core dependency 均可能产生跨租户漂移。
- **工作量估算**：4 TC，涉及 app/pipeline/detector lifecycle，M。

### S5：Tenant Router/models

- **依赖关系**：依赖 resolver；S6 需要 Provider 和 pipeline 都能从 bundle 取得。
- **风险分析**：chat route miss 和 `/models` 是公开协议边界；必须零 Provider 调用、无拓扑泄漏、legacy passthrough 不变。
- **工作量估算**：5 TC，router/chat/models，M。

### S6：全路径 snapshot

- **依赖关系**：汇合 S4/S5，是生产执行正确性的核心切片。
- **风险分析**：EXP-2026-0001；async closure、SSE handler 和 post-audit 很容易重新读取 global app state。
- **工作量估算**：2 个高复杂度矩阵 TC，覆盖 7 条路径，M。

### S7：Production integration 与文档

- **依赖关系**：只有所有 runtime 路径完成后才能证明 YAML 配置真实生效。
- **风险分析**：EXP-2026-0005/0008/0022/0023/0025；需要 secrets、真实 env、checkpoint 节点和 roadmap 状态同时一致。
- **工作量估算**：4 TC + 全量回归与文档更新，M。

## 覆盖检查

- 14/14 Requirements 被至少一个切片覆盖。
- 27/27 Scenarios 与 27/27 TC 被恰一主要切片覆盖。
- P0 切片全部位于关键路径；P1 与同一 contract 紧密相关，不延后。
- 人工依赖图无循环，CLI cycles 也为空。
