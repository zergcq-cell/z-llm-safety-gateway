# v0.3.0 租户证据与可观测性隔离 - 技术设计

> Gate 2 review draft。基线 d2b3634。Gate 1 已由用户明确确认；本阶段未授权实施。

## Context

公共 v0.3.0 路线的第三个独立 change。第一项建立 TenantContext，第二项建立 TenantPolicyContext 与请求级 FlowExecutionSnapshot。AuditEntry 尚未包含租户归属；现有 lifecycle 事件具有 policy_id；Flow 观测已有部分脱敏机制，但没有统一租户上下文。当前 metrics/tracing 有模块级状态，不能承载跨 app 的租户配置。

范围是可信归属、逻辑证据隔离、安全投影和有界指标。现有审计和遥测 sinks 是管理员共享通道；本变更不提供租户直接查询 API、租户 ACL、物理分库、独立 exporter 或配额调度。运维需在现有基础设施限制共享 sinks 的访问。第四项资源与失败兼容验收仍独立执行。

参考现有实现：
- `src/z_llm_safety_gateway/tenancy/context.py` 与 `tenancy/policy.py`
- `src/z_llm_safety_gateway/middleware/policy_resolution.py`
- `src/z_llm_safety_gateway/pipeline/snapshot.py`
- `src/z_llm_safety_gateway/routes/chat.py` 与 `app.py` 的异常审计
- `src/z_llm_safety_gateway/audit/models.py`、`audit/logger.py`
- `src/z_llm_safety_gateway/flow/evidence.py`
- `src/z_llm_safety_gateway/observability/flow.py`、`metrics.py`、`tracing.py`

## Project Principle Check

| 原则 | 本设计如何满足 | 风险或取舍 | 验证方式 |
|------|---------------|-----------|---------|
| Plugin / Flow；核心最小 | 新增通用归属、投影和生命周期机制；不改变插件判断和 Flow 顺序 | 不把租户业务策略放入 logger | 依赖审阅；真实请求的插件及 Provider 调用保持原语义 |
| 策略显式；失败不静默 | 入口身份无效拒绝；sink 失败沿用 best-effort 且显式失败证据；禁用配置启动可见 | 审计失败不改变安全结果是既有可用性政策 | 注入身份错误、sink/exporter 故障、无 sink、禁用矩阵 |
| 边界透明；契约稳定 | 保持 FlowEvidence v1.0；AuditEntry 增量字段；保留旧指标 schema、HTTP/SSE | 多租户旧指标的自由文本标签会归并，需运维说明 | 旧 JSON/配置回归；真实 HTTP/SSE；指标 label schema 对比 |
| 决策有证据；默认保护数据 | 精确租户/策略快照关联原 Flow/节点/版本/有效策略；不复制秘密 | 指标仅有限租户明细，完整归属保留在管理员审计 | 秘密金丝雀、并发共策略、整 envelope 字节计量 |

不偏离四项原则。审计共享存储不意味着向租户开放其他租户证据；本 change 只承诺运行时逻辑隔离。

## Decisions

### 1. 单次捕获，显式传递的 TenantObservationContext v1.0

**方案**：新增 frozen 数据契约，仅包含 `contract_version="1.0"`、`scope`、`tenant_id`、`policy_id`。scope 为 tenant / legacy / unattributed / policy / system。tenant scope 两个 ID 必填且匹配启动期绑定；policy scope 仅 policy_id；其余两个 ID 均为空。ID 复用既有 1–64 字符契约，由维护者保证其非秘密性。

认证及策略解析成功后，从同一 TenantContext/TenantPolicyContext 构造并验证。挂到 request state 并传入 FlowExecutionSnapshot、审计 builder、观测函数、流式生成器及后台闭包；不把 runtime bundle 或完整配置放进观测对象。每次归属验证使用 app 私有预编译映射，预期 O(1)，不扫描全部租户。

**为什么**：同一策略可被多个租户共享，policy_id 不能替代 tenant_id；X-Request-ID 可由客户端提供，不能作为身份缓存 key。

**备选方案及排除原因**：仅使用 contextvars 无法证明后台和生成器一致；每阶段重新解析会漂移；按 request_id 查表可碰撞且导致无界缓存。

### 2. 生命周期与中间件边界

**方案**：请求入口清除/恢复当前 app 的观测绑定，在认证和策略解析之后绑定可信快照。contextvars 仅便利网关日志，显式参数为权威。ASGI wrapper 作用域覆盖 send、流式迭代和响应背景工作；独立任务在自身 finally 重置 token。不能仅围绕 BaseHTTPMiddleware.call_next 绑定，因为响应体可能稍后迭代。

入口缺失/冲突遵守既有 503 tenant_policy_unavailable，不调用 Provider。已开始响应之后发现无效观测输入，只发 unattributed 固定诊断并拒绝假归属，不重写已发出的响应；独立后台工作缺失快照不得用其他请求上下文补齐。401 保持原语义。取消向上传播，finally 清理归属。

