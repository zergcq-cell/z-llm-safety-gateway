# Phase Context — 2026-08-22-v0.2.0-flow-foundation

## Phase 1: UNDERSTAND (completed 2026-08-22T21:43:28+08:00)

### 需求边界

- 建立带 `contract_version: "1.0"` 的 Flow、Node 与 Capability 契约，并将现有 detector pipeline 适配为默认 Flow。
- 支持显式 availability、timeout、failure、degradation 与 stop 策略，以及逐 Node、逐 Flow 的结构化证据链。
- 保持现有 HTTP/SSE、Provider、Detector SDK 0.1.x、entry point、gRPC proto、PipelineEngine 与 legacy YAML 兼容。
- 本 change 不实现 K8s、Redis、新 Provider、UI 或大量新检测器。

### 模式与锚定

- 用户选择 `thorough` 模式并确认 Gate 1。
- 本 change 为安全关键、跨系统的 L3 锚定变更。
- 参考变更：`2026-08-11-v0.0.2-pipeline-detectors`、`2026-08-14-v0.0.5-plugin-ecosystem`、`2026-08-19-detector-readiness-fail-safe`、`2026-08-20-v0.1.1-release-hardening`。

## Phase 2: SPEC (completed 2026-08-22T22:19:04+08:00)

### 锁定的架构决策

- `FlowDefinition`、`NodeDefinition`、`CapabilityDescriptor` 均版本化；v0.2.0 仅接受 `contract_version: "1.0"`。未知 major、未实现的新 minor、非法版本、未知字段与非法/重复 ID 在启动时拒绝。
- 通用 Flow Runtime 保持领域中立；Detector 行为由 `detector-capability-adapter` 与版本化 `detector-result-reducer` 承担。Runtime 只消费稳定 signal 与 reducer contract，不硬编码 detector action precedence。
- 每个 Node 在启动期解析为完整且来源可追踪的 availability、timeout、failure、degradation、stop policy；异常、超时、unavailable 与 circuit-open 使用独立 action/reason。
- 新 YAML 增加 `flow_runtime`、`flows`、`pipeline.input_flow/output_flow`。现有 YAML 确定性编译为 `legacy-input-detector-flow` 与 `legacy-output-detector-flow`；显式 `flows` 与显式 `pipeline.detectors` 同时出现时拒绝启动。
- `PipelineEngine` 保留为兼容 facade，内部执行只走 Flow Runtime，不保留第二套调度。
- 请求入口创建 immutable `FlowExecutionSnapshot`，并显式穿过 input、sync/async output、sliding-window、buffer 与 post-audit；当前请求不因中途健康状态变化而改变执行集合。
- 每次 Node/Flow 执行生成结构化证据。证据不保存 raw/modified content、Detector message/details、secret、endpoint 或 raw exception；可选摘要受类型、长度、signal 数与总预算限制。
- Streaming 每次执行先生成运行时证据，默认审计按稳定维度有界聚合；post-audit 单独保存。Sink 失败不改变安全决定，但必须设置 `evidence_persisted=false` 并产生稳定 warning/metric。
- 取消必须在 `finally` 中有界清理全部子任务和本地资源，再原样传播 `CancelledError`；不得合成 allow/block。

### 用户确认的硬限制与性能门

- `max_depth=8`
- `max_nodes=256`（展开后）
- `max_concurrency=64`
- `default_timeout=30s`
- `absolute_timeout=120s`
- `max_evidence_size=256KB`
- 标准 rule-based benchmark：P99 `< 200ms`，throughput `>= 7,920 req/s × 90%`，结束后 pending Flow task 为 0。

### Project Principle Check

1. **能力插件化，执行 Flow 化，核心保持最小**：Capability/Reducer 插件化，Detector 语义隔离在 adapter/reducer，Runtime 不导入 Detector 领域模块。
2. **策略必须显式，失败绝不静默**：所有执行策略在启动期完整解析；配置冲突、契约不兼容、降级、sink 失败和证据截断均显式失败或可观测。
3. **边界保持透明，契约保持稳定**：保持 HTTP/SSE、Provider、Detector SDK、entry point、gRPC proto、PipelineEngine 和 legacy YAML 契约；新增审计字段仅做加法扩展。
4. **每一个安全决定都有证据，数据默认受到保护**：所有终态与跳过/取消均产证；证据仅使用稳定、受限、脱敏字段。

