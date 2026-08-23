# v0.2.0 Flow Foundation 测试方案与详细案例

> 版本：v0.2.0
> 创建日期：2026-08-22
> 对应 Phase 2 Spec：12 个 Capability canonical specs
> 总计：61 TC（P0=54 / P1=6 / P2=1；high=46 / medium=15 / low=0）

## 一、测试策略

### 1.1 测试金字塔

- **单元测试（约 70%）**：契约/Pydantic、版本与图验证、policy resolution、Runtime 调度/取消、reducer、adapter、evidence sanitizer/budget、metrics/tracing helper。
- **集成测试（约 25%）**：app initialization、request Flow snapshot、input/output/async/stream/buffer/post-audit、readiness/admission、audit sink。
- **契约与性能（约 5%）**：HTTP/SSE、Detector SDK/entry point/gRPC proto、旧 YAML corpus、PipelineEngine facade、benchmark 和 task leak。

### 1.2 测试原则

- 严格 RED → GREEN → REFACTOR；每个 TC 先出现可观察失败。
- P0 失败、Provider 在 fail-closed admission 下被调用、原文泄露、证据静默丢失或任务泄漏时不得进入下一 slice。
- 并发测试使用 deterministic barriers/events，不依赖不稳定 sleep。
- 同一行为同时验证结果与证据；不能只断言 action。
- 配置错误必须在 Provider/Capability 初始化或业务监听之前失败。
- Agent checkpoint 使用精确 pytest node；Gate 3 用 AST 与 collect 验证节点真实存在，禁止空 glob。
- 兼容测试以 Phase 4 入口的 899 passed / 1 skipped 基线与归档 specs 为锚点，不通过修改旧预期掩盖漂移。

### 1.3 已有测试资产

| 测试文件/区域 | 类型 | 复用范围 |
|---|---|---|
| `tests/unit/pipeline/test_engine.py`、`test_aggregator.py`、`test_flag_escalation.py` | 单元 | 并行、短路、动作/风险/修改聚合 |
| `tests/unit/config/test_v2_models.py`、`test_validators.py`、`test_detector_required.py` | 单元 | legacy YAML、策略和 required 校验 |
| `tests/integration/test_chat.py`、`test_pipeline_flow.py` | 集成 | HTTP、Provider 边界与 input/output |
| `tests/integration/test_streaming.py` | 集成 | sliding window、buffer、async、post-audit、SSE |
| `tests/unit/routes/test_detector_readiness.py`、`test_availability_guard.py` | 单元/集成 | request admission、snapshot 基线 |
| `tests/unit/audit/` | 单元 | 内容保护、availability、write failure |
| `tests/unit/observability/` | 单元 | metrics、tracing、低基数/disabled |
| `tests/unit/detectors/`、`tests/unit/plugins/`、SDK/示例测试 | 契约 | Detector SDK、entry point、gRPC lifecycle |
| `tests/benchmarks/bench_pipeline.py`、2026-08-21 report | 性能 | P99 0.16ms、7,920 req/s 基线 |

## 二、详细测试案例