**备选方案及排除原因**：新增全局 last_tenant 会串请求；全局清空 structlog 上下文会破坏调用者自己的字段，使用 token 恢复。

### 3. 保持 FlowEvidence 稳定，扩展审计 envelope

**方案**：AuditEntry 新增可选 `tenant_context`，旧 entry 缺省可解析；legacy 默认不序列化该字段。FlowEvidence v1.0 不加字段，不改版本或 strict 模型；通过 AuditEntry 外层上下文加 execution_id 关联。Flow/节点观测 API 接受同一快照参数，嵌套 Flow 继承。

AuditEntry 精确记录 tenant_id、policy_id，已有节点 evidence 继续说明 Flow、节点、插件实现版本和有效策略。不引入不存在的 policy_version，也不把配置哈希作为新身份。归属 envelope 紧凑 JSON UTF-8 增量不超过 512 bytes；现有 FlowEvidence 独立字节预算继续满足。

**备选方案及排除原因**：直接给 FlowEvidence v1.0 加字段会破坏 extra=forbid 消费者；给每个 Node 重复身份浪费预算。

### 4. 非请求事件与失败归属

**方案**：共享策略 detector 生命周期标记 scope=policy，仅有 policy_id，保留现有顶层 policy_id。不向所有绑定租户扇出。系统初始化/关闭使用 system；未认证和非法内部上下文使用 unattributed；旧单租户使用 legacy，不改变旧 TenantContext default 的含义。

任何配置启用的 audit sink 失败均令 entry.evidence_persisted=false，包含没有附着 FlowEvidence 的情况；有附着 evidence 时同步返回值。诊断使用 audit_sink_failed，不回显路径、异常或输入。沿用现有 audit sink 的 best-effort 行为，不更改安全动作。所有 sink 都不可写时无法声称证据已持久化，保留内存失败状态并尝试其他已启用诊断通道；失败诊断不得递归。audit.enabled=false 不是写入失败，沿用禁用语义，启动时记录固定禁用事件。

**备选方案及排除原因**：给 lifecycle 选择任意租户不真实；本次将审计写入失败改为 fail-closed 会改变已有行为并越过第四项总体失败矩阵。

### 5. 日志和 Trace 的安全投影

**方案**：网关管理的事件统一应用 allowlist 投影。可信字段覆盖同名非可信字段；scope/ID 只能来自 app 验证的快照。日志字段为 tenant_scope/tenant_id/tenant_policy_id；Trace 对应 tenant.scope/tenant.id/tenant.policy_id。仅在有值时输出 ID。

不使用请求 Header/body/baggage/异常构造属性。多租户 request/provider model 在遥测投影为 redacted；事件/span 名称固定，不嵌入租户或客户端字段。非租户标识仅允许部署配置 ID 和有限枚举；无效自由文本映射 unknown/invalid 或省略，不截断或哈希后保留。保持已有审计 content_hash 和显式 store_content 政策，此许可不扩展到日志、Trace、指标。

FastAPI 自动 instrumentation 的 Header 捕获关闭；URL query 在导出前删除，异常自动记录不得导出原始文本。实现阶段必须用实际 exporter 输出夹具检查；若可选 instrumentation 不能满足投影契约，则使用网关显式受控 spans，记录 tracing_unavailable/降级诊断，不放宽隐私要求。W3C traceparent 可用于关联，baggage 不能携带租户数据向上游传播。

覆盖范围是网关管理的请求、路由、Flow、节点、异步/流式、生命周期及失败日志；不承诺过滤第三方插件自行配置的 logger/exporter。

**备选方案及排除原因**：仅正则判定字符串可打印不能证明非秘密；异常字符串截断仍泄漏秘密；span 名加入 tenant 会形成高基数名称。

### 6. 独立租户指标及明确聚合

**方案**：新增 `observability.tenancy.metric_tenant_ids: []`，最多 32 个唯一、已配置租户。未列出的可信租户投影 tenant_other/other；列出的投影 tenant/<id>。其余 scope 固定为 legacy、unattributed、policy、system，tenant_id=none。通过 scope 区分名字为 other/none 的合法租户，身份组合最多 37。

新增两个 Counter：
- `safety_tenant_decisions_total{tenant_scope,tenant_id,direction,action}`：direction=input/output；action=allow/block/flag/modify/error；每个实际最终方向决策只记录一次。async pending、窗口局部结果、重试不重复计数。不以审计是否启用控制指标，不在 AuditLogger.record 中计决策。
- `safety_tenant_observability_events_total{tenant_scope,tenant_id,event}`：event 只有 tenant_context_invalid、audit_sink_failed、tracing_unavailable、projection_sanitized、auth_rejected、policy_unavailable、background_failed、cancelled 八项。

