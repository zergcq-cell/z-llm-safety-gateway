# v0.2.0 Flow Foundation — 技术设计

## Context

当前 `PipelineEngine` 已实现 detector/context 并行、block/modify 短路、per-detector timeout、`fail_open`/`fail_closed`、circuit breaker fallback、阈值判定、flag escalation 和结果聚合。`chat.py`、`StreamingHandler` 与 `PostAuditRunner` 分别装配 input、sync/async output、sliding-window、buffer 和 post-audit 路径；Detector 初始化与 readiness 由 app-scoped `DetectorStatusRegistry` 协调。

现有实现的问题不是缺少检测能力，而是执行、策略、领域语义和证据边界耦合：

- Pipeline 核心直接理解 Detector、`block/modify/flag/allow` 和阈值。
- unavailable Detector 在请求入口被过滤，后续 runner 若重用全局集合可能重新引入它。
- timeout、异常、短路、readiness 与 circuit fallback 分散在 route、engine 和 status guard。
- 审计记录 detector 结果，但不能统一解释 skip、cancel、timeout、partial 和 nested execution。
- 旧 YAML、Detector SDK 和 HTTP/SSE 已成为外部兼容基线，不能以重写为由破坏。

本 change 只将安全检测执行 Flow 化。HTTP/Provider 全生命周期、通用 branch/join/retry、分布式调度、Redis、K8s 和 UI 均不在范围内。

## Project Principle Check

| 原则 | 本设计如何满足 | 风险或取舍 | 验证方式 |
|------|---------------|-----------|---------|
| Plugin / Flow；核心最小 | Capability adapter 和 reducer 承载 detector 输入、signal、阈值与动作聚合；Flow Runtime 只负责版本化契约、调度、生命周期、策略执行、上下文和证据 | v0.2.0 只 Flow 化检测阶段，HTTP/Provider 尚不是 Node | 依赖边界测试禁止 `flow/` 导入 detector/pipeline 领域模块；reducer contract 测试 |
| 策略显式；失败不静默 | 每个 Node 在启动时得到不可变 resolved policy；error、timeout、unavailable、circuit-open、stop、cancel 与 sink failure 都有稳定 reason | 旧 YAML 仍允许省略字段，但编译后必须全部显式 | 配置快照、失败矩阵、invalid-policy 启动拒绝测试 |
| 边界透明；契约稳定 | 保留 HTTP/SSE、Provider、Detector SDK、PipelineEngine facade 与旧 YAML；Flow 契约严格版本化 | 为资源有界引入硬上限，超过上限的极端旧配置会明确失败 | 契约回归、旧配置 corpus、基准与 hard-limit 测试 |
| 决策有证据；数据默认保护 | 每个 Node 与嵌套 Flow 有核心证据；原文、修改内容、插件 details、密钥和异常正文不得进入证据 | streaming 默认聚合持久化，而非展开所有 allow window | 恶意内容/插件测试、证据预算、streaming aggregate 与 sink-failure 测试 |

## Decisions

### D1. 契约版本与严格解析

**方案**：Flow、Node、Capability descriptor 都携带 `contract_version`。v0.2.0 支持集合仅含 `1.0`；未知 major、尚未实现的更新 minor、未知字段、非法 SemVer、重复或超长 ID 均在启动时拒绝。Flow version 使用 SemVer；Capability 实现版本保留插件实际非空字符串，Flow 可选声明精确预期值。

**为什么**：显式支持集合比自动接受同 major 更安全，避免新增 minor 字段被旧 runtime 静默忽略。Capability 版本不强制 SemVer，以兼容现有第三方 Detector。

**备选方案及排除原因**：

- 自动接受任意 `1.x`：旧 runtime 可能不理解新增策略字段。
- 依赖 Pydantic 默认 `extra=ignore`：会使安全策略拼写错误静默生效。
- 只版本化 Flow：Node/Capability 演进仍会形成隐式契约。

### D2. Flow 输入与执行模型

**方案**：`FlowInput` 是版本化 ordered items + immutable request context。Capability Node 默认 `input_mode=each`，Nested Flow Node 使用相同 envelope。Runtime 以 semaphore 限制并发，按 Node 定义顺序和 item 顺序输出结果与证据。