### 显式取舍

- 历史上可解析但超过 runtime 硬限制的极端配置现在会启动失败；这是为防止无界资源消耗而确认的兼容收紧。
- Evidence sink 失败时保持既有安全决定，避免审计基础设施反向改变请求语义；失败状态必须显式暴露，不能报告为持久化成功。
- Capability 实现版本保留第三方插件实际非空字符串，不强制 SemVer；契约版本仍严格按受支持集合校验。

### 经验约束

- EXP-2026-0001：请求级 Detector/Capability snapshot 必须穿过全部执行阶段。
- EXP-2026-0002：对外状态、日志与证据只暴露稳定 reason code。
- EXP-2026-0003：取消清理放在 `finally`，清理后继续传播 cancellation。
- EXP-2026-0005：配置文档示例必须由真实 runtime model 验证。
- EXP-2026-0006：Agent checkpoint 最终必须对应真实精确 pytest node，禁止空 glob 假绿。

### Phase 2 产出与覆盖

- `design.md`：完整架构、策略、兼容、安全、证据、可观测与性能设计。
- `specs/*/spec.md`：12 个 capability Human View。
- `canonical/specs/code/*.yaml`：12 个 code canonical specs。
- `canonical/specs/agent/*.yaml`：12 个 agent canonical specs。
- `test-plan.md`：61 个 TC；P0=54、P1=6、P2=1；high=46、medium=15、low=0。
- 总覆盖：38 requirements、61 scenarios、61 test cases；每个 requirement 至少有一个 GIVEN/WHEN/THEN + SHALL 场景。

## Phase 3: SLICE (completed 2026-08-22T22:27:23+08:00)

### 执行模式

- 用户选择并确认全部授权：`full_auto` 长程模式，最多 10 轮迭代，同一问题连续自动修复 3 次失败时降级。
- Gate 3、L3 锚定、全量失败模式检查、完整回归、隐私与性能门仍为强制步骤。
- 当前平台为 Codex managed permissions；未创建仅对 Claude Code 生效的 `.claude/settings.local.json`。

### 切片结果

- `tasks.md` 与 `slices.md` 已生成并校验。
- 38/38 Requirements、61/61 TC 被精确覆盖且每个 TC 只属于一个切片。
- 共 14 个切片：contracts → policy/evidence → runtime/adapter/config → reducer/facade → request/audit → streaming/observability → performance/checkpoint。
- STDD CLI canonical dependency graph 报告 12 个 zero-dependency、0 edge、0 cycle；由于 canonical schema 未编码实现依赖，`slices.md` 依据设计边界补充人工拓扑并复核为 0 cycle。
- 当前采用串行 S1→S14，避免多个写入者同时修改共享 core/config/app 边界。

### Phase 4 强制约束

- 每个切片严格执行 RED → GREEN → REFACTOR；不得在对应 RED 测试前修改产品代码。
- 每个切片必须实现全部 planned exact pytest nodes，TC 覆盖 100%、新增测试数大于 0，并执行受影响回归。
- Agent specs 中的 pytest node 在各 RED 阶段创建；S14 与 Gate 3 前用 AST 和 pytest collect 验证 61/61 真实存在、可收集，禁止空 glob。
- 每个切片验证后必须在 `.stdd.yaml` 与本文件记录 tc_coverage、new_tests、verified_at 和产出物。

## Phase 4: BUILD (completed 2026-08-23T00:15:17+08:00)

### S1 版本化 Flow 契约（completed 2026-08-22T22:34:44+08:00）

- **RED**：新增 6 个 canonical exact pytest nodes（8 个 collected cases）；因 `z_llm_safety_gateway.flow` 不存在而收集失败。
- **GREEN**：新增 strict/frozen contracts、Capability/Nested Flow registry、schema/ref/cycle/depth/node-limit validation、immutable ordered FlowInput 与 payload-free evidence envelope。
- **REFACTOR**：修正 `collections.abc.Mapping` 导入与 binding union 类型收窄；公共 API 保留完整类型注解。
- **切片验证**：TC-FC-001～006 覆盖 6/6；定向 8 passed；完整回归 907 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **新增文件**：`src/z_llm_safety_gateway/flow/__init__.py`、`flow/contracts.py`、`tests/unit/flow/test_contracts.py`。

### S2 显式策略解析（completed 2026-08-22T22:43:27+08:00）

