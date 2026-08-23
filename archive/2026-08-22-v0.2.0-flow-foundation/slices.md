# v0.2.0 Flow Foundation 切片执行计划

## Dependency Graph Summary

STDD CLI 对 canonical specs 的结果为 12 个 `zero_dependency`、0 条 edge、0 个 cycle。当前 canonical schema 未编码实现依赖，因此以下拓扑是依据 `design.md`、模块边界和测试前置条件补充的人工依赖图；它不改变已锁定规格。

```text
S1 Contracts
├── S2 Policy ───────┬── S3 Evidence ───┬── S4 Runtime ──────────┐
│                    │                  ├── S6 Lifecycle          │
│                    │                  └── S11 Audit ─────────┐  │
├── S5 Adapter ──────┼── S6 Lifecycle                        │  │
└── S7 Config ───────┴── S8 Legacy Compiler                  │  │
                                            │                 │  │
S4 Runtime + S5 Adapter + S8 Legacy ─────── S9 Reducer/Facade │  │
S6 Lifecycle + S9 Facade ───────────────── S10 Request Flow ──┼──┤
S10 Request Flow + S11 Audit ──────────────┬─ S12 Streaming ──┘  │
                                           └─ S13 Observability ─┤
S1 ... S13 ─────────────────────────────────────── S14 Perf/Gates ┘
```

**并行化说明**：

- 并行组 1：S1（唯一基础契约）。
- 并行组 2：S2、S5、S7（完成 S1 后，策略、Detector adapter、新配置可独立推进）。
- 并行组 3：S3、S8（分别依赖策略与 adapter/config）。
- 并行组 4：S4、S6（分别推进 Runtime 和 Detector lifecycle）。
- 并行组 5：S9、S11（默认 reducer/facade 与审计扩展可在共享核心稳定后独立推进）。
- 并行组 6：S10（请求级集成）。
- 并行组 7：S12、S13（streaming evidence 与 observability 可并行）。
- 并行组 8：S14（统一性能与 checkpoint 收口）。
- 当前不启用子代理并行写共享工作区；执行顺序按 S1→S14 串行，以保持严格切片验证与用户已有改动安全。

## Five-step Analysis

### 1. 依赖与关键路径

- CLI cycle 检测：0；人工拓扑复核：0 个循环。
- 最长路径：S1 → S2 → S3 → S4 → S9 → S10 → S12/S13 → S14。
- 关键路径优先保证契约、策略、证据与 Runtime，不允许先改 HTTP/streaming 再倒推核心语义。

### 2. Capability 风险评分

评分以 1 为基线；匹配 high experience +2、Scenario >5 +1、跨模块 +1、MODIFIED 公共边界 +1，最高记 5。

| Capability | 分数 | 等级 | 主要依据 |
|---|---:|---|---|
| flow-contracts | 3 | 中 | 6 scenarios；跨所有模块的版本化公共契约 |
| flow-policy | 3 | 中 | 6 scenarios；跨 Runtime/config/admission |
| node-evidence-chain | 5 | 高 | 7 scenarios；EXP-2026-0002；隐私与跨模块审计 |
| flow-runtime | 5 | 高 | 6 scenarios；EXP-2026-0001/0003；并发、取消、行为漂移 |
| detector-capability-adapter | 4 | 高 | EXP-2026-0003；跨 SDK/lifecycle/runtime 边界 |
| detector-framework | 5 | 高 | MODIFIED；EXP-2026-0003/0007；四类 Detector 生命周期 |
| config-system | 5 | 高 | 6 scenarios；MODIFIED；EXP-2026-0005；双重事实来源 |
| default-detector-flow | 5 | 高 | 7 scenarios；EXP-2026-0001；跨全部请求阶段 |
| pipeline-engine | 5 | 高 | MODIFIED facade；行为/性能兼容与任务泄漏 |
| audit-logger | 5 | 高 | MODIFIED；EXP-2026-0002；隐私与 sink failure |
| degraded-safety-visibility | 5 | 高 | MODIFIED；EXP-2026-0001/0002；fail-open/fail-closed 可解释性 |
| observability | 5 | 高 | MODIFIED；EXP-2026-0002；低基数与隐私边界 |

### 3. 工作量

- S：1–2 TC，局部文件。
- M：3–5 TC，2–3 个主要模块或一条垂直集成路径。
- L：6 个 TC 或跨 3 个以上主要文件。大能力已按契约、生命周期、持久化或集成边界拆开，避免单切片超过 8 TC。