**为什么**：保留现有 detector × message 并行语义，同时避免一次创建无界 Task。确定输出顺序使聚合、审计和测试可复现。

**备选方案及排除原因**：

- Capability adapter 内部自行遍历所有 message：把组合逻辑推回插件。
- 一次性 `create_task` 全量 fan-out：大请求会产生无界任务。
- 按完成顺序输出：同一输入可能得到不同证据与 tie-break 顺序。

### D3. Signal + Reducer 隔离领域行为

**方案**：Capability 返回内存 output、稳定 signals 和受约束 evidence summary。Stop policy 匹配 signal；Flow 最终结果由版本化 reducer capability 生成。默认 Flow 使用 `detector-result-reducer`，Detector adapter 将动作映射为 `safety.allow|flag|modify|block` signal。

**为什么**：通用 Runtime 不需要知道 detector action precedence、risk、modification 或 flag escalation，满足核心最小原则。

**备选方案及排除原因**：

- 在 Runtime 中硬编码 `block > modify > flag > allow`：领域逻辑继续积累在核心。
- 让 Detector 决定全 Flow 结果：插件开始控制端到端过程。
- 通用表达式 DSL 聚合任意 JSON：首版复杂度和攻击面过大。

### D4. 显式策略模型

**方案**：每个 Node 解析为完整 `availability`、`timeout`、`failure`、`degradation` 和 `stop` policy。Runtime 不在请求期推断默认值；每个字段记录来源 `explicit|legacy|default`。普通异常、Node timeout、unavailable 和 circuit-open 分别使用独立 action/reason。

**为什么**：`on_error` 不能再隐式兼任所有失败类型。分离策略允许保持 legacy 映射，同时让新 Flow 明确表达取舍。

**备选方案及排除原因**：

- 继续只有 `on_error`：timeout 与不可用的原因和选择不可区分。
- 异常时统一 fail-closed：破坏现有 fail-open 兼容。
- Runtime 自动修复冲突配置：违反失败不静默原则。

### D5. Runtime 硬限制

**方案**：默认 `max_depth=8`、`max_nodes=256`、`max_concurrency=64`、`default_timeout=30s`、`absolute_timeout=120s`；v0.2.0 的 `max_evidence_size` 固定为 `256KB`，启动期拒绝更小或更大的值。Node timeout 仍继承既有 detector timeout；sync output 的有效 deadline 取 Flow deadline 与现有 `sync_timeout` 的较小值。

**为什么**：嵌套、并行和证据若无硬边界会引入不可预测延迟与内存成本。数值足以覆盖当前常规 detector 配置，又能形成可测试上界。

**兼容取舍**：历史上可解析但超过这些上限的极端配置将明确启动失败。这是原则要求的有意收紧，已在 Gate 2 确认。

### D6. 新 Flow 配置与 Legacy Compiler

**方案**：新增顶层 `flow_runtime`、`flows`、可选 `capabilities`，以及 `pipeline.input_flow/output_flow`。`capabilities` 仅为显式 Flow 提供 Detector implementation binding 与私有配置，不表达顺序或执行策略；绑定 ID 必须严格匹配 `detector.<detector_name>`，重复和未使用绑定在启动期拒绝。原始 YAML 显式含 `flows` 和 `pipeline.detectors` 时拒绝。未配置 `flows` 时，Legacy Compiler 生成 `legacy-input-detector-flow` 与 `legacy-output-detector-flow`，完整映射 detector 配置、阈值、priority、required、timeout、on_error、circuit breaker、short circuit 和 flag escalation。

**为什么**：双模式迁移能保持旧 YAML，同时避免两套配置产生静默优先级。冲突判断必须基于原始键存在性，不能被 Pydantic 默认空模型误导。

**备选方案及排除原因**：

- 新 Flow 覆盖旧 detector 配置：行为来源不透明。
- 自动合并两者：同名 Node 与策略冲突难以确定。
- 立即删除旧 YAML：破坏公开兼容承诺。

### D7. 请求级 FlowExecutionSnapshot