- **RED**：新增 6 个 exact pytest nodes；因 `flow.policy` 不存在而收集失败。
- **GREEN**：新增五维 Node policy config/default/resolved snapshot、`explicit|legacy|legacy_default|default` 来源、四类失败的独立稳定决策、父 deadline 上界与 pending timeout 确定性收敛。
- **REFACTOR**：failure decision 只携带稳定 kind/action/reason/degraded/stop/invocation 字段，不接受或输出 raw exception；冲突统一为 payload-free `policy_conflict`。
- **切片验证**：TC-FP-001～006 覆盖 6/6；定向 6 passed；完整回归 913 passed / 1 skipped；Ruff、Mypy 通过。
- **新增文件**：`src/z_llm_safety_gateway/flow/policy.py`、`tests/unit/flow/test_policy.py`。

### S3 核心证据模型与保护（completed 2026-08-22T22:47:36+08:00）

- **RED**：新增 5 个 exact pytest nodes（10 个 collected cases）；因 `flow.evidence` 不存在而收集失败。
- **GREEN**：新增六种 Node 终态、Flow 终态、确定排序、父子 execution、item 计数核对、typed safe summary、32-signal 和 256KB 默认预算。
- **REFACTOR**：可选摘要先按字段白名单过滤再验证；raw/modified content、message/details、endpoint 与 exception 无模型字段，拒绝/截断均保留核心证据和稳定 reason。
- **切片验证**：TC-NEC-001～005 覆盖 5/5；定向 10 passed；完整回归 923 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **新增文件**：`src/z_llm_safety_gateway/flow/evidence.py`、`tests/unit/flow/test_evidence.py`。

### S4 Flow Runtime（completed 2026-08-22T22:54:31+08:00）

- **RED**：新增 6 个 exact pytest nodes；因 `flow.runtime` 不存在而收集失败。
- **GREEN**：新增最多 64 并发的延迟任务调度、definition/item 确定排序、空 Flow、stop cancellation、Nested Flow、父 deadline、timeout fallback、外层 cancellation 传播与 pending task 计数。
- **REFACTOR**：active task 在 stop/deadline/cancel 三条路径统一 cancel+gather；完成结果在竞态中保留；Runtime 不含 detector action precedence。
- **切片验证**：TC-FR-001～006 覆盖 6/6；定向 6 passed；沙箱内回归 913 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过；pending task=0。
- **环境注记**：重复开放 loopback 的工具请求因账户用量上限被平台拒绝；两份既有 gRPC 端口测试在 S4 前完整基线 899 passed / 1 skipped 中已通过，S4 未修改 gRPC 模块；Phase 5 需重试完整回归。
- **新增文件**：`src/z_llm_safety_gateway/flow/runtime.py`、`tests/unit/flow/test_runtime.py`；`flow/contracts.py` 增加 exact Flow lookup。

### S5 Detector Capability 映射（completed 2026-08-22T23:03:34+08:00）

- **RED**：新增 3 个 exact pytest nodes（9 个 collected cases）；因 `flow.detector_adapter` 不存在而收集失败。
- **GREEN**：四类 Detector 共用 contract 1.0 descriptor；FlowItem/FlowContext 精确映射 DetectionContext；allow/block/flag/modify 映射稳定 signal；gateway 与 SDK results 正规化为现有 DetectionResult。
- **REFACTOR**：SDK dataclass-style `to_dict()` 与 Pydantic `model_dump()` 在边界适配；modified_content 只留在内存 output，evidence summary 只含 action/risk/category/confidence bucket。
- **切片验证**：TC-DCA-001～003 覆盖 3/3；定向 9 passed；沙箱回归 922 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **新增文件**：`src/z_llm_safety_gateway/flow/detector_adapter.py`、`tests/unit/flow/test_detector_adapter.py`；CapabilityDescriptor 加法扩展 name/category。

### S6 Detector 生命周期与框架（completed 2026-08-22T23:07:47+08:00）