### 4. 分组原则

- Flow core 按 contracts/policy/evidence/runtime 四层拆分。
- Detector 适配按数据映射与 lifecycle/SDK 兼容拆分。
- Config 按新严格 schema 与 legacy compiler 拆分。
- 默认 Flow 按 reducer/facade 与请求级路径拆分。
- Evidence 按核心模型、audit sink、streaming aggregation 与 observability 拆分。

### 5. 并行建议

- 并行组仅表达逻辑独立性；共享 `flow/`、config、app 和 route 边界的改动仍需在合并前运行受影响回归。
- 高风险切片独立验证，不以一次全量实现覆盖多个 RED 阶段。

## Slice Execution Plan

| # | 优先级 | 风险 | 工作量 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|---|---|---|---:|---|---|---|
| S1 | P0 | 中 | L | 1 | TC-FC-001～006 | 版本化 contracts、严格 schema、Node union、FlowInput | 无 |
| S2 | P0 | 中 | L | 2 | TC-FP-001～006 | resolved policy、独立失败矩阵、conflict validation | S1 |
| S3 | P0 | 高 | M | 3 | TC-NEC-001～005 | 核心 evidence、终态、排序、sanitizer、budget | S1、S2 |
| S4 | P0 | 高 | L | 4 | TC-FR-001～006 | 有界调度、stop、nesting、deadline、cancellation | S1～S3 |
| S5 | P0 | 高 | M | 2 | TC-DCA-001～003 | Detector descriptor/context/result/signal/SDK mapping | S1 |
| S6 | P0 | 高 | M | 4 | TC-DCA-004～005、TC-DF-701～703 | lifecycle/status、四类 Detector、SDK/entry point/gRPC | S2、S3、S5 |
| S7 | P0 | 高 | M | 2 | TC-CFG-001～002、TC-CFG-005～006 | strict Flow YAML、refs、conflict、docs contract | S1、S2 |
| S8 | P0 | 高 | M | 3 | TC-CFG-003～004、TC-DDF-001～002 | legacy defaults 与确定性默认 Flow compiler | S5、S7 |
| S9 | P0 | 高 | M | 5 | TC-DDF-003～004、TC-DDF-007、TC-PE-001～002 | detector reducer、stop parity、PipelineEngine facade | S4、S5、S8 |
| S10 | P0 | 高 | M | 6 | TC-DDF-005～006、TC-DSV-701～702 | request snapshot、六条路径、HTTP/SSE/Provider admission | S6、S9 |
| S11 | P0 | 高 | M | 5 | TC-AUD-701～703、TC-AUD-705、TC-NEC-007 | AuditEntry、数据保护、sink failure visibility | S3、S4 |
| S12 | P0 | 高 | S | 7 | TC-AUD-704、TC-NEC-006 | streaming runtime evidence 与有界审计聚合 | S10、S11 |
| S13 | P0 | 高 | M | 7 | TC-DSV-703、TC-OBS-701～704 | 稳定 reason、metrics、traces、label/attribute privacy | S10、S11 |
| S14 | P1 | 高 | S | 8 | TC-PE-003 | benchmark、task leak、61 checkpoints、全兼容回归 | S1～S13 |

## Rationale

### S1: 版本化 Flow 契约

- **依赖关系**：零依赖；所有后续模型与 runtime 的唯一类型基础。
- **风险分析**：契约过早固化与 strict parsing 可能收紧兼容，但 Gate 2 已锁定支持集合和 ID/版本规则。
- **工作量估算**：6 TC，包含模型、版本、图与 envelope，L。

### S2: 显式策略解析

- **依赖关系**：依赖 S1 的 Node/Flow identity；为 runtime、config、evidence 提供不可变 resolved policy。
- **风险分析**：fail-open/fail-closed 默认映射错误会改变安全语义。
- **工作量估算**：6 TC、完整失败矩阵，L。

### S3: 核心证据模型与保护

- **依赖关系**：引用 S1 identity 与 S2 policy snapshot；S4、S11、S13 共同消费。
- **风险分析**：匹配 EXP-2026-0002；泄密、静默截断或非确定排序均为 Gate 阻塞项。
- **工作量估算**：5 TC，模型/sanitizer/budget 三个关注面，M。

### S4: Flow Runtime