**方案**：请求入口在 Provider 前解析 input/output Flow、版本、Capability 状态与 resolved policy，形成 immutable snapshot。sync、async、sliding-window、buffer 和 post-audit 必须显式传递该 snapshot；当前请求不因中途健康恢复而改变集合。

**为什么**：直接应用 EXP-2026-0001，阻止全局 runner 在后续阶段重新引入 unavailable Detector，并使一次请求可复现。

**备选方案及排除原因**：

- 每阶段重新读全局状态：请求内行为可能漂移。
- 入口只过滤 Detector list：丢失为何跳过的 Node 证据。

### D8. Detector Capability Adapter 与 lifecycle

**方案**：现有 Detector 无需实现新接口。Adapter 生成 descriptor、构造 DetectionContext、映射 result/signal，并委托既有初始化、health、status 和 shutdown 协调器。四类 Detector 共用路径；不新增 sentinel，不重复 initialize/shutdown。

**为什么**：保护 SDK 0.1.x、entry point 与 gRPC v1，同时把现有插件纳入 Capability 契约。

**备选方案及排除原因**：

- 修改 Detector SDK 强制实现 Capability：破坏第三方插件。
- Runtime 直接拥有第二套 Detector lifecycle：会双重初始化和关闭。

### D9. PipelineEngine 兼容 facade

**方案**：保留构造器、`run(detectors, contexts, detector_configs)` 与 `PipelineResult`。Facade 构建/缓存默认 Flow binding 并委托 Runtime；旧 asyncio 调度路径移除，避免双执行。

**为什么**：现有测试、benchmark 和内部消费者依赖该 API；facade 允许分阶段迁移 route/streaming。

### D10. Evidence 数据模型

**方案**：`FlowEvidence` 记录 execution/parent、Flow identity/version、stage、status、deadline、final signal、duration 与 persistence 状态。`NodeEvidence` 记录 Node/target identity、status、degraded、reason、effective policy、duration 和 item 计数。Node status 为 `succeeded|failed|timed_out|skipped|cancelled|partial`。

核心证据必须保留；插件可选 summary 通过字段类型、长度、signal 数和总预算限制。超限时先删除可选 summary/signal、再对长身份做不可逆缩写；若最大合法图的完整 stop-signal tuple 仍不可表示，仅将该 tuple 替换为确定性 SHA-256 指纹。全部 Node 终态、status、reason、其他策略事实和 source 仍保留，并标记 `details_truncated` / `evidence_budget_exceeded`。

### D11. 审计与 streaming 证据

**方案**：AuditEntry 加法扩展 Flow 字段与 NodeEvidence。Flow evidence 永不保存 raw content、modified content、Detector message/details、plugin config 或异常正文；即使 `store_content=true`，内容仍只使用现有独立 content 字段与 sanitizer。

每次 streaming window Flow 执行都先产生运行时证据；默认持久化按 flow/node/action/reason 聚合，保留次数、滚动摘要和触发窗口，post-audit 作为主 Flow evidence 单独完整保存。Streaming 摘要中的 post-audit 副本需为外层 envelope 预留字节；若不可压缩的核心仍无法容纳，只省略该副本并标记截断。Sink 失败不改变安全决定，但设置 `evidence_persisted=false` 并记录 warning/metric；生产 file handler 内部吞掉的 I/O 异常也必须转成该稳定失败状态。

### D12. Stop、取消与清理

**方案**：stop signal 触发后保留 completed 结果，取消并 await pending 调用，再执行 reducer。外部 `CancelledError` 在 `finally` 清理后重新抛出，不合成 safety result。Nested Flow 的子 stop 先收敛为子结果，再由父 Node policy 决定父 Flow 是否停止。

**为什么**：既保持当前 short-circuit，又直接应用 EXP-2026-0003 防止 channel、client 或部分资源泄漏。

### D13. Observability

**方案**：新增 flow execution/duration 和 node execution 指标。Metrics labels 仅含验证后的 flow_id、direction、node_id、status、reason_code；Capability/Flow version 进入 span 和 audit，不进入 metrics。Trace 层级为 request → flow → node → nested flow。