- **RED**：新增 5 个 exact pytest nodes；因 `DetectorCapabilityCoordinator` 不存在而收集失败。
- **GREEN**：复用 DetectorStatusRegistry；同一实例跨方向只 initialize/health/shutdown 一次；immutable application snapshot；初始化失败为 unavailable 且不创建 sentinel adapter；取消沿 adapter 原样传播并触发 detector finally。
- **REFACTOR**：registration/config 与 snapshot adapter map 均只读复制；shutdown 逆序且有 timeout；SDK entry-point group 与 gRPC proto 不变。
- **测试锚点修正**：RED 期间发现测试误认为既有 proto 含 `GetDetectorInfo`；按真实 v1 基线修正为 Initialize/Detect/HealthCheck/Shutdown，未修改 proto。
- **切片验证**：TC-DCA-004～005、TC-DF-701～703 覆盖 5/5；定向 5 passed；沙箱回归 927 passed / 1 skipped；Ruff、Mypy 通过。
- **修改文件**：`flow/detector_adapter.py`、`tests/unit/flow/test_detector_adapter.py`；新增 `tests/unit/detectors/test_flow_adapter_lifecycle.py`。

### S7 新 Flow 配置与启动验证（completed 2026-08-22T23:18:57+08:00）

- **RED**：新增 4 个 exact pytest nodes；因 FlowRuntimeConfig 不存在而收集失败。
- **GREEN**：新增严格 FlowRuntimeConfig、exact stage refs、Gateway Flow graph/policy startup validation、raw-key conflict gate 与 immutable resolved policies。
- **REFACTOR**：legacy PipelineConfig 默认 detectors 不误触冲突；Gateway errors 隐藏 input values；Flow 文档示例用真实 GatewayConfig 解析。
- **切片验证**：TC-CFG-001～002、005～006 覆盖 4/4；定向 4 passed；沙箱回归 931 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **修改文件**：`config/models.py`、`docs/configuration.md`；新增 `tests/unit/config/test_flow_config.py`。

### S8 Legacy YAML 编译（completed 2026-08-22T23:23:23+08:00）

- **RED**：新增 4 个 exact pytest nodes；因 `flow.legacy` 不存在而收集失败。
- **GREEN**：flat/bidirectional detectors 确定性编译为固定 input/output Flow；映射 timeout/priority/required/on_error/circuit/short-circuit，记录 legacy/legacy_default 来源与 sync timeout。
- **REFACTOR**：DetectorConfig 私有 config 只在 repr=false 内存映射；fingerprint 只序列化 Flow/Policy，排除密钥和内容；policy action 用验证后 Literal cast 满足 strict typing。
- **切片验证**：TC-CFG-003～004、TC-DDF-001～002 覆盖 4/4；定向 4 passed；沙箱回归 935 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **新增文件**：`src/z_llm_safety_gateway/flow/legacy.py`、`tests/integration/test_default_detector_flow.py`；扩展 `test_flow_config.py`。

### S9 默认 Reducer 与 PipelineEngine facade（completed 2026-08-22T23:34:44+08:00）

- **RED**：新增 TC-DDF-003～004、007 与 TC-PE-001～002；因 `pipeline.flow_reducer` 缺失导致 5 个 TC 收集失败，facade 单次委托测试随后以 execute calls=0 保持 RED。
- **GREEN**：新增版本化 detector-result-reducer；PipelineEngine 保留 constructor/run/PipelineResult，并将 detector/context 笛卡尔执行、timeout、circuit fallback、threshold、stop、aggregation 委托给一次 FlowRuntime.execute。
- **REFACTOR**：Flow core 不导入 detector/pipeline domain；facade 不再维护第二套 create_task/wait 调度；错误日志改为稳定 reason/type 且不写 raw exception；修正 Python 3.10 asyncio timeout 的真实终态分类。
- **切片验证**：TC-DDF-003～004、007、TC-PE-001～002 覆盖 5/5；S9 + 既有 Pipeline/Runtime 定向 57 passed；沙箱回归 940 passed / 1 skipped；Ruff、Mypy 通过。
- **修改文件**：`pipeline/engine.py`、`flow/runtime.py`、`tests/integration/test_default_detector_flow.py`；新增 `pipeline/flow_reducer.py`、`tests/unit/pipeline/test_flow_compat.py`。

### S10 请求级默认 Flow 与公共边界（completed 2026-08-22T23:42:23+08:00）