- **依赖关系**：在 contracts/policy/evidence 稳定后实现；下游 facade 与集成路径必须只委托该 Runtime。
- **风险分析**：匹配 EXP-2026-0001/0003；并发竞态、取消吞噬和任务泄漏风险最高。
- **工作量估算**：6 个并发与嵌套 TC，L。

### S5: Detector Capability 映射

- **依赖关系**：只依赖公共 contracts，可与 S2/S7 逻辑并行。
- **风险分析**：必须保持 SDK 0.1.x 和 modified_content 仅内存传递。
- **工作量估算**：3 TC，descriptor/context/result 映射，M。

### S6: Detector 生命周期与框架

- **依赖关系**：复用 S5 adapter、S2 failure policy 和 S3 evidence reason。
- **风险分析**：匹配 EXP-2026-0003/0007；initialize/shutdown 重复或 gRPC 取消清理会泄漏资源。
- **工作量估算**：5 TC，跨 registry/status/plugins/SDK，M。

### S7: 新 Flow 配置

- **依赖关系**：配置模型直接承载 S1/S2；legacy 编译必须等其验证边界稳定。
- **风险分析**：匹配 EXP-2026-0005；未知字段与新旧冲突不得被 Pydantic 默认吞掉。
- **工作量估算**：4 TC，模型、交叉校验和文档契约，M。

### S8: Legacy YAML 编译

- **依赖关系**：需要 S7 新模型和 S5 capability identity；为 S9 提供默认 Flow。
- **风险分析**：默认值、threshold、priority、required、circuit breaker 任一漂移都会改变既有安全结果。
- **工作量估算**：4 TC，兼容 compiler 与确定性指纹，M。

### S9: Reducer 与 PipelineEngine facade

- **依赖关系**：使用 S4 Runtime、S5 adapter 与 S8 compiled Flow。
- **风险分析**：action precedence、修改顺序、flag escalation、short-circuit 与双重调度均有既有回归锚点。
- **工作量估算**：5 TC，领域 reducer 加兼容 facade，M。

### S10: 请求级默认 Flow

- **依赖关系**：只有 adapter lifecycle 与 facade 完整后才能迁移 input/output/stream/post-audit 路径。
- **风险分析**：匹配 EXP-2026-0001；全局 runner 重新引入 unavailable Detector 会造成 fail-open 快照漂移。
- **工作量估算**：4 个高密度集成 TC，M。

### S11: 审计与 sink failure

- **依赖关系**：消费 S3 evidence，并依赖 S4 真实终态；可与 S9 逻辑并行。
- **风险分析**：匹配 EXP-2026-0002；审计字段必须加法兼容，sink 失败不能伪装成功或改变安全决定。
- **工作量估算**：5 TC，schema/privacy/persistence，M。

### S12: Streaming 聚合

- **依赖关系**：依赖 S10 streaming 执行路径和 S11 audit persistence。
- **风险分析**：长流可能导致证据无界膨胀；聚合不能改变 SSE chunk/event 行为。
- **工作量估算**：2 个聚焦 TC，S。

### S13: 降级可观测性

- **依赖关系**：需要 S10 的 request degradation 与 S11 的 evidence persistence 状态。
- **风险分析**：匹配 EXP-2026-0002；动态 labels、异常正文、endpoint 或 user/request ID 均可能泄密或爆炸基数。
- **工作量估算**：5 TC，metrics/tracing/sanitization，M。

### S14: 性能与 checkpoint 收口

- **依赖关系**：必须在全部行为切片完成后度量真实 Flow 版本。
- **风险分析**：匹配 EXP-2026-0006；空 checkpoint 假绿、P99/throughput 退化与 pending task 都阻塞 Gate 3。
- **工作量估算**：1 个性能 TC 加全局 collect/回归，S。

## Required Principle Check

1. **Plugin / Flow**：S5/S6/S9 将 Detector domain 限定在 adapter/reducer；S1～S4 核心只实现契约、策略、证据与运行机制。
2. **Explicit policy / failure**：S2、S3、S7、S11、S13 分别验证策略解析、失败终态、启动拒绝、持久化故障和降级可观测性。
3. **Transparency / contracts**：S6、S8～S10、S14 锁定 SDK/YAML/PipelineEngine/HTTP/SSE/Provider 与性能边界。
4. **Evidence / data**：S3、S11～S13 覆盖所有终态证据、最小化、脱敏、有界聚合和稳定低基数信号。

本阶段没有新增原则取舍；仅把 Gate 2 已确认的设计按依赖机械拆分。
