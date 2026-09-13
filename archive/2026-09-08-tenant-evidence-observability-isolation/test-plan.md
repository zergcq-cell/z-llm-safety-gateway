# v0.3.0 第三项测试方案与详细案例

> Gate 2 review draft。对应五份 specs/*/spec.md；测试均为计划，尚未实现或执行。

## 一、测试策略

### 1.1 测试金字塔
单元验证契约、配置、投影和计数；集成通过真实 ASGI + HTTPX mock Provider、内存日志/OTel exporter 和 Prometheus scrape 验证生产接线。每个 Scenario 一个主 TC，共 26 个；参数化后实际 pytest case 数可能更多。不依赖真实外部 Provider 或遥测服务器。

### 1.2 测试原则
- 每个切片先记录 RED，再最小 GREEN，最后重构与切片验证。
- 并发使用 asyncio.Event/Barrier 实际交错，不靠 sleep 猜顺序；至少两个租户共享 policy、另一个使用不同 policy。
- 用不应出现的密钥/原文金丝雀检查最终序列化输出，不能只检查 mock 调用。
- 运行真实 sync/async/buffer/sliding/post-audit 请求；覆盖合并事件与分裂 SSE 边界、断连、取消和后台延后完成。
- 测试接口默认值、配置禁用/启用组合、任意客户端字段、missing context、sink 失败、两个 app 同时运行。
- 结构操作计数和 label tuple/sample 数为资源断言；性能测量与覆盖率插桩分离。
- 所有 planned checkpoint 节点必须在 Build 后 collect-only 验证存在；不允许空集合或用别的测试冒充。

### 1.3 已有测试资产

| 测试路径 | 用例数 | 类型 | 覆盖范围 |
|---|---|---|---|
| `tests/unit/audit` | 49 | 单元 | 审计模型、sink 失败、Flow evidence |
| `tests/unit/observability` | 28 | 单元 | Flow/metrics/tracing、可用性指标 |
| `tests/integration/test_tenant_policy_runtime.py` | 7 | 集成 | 真实租户运行时与多路径快照 |
| `tests/integration/test_tenant_identity_contract.py` | 4 | 集成 | 可信身份与协议兼容 |

现有资产仅提供回归保护，不能作为新增租户观测场景已覆盖的证据。收集结果见 review/existing-test-assets.txt。

## 二、详细测试案例

### 案例 SC-TEC-001

| 字段 | 内容 |
|---|---|
| **ID** | TC-TEC-001 |
| 对应 Spec | tenant-evidence-context/spec.md → REQ-TEC-001 / SC-TEC-001 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 已认证 acme/globex 且具有 TenantPolicyContext |
| 输入 | 策略解析后构建观测快照 |
| 预期结果 | SHALL 创建 frozen TenantObservationContext v1.0，包含 scope=tenant、tenant_id 和 policy_id；身份必须同时匹配启动期租户与策略绑定。 快照只含 contract_version、scope、tenant_id、policy_id；不含密钥、认证凭据名、配置对象或请求原文。 tenant_id 和 policy_id 复用既有 1–64 字符配置 ID 契约。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tec.py::test_tc_tec_001` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TEC-002

| 字段 | 内容 |
|---|---|
| **ID** | TC-TEC-002 |
| 对应 Spec | tenant-evidence-context/spec.md → REQ-TEC-001 / SC-TEC-002 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 请求伪造 tenant Header/body、baggage 或日志同名字段 |
| 输入 | 执行真实认证与策略解析 |
| 预期结果 | SHALL 仅以已认证上下文选择归属，忽略所有客户端归属声明。 两个租户使用相同 X-Request-ID 也不合并上下文或审计归属。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tec.py::test_tc_tec_002` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TEC-003

| 字段 | 内容 |
|---|---|
| **ID** | TC-TEC-003 |
| 对应 Spec | tenant-evidence-context/spec.md → REQ-TEC-001 / SC-TEC-003 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | tenancy.enabled=true 且内部上下文缺失、身份未知或绑定冲突 |
| 输入 | 进入安全检测或 Provider 调用前验证快照 |
| 预期结果 | SHALL 返回 OpenAI-compatible 503 tenant_policy_unavailable，且不调用插件或 Provider。 诊断归属 unattributed，原因码 tenant_context_invalid；禁止 default、其他租户或全局策略回退。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tec.py::test_tc_tec_003` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TEC-004

| 字段 | 内容 |
|---|---|
| **ID** | TC-TEC-004 |
| 对应 Spec | tenant-evidence-context/spec.md → REQ-TEC-002 / SC-TEC-004 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 两个租户以屏障交错执行真实 HTTP 请求 |
| 输入 | 分别走 sync-output、async-output、SSE buffer、sliding-window 和 post-audit/recall |
| 预期结果 | SHALL 每条证据和后台诊断保留发起请求快照；共享 policy_id 时 tenant_id 仍不同。 后台任务和生成器显式携带快照，不在执行时读取最近请求或重新解析全局默认值。 每一运行路径分别参数化并断言真实调用、证据及输出，而非仅枚举阶段名称。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tec.py::test_tc_tec_004` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TEC-005

| 字段 | 内容 |
|---|---|
| **ID** | TC-TEC-005 |
| 对应 Spec | tenant-evidence-context/spec.md → REQ-TEC-002 / SC-TEC-005 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 响应完成、异常、断连或取消，随后在同一执行环境处理其他请求 |
| 输入 | 退出请求/后台观测作用域 |
| 预期结果 | SHALL 用 token/finally 恢复上下文且不吞掉取消；后续请求不继承前一租户。 在 ASGI send/迭代结束前保留流式作用域；禁止仅围绕 BaseHTTPMiddleware.call_next 绑定。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tec.py::test_tc_tec_005` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TEC-006

| 字段 | 内容 |
|---|---|
| **ID** | TC-TEC-006 |
| 对应 Spec | tenant-evidence-context/spec.md → REQ-TEC-002 / SC-TEC-006 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | tenancy 关闭、未认证请求和非请求生命周期事件 |
| 输入 | 生成观测上下文 |
| 预期结果 | SHALL 分别使用 legacy、unattributed、system scope；只有已验证 policy 生命周期事件使用 policy scope。 legacy 的 tenant_id/policy_id 为 null，保留已有 TenantContext default 的认证契约，不将其误认为多租户 default。 未认证请求维持现有 401，不引入归属查询。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tec.py::test_tc_tec_006` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TAU-001

| 字段 | 内容 |
|---|---|
| **ID** | TC-TAU-001 |
| 对应 Spec | audit-logger/spec.md → REQ-TAU-001 / SC-TAU-001 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 包含 allow/block/flag/modify、降级或安全不可用的 input/output 决策 |
| 输入 | 构建并写入 AuditEntry |
| 预期结果 | SHALL 在新增可选 tenant_context 字段中记录可信观测快照，并保留现有 Flow/节点/插件版本/有效策略证据。 FlowEvidence v1.0 schema 不变；归属写在 AuditEntry 外层，避免破坏 extra=forbid 消费者。 旧 AuditEntry JSON 无该字段仍可读取，单租户默认序列化不增加该字段。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tau.py::test_tc_tau_001` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TAU-002

| 字段 | 内容 |
|---|---|
| **ID** | TC-TAU-002 |
| 对应 Spec | audit-logger/spec.md → REQ-TAU-001 / SC-TAU-002 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 后台异步输出、流式审计与 recall，含多个合并 SSE event |
| 输入 | 最终记录或发出后台诊断 |
| 预期结果 | SHALL 使用发起请求快照，保持现有 request_id、Flow execution_id 与归属关联。 失败或取消诊断不得复制另一个请求的归属或原文。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tau.py::test_tc_tau_002` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TAU-003

| 字段 | 内容 |
|---|---|
| **ID** | TC-TAU-003 |
| 对应 Spec | audit-logger/spec.md → REQ-TAU-001 / SC-TAU-003 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 多个租户共用策略，策略私有 detector 发生状态变化 |
| 输入 | 写入 DetectorLifecycleEvent |
| 预期结果 | SHALL 记录 scope=policy 和可信 policy_id，tenant_id=null，保持原有顶层 policy_id。 不伪造请求归属，不向每个租户重复发出事件。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tau.py::test_tc_tau_003` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TAU-004

| 字段 | 内容 |
|---|---|
| **ID** | TC-TAU-004 |
| 对应 Spec | audit-logger/spec.md → REQ-TAU-002 / SC-TAU-004 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 审计原文默认关闭，并植入 API Key、Provider key、异常文本和伪造归属 |
| 输入 | 序列化租户审计 envelope |
| 预期结果 | SHALL 归属字段仅来自可信快照；新增元数据不泄露秘密，默认不记录 content。 store_content=true 的现有显式内容政策保留；它不授权把内容写入日志、Trace 或指标。 新增归属 JSON UTF-8 增量上限 512 bytes，不复制租户配置；现有 Flow evidence size 预算仍成立。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tau.py::test_tc_tau_004` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TAU-005

| 字段 | 内容 |
|---|---|
| **ID** | TC-TAU-005 |
| 对应 Spec | audit-logger/spec.md → REQ-TAU-002 / SC-TAU-005 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | file/stdout 单独或共同失败、无可用 sink 或初始化失败 |
| 输入 | 记录有/无 FlowEvidence 的租户审计 |
| 预期结果 | SHALL 标记 entry.evidence_persisted=false，并保持原有不因审计 sink 失败改变安全结果的行为。 如有 FlowEvidence，返回值和 entry 内的 evidence_persisted 一致。 发出稳定 audit_sink_failed 诊断，不包含路径、原始异常或原文；诊断 sink 再失败不递归。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tau.py::test_tc_tau_005` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TAU-006

| 字段 | 内容 |
|---|---|
| **ID** | TC-TAU-006 |
| 对应 Spec | audit-logger/spec.md → REQ-TAU-002 / SC-TAU-006 |
| 优先级 | P1 |
| 层次 | unit |
| 预置条件 | audit.enabled=false 或审计投影收到非法归属 |
| 输入 | 尝试记录 |
| 预期结果 | SHALL 分别显式跳过写入，或以 unattributed 记录 tenant_context_invalid 诊断并拒绝伪造的归属。 审计关闭不禁用其他已启用观测通道；非法归属不补写为已知租户。 禁用设置通过启动时固定事件可见，不逐请求产生禁用日志。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tau.py::test_tc_tau_006` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOB-001

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOB-001 |
| 对应 Spec | observability/spec.md → REQ-TOB-001 / SC-TOB-001 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 已验证租户快照与 Flow/节点证据 |
| 输入 | 生成网关管理的请求、安全决策、Provider、Flow/node 日志及 span |
| 预期结果 | SHALL 通过统一安全投影附加 tenant.scope、tenant.id、tenant.policy_id；无值字段省略。 日志采用 tenant_scope、tenant_id、tenant_policy_id 对应键；可信投影覆盖同名非可信字段。 Flow/Node 观测函数显式接受快照，第三方插件内部日志不承诺可强制隔离。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tob.py::test_tc_tob_001` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOB-002

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOB-002 |
| 对应 Spec | observability/spec.md → REQ-TOB-001 / SC-TOB-002 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 请求 model、request_id、Header、baggage 或异常包含秘密和长字符串 |
| 输入 | 网关观测事件被导出 |
| 预期结果 | SHALL 不将原文、密钥、原始异常、URL query 或客户端 baggage 导出为租户观测属性。 Trace span 名称不包含租户或客户端字段；请求/Provider model 在多租户模式投影为固定 redacted。 自动 FastAPI instrumentation 的 Header 捕获必须关闭、URL query 必须脱敏；traceparent 仅用于链路连接，不用于身份。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tob.py::test_tc_tob_002` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOB-003

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOB-003 |
| 对应 Spec | observability/spec.md → REQ-TOB-001 / SC-TOB-003 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 嵌套 Flow、流式和后台任务交错运行 |
| 输入 | 导出 spans 和结构化日志 |
| 预期结果 | SHALL 每个请求关联事件使用其显式快照，嵌套 Flow 延续相同归属。 取消、正常结束与失败之后无残留 contextvars。 Span exporter、日志捕获夹具验证实际输出而非只验证调用参数。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tob.py::test_tc_tob_003` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOB-004

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOB-004 |
| 对应 Spec | observability/spec.md → REQ-TOB-002 / SC-TOB-004 |
| 优先级 | P1 |
| 层次 | integration |
| 预置条件 | tracing 禁用、可选依赖缺失或 exporter 故障 |
| 输入 | 初始化/导出观测 |
| 预期结果 | SHALL 保持禁用时 no-op；启用但不可用时产生稳定 tracing_unavailable 诊断，安全结果和 Provider 语义不变。 沿用已有 best-effort tracing 政策；不得每次请求重复初始化或新建 exporter。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tob.py::test_tc_tob_004` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOB-005

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOB-005 |
| 对应 Spec | observability/spec.md → REQ-TOB-002 / SC-TOB-005 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 观测投影内部收到非法字段或不可序列化异常对象 |
| 输入 | 执行安全投影 |
| 预期结果 | SHALL 使用固定 unknown/invalid 值或省略非法字段，并产生 projection_sanitized 诊断。 不截取、哈希或缓存任意输入来创建身份/标签；异常对象不得进入诊断文本。 网关管理的日志及 Trace 失败诊断路径都经过相同安全投影。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tob.py::test_tc_tob_005` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TME-001

| 字段 | 内容 |
|---|---|
| **ID** | TC-TME-001 |
| 对应 Spec | prometheus-metrics/spec.md → REQ-TME-001 / SC-TME-001 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | metrics 启用且 tenant_ids 白名单为 acme |
| 输入 | acme、其他可信租户、legacy 和无归属请求产生日志/决策 |
| 预期结果 | SHALL 新增 safety_tenant_decisions_total{tenant_scope,tenant_id,direction,action} 和 safety_tenant_observability_events_total{tenant_scope,tenant_id,event}。 acme 使用 tenant/acme；其他可信租户使用 tenant_other/other；legacy、unattributed、policy、system 使用相应 scope 和固定 none。 不新增 policy、model、request_id、Flow/node、API key 标签；policy 生命周期不扇出为租户指标。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tme.py::test_tc_tme_001` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TME-002

| 字段 | 内容 |
|---|---|
| **ID** | TC-TME-002 |
| 对应 Spec | prometheus-metrics/spec.md → REQ-TME-001 / SC-TME-002 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 同一请求多个 Flow 节点、多个 SSE 窗口或 async pending/completed 审计 |
| 输入 | 统计最终 input/output 安全决策 |
| 预期结果 | SHALL 每个实际最终方向决策计数一次；pending、窗口和持久化重试不得重复计数。 action 枚举 allow/block/flag/modify/error；direction 仅 input/output。 未形成方向安全决策的 401/路由错误只产生诊断，不伪造 allow。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tme.py::test_tc_tme_002` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TME-003

| 字段 | 内容 |
|---|---|
| **ID** | TC-TME-003 |
| 对应 Spec | prometheus-metrics/spec.md → REQ-TME-002 / SC-TME-003 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 白名单最多 32 个已配置租户，攻击者发送 10000 个不同请求字段 |
| 输入 | 检查两个新指标 family 的所有 label tuples |
| 预期结果 | SHALL 身份组合最多 37，决策 tuples 最多 370，诊断 tuples 最多 296。 event 固定八项：tenant_context_invalid、audit_sink_failed、tracing_unavailable、projection_sanitized、auth_rejected、policy_unavailable、background_failed、cancelled。 每个 counter 的 total/created 样本合计最多 1332；诊断记录不递归产生诊断。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tme.py::test_tc_tme_003` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TME-004

| 字段 | 内容 |
|---|---|
| **ID** | TC-TME-004 |
| 对应 Spec | prometheus-metrics/spec.md → REQ-TME-002 / SC-TME-004 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 多租户请求产生任意 model/category/reason/error 和插件描述 |
| 输入 | 更新现有 gateway/provider/detector/Flow 指标 |
| 预期结果 | SHALL 保留现有 metric 名称和 label schema，model 固定 redacted；自由文本映射固定 unknown，ID 仅允许启动期受限配置集合。 动作、状态、direction 使用现有有限枚举；category、reason_code、error_type、field、detector_type 采用实现中固定允许值集合加 unknown。 Counter/Histogram 的 ID label 白名单取配置字典序前 256 项，其余归并 other；Gauge 仅接受完整预编译实体集合，不聚合实体，未知实体拒绝。 不得将任意输入加入缓存；单租户旧指标行为保持兼容。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_tme.py::test_tc_tme_004` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TME-005

| 字段 | 内容 |
|---|---|
| **ID** | TC-TME-005 |
| 对应 Spec | prometheus-metrics/spec.md → REQ-TME-002 / SC-TME-005 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | metrics 关闭或同进程创建两个不同配置 app |
| 输入 | 记录/导出事件 |
| 预期结果 | SHALL 禁用时不分配 label 状态；不同 app 的租户白名单和新增 registry 不相互覆盖。 使用 app-scoped observation runtime 及显式注入，不能把租户配置保存在模块级最近 app 变量。 现有全局 metrics/tracing API 的兼容调用保留，但多租户请求路径必须绑定其所属 app runtime。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_tme.py::test_tc_tme_005` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOC-001

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOC-001 |
| 对应 Spec | config-system/spec.md → REQ-TOC-001 / SC-TOC-001 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 未提供新增配置或提供合法已配置租户列表 |
| 输入 | 加载 observability.tenancy.metric_tenant_ids |
| 预期结果 | SHALL 默认 []，最多 32 个唯一已声明租户 ID；tenancy 关闭时要求列表为空。 新增子模型 extra=forbid，严格字符串列表，不接受重复、未知、超长或类型强制转换。 不新增 metrics/audit/tracing 默认启用开关；沿用已有默认关闭设置。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_toc.py::test_tc_toc_001` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOC-002

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOC-002 |
| 对应 Spec | config-system/spec.md → REQ-TOC-001 / SC-TOC-002 |
| 优先级 | P0 |
| 层次 | unit |
| 预置条件 | 配置非法或 tenant 名称与系统保留字同名 |
| 输入 | 执行启动校验 |
| 预期结果 | SHALL 非法配置以固定 tenant_observability_config_invalid 失败，不回显输入；合法配置 ID 通过 scope 区分保留字。 tenant/other 与 tenant_other/other 不碰撞；不存在全局禁用保护的静默回退。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_toc.py::test_tc_toc_002` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOC-003

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOC-003 |
| 对应 Spec | config-system/spec.md → REQ-TOC-002 / SC-TOC-003 |
| 优先级 | P0 |
| 层次 | integration |
| 预置条件 | 旧单租户示例及新的多租户观测示例 |
| 输入 | 加载配置并通过真实 HTTP/SSE 请求运行 |
| 预期结果 | SHALL 保持旧 JSON/SSE/body/header 状态语义和 FlowEvidence v1.0；新增观测字段只进入管理员观测数据。 不向 Provider Header/body/baggage 或客户端响应注入租户身份。 示例包含白名单聚合、非秘密 ID、共享管理员 sinks、disabled 与写入失败策略说明。 |
| 计划测试节点 | `tests/integration/test_tenant_observation_toc.py::test_tc_toc_003` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

### 案例 SC-TOC-004

| 字段 | 内容 |
|---|---|
| **ID** | TC-TOC-004 |
| 对应 Spec | config-system/spec.md → REQ-TOC-002 / SC-TOC-004 |
| 优先级 | P1 |
| 层次 | unit |
| 预置条件 | 第三项通过验证但第四项尚未交付 |
| 输入 | 更新路线与交付文档 |
| 预期结果 | SHALL 仅在 Gate 3/Deliver 后将第三项标为 delivered，第四项及公共 v0.3.0 保持未完成。 本次不更改包版本、不创建发布标签，不声称实现物理租户存储或访问授权隔离。 |
| 计划测试节点 | `tests/unit/tenancy/test_observation_toc.py::test_tc_toc_004` |
| 当前状态 | 测试缺；Gate 2 后按 TDD 新增 |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 集成测试 | E2E | 状态 |
|---|---|---|---|---|
| tenant-evidence-context | SC-TEC-001 | SC-TEC-002, SC-TEC-003, SC-TEC-004, SC-TEC-005, SC-TEC-006 | 无外部服务；ASGI 接线验证 | planned |
| audit-logger | SC-TAU-001, SC-TAU-003, SC-TAU-004, SC-TAU-006 | SC-TAU-002, SC-TAU-005 | 无外部服务；ASGI 接线验证 | planned |
| observability | SC-TOB-001, SC-TOB-005 | SC-TOB-002, SC-TOB-003, SC-TOB-004 | 无外部服务；ASGI 接线验证 | planned |
| prometheus-metrics | SC-TME-001, SC-TME-004 | SC-TME-002, SC-TME-003, SC-TME-005 | 无外部服务；ASGI 接线验证 | planned |
| config-system | SC-TOC-001, SC-TOC-002, SC-TOC-004 | SC-TOC-003 | 无外部服务；ASGI 接线验证 | planned |

## 四、回归风险矩阵

| 风险区域 | 本次改动 | 已有回归保护 | 风险等级 |
|---|---|---|---|
| 中间件/后台/流式 | 快照传播与 finally | tenant policy runtime、streaming | 高 |
| 审计模型与写入 | 增量归属及失败标记 | unit/audit | 高 |
| registry/tracer 生命周期 | app 私有句柄 | unit/observability + 新双 app 场景 | 高 |
| 指标 label 投影 | 多租户归并 | metrics/flow observability | 高 |
| 配置/文档 | strict 新子模型 | config、release documentation contract | 中 |

## 五、建议补充顺序

1. P0：SC-TEC-001, SC-TEC-002, SC-TEC-003, SC-TEC-004, SC-TEC-005, SC-TEC-006, SC-TAU-001, SC-TAU-002, SC-TAU-003, SC-TAU-004, SC-TAU-005, SC-TOB-001, SC-TOB-002, SC-TOB-003, SC-TOB-005, SC-TME-001, SC-TME-002, SC-TME-003, SC-TME-004, SC-TME-005, SC-TOC-001, SC-TOC-002, SC-TOC-003。
2. P1：SC-TAU-006, SC-TOB-004, SC-TOC-004。本 change 交付前同样必须通过。
3. P2：无。

## 六、执行与质量门
Gate 2 后：先各切片聚焦 pytest + ruff/mypy，再完整测试；依项目既有质量门覆盖 Python 3.10/3.11/3.12、覆盖率、依赖安全检查及 12 类失败模式。新测试预期使用 .venv/bin/python -m pytest，并按实际解释器切换。已有性能基准按原阈值运行并报告，不能为通过而降阈值；覆盖率插桩性能信号独立报告。
Phase 5 thorough 模式执行独立安全/性能及代码/测试/文档审阅，依验证技能要求开展。此处不提前执行 Phase 3–5，也不标记任何测试 PASS。