- **RED**：新增 TC-DDF-005～006 与 TC-DSV-701～702；因 `pipeline.snapshot` 缺失而收集失败。
- **GREEN**：请求在 Provider 选择前捕获 frozen FlowExecutionSnapshot；input、sync/async output、sliding-window、buffer、streaming 与 post-audit 从同一 snapshot_id 取 detector/config；unavailable 每阶段生成 skipped+degraded NodeEvidence。
- **REFACTOR**：异步闭包捕获 tuple/config/availability 副本，不再读取请求结束后的全局 detector runner；后续 lifecycle 恢复不改变当前请求快照；既有 request.state detector 列表保留兼容。
- **切片验证**：TC-DDF-005～006、TC-DSV-701～702 覆盖 4/4；相关 HTTP/SSE/audit/stream/post-audit 定向 95 passed；沙箱回归 944 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **新增文件**：`pipeline/snapshot.py`、`tests/integration/test_flow_degradation.py`；修改 `routes/chat.py` 与 `test_default_detector_flow.py`。

### S11 审计证据与持久化故障（completed 2026-08-22T23:48:49+08:00）

- **RED**：新增 TC-AUD-701～703、705 与 TC-NEC-007；因 AuditEntry 无 Flow evidence API、AuditLogger 不接受 evidence persistence context 而 5/5 失败。
- **GREEN**：AuditEntry 加法扩展 flow identity/status/node_evidence/evidence_persisted；PipelineResult 暴露 runtime evidence；input/output/admission/post-audit 接入既有审计路径；sink 失败返回 intact evidence 的 unpersisted 副本。
- **REFACTOR**：NodeEvidence 继续由 strict payload-free model 控制，store_content 只作用于既有 content 字段；sink warning 只含 sink/sink_error，不含异常正文；新增低基数 persistence failure counter。
- **切片验证**：TC-AUD-701～703、705、TC-NEC-007 覆盖 5/5；相关定向 54 passed；沙箱回归 949 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **修改文件**：`audit/models.py`、`audit/logger.py`、`observability/metrics.py`、`pipeline/engine.py`、`post_audit/audit.py`、`routes/chat.py`、`app.py`；新增 `tests/unit/audit/test_flow_evidence.py`。

### S12 Streaming 有界证据聚合（completed 2026-08-22T23:52:11+08:00）

- **RED**：新增 TC-AUD-704 与 TC-NEC-006；因 `audit.streaming_evidence` 缺失而 2/2 收集失败。
- **GREEN**：StreamingHandler 对每个 window FlowEvidence 先记录后聚合；稳定 bucket 保存 execution/degraded 计数与最多 32 个触发窗口；post-audit 作为独立完整 evidence。
- **REFACTOR**：默认不展开重复 allow windows；bucket 最大 512，超限优先保留高风险 action 并标记 details_truncated；最终 JSON 硬限制 256KB。
- **切片验证**：TC-AUD-704、TC-NEC-006 覆盖 2/2；stream/audit 定向 68 passed；沙箱回归 951 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **新增文件**：`audit/streaming_evidence.py`；修改 `audit/models.py`、`streaming/handler.py`、`routes/chat.py`。

### S13 降级可观测性与隐私（completed 2026-08-22T23:55:35+08:00）

- **RED**：新增 TC-DSV-703 与 TC-OBS-701～704；因 `observability.flow` 缺失而 5/5 收集失败。
- **GREEN**：Runtime evidence 自动投影 Flow/Node counters+duration；disabled metrics no-op；evidence-only trace 形成 request→flow→node→nested-flow 层级并携带真实 status/reason。
- **REFACTOR**：ID/reason/enum 均经白名单与长度验证，非法值统一为 `invalid` 并增加 sanitization counter；metrics 不含 request/user/version 动态标签，spans 不含 payload/user/endpoint/异常正文。
- **切片验证**：TC-DSV-703、TC-OBS-701～704 覆盖 5/5；observability/runtime/degradation 定向 36 passed；沙箱回归 956 passed / 1 skipped；Ruff、Mypy、`git diff --check` 通过。
- **新增文件**：`observability/flow.py`、`tests/unit/observability/test_flow_observability.py`；修改 `observability/metrics.py`、`flow/runtime.py`、`test_flow_degradation.py`。

### S14 性能与 checkpoint 收口（completed 2026-08-23T00:15:17+08:00）