上限分别为 370/296 个 label tuples。包括 Counter 的 created 样本，两个 family 总样本最多 1332。无新增 policy/model/request_id/Flow/node 标签。禁用 metrics 时不创建 registry 或 label 状态；没有每请求去重表，计数所有权由各终态控制路径决定。

**备选方案及排除原因**：在所有旧指标加 tenant 标签会乘法膨胀并破坏 dashboards；对所有配置租户默认展开浪费资源；只按 policy 聚合不能区分共享策略租户。默认聚合牺牲指标级逐租户明细，但审计仍有精确归属，维护者可显式选最多 32 个租户。

### 7. 既有指标在多租户模式的边界

**方案**：保留现有指标名和标签名；多租户模式对请求影响的 model 使用 redacted，动作/状态等有限枚举保持语义，自由文本 category/error/reason 等使用固定允许值加 unknown。配置 ID 每个 label 对 Counter/Histogram 采用字典序前 256 项加 other（最多 257），映射在启动完成，不因请求增长；具体 enum 允许值在实现时以现有契约常量为权威并写入验证报告，禁止动态积累插件输出值。

状态 Gauge 不聚合不同实体：detector_up / circuit_breaker 等仅接受真实预编译配置身份，其实体数量受既有租户策略、capability 上限约束；未知实体拒绝并计固定 projection_sanitized。无 label 的活动计数 Gauge 不变。Gauge 不能以 other 合并，否则最后一次写入会伪造其他实体健康状态。

对每个 family 记录实装标签集合大小及乘积上界；label tuples 上界为各维度有限大小乘积，Histogram 样本再乘实际 bucket/count/sum/created 数量。压力验证随机输入不会扩大这些集合，不以“字符串长度有限”代替基数上界。只增加本次通用观测投影，不改变安全执行配置。

**备选方案及排除原因**：原样记录合法语法的 model/reason 仍可产生无限序列；对 Gauge 聚合会损失正确性；本次限制真实策略配置数量会越过既有契约和第四项资源设计。

### 8. App 私有 runtime 与配置校验

**方案**：ObservationRuntime 为 app 所有，持有不可变绑定/白名单、registry 和可选 tracer 句柄。多租户请求和后台任务显式绑定所属 runtime，不能读取模块级最近 app 配置。兼容保留旧模块 API；必要时作为 legacy facade；多租户路径注入 app-owned registry/provider，关闭时只清理自己拥有的资源，不覆盖宿主全局 tracer provider。

新增配置子模型 extra=forbid、严格字符串列表；未知、重复、非字符串、超过 32 项、tenancy 关闭却非空列表均以 tenant_observability_config_invalid 拒绝，启动异常不得回显原值。保持原有 audit/metrics/tracing 默认关闭；不新增隐含依赖或启用策略。

**备选方案及排除原因**：模块级 tenant allowlist 在同进程多个 app 时会串配置；为每个租户创建 exporter 是不必要的资源放大。

### 9. 锚定与实现自由度

关键安全变更最低 L3，实际 L3：锚定 2026-08-22-v0.2.0-flow-foundation、2026-08-30-tenant-identity-config-contract、2026-09-01-tenant-flow-policy-resolution。复用已交付可信身份、immutable snapshot、稳定原因码、evidence privacy 和 best-effort audit 模式。

已锁定身份来源、scope 字段、各阶段传播、失败默认值、指标名字/维度/白名单上限、旧契约兼容边界。不预选 helper 函数名字和文件拆分；它们只影响实现组织。七个中置信度场景为新增设计决策，需 Gate 2 审阅；无低置信度或未决产品问题。

## Architecture

配置加载 → 启动验证/编译 ObservationRuntime → 认证 → TenantPolicyResolution → 可信观测快照 → FlowExecutionSnapshot

快照 + app runtime → input/output Flow（插件执行不变）→ 审计 envelope / 安全日志 / Trace / 有界指标

快照 + app runtime → 显式捕获的 async/SSE/post-audit/recall 工作 → 同一组投影出口 → finally 恢复作用域

策略生命周期 → scope=policy；系统生命周期 → scope=system；认证前/非法上下文 → scope=unattributed。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| middleware task 边界导致 contextvars 不传播 | 以显式快照为权威；真实 ASGI 流式 send 与后台捕获测试 |
| 指标计数重复或漏 async 终态 | 在终态拥有者计数；参数化 pending/complete/window/retry 测试 |
| 原始异常通过自动 instrumentation 导出 | 使用内存 exporter 检查最终属性/events；不满足则受控 spans |
| 审计写入失败而用户响应已发送 | 保留失败标记和固定诊断，不声称可撤回响应 |
| app-private runtime 改装影响全局 facade | 双 app 隔离测试与旧 API 回归并行覆盖 |
| 既有指标多租户 label 值发生归并 | 文档说明 dashboards 变化；名称和 label schema 不变 |
| 完整测试未运行 | 本阶段仅验证文档；Gate 2 后按 RED→GREEN→REFACTOR 实施 |
