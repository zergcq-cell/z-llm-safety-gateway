# v0.3.0 租户级 Flow 与安全策略解析 - 技术设计

## Context

当前 Gateway 已通过 `TenantContext v1.0` 从可信 API Key 绑定解析请求租户，但应用装配仍是
单一全局实例：`ModelRouter` 使用全局 `routing.rules`，`PipelineEngine` 使用全局 stage Flow，
Detector 实例、配置和可用性状态也存放在 `app.state` 的全局字段。请求入口虽然会创建
`FlowExecutionSnapshot`，其内容仍来自这些全局对象。因此两个已认证租户目前无法选择不同的
Flow、Detector 阈值、词表、失败策略或 Provider 路由。

本 change 将可信身份扩展为可信策略解析，但不把租户专属检测逻辑放进核心。全局 `flows` 和
`providers` 继续声明可用实现；租户策略只引用这些声明、提供插件配置并限制路由域。审计、日志、
Trace、Metrics 的租户投影属于第 3/4 个 change，配额、并发公平性和整体验收属于第 4/4 个 change。

Phase 1 Human View 的结构化提取器未识别 `### New/Modified Capabilities`，本设计以已确认的
canonical proposal 为权威，覆盖全部 5 个 Capability。该工具限制不改变产品设计。

## Project Principle Check

| 原则 | 本设计如何满足 | 风险或取舍 | 验证方式 |
|------|---------------|-----------|---------|
| Plugin / Flow；核心最小 | Detector 行为和词表仍在插件配置中；组合、顺序、节点失败与停止策略仍由 Flow 定义；核心只负责严格引用、编译、上下文传播和路由域限制 | 为每个策略建立 runtime bundle 增加少量核心装配机制，但不增加租户专属检测分支 | 依赖边界测试、两个策略不同 Flow/Detector 行为的真实 HTTP 测试 |
| 策略显式；失败不静默 | 每个租户必须显式引用策略；stage 禁用使用显式 `null`；未知、悬空、冲突和越权配置均拒绝，无跨租户或全局回退 | 多租户内部不再继承全局执行选择器，配置更冗长但安全来源唯一 | 启动失败矩阵、503 invariant failure、404 route miss 和无 Provider 调用断言 |
| 边界透明；契约稳定 | `model`、HTTP/SSE 和上游 payload 不改写；旧单租户继续使用原路由和 pipeline；请求期为 O(1) 策略查找加至多 256 条规则的确定性匹配 | `/v1/models` 在多租户模式必须显式指定 Provider，避免继续访问全局首项 | 旧配置 corpus、HTTP/SSE byte/order 回归、最大规则操作计数测试 |
| 决策有证据；数据默认保护 | 请求只公开冻结的非秘密 `TenantPolicyContext`；原始 Detector 配置、词表、Provider 实例和 Key 留在私有 runtime bundle | 完整 audit/metrics 租户投影延后，但本 change 提供稳定 policy/flow/provider 标识入口 | frozen/serialization 测试、异常/日志秘密扫描、后续 evidence contract 边界测试 |

**原则取舍**：多租户策略解析失败采用 fail-closed；显式禁用某 stage 仍允许，因为这是可审计的
Flow 选择而非静默降级。旧单租户配置保持现有全局行为。无原则偏离。

## Decisions

### 1. 租户引用具名、严格且可复用的策略配置

**方案**：`TenancyConfig` 新增 `policies`，`TenantConfig` 新增必填 `policy_id`（仅在
`tenancy.enabled=true` 时）。策略 ID 使用与 tenant ID 相同的 1–64 位小写 ASCII slug。
不同租户可以显式引用同一策略；每个策略只编译一次。

```yaml
tenancy:
  enabled: true
  tenants:
    - id: acme
      policy_id: strict-chat
    - id: globex
      policy_id: research-chat
  policies:
    - id: strict-chat
      input_flow: {flow_id: strict-input, version: "1.0.0"}
      output_flow: {flow_id: strict-output, version: "1.0.0"}
      capabilities: []
      result_policy: {}
      routing:
        models_provider: acme-openai
        rules:
          - {pattern: "gpt-*", provider: acme-openai}
```

`input_flow` 与 `output_flow` 字段必须出现，但允许显式 `null` 表示该方向不执行安全 Flow。
策略模型使用 `extra="forbid"` 和隐藏输入错误，最多 1024 个策略。

**为什么**：具名策略允许安全复用，同时保持 tenant → policy 的唯一关系；显式 null 能区分“部署者
选择不运行”与“字段漏配”。

**备选方案及排除原因**：