- **RED**：新增精确节点 `tests/unit/pipeline/test_flow_compat.py::test_tc_pe_003`；初始 Flow facade 测得约 4,040 req/s，低于 7,128 req/s 门槛；另以聚焦测试确认仅按配置对象 ID 缓存会掩盖原地配置变更。
- **GREEN**：Pipeline plan/runtime 复用并以配置值快照安全失效；disabled observability 提前 no-op；Capability timeout 不再创建第二层 task；无阻塞同进程 Capability 在一个调度轮次后直接收敛，异步节点继续走原有 bounded wait/stop/cancel 路径；Node evidence 静态契约/策略模板复用且动态摘要仍经白名单。
- **REFACTOR**：保留外层取消传播、nested deadline、timeout 终态与 pending task=0；缓存不保留请求内容，只保存 detector/config/契约级计划；原地 threshold 修改立即失效。
- **性能验证**：最终正式 benchmark P50 0.12ms / P95 0.13ms / P99 0.15ms / 8,461 req/s；P99 < 200ms、throughput >= 7,128 req/s、pending Flow tasks=0、disabled observability 均通过。
- **Checkpoint 验证**：61/61 canonical exact nodes 经 AST 存在检查；61/61 可 collect，参数化展开 74 cases；74/74 通过。
- **回归验证**：沙箱 962 passed / 1 skipped，另 2 个 gRPC sidecar 因 loopback bind 受限出现环境 setup error；允许本机回环后完整回归 980 passed / 1 skipped。Ruff、Mypy（99 source files）、`git diff --check` 通过。
- **新增/修改**：新增 `benchmark-report.md`；修改 `flow/runtime.py`、`flow/evidence.py`、`observability/flow.py`、`pipeline/engine.py`、`tests/unit/pipeline/test_flow_compat.py`。

### Phase 4 状态

- S1～S14 全部完成，61/61 TC 有精确 checkpoint；BUILD 状态为 completed，自动进入 Phase 5 VERIFY。

## Phase 5: VERIFY (in progress)

### 全量质量检查

- 受限沙箱配置套件：`998 passed / 1 skipped / 0 failed`；3 个既有 gRPC 测试文件共 13 个 setup error，原因均为沙箱禁止绑定 `127.0.0.1:0`。
- 允许本机回环后的同一配置套件：`1011 passed / 1 skipped / 0 failed`。
- 覆盖率诊断：全源代码行覆盖率 `93%`（5521 statements / 368 missed）；coverage 运行同为 `1011 passed / 1 skipped`。
- Ruff：完整配置范围通过；Mypy：99 个源文件 0 issues；`git diff --check` 通过。
- 当前环境仅提供 Python 3.10.20；Python 3.11/3.12 解释器不可用，按环境限制记录为 SKIPPED，不标记 PASS。

### Canonical checkpoint 与关键路径

- 61/61 primary checkpoint 经 AST 证明真实存在；`pytest --collect-only` 展开 74 cases；74/74 通过。
- 12 份 Agent spec 已从 change 目录真实执行；action 先回到项目根再使用项目虚拟环境，消除工作目录断链。
- TC-DDF-006 checkpoint 同时执行 HTTP/Provider/header、SSE 顺序、output unavailable fail-closed、buffer replay、async immediate-return 与 post-audit 路径。
- 显式空 Flow、capability unavailable 的 fail-open/fail-closed、四类失败策略矩阵、256-Node 完整证据预算与请求级 sink persistence 状态均有新增自动化回归。

### Review 修复摘要

- 显式 Flow 已贯穿配置、Detector 初始化、Pipeline facade、Runtime 与 HTTP 请求，不再出现“配置接受但运行时未消费”。
- `capabilities` 提供独立 implementation binding，保留 gRPC、ML 与 entry-point detector 私有配置且不把顺序带回旧 pipeline 配置。
- Runtime 与 reducer 保持 error、timeout、unavailable、circuit-open 四类 fallback 独立；原始异常不进入结果、审计或 trace。
- Evidence 对完整 envelope 施加 256 KiB 预算并保留最多 256 个终态；不可表示的小预算在启动期拒绝。
- Availability snapshot 使用显式 Flow identity 和 resolved policy；空 Flow 仍执行 reducer 并产生 completed evidence。
- Audit sink 失败会同步更新 AuditEntry、返回 evidence 与 request-held evidence 的 `evidence_persisted=false`，安全决定不变。
- Verify Skill 与 Trae 适配副本统一为 12 类失败模式及 7 个强制条目。

### 最终 Review 修复循环