禁止 payload、request/user ID、endpoint、异常正文和任意 evidence text 进入指标或 span attributes。metrics disabled 时 helper 为 no-op。

### D14. 兼容与性能门

**方案**：HTTP status/body/header、SSE event/chunk、Provider 调用、Detector SDK、entry point、gRPC proto、PipelineEngine 和旧 YAML 均有契约回归。标准 rule-based benchmark 要求 P99 继续低于 200ms、throughput 不低于 7,920 req/s 基线的 90%，且执行后无 pending Flow task。

## Architecture

```text
Gateway YAML
   │
   ├─ explicit flows ───────────────┐
   └─ legacy detector config        │
          │                         │
          ▼                         │
   LegacyDetectorFlowCompiler       │
          └──────────────┬──────────┘
                         ▼
               Contract + Graph Validator
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
   Capability Registry       Resolved Flow Registry
   ├─ Detector adapters              │
   ├─ reducer capability             │
   └─ lifecycle/status               │
            │                         │
            └────────────┬────────────┘
                         ▼
 Request admission → FlowExecutionSnapshot
                         │
        ┌────────────────┼────────────────────────┐
        ▼                ▼                        ▼
   input Flow       Provider boundary       output Flow
                                           sync / async
                                           stream / buffer
                                           post-audit
                         │
                         ▼
                    Flow Runtime
        ┌──────────────┬───────────────┐
        ▼              ▼               ▼
 Capability Node  Nested Flow Node  Policy/limits
        │              │               │
        └──────────────┴──────┬────────┘
                              ▼
                     Reducer Capability
                              │
                ┌─────────────┴────────────┐
                ▼                          ▼
          Compatible result          Evidence chain
                                           │
                                 Audit / Metrics / Trace
```

### 主要模块边界

```text
src/z_llm_safety_gateway/
├── flow/
│   ├── contracts.py       # domain-neutral envelopes/descriptors/results
│   ├── policy.py          # resolved policies and validation
│   ├── runtime.py         # bounded execution, nesting, stop/cancel
│   ├── evidence.py        # core evidence and sanitization/budget
│   ├── detector_adapter.py # Detector-domain Capability boundary adapter
│   └── legacy.py          # legacy config → default Flow
├── pipeline/
│   ├── engine.py          # compatibility facade
│   ├── flow_reducer.py    # detector-result-reducer implementation
│   ├── snapshot.py        # immutable request execution snapshot
│   └── aggregator.py      # legacy result aggregation primitive
├── config/                # new Flow models + raw source conflict validation
├── audit/                 # additive Flow evidence schema
└── observability/         # Flow metrics/spans
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 默认 Flow 与旧 Pipeline 结果漂移 | 以归档 v0.0.2 spec 和现有测试为双执行 oracle；逐路径对照 action/risk/modification/HTTP/SSE |
| 新旧配置双重事实来源 | 基于 raw YAML 检测显式键；冲突启动失败 |
| unavailable Detector 在后续阶段复活 | immutable request snapshot 显式传递给所有 runner |
| short-circuit/cancel 遗留任务或资源 | cancel + await + finally bounded cleanup；任务泄漏测试 |
| reducer 将领域逻辑带回核心 | 注册 reducer contract；依赖边界禁止 flow core 导入 detector/pipeline domain |
| 证据泄露内容、秘密或内部拓扑 | 核心 allowlist、稳定 reason code、总预算、恶意插件/异常测试 |
| streaming 证据量膨胀 | 运行时逐次产证，审计按稳定维度有界聚合 |
| sink 失败造成“审计成功”假象 | evidence_persisted=false + warning + metric；决策保持兼容 |
| 硬限制拒绝极端旧配置 | 启动给出明确 limit code 和迁移说明；无静默截断 |
| Runtime 抽象增加延迟 | semaphore/lazy task、禁用观测 no-op、基准门和 profile |
| SDK 或第三方插件破坏 | adapter-only 集成；SDK/entry point/gRPC proto 契约测试 |
| Agent spec 引用不存在测试 | Phase 4 按精确 TC node 创建 RED 测试；Gate 3 AST + pytest collect 禁止空集合 |