- 在每个 tenant 下复制完整 GatewayConfig：重复 Provider secrets，难以验证来源与兼容。
- 按 tenant ID 隐式寻找同名 Flow：命名约定会成为不可见策略并产生静默 fallback。
- 允许缺省 stage 继承全局 pipeline：多租户与全局配置形成双重事实来源。

### 2. 策略引用全局 Flow/Provider，但拥有独立 Capability bindings

**方案**：全局 `flows` 和 `providers` 继续作为版本化定义与实现注册表。每个 tenant policy 提供
自己的 `CapabilityBindingConfig` 列表，Detector 阈值、敏感词表、类型和初始化配置均在该列表中。
所选 Flow 展开的每个 Detector capability 必须有且只有一个 binding；未使用 binding 也拒绝。

每个策略最多 256 个 bindings，与现有 Flow 最大展开节点数一致。Provider Key 只存在于全局
`ProviderConfig`，tenant policy 只引用 Provider name。

**为什么**：Flow 决定执行结构和 Node policy；binding 决定插件实现参数。两者分离后，同一 Flow
拓扑可以在租户间复用而使用不同阈值/词表，且秘密不会复制到租户上下文。

**备选方案及排除原因**：

- 直接覆盖 Flow Node 字段：把插件配置与执行结构混在一起，破坏 Capability contract。
- 复用单一全局 capability binding：同名 Detector 无法具有租户级阈值和词表。
- 允许运行期缺 binding 使用插件默认值：安全默认不再显式，且不同插件版本可能漂移。

### 3. Result policy 只承载当前无法由 Node policy 表达的 reducer 设置

**方案**：tenant policy 的 `result_policy` 只包含现有 `flag_escalation`。timeout、availability、
failure、degradation 和 stop 继续由所选 Flow Node policy 定义。Streaming mode/window、post-audit、
output sync/async、webhook、Auth、TLS 和 Rate Limit 在本 change 中仍为部署级全局配置。

每个策略构造自己的 `PipelineEngine` facade，使 flag escalation 不跨租户共享；Flow Runtime 与
Reducer contract 不增加 tenant-domain 分支。

**为什么**：这覆盖当前 final action 的租户级策略差异，同时不把传输策略、证据投影和资源治理
扩进本 change。

**备选方案及排除原因**：

- 把全部 pipeline/security/audit 配置复制进 tenant policy：跨越后续 evidence/resource changes。
- 在通用 Flow Runtime 中判断 tenant：违反核心领域中立性。
- 保留全局 flag escalation：两个租户可能从相同 Detector 结果得到错误的同一 final action。

### 4. 启动期编译私有 `TenantRuntimeBundle`，请求只传播安全 Context

**方案**：新增 app-scoped `TenantPolicyResolver`。启动时为每个 policy 编译冻结的私有
`TenantRuntimeBundle`，包含：独立 PipelineEngine、input/output Detector 实例及配置、独立
DetectorStatusRegistry、Flow identities、resolved Node policies 和 tenant-scoped Router view。

请求解析产生两个层次：

- `TenantPolicyContext v1.0`：冻结、可安全进入未来 evidence，只含 tenant_id、policy_id、input/output
  Flow identity 和 routing profile ID；不含词表、Detector 配置、Provider 对象或 Key。
- 私有 runtime bundle 引用：只供路由和 pipeline 内部消费，不序列化、不记录。

同一 policy 被多个租户引用时复用 bundle，但每个请求的 Context 仍保留自己的 tenant_id。

**为什么**：隔离安全标识与含敏感配置的执行对象，既提供稳定证据入口，又避免秘密扩散。

**备选方案及排除原因**：

- 把完整 config 放入 request.state 的公开 snapshot：容易被日志或异常序列化。
- 每个请求重新构造 Detector/Engine：成本无界且可能观察到不一致状态。
- 只传播 policy_id 后在每阶段重新查询：后台/流式阶段可能重新引入全局或不同策略。

### 5. 策略在 Provider 选择前解析并冻结，贯穿全部输出路径

**方案**：`AuthMiddleware` 建立 `TenantContext` 后，chat/models route 立即调用 resolver。chat route
先捕获 policy runtime bundle 和 `FlowExecutionSnapshot`，再检查 Detector availability 和选择 Provider。
input、sync/async output、sliding-window、buffer 和 post-audit 都消费同一个 bundle/snapshot；后台任务
通过闭包持有冻结引用，不重新读取 app 全局默认值。

每个 policy 使用独立 DetectorStatusRegistry。同名 Detector 在 policy A 不可用时，不得从 policy B
移除或降级；required Detector 初始化失败仍阻止整个 Gateway 就绪，因为配置声明的租户策略不可用。