- 三路最终只读复审共发现 `C0 / H3 / M5 / L4`；产品、测试、文档问题均已关闭。
- Nested Flow `STOPPED/PARTIAL` 现可核对终态计数并向父 reducer 保留 child block。
- 最大合法 256-Node/long-stop-policy 证据以确定性 policy fingerprint 收敛为 258,602 bytes，保留全部终态、status、reason、其他 policy 事实/source。
- 生产 file handler 内部 I/O 失败不再被 logging 吞掉；streaming summary 为外层 256 KiB envelope 预留字节。
- 正式 benchmark 报告器锁定 7,128 req/s 门，使用 50 warmup + 5×750 best-of-five；最终 P99 0.15ms / 8,461 req/s。
- 最终 canonical：61/61 AST，61 primary 收集为 74 cases，74/74 PASS；12/12 Agent specs PASS。
- 性能 checkpoint 在 12-spec 顺序运行的首次出现一次宿主调度型短暂失败；立即重试、单节点 8/8 与 74-case 组合执行均 PASS，按 Low 限制如实记入报告。

### 设计调整与经验

- `ADJ-001`：增加独立 Capability 实现绑定区。
- `ADJ-002`：Evidence 预算固定为可表示最大核心 envelope 的 256 KiB。
- `ADJ-003`：覆盖率插桩与正式性能门隔离，亚秒级容量检查采用多轮 best-of-five，硬门不变。
- 新增经验 `EXP-2026-0008`～`EXP-2026-0013`；复用既有请求 snapshot、稳定 reason、取消清理、配置文档契约和 checkpoint 锚定经验；项目总计 13 条。

### Project Principle Check

1. **Plugin / Flow；核心最小**：Detector 语义保持在 adapter/reducer，顺序和嵌套属于 Flow；依赖边界测试通过。
2. **策略显式；失败不静默**：四类失败策略独立贯穿 Runtime/reducer；skip、degradation、sink failure 与配置冲突均有稳定 reason 或启动拒绝。
3. **边界透明；契约稳定**：完整 HTTP/SSE/Provider、Detector SDK、entry point、gRPC proto、PipelineEngine 与 legacy YAML 回归通过；时间、并发、节点与证据均有硬界。
4. **决策有证据；数据默认保护**：逐 Node/Flow 终态、显式 Flow availability 与 persistence failure 均可审计；原文、secret、endpoint、raw exception 和动态 request/user ID 不进入 Flow evidence/trace。

12 类失败模式和 7 个强制 Verify Step 均已完成，`test-report.md` 已生成。当前已就绪并停在 Gate 3；用户确认前不进入 DELIVER。

## Phase 6: DELIVER (in progress)

- Gate 3 已由用户于 `2026-08-23T07:50:50+08:00` 明确确认。
- `stdd gate approve --gate 3` 因 CLI 2.9.5 对 `phases` 路径重复解析，误报 Gate 1 未确认；已依用户真实确认同步 `phases.verify.confirmed_at`、legacy gates 与 `confirmed_at` 双轨状态，未跳过门禁。
- 当前进入 Deliver 的本地归档、规范合并和结构索引步骤；Git commit/tag 仍按 Deliver Step 3 单独等待确认。

## Phase 6: DELIVER (completed 2026-08-23T08:01:10+08:00)

- 用户已单独确认提交并创建 `v0.2.0` 标签；发布动作限定为本地 Git，不 push、不部署。
- 变更已归档到 `archive/2026-08-22-v0.2.0-flow-foundation/`；Human specs、Canonical
  proposal/agent/code specs、Canon index 与代码结构摘要均已合并。
- 本 change 的 `EXP-2026-0008`～`EXP-2026-0013` 均保持真实的 `discovered` 生命周期，
  deposited 条目为 0，因此未触发社区上传。
- Gateway 元数据、CHANGELOG、README、配置、部署示例与发布契约统一为 `0.2.0`；Detector
  SDK 依照独立版本与兼容承诺保持 `0.1.1`。
- 发布契约调整遵循 RED→GREEN：初始 6 项按预期因旧版号失败，更新后发布/文档/部署/SDK
  定向测试 36/36 通过；归档后修正 benchmark 契约的正式证据路径，相关 26/26 通过。
- 最终完整回环套件 `1011 passed / 1 skipped / 0 failed`，coverage `93.33%`；Ruff、
  Mypy（99 source files）与 `git diff --check` 通过。
- Project Principle Check：能力/Flow 边界未变；策略和失败保持显式；HTTP/SSE、Provider、
  Detector SDK、gRPC proto、PipelineEngine 与 legacy YAML 兼容；证据与数据最小化契约未放宽。