| ID | 对应 Spec | 优先级 | 预置条件（Arrange） | 输入（Act） | 预期结果（Assert） | 当前状态 |
|---|---|---:|---|---|---|---|
| TC-AUD-701 | audit-logger / SC-AUD-701 | P0 | 一次 input 或 output Flow 完成 | 构造 AuditEntry | 审计 SHALL 增加 flow_id、flow_version、flow_execution_id、flow_status 和 node_evidence；现有 request/detector/final_action 字段 SHALL 保持；node_evidence 顺序 SHALL 确定；schema 扩展 SHALL 为加法兼容 | ✅ PASS |
| TC-AUD-702 | audit-logger / SC-AUD-702 | P0 | Flow 出现 fail_open、fail_closed、stop、timeout、skip 或 cancellation | 审计结果 | 审计 SHALL 记录实际策略、稳定 reason、degraded 与 evidence_persisted 状态；fail-open allow SHALL NOT 伪装成完整安全执行；fail-closed admission SHALL 在 Provider 前留下证据；cancelled Node SHALL 可与未配置 Node 区分 | ✅ PASS |
| TC-AUD-703 | audit-logger / SC-AUD-703 | P0 | audit.store_content 分别为 false/true，输入含秘密、PII、modified_content 与恶意 exception | 写 JSONL/stdout 审计 | node_evidence SHALL 始终不含原文、修改后内容、密钥、endpoint 或原始异常；store_content=false SHALL 维持无 plaintext；store_content=true SHALL 仅在既有 content 字段按 sanitizer 存储；reason_code SHALL 为稳定枚举 | ✅ PASS |
| TC-AUD-704 | audit-logger / SC-AUD-704 | P1 | 长 streaming response 产生多个 window FlowEvidence | StreamingEvidenceAccumulator 写最终审计 | 审计 SHALL 按 flow/node/action/reason 有界聚合并记录执行计数与触发窗口；默认 SHALL NOT 展开全部 allow window；post_audit SHALL 单独保存完整摘要；聚合大小 SHALL 受 256KB 总证据预算约束 | ✅ PASS |
| TC-AUD-705 | audit-logger / SC-AUD-705 | P1 | file/stdout evidence sink 抛出异常 | AuditLogger.record 被调用 | 业务安全结果 SHALL 不变且持久化失败 SHALL 显式可观测；FlowEvidence SHALL 标记 evidence_persisted=false；warning SHALL 使用稳定 error_type；Prometheus failure counter SHALL 增加；AuditLogger SHALL NOT 抛出原始 sink exception | ✅ PASS |
| TC-CFG-001 | config-system / SC-CFG-001 | P0 | gateway YAML 含 flow_runtime、flows、pipeline.input_flow/output_flow | load_config 解析配置 | 配置 SHALL 生成严格类型的 FlowRuntimeConfig、FlowDefinition 和 NodeDefinition；stage ref SHALL 精确解析已定义 Flow ID；Node kind SHALL 使用 discriminated union；所有缺省策略 SHALL 在规范化结果中显式存在 | ✅ PASS |
| TC-CFG-002 | config-system / SC-CFG-002 | P0 | 原始 YAML 同时显式包含 flows 与 pipeline.detectors | 配置加载器检查原始键存在性 | 启动 SHALL 失败并报告 conflicting_flow_sources；Pydantic 默认空 detectors SHALL NOT 误报冲突；系统 SHALL NOT 选择静默优先级 | ✅ PASS |
| TC-CFG-003 | config-system / SC-CFG-003 | P0 | v0.1.x/v0.2-style flat或input/output detector YAML 且无 flows | load_config 完成 | 配置 SHALL 继续加载并进入 LegacyDetectorFlowCompiler；legacy threshold 正规化 SHALL 保持；required/on_error/circuit breaker SHALL 保持；不要求新增 flow_runtime 字段 | ✅ PASS |
| TC-CFG-004 | config-system / SC-CFG-004 | P0 | 旧配置省略 timeout、required、priority、on_error 和 short_circuit_on | 编译 resolved Flow | resolved policy SHALL 分别使用现有默认值并标记 source=legacy_default；Detector timeout SHALL 继承 security.timeout.detector；output sync deadline SHALL 继承 sync_timeout；默认 short circuit SHALL 仅匹配 block | ✅ PASS |
| TC-CFG-005 | config-system / SC-CFG-005 | P0 | 配置含未知 ref、重复 ID、循环、超限、版本不兼容、schema 不匹配或 policy conflict | validate_config 执行图与策略验证 | 网关 SHALL 在创建 Provider 或接受流量前拒绝配置；错误 SHALL 使用稳定 code 与 Flow/Node 定位；配置异常 SHALL NOT 包含 secret values；所有错误顺序 SHALL 确定 | ✅ PASS |
| TC-CFG-006 | config-system / SC-CFG-006 | P0 | README、DESIGN 和 configuration 文档中的 legacy/new Flow YAML 示例 | 文档契约测试提取并调用 load_config/Pydantic | 每个示例 SHALL 成功解析为预期结构或作为明确 invalid 示例失败；关键策略字段 SHALL 出现在正确层级；未知安全字段 SHALL NOT 被静默忽略；示例 SHALL NOT 需要真实密钥 | ✅ PASS |
| TC-DDF-001 | default-detector-flow / SC-DDF-001 | P0 | 现有 pipeline.detectors input/output、threshold、priority、required、on_error、timeout、circuit breaker、short_circuit 和 flag escalation 配置 | LegacyDetectorFlowCompiler 在启动时运行 | 编译器 SHALL 生成等价 legacy-input-detector-flow 与 legacy-output-detector-flow；每个 detector SHALL 对应唯一 Node；所有旧策略 SHALL 映射为显式 resolved policy；旧配置文件 SHALL 无需修改；编译结果 SHALL NOT 持久化秘密 | ✅ PASS |
| TC-DDF-002 | default-detector-flow / SC-DDF-002 | P0 | 同一旧 YAML 被重复加载 | 规范化为默认 Flow | 两次 resolved Flow 结构、Node 顺序、策略和 reducer 配置 SHALL 相同；结果 SHALL 不依赖 dict 哈希或任务完成顺序；诊断指纹 SHALL 排除密钥和原始内容 | ✅ PASS |
| TC-DDF-003 | default-detector-flow / SC-DDF-003 | P0 | Detector 结果包含 allow、flag、modify、block、不同 risk 和 priority | detector-result-reducer 聚合 Flow 结果 | final action SHALL 保持 block>modify>flag>allow，risk SHALL 取最高，modification SHALL 按 priority/配置顺序排列；flag escalation SHALL 保持既有 DSL 行为；空结果 SHALL 为 allow/low；触发结果 SHALL 保留 detector identity | ✅ PASS |
| TC-DDF-004 | default-detector-flow / SC-DDF-004 | P0 | short_circuit_on 分别为 block 或 block_and_modify | Detector Node 发出 block 或 modify signal | stop signals SHALL 精确复现既有短路矩阵；block 模式 SHALL 仅因 block 停止；block_and_modify SHALL 因 block 或 modify 停止；pending 调用 SHALL 取消并产证 | ✅ PASS |
| TC-DDF-005 | default-detector-flow / SC-DDF-005 | P0 | 一次请求包含 input、sync/async output、sliding window、buffer 或 post-audit 阶段，且存在 fail-open unavailable Detector | 请求入口创建 snapshot 并进入各阶段 | 全部阶段 SHALL 使用同一 Flow/Capability 可用性快照；unavailable Detector SHALL 在所有阶段保持跳过；async background SHALL 持有 snapshot 副本；不得通过全局 runner 重新引入 Detector；每次跳过 SHALL 有 NodeEvidence | ✅ PASS |
| TC-DDF-006 | default-detector-flow / SC-DDF-006 | P0 | 现有 HTTP、SSE、Provider 与 safety header 回归样例 | 内部 detector pipeline 改由默认 Flow 执行 | 公开状态码、body、header、SSE event 顺序和 Provider 透传 SHALL 与基线一致；fail-closed output unavailable 时 Provider SHALL NOT 被调用；stream buffer replay SHALL 保持原 chunk；async output SHALL 继续立即返回 | ✅ PASS |
| TC-DDF-007 | default-detector-flow / SC-DDF-007 | P0 | 通用 FlowRuntime 与注册的 detector-result-reducer | 执行默认 Detector Flow | Runtime SHALL 仅通过 reducer contract 聚合结果且 SHALL NOT 包含 detector action precedence 分支；reducer descriptor SHALL 带版本；reducer failure SHALL 按 Flow failure policy 处理；依赖边界测试 SHALL 阻止 flow core 导入 detector 模块 | ✅ PASS |
| TC-DSV-701 | degraded-safety-visibility / SC-DSV-701 | P0 | optional fail_open Capability 在请求入口 unavailable/unhealthy | 请求经过 input、provider、sync/async/streaming/post-audit 阶段 | 请求 SHALL 继续且该 Capability SHALL 在所有适用阶段保持 skipped+degraded；每个跳过 SHALL 有 NodeEvidence；request audit SHALL 标记 safety_degraded；metrics SHALL 每请求/节点确定计数；后续恢复 SHALL 不改变当前 snapshot | ✅ PASS |
| TC-DSV-702 | degraded-safety-visibility / SC-DSV-702 | P0 | required 或 fail_closed Capability 在 input/output Flow snapshot 中不可用 | 聊天请求通过 Flow admission | 网关 SHALL 在任何 Provider 调用前返回既有 503 safety_unavailable；admission SHALL 生成对应 Flow/Node evidence；affected direction 与 detector 排序 SHALL 确定；HTTP body/header SHALL 保持兼容 | ✅ PASS |
| TC-DSV-703 | degraded-safety-visibility / SC-DSV-703 | P0 | 节点因 unavailable、unhealthy、circuit_open、timeout、capability_error 或 sink_error 降级 | API、日志、审计、metric 与 trace 发出信号 | 每条信号 SHALL 使用稳定 bounded reason_code 并关联 effective policy；原始异常和 endpoint SHALL NOT 外泄；不同原因 SHALL NOT 全部折叠为 generic error；任何 skip SHALL NOT 无 degraded 标记 | ✅ PASS |
| TC-DCA-001 | detector-capability-adapter / SC-DCA-001 | P0 | built-in、ML、in-process plugin 或 gRPC Detector 已加载 | DetectorCapabilityAdapter 创建 descriptor | descriptor SHALL 包含稳定 Capability ID、contract_version=1.0、Detector name/category/version 和输入输出 schema；四类 Detector SHALL 使用同一 descriptor schema；Detector version SHALL 作为实际实现版本记录；adapter SHALL NOT 修改 Detector 类属性 | ✅ PASS |
| TC-DCA-002 | detector-capability-adapter / SC-DCA-002 | P0 | 有序 Flow item 与 request snapshot context | adapter 调用 Detector.detect | adapter SHALL 构造兼容 DetectionContext 并传入对应 content；direction、request_id、user_id、language、message_index SHALL 保留；DetectorResult SHALL 映射为 CapabilityResult；allow/block/flag/modify SHALL 映射为稳定 signals；modified_content SHALL 仅保留在内存输出 | ✅ PASS |
| TC-DCA-003 | detector-capability-adapter / SC-DCA-003 | P0 | 现有 Detector SDK 0.1.x 插件与导入语句 | 插件在 Flow Runtime 下安装、初始化并执行 | Detector、DetectionContext、DetectionResult、Modification 的公开导入和签名 SHALL 保持兼容；现有示例插件 SHALL 无源码修改通过；SDK lifecycle SHALL 保持 initialize→detect→shutdown；不得要求插件实现新的 Capability 类 | ✅ PASS |
| TC-DCA-004 | detector-capability-adapter / SC-DCA-004 | P0 | Detector 生命周期协调器已创建健康、unavailable 和 unhealthy 状态 | Capability registry 注册 adapter 并执行 lifecycle | 每个 Detector SHALL 只初始化和关闭一次，health/status SHALL 使用既有协调器；unavailable Detector SHALL NOT 由 sentinel 替代；相同 Detector 的 Node SHALL 共享请求快照状态；fatal startup cleanup SHALL 保持逆序有界 | ✅ PASS |
| TC-DCA-005 | detector-capability-adapter / SC-DCA-005 | P0 | Detector 抛出普通异常或 CancelledError | adapter 执行 detect | 普通异常 SHALL 交给 Runtime policy 且外部只见稳定 reason，CancelledError SHALL 原样传播；原始异常可在边界内用于控制流但 SHALL NOT 进入证据；adapter SHALL NOT 把取消转换为 fail_open；gRPC 本地 channel SHALL 在 finally 有界关闭 | ✅ PASS |
| TC-DF-701 | detector-framework / SC-DF-701 | P0 | built-in、ML、in-process plugin 和 gRPC sidecar 配置 | 应用初始化 Capability registry 与默认 Flow | 四类 Detector SHALL 经同一 adapter/lifecycle/status 路径注册；initialize SHALL 在首次 invoke 前且仅一次；health 与 shutdown SHALL 委托现有 Detector 合约；初始化失败 SHALL 保持 required/on_error 矩阵 | ✅ PASS |
| TC-DF-702 | detector-framework / SC-DF-702 | P0 | 同一请求的 Detector 在 snapshot 中 healthy、unavailable 或 unhealthy | 多个 Flow 阶段解析对应 Capability | 所有阶段 SHALL 使用 snapshot 中同一状态并保持 app 隔离；unavailable SHALL 不调用 detect；恢复 SHALL 只影响后续请求 snapshot；同名 input/output 实例 SHALL 保持方向身份 | ✅ PASS |
| TC-DF-703 | detector-framework / SC-DF-703 | P0 | SDK 0.1.x 包、entry point 插件和 gRPC DetectorService v1 | 在 Flow Foundation 版本运行现有 SDK、示例与插件测试 | 全部公开接口与发现协议 SHALL 无破坏性变化；entry point group SHALL 不变；gRPC proto SHALL 不变；现有插件 SHALL NOT 依赖 gateway flow 包 | ✅ PASS |
| TC-FC-001 | flow-contracts / SC-FC-001 | P0 | contract_version=1.0 的 Flow、Node 和 Capability descriptor | 配置加载并构建运行时契约 | 三个契约 SHALL 被接受并保留各自 ID、契约版本和实现版本；Flow version SHALL 为有效 SemVer；Capability 实现版本 SHALL 作为非空字符串进入证据 | ✅ PASS |
| TC-FC-002 | flow-contracts / SC-FC-002 | P0 | 未知 major、未实现的更新 minor 或不受支持的契约版本 | 启动时验证契约 | 网关 SHALL 拒绝启动并返回稳定的 incompatible_contract_version 诊断；运行时 SHALL NOT 静默降级或忽略版本；错误 SHALL 指出对象类型和 ID 但不含敏感配置 | ✅ PASS |
| TC-FC-003 | flow-contracts / SC-FC-003 | P0 | 新 Flow 配置含未知字段、重复 ID、超长 ID 或非法 SemVer | Pydantic 和交叉验证运行 | 配置 SHALL 在启动阶段被拒绝；新 Flow 模型 SHALL 使用 extra=forbid；Flow 内 Node ID SHALL 唯一；标识符长度 SHALL 不超过 128 字符 | ✅ PASS |
| TC-FC-004 | flow-contracts / SC-FC-004 | P0 | kind=capability 且目标 descriptor 已注册的 Node | Flow validator 解析 Node | Node SHALL 解析为 CapabilityNode 并精确绑定目标 Capability；输入/输出 schema 不兼容时 SHALL 拒绝；解析结果 SHALL 保留 Node 优先级和完整策略 | ✅ PASS |
| TC-FC-005 | flow-contracts / SC-FC-005 | P0 | kind=flow 且引用确定 ID/version 的子 Flow Node | Flow 图在启动时展开 | Node SHALL 解析为 NestedFlowNode 并使用与 CapabilityNode 相同的生命周期和证据外壳；缺失或版本不匹配的子 Flow SHALL 被拒绝；循环引用或深度超过 8 SHALL 被拒绝 | ✅ PASS |
| TC-FC-006 | flow-contracts / SC-FC-006 | P1 | 包含多个 content item、request_id、direction、stage 和 metadata 的 FlowInput | 父 Flow、Capability Node 与嵌套 Flow 接收输入 | 所有执行层 SHALL 使用同一版本化 envelope 且保持 item 顺序；请求上下文 SHALL 对节点只读；子 Flow SHALL 继承 correlation 与 parent_execution_id；敏感 payload SHALL NOT 进入证据 envelope | ✅ PASS |
| TC-FP-001 | flow-policy / SC-FP-001 | P0 | 新 Flow 或旧 detector YAML 省略部分策略字段 | 配置规范化完成 | 每个 Node SHALL 具有显式 timeout、failure、degradation、stop 与 availability 策略；默认来源 SHALL 可追踪为 explicit、legacy 或 default；执行期 SHALL NOT 再猜测缺失默认值；策略快照 SHALL 进入 NodeEvidence | ✅ PASS |
| TC-FP-002 | flow-policy / SC-FP-002 | P0 | Capability 抛出普通异常且 failure.action 分别为 fail_open/fail_closed | Runtime 捕获异常 | 目标 adapter SHALL 生成对应 fail-open 或 fail-closed fallback 结果；fail_open SHALL 标记 degraded 并继续；fail_closed SHALL 发出停止所需 signal；原始异常 SHALL NOT 进入外部证据 | ✅ PASS |
| TC-FP-003 | flow-policy / SC-FP-003 | P0 | Capability 超过 Node timeout 且 timeout.action 已配置 | Node deadline 到期 | Runtime SHALL 取消调用并应用 timeout.action；timeout SHALL 与普通 exception 使用不同 reason code；on_timeout SHALL NOT 被 on_error 静默替代；实际等待时长 SHALL 进入证据 | ✅ PASS |
| TC-FP-004 | flow-policy / SC-FP-004 | P0 | Capability 在 request snapshot 中 unavailable 或 circuit open | Runtime 解析 Node | Runtime SHALL 分别应用 on_unavailable 或 on_circuit_open；Capability SHALL NOT 被调用；fail_open SHALL 产生 skipped+degraded 证据；fail_closed SHALL 在 Provider 前阻断适用请求；circuit fallback SHALL 保留现有配置语义 | ✅ PASS |
| TC-FP-005 | flow-policy / SC-FP-005 | P0 | Flow deadline 到期时部分 Node 已完成、部分 pending | Runtime 收敛 Flow | 已完成结果 SHALL 保留，pending Node SHALL 分别按自身 on_timeout 生成结果；父 deadline SHALL 覆盖更晚的子 deadline；最终 reducer SHALL 在全部 timeout fallback 收敛后执行；FlowEvidence SHALL 标记 timed_out | ✅ PASS |
| TC-FP-006 | flow-policy / SC-FP-006 | P0 | required=true 配合 fail_open、非正 timeout、未知 action、空 stop signals 或互相矛盾策略 | 启动验证策略 | 配置 SHALL 被拒绝并给出稳定 policy_conflict 诊断；错误 SHALL 定位 Flow 和 Node ID；运行时 SHALL NOT 修正或忽略矛盾配置 | ✅ PASS |
| TC-FR-001 | flow-runtime / SC-FR-001 | P0 | 多个 Node 与多个有序 item，max_concurrency=64 | FlowRuntime.execute 被调用 | Runtime SHALL 在不超过 64 个并发调用的前提下并行执行 Node/item；结果 SHALL 按 Node 配置顺序再按 item 顺序排列；实际完成顺序 SHALL NOT 改变聚合输入；Runtime SHALL 延迟创建调用而非一次创建无界 Task | ✅ PASS |
| TC-FR-002 | flow-runtime / SC-FR-002 | P1 | Flow 没有 Node 或 FlowInput 没有 item | Runtime 执行 Flow | Flow SHALL 确定性完成且不调用 Capability；结果 reducer SHALL 收到空结果集合；FlowEvidence SHALL 记录 completed 而非静默跳过 | ✅ PASS |
| TC-FR-003 | flow-runtime / SC-FR-003 | P0 | 并行 Node 中一个结果发出 stop policy 匹配的 signal | Runtime 观察到该结果 | Runtime SHALL 立即停止 Flow 并取消全部 pending 调用；已完成结果 SHALL 被保留；每个 pending Node SHALL 产生 cancelled 或 partial 证据；Runtime SHALL NOT 等待被取消调用正常完成；最终 reducer SHALL 收到停止触发结果 | ✅ PASS |
| TC-FR-004 | flow-runtime / SC-FR-004 | P0 | 父 Flow 包含一个合法的 NestedFlowNode | 父 Flow 执行该 Node | 子 Flow SHALL 在相同 request snapshot 下执行并返回版本化结果；子 Flow timeout SHALL 受父 deadline 上界约束；父 NodeEvidence SHALL 引用 child execution；子证据 SHALL 保留 parent_execution_id；子 Flow 的 stop SHALL 先收敛为子结果再由父策略处理 | ✅ PASS |
| TC-FR-005 | flow-runtime / SC-FR-005 | P0 | 外层请求取消正在执行的 Flow，Capability 持有本地资源 | Runtime 收到 asyncio.CancelledError | Runtime SHALL 在 finally 中执行有界清理后重新抛出 CancelledError；Runtime SHALL NOT 合成 allow 或 block；所有子任务 SHALL 被取消并 await；清理异常 SHALL 记录稳定 reason code 而不吞掉取消 | ✅ PASS |
| TC-FR-006 | flow-runtime / SC-FR-006 | P0 | Flow 超过 depth=8、expanded_nodes=256、timeout=120s 上界或执行达到 deadline | 配置验证或运行时限制触发 | 静态超限 SHALL 启动失败，动态 deadline SHALL 有界取消 pending 调用；max_concurrency SHALL 固定限制同时运行调用；已完成 Node 结果 SHALL 保留；pending Node SHALL 按其 on_timeout 策略收敛；限制原因 SHALL 进入 FlowEvidence | ✅ PASS |
| TC-NEC-001 | node-evidence-chain / SC-NEC-001 | P0 | 任意 Node 执行并产生安全结果 | Runtime 完成或中止 Flow | NodeEvidence SHALL 包含 Flow/Node/Capability 身份与版本、策略、状态、reason、耗时和结果摘要；FlowEvidence SHALL 包含 execution_id、stage、终态和 final signal；核心字段 SHALL 不依赖插件任意 details | ✅ PASS |
| TC-NEC-002 | node-evidence-chain / SC-NEC-002 | P0 | 并发 Node 和嵌套 Flow 以非确定顺序完成 | 证据链被序列化 | 证据 SHALL 按定义顺序确定输出；子 Flow 证据 SHALL 引用 parent_execution_id；相同输入与配置 SHALL 产生相同结构顺序 | ✅ PASS |
| TC-NEC-003 | node-evidence-chain / SC-NEC-003 | P0 | Node 分别成功、异常、超时、跳过、取消，或部分 item 完成后取消 | 构建 NodeEvidence | status SHALL 分别为 succeeded、failed、timed_out、skipped、cancelled 或 partial；degraded SHALL 为独立布尔语义；每个非成功状态 SHALL 有稳定 reason_code；调用总数和各终态计数 SHALL 可核对 | ✅ PASS |
| TC-NEC-004 | node-evidence-chain / SC-NEC-004 | P0 | 内容、modified_content、Detector details/message、密钥、endpoint 和含秘密异常 | 生成并持久化证据 | 外部证据 SHALL NOT 包含任何上述原值；异常 SHALL 映射为稳定 reason_code；内容仅允许现有 content_hash/length 独立字段；指标与 span SHALL NOT 包含原始动态文本 | ✅ PASS |
| TC-NEC-005 | node-evidence-chain / SC-NEC-005 | P0 | 可选 evidence_summary 或 signals 超过字段/总量限制 | 证据收集器施加 256KB 上界 | 核心 NodeEvidence SHALL 被保留，可选摘要 SHALL 被有信号地截断或拒绝；details_truncated SHALL 为 true；evidence_rejected reason SHALL 可观测；Runtime SHALL NOT 静默删除整个 NodeEvidence | ✅ PASS |
| TC-NEC-006 | node-evidence-chain / SC-NEC-006 | P0 | 滑动窗口产生多次 output Flow 执行 | 运行时产证并由审计层持久化 | 每次执行 SHALL 先产生 NodeEvidence，默认审计 SHALL 按稳定维度有界聚合；聚合 SHALL 保留计数、滚动摘要和触发窗口索引；post-audit SHALL 作为独立完整 FlowEvidence；聚合 SHALL NOT 改变 SSE 行为 | ✅ PASS |
| TC-NEC-007 | node-evidence-chain / SC-NEC-007 | P0 | Flow 决策完成但 evidence sink 写入失败 | 持久化证据 | 安全决定 SHALL 保持不变且 FlowEvidence SHALL 标记 evidence_persisted=false；系统 SHALL 记录稳定 warning 和 metric；失败 SHALL NOT 被报告为持久化成功；内存中的核心证据 SHALL 仍返回调用方 | ✅ PASS |
| TC-OBS-701 | observability / SC-OBS-701 | P0 | metrics enabled 且 Flow/Node 分别成功、失败、超时、取消或降级 | 记录执行并抓取 /metrics | flow execution/duration 与 node execution 指标 SHALL 使用 flow_id、direction、node_id、status、reason_code 的稳定标签；指标 SHALL 反映实际计数；Capability version SHALL NOT 用作 metric label；node_id 基数 SHALL 受 max_nodes 限制 | ✅ PASS |
| TC-OBS-702 | observability / SC-OBS-702 | P2 | observability.metrics.enabled=false | 执行所有 Flow metric helper | helper SHALL 为 no-op 且 SHALL NOT 改变 Flow 决策、证据或抛出异常；不得注册重复 collector；禁用模式 SHALL 不创建高成本 label 数据 | ✅ PASS |
| TC-OBS-703 | observability / SC-OBS-703 | P1 | tracing enabled 且父 Flow 含 Capability 与 NestedFlowNode，部分 Node 被取消 | 执行请求并导出 spans | trace SHALL 形成 request→flow→node→nested-flow 层级并标记真实终态；span SHALL 包含 Flow/Node/Capability identity 与 version；cancelled/timeout SHALL 设稳定 status/reason；span SHALL NOT 包含 payload、异常正文或 user_id | ✅ PASS |
| TC-OBS-704 | observability / SC-OBS-704 | P0 | 恶意 ID、动态异常、请求 ID、用户 ID、endpoint 和大 evidence summary | 日志、metric 和 span 属性生成 | 可观测边界 SHALL 拒绝或清理超长/敏感动态值；metric labels SHALL 仅来自验证后的配置 ID 与枚举；request/user IDs SHALL NOT 进入 metrics；日志与 spans SHALL 使用稳定 reason_code；超限 SHALL 有 observable sanitization signal | ✅ PASS |
| TC-PE-001 | pipeline-engine / SC-PE-001 | P0 | 现有调用方使用 PipelineEngine constructor、run(detectors, contexts, configs) 和 PipelineResult | 升级到 v0.2.0 | 公开 Python 签名和 PipelineResult 字段 SHALL 保持可用且语义不变；short_circuit_on 与 flag_escalation 参数 SHALL 继续生效；无 detector/context SHALL 保持 allow；现有 pipeline 单元测试 SHALL 无行为改写通过 | ✅ PASS |
| TC-PE-002 | pipeline-engine / SC-PE-002 | P0 | PipelineEngine facade 收到一次 run 调用 | facade 构建或取得默认 Flow runner | 每个 Detector/context 对 SHALL 仅执行一次并由 FlowRuntime 产生结果；facade SHALL NOT 再运行第二套 asyncio 调度；pipeline_duration_ms SHALL 覆盖 Flow 聚合完成；错误和 timeout SHALL 仅由 resolved policy 处理一次 | ✅ PASS |
| TC-PE-003 | pipeline-engine / SC-PE-003 | P1 | 标准 rule-based benchmark 基线 P99=0.16ms、throughput=7920 req/s | 运行同环境 Flow 版本 benchmark 与任务泄漏检查 | P99 SHALL 低于 200ms 且 throughput SHALL 不低于基线的 90%；测试结束 pending Flow tasks SHALL 为 0；差异 SHALL 写入 benchmark report；禁用 observability 时 SHALL 无 exporter 开销 | ✅ PASS |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 集成测试 | 契约/E2E | 状态 |
|---|---|---|---|---|
| Flow/Node/Capability contracts | 版本、schema、ID、图验证 | startup validation | YAML 文档样例 | ✅ PASS |
| Runtime / nesting / stop / cancel | deterministic scheduler、limits | request cancellation | task leak | ✅ PASS |
| Policy resolution | 完整失败矩阵 | readiness/admission | legacy policy parity | ✅ PASS |
| Evidence | model、sanitizer、budget | audit/stream aggregate | malicious plugin/content | ✅ PASS |
| Detector adapter / framework | mapping、lifecycle | 四类 Detector | SDK/entry point/gRPC | ✅ PASS |
| Default Flow / Pipeline facade | reducer、compat facade | 六条执行路径 | HTTP/SSE/Provider | ✅ PASS |
| Configuration | strict new schema、legacy compiler | create_app | docs contract | ✅ PASS |
| Audit / degradation | schema、sink failure | fail-open/fail-closed | JSONL/stdout privacy | ✅ PASS |
| Observability | helpers、labels、spans | app-enabled/disabled | exporter capture | ✅ PASS |
| Performance | scheduler microbench | pipeline benchmark | P99/throughput/leak | ✅ PASS |