**为什么**：直接应用 EXP-2026-0001/0008，避免“请求初始正确、后续阶段回到全局 runner”。

**备选方案及排除原因**：

- 仅在 chat handler 中替换 Detector 列表：stream/post-audit/async 仍可能绕回全局配置。
- 全部策略共享状态注册表的 `(direction, name)` 键：同名实例发生状态碰撞。
- required policy 失败但 Gateway 继续 ready：部署会静默存在不可用租户。

### 6. Tenant Router view 复用 Provider 实例但限制规则域

**方案**：全局 `ModelRouter` 继续初始化一次 Provider adapters。每个 policy 编译最多 256 条有序
glob rules 的 immutable Router view，只能引用已声明 Provider。精确重复 pattern 指向不同 Provider
时以 `tenant_policy_route_conflict` 拒绝；其他重叠 pattern 保持显式 first-match 语义。

chat 的 `model` 只在当前 policy rules 中匹配。无匹配继续返回 OpenAI-compatible 404
`model_not_found`，且不调用任何 Provider、不列出其他可用 Provider。客户端 Header/body 中的 tenant、
policy 或 provider 字段均不参与选择。

**为什么**：共享 adapter 避免复制连接池和 secrets；规则视图保证路由不会越出租户允许集合。

**备选方案及排除原因**：

- 先全局 route 再检查 Provider allowlist：错误 Provider 可能已初始化、记录或被调用。
- 每租户复制 ProviderConfig：扩大 Key 的内存与日志表面。
- 无匹配回退全局 router：直接破坏隔离。

### 7. `/v1/models` 使用显式 `models_provider`

**方案**：每个 multi-tenant routing policy 必须指定 `models_provider`，且该 Provider 必须至少被一条
policy rule 引用。`GET /v1/models` 使用该 Provider；不聚合、不重写响应，保持现有透传协议。Legacy
模式继续访问全局第一个 Provider。

**为什么**：当前 endpoint 无 model 字段，若继续固定全局首项会绕过 tenant routing 并暴露未授权
Provider。显式选择比“取第一条 rule”更稳定。

**备选方案及排除原因**：

- 禁用 multi-tenant `/models`：不必要地破坏公开 API。
- 查询所有允许 Provider 并聚合：改变响应语义并引入去重/分页问题。
- 使用第一条 routing rule：规则重排会隐式改变 models endpoint。

### 8. 多租户执行选择器与 legacy 全局选择器互斥

**方案**：multi-tenant mode 下，tenant policies 是唯一执行选择源。显式全局 `routing.rules`、
`pipeline.detectors`、`pipeline.input_flow/output_flow` 和顶层 `capabilities` 与 tenant policies 同时出现时，
启动以 `conflicting_tenant_policy_sources` 拒绝。全局 `flows`、`providers`、`flow_runtime` 和部署级
pipeline transport settings 仍允许。

tenancy disabled/absent 时，`policies` 或 tenant `policy_id` 以
`tenancy_disabled_with_tenant_policy` 拒绝；完全不含租户策略字段的旧配置保持原行为。

**为什么**：静默优先级会让配置文件看似生效但生产请求消费另一来源。

**备选方案及排除原因**：

- tenant 字段覆盖 global：旧字段仍被接受却静默无效。
- global 作为 tenant fallback：策略缺失可能跨越安全边界。
- 自动迁移 identity-only 示例：运行时不应猜测 Flow/Provider 意图。

### 9. 启动与运行期失败契约稳定、脱敏

**方案**：启动期至少锁定以下 reason codes：

| 状态 | reason code |
|------|-------------|
| tenant 缺 policy_id / policies 为空 | `tenant_policy_required` |
| 重复 policy ID / 超过 1024 | `duplicate_tenant_policy_id` / `tenant_policy_limit_exceeded` |
| tenant 引用未知 policy | `unknown_tenant_policy` |
| Flow 引用未知或 binding 缺失/未使用 | `tenant_policy_flow_not_found` / `tenant_policy_capability_binding_missing` / `tenant_policy_capability_binding_unused` |
| route Provider 未知或 models Provider 不允许 | `tenant_policy_route_provider_not_found` / `tenant_policy_models_provider_not_allowed` |
| 精确 route 冲突 / rules 超过 256 | `tenant_policy_route_conflict` / `tenant_policy_route_limit_exceeded` |
| global 与 tenant sources 冲突 | `conflicting_tenant_policy_sources` |

若已通过启动验证的运行期请求缺 TenantContext、policy 或 bundle，返回 OpenAI-compatible HTTP 503
`tenant_policy_unavailable`，不回退。正常的 tenant route miss 返回兼容 404 `model_not_found`。
错误、日志和 Context 不含 API Key、Provider Key、完整词表、原始请求或未过滤异常文本。

**为什么**：静态错误尽早失败；不可达 invariant failure 仍需安全、可观察且不泄密。

**备选方案及排除原因**：

- 运行期 KeyError/500：错误不稳定且可能暴露内部对象。
- 503 后使用 legacy pipeline：跨租户 fail-open。
- 在 public error 中列出有效 policy/provider：泄露租户内部拓扑。

### 10. 有界性、兼容性和文档由真实生产路径证明

**方案**：policy 查找为预编译 mapping 的 O(1) expected lookup；route 为 O(R)，`R <= 256`；Flow
沿用 depth 8、nodes 256 的既有硬界。测试用拒绝迭代的 mapping sentinel 和最大规则计数证明结构边界，
不使用 coverage 插桩下的易抖动微基准。

真实 `create_app` 测试从 YAML 和两个 Bearer keys 开始，断言相同 model 进入不同 Provider、不同
Flow/threshold/word-list 结果，并覆盖 HTTP、SSE 和后台路径。文档示例必须经 `load_config` 验证。
旧单租户 corpus、Provider payload、HTTP status/body/header 和 SSE chunk order 全量回归。

**为什么**：应用 EXP-2026-0005/0008/0011/0022/0023/0025，避免只验证 schema、假 checkpoint、
归一化不可达值和插桩性能误报。

**备选方案及排除原因**：

- 只测 Pydantic：不能证明生产装配消费 policy。
- 只做 wall-clock microbenchmark：桌面调度和 coverage 会产生伪回归。
- 只测 chat sync：遗漏 SSE、post-audit、async 和 `/models` 绕过。

## Architecture

```text
Gateway YAML
   ├─ providers / flows (global declarations, secrets stay here)
   └─ tenancy
        ├─ tenants: tenant_id -> policy_id
        └─ policies: Flow refs + capability bindings + result/routing policy
                         │
                         ▼ startup validate + compile
                TenantPolicyResolver (app scoped)
                         │ policy_id -> private TenantRuntimeBundle
                         │
Request -> AuthMiddleware -> frozen TenantContext
                         │ O(1)
                         ▼
                TenantPolicyContext v1.0 (secret-free)
                         + private runtime bundle reference
                         │
             ┌───────────┼──────────────────────┐
             ▼           ▼                      ▼
       input Flow   tenant Router view      output Flow
                    ├─ chat model rules      sync / async
                    └─ models_provider       SSE / buffer / post-audit
             │                                  │
             └──────── same frozen request snapshot ────────┘
```

主要实现边界：

```text
src/z_llm_safety_gateway/
├── tenancy/
│   ├── context.py          # existing TenantContext
│   └── policy.py           # TenantPolicyContext/Resolver/private bundle contracts
├── config/
│   ├── models.py           # strict policy/routing/result models
│   └── validators.py       # cross-reference/source/failure matrix
├── app.py                  # compile one runtime bundle per policy
├── pipeline/snapshot.py    # bind chosen policy bundle across every stage
├── providers/router.py     # immutable tenant Router views over shared adapters
└── routes/
    ├── chat.py             # resolve before availability/provider selection
    └── models.py           # explicit tenant models_provider
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| tenant policy schema 成为第二套 GatewayConfig | 只包含 Flow refs、bindings、result policy 和 routing；部署级 transport/security/audit 保持全局 |
| 同名 Detector 状态跨 policy 污染 | 每个 compiled policy 独立 status registry；所有阶段使用同一 bundle |
| shared policy 导致 tenant identity 丢失 | bundle 可共享，request `TenantPolicyContext` 每次从 TenantContext 新建并保留 tenant_id |
| Detector config/word-list 被序列化或记录 | 安全 Context 与私有 bundle 分离；异常、repr、日志负向扫描 |
| Provider route 越权或 `/models` 绕过 | tenant Router view + 显式 models_provider；无匹配不调用 Provider |
| 多租户与全局配置来源冲突 | raw YAML/source-presence 启动拒绝，不设静默优先级 |
| Async/SSE/post-audit 重新读取全局对象 | route 开始捕获 engine/bundle/snapshot，后台闭包只持冻结引用 |
| 1024 policies 导致大量 Detector 实例 | 本 change 设置声明和每 policy 节点界；实例共享/容量治理由第 4/4 change 统一验收 |
| 新 schema 使 identity-only interim example 失效 | 更新 v0.3.0 未发布示例；公开 v0.2.2 单租户配置保持兼容 |
| 错误码泄露内部拓扑或 secrets | public runtime 只返回稳定 code；详细启动定位仅使用有界 ID，绝不包含配置值 |