## 四、回归风险矩阵

| 风险区域 | v0.2.0 改动 | 已有回归保护 | 风险等级 |
|---|---|---|---|
| HTTP/Provider request path | route 改用 Flow snapshot/runner | chat、block、models、error handling | 🔴 高 |
| Streaming/async/post-audit | runner 与 evidence 贯穿 | integration streaming suite | 🔴 高 |
| fail-open/fail-closed admission | policy 来源改为 Flow | readiness/availability/audit tests | 🔴 高 |
| Pipeline aggregation/short-circuit | reducer + facade | pipeline unit suite | 🔴 高 |
| Detector lifecycle/plugins | Capability adapter | detector/plugin/gRPC tests | 🔴 高 |
| Config backward compatibility | legacy compiler + new schema | config corpus/validators | 🔴 高 |
| Audit/privacy | add Flow evidence | audit sanitizer/logger tests | 🔴 高 |
| Metrics/tracing | 新 Flow signals | observability unit suite | 🟡 中 |
| Performance/resources | semaphore/limits/evidence | benchmark report | 🟡 中 |
| Provider adapters本身 | 无设计修改 | provider unit/integration tests | 🟢 低 |

## 五、建议补充顺序

1. **P0（54）**：contracts → policy/config → runtime/cancel → adapter/lifecycle → reducer/default Flow → admission/HTTP/SSE → evidence/privacy。
2. **P1（6）**：空 Flow、immutable envelope、性能、streaming aggregate、sink failure、nested trace。
3. **P2（1）**：observability disabled no-op。
4. 每个 slice 必须完成目标 TC、相关回归、Ruff、Mypy；Phase 5 执行全量测试、覆盖率、benchmark、12 类失败模式和精确 checkpoint collect。
