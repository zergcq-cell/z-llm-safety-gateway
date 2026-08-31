# v0.3.0 租户身份与配置契约 - 技术设计

## Context

当前 Gateway 通过 `security.auth.api_keys` 的 Bearer token 完成认证，并把匹配项的
`name` 写入 `request.state.api_key_name`。认证关闭时请求直接通过；认证开启时缺失或
无效凭据返回 OpenAI-compatible 401。配置由 Pydantic v2 模型和跨字段 validator 在启动期加载，
`AuthMiddleware` 位于 Request ID 之后、Rate Limit 之前。

这套模型能区分调用凭据，但没有租户声明、凭据到租户的绑定、稳定的请求级租户上下文或
跨字段一致性校验。后续若直接按 API Key 名称解析租户 Flow，会把显示名误当安全边界，并可能因
重复名称、悬空绑定或客户端伪造 Header 产生跨租户越权。

本 change 只建立 v0.3.0 的身份信任根和配置契约。租户级 Flow/Detector/Provider 解析、证据与
可观测性隔离、并发与容量隔离仍由后三个独立 change 完成。Phase 1 提案中的
`api-key-authentication` 在本设计中规范化为仓库已有 capability 名 `authentication`；这是命名映射，
不改变已确认行为边界。

## Project Principle Check

| 原则 | 本设计如何满足 | 风险或取舍 | 验证方式 |
|------|---------------|-----------|---------|
| Plugin / Flow；核心最小 | 核心只增加租户配置契约、认证绑定和不可变请求上下文；不加入租户专属检测或策略逻辑 | 身份上下文必须位于核心，供后续 Flow 解析消费；这是持久运行时机制而非领域能力 | 依赖边界审查；规格禁止本 change 解析 Flow、Detector 或 Provider |
| 策略显式；失败不静默 | 多租户为显式 opt-in；所有绑定矛盾在启动期拒绝；运行期缺失或无效凭据保持 fail-closed 401 | 不提供多租户默认回退，部署者必须为每个租户显式绑定凭据 | 启动失败矩阵、401 回归、无跨租户 fallback 测试 |
| 边界透明；契约稳定 | 不新增租户 Header，不改 HTTP/SSE/Provider 语义；旧配置进入固定兼容上下文 | 兼容上下文增加内部状态，但不改变客户端可见响应 | 旧配置 corpus 与真实 HTTP/SSE 回归；请求体和 Provider 调用等价性断言 |
| 决策有证据；数据默认保护 | 上下文只含有界租户 ID、来源和契约版本；API Key 不进入上下文、错误或日志 | 完整审计/metrics 租户隔离延后，本 change 只保证身份可供后续证据链消费 | 冻结模型、序列化字段、错误脱敏与 Header 伪造测试 |

**原则取舍**：多租户模式要求启用现有 API Key 认证，并拒绝无绑定租户；这牺牲了“匿名多租户”
的便利性，以换取明确的信任边界。没有原则偏离。

## Decisions

### 1. 显式 `tenancy` 配置块，默认关闭

**方案**：Gateway 顶层新增严格解析的 `tenancy`：

```yaml
tenancy:
  enabled: true
  tenants:
    - id: acme
    - id: globex

security:
  auth:
    enabled: true
    api_keys:
      - key: ${ACME_GATEWAY_KEY}
        name: acme-app
        tenant_id: acme
      - key: ${GLOBEX_GATEWAY_KEY}
        name: globex-app
        tenant_id: globex
```

`TenancyConfig` 和 `TenantConfig` 使用 `extra="forbid"`，避免安全字段拼写错误被 Pydantic 静默忽略。
`ApiKeyConfig.tenant_id` 为可选字段，仅为旧配置兼容；多租户启用后它必须存在。

**为什么**：显式开关可以清楚区分旧单租户语义和新安全边界，严格新模型不会扩大旧模型的破坏面。

**备选方案及排除原因**：

- 从多个 API Key 名称自动推断租户：显示名不是稳定身份，且重复名称会产生歧义。
- 每个租户复制完整 GatewayConfig：会在身份 change 中提前实现 Flow/Provider 解析并放大配置漂移。
- 直接把租户字段放进 Flow：身份信任根不能由被选择的策略本身决定。

### 2. 租户 ID 使用有界的小写 ASCII slug

**方案**：租户 ID 长度 1–64，匹配
`^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$`。多租户配置最多 1024 个租户、4096 个 API Key；
启动校验为 O(T+K)，请求解析为字典 O(1)。ID 区分于显示名称，不含密钥或用户输入。

**为什么**：规范化 slug 可避免大小写、Unicode 同形字符和无界 label，且适合后续配置键与证据引用。

**备选方案及排除原因**：

- 任意 Unicode：可读性高但存在规范化、同形字符和可观测性边界问题。
- UUID-only：稳定但降低自托管配置可读性，也迫使现有用户引入额外标识管理。
- 无上限字符串与列表：启动成本、内存与后续 cardinality 无法形成契约。

### 3. API Key 绑定是 v0.3.0 首个可信身份来源

**方案**：多租户模式复用现有 Bearer API Key。认证成功后，middleware 依据服务端预编译的
`key -> TenantContext` 映射解析租户。多租户模式要求认证开启、每个 key 具有非空且唯一的
`name`、每个 key 绑定已声明租户、每个租户至少有一个 key。重复密钥值、重复 key name、
未知绑定和未绑定租户均在启动期拒绝，错误不得回显密钥。

**为什么**：不引入新认证协议即可建立可信身份，并让 OAuth/JWT 后续通过同一个 Context 契约扩展。

**备选方案及排除原因**：

- 信任 `X-Tenant-ID`：任何持有一个有效 key 的客户端都可能切换到其他租户。
- 本 change 实现 JWT/OAuth：扩大认证攻击面，并违反 roadmap 的独立 STDD 边界。
- 运行期遇到未知绑定再 fallback：会把配置错误变成跨租户安全事件。

### 4. 启动期采用完整的 fail-closed 一致性矩阵

**方案**：以下状态在 `load_config()` 阶段以稳定、脱敏 reason code 拒绝：

| 状态 | reason code |
|------|-------------|
| tenancy 开启但 auth 关闭 | `tenancy_enabled_requires_auth` |
| tenancy 开启但租户列表为空 | `tenancy_requires_tenants` |
| 租户或 API Key 超过硬上限 | `tenant_limit_exceeded` / `tenant_api_key_limit_exceeded` |
| 重复租户 ID | `duplicate_tenant_id` |
| 多租户 key 缺少 tenant_id | `api_key_tenant_required` |
| key 绑定未知租户 | `unknown_api_key_tenant` |
| 重复密钥或重复/空 key name | `duplicate_api_key` / `invalid_api_key_name` |
| 空值或首尾空白导致不可认证的 key | `invalid_api_key` |
| 已声明租户没有任何 key | `tenant_without_api_key` |
| tenancy 关闭但仍声明租户或 tenant_id | `tenancy_disabled_with_tenant_configuration` |

新模型的非法 ID、未知字段和类型错误由 Pydantic 字段路径表达，并通过 `hide_input_in_errors` 避免
原始输入泄漏。validator 只输出 reason code 和安全的字段位置，不输出 key 值。

**为什么**：所有静态矛盾都能在接流量前发现，避免运行期猜测默认值。

**备选方案及排除原因**：

- 忽略矛盾字段：违反“失败不静默”。
- 允许未绑定租户待后续启用：当前没有动态控制面，该配置不可达且容易被误认为已隔离。
- 自动选择列表首项为默认租户：配置重排会改变安全行为。

### 5. 每个放行请求获得冻结的 `TenantContext v1.0`

**方案**：新增核心 `TenantContext`，字段固定为 `contract_version="1.0"`、`tenant_id`、
`identity_source`（`api_key` 或 `legacy_single_tenant`），并使用 frozen/slots 数据结构。
`AuthMiddleware` 在调用 Rate Limit 和路由前写入 `request.state.tenant_context`：

- 多租户 + 有效 key：绑定租户、来源 `api_key`；
- 旧 auth + 有效 key：固定租户 `default`、来源 `legacy_single_tenant`；
- auth 关闭的旧配置：固定租户 `default`、来源 `legacy_single_tenant`；
- 多租户缺失/无效 key：沿用现有 401，不创建或 fallback TenantContext。

现有 `request.state.api_key_name` 保留，避免影响 Rate Limit 和审计消费者。

**为什么**：冻结请求快照能保证并发请求和后续阶段看到同一身份，且不把凭据放入上下文。

**备选方案及排除原因**：

- 只传播字符串 `tenant_id`：缺少来源与契约版本，后续证据无法区分兼容入口。
- 每阶段重新查询全局配置：请求内身份可能随未来热更新漂移。
- 把 API Key 放入上下文：扩大秘密传播与日志泄漏面。

### 6. 不建立客户端租户选择 Header

**方案**：本版本不读取或定义 `X-Tenant-ID` 等客户端 Header。即使客户端发送该 Header，
解析结果也只由已认证 key 决定；Header 不改变租户、不进入 Context、不产生 Provider 协议改写。

**为什么**：最安全的伪造防护是让不可信输入不参与身份决策，同时避免创建新的公开协议承诺。

**备选方案及排除原因**：

- Header 与 key 一致才接受：仍会把 Header 变成公开契约，没有提供额外安全价值。
- 一律因 Header 返回 403：可能破坏携带同名自定义 Header 的透明代理客户端。

### 7. 单租户兼容入口没有配置迁移

**方案**：`tenancy` 缺失或显式关闭且没有租户字段时，所有当前合法配置继续加载。
唯一新增内部行为是为已放行请求注入 `default` 兼容上下文；HTTP 状态、错误体、Header、请求体、
SSE、Provider 路由、Detector/Flow 和 SDK 契约均不改变。旧 auth key 不要求 tenant_id。

**为什么**：v0.3.0 可以增量采用，不迫使现有自托管部署先完成租户迁移。

**备选方案及排除原因**：

- 立即要求所有 key 添加 tenant_id：破坏公开 v0.2.2 配置。
- 旧模式不创建 Context：后续每个 change 都要处理“可能没有身份”的隐式分支。

### 8. 规格证据覆盖配置、middleware 与真实 HTTP 接线

**方案**：单元测试分别锚定 schema/validator 和 frozen Context；middleware 测试锚定认证及伪造；
真实 `create_app` HTTP 集成测试证明 YAML 绑定被生产请求链消费，并回归 Provider 请求语义。
配置示例由 `load_config()` 契约测试反向校验。TC-ID 全局唯一并绑定真实 pytest 节点。

**为什么**：直接应用 EXP-2026-0005、EXP-2026-0008、EXP-2026-0022 和 EXP-2026-0023，防止
“配置能解析但生产链没消费”、错误示例、假 checkpoint 和异步测试漏映射。

**备选方案及排除原因**：

- 只测 Pydantic：不能证明 middleware 和请求路径使用租户身份。
- 只测 HTTP：启动失败原因和边界组合定位不清晰。
- 临时脚本而非 pytest 节点：无法形成持久、可追溯的质量门。

## Architecture

```text
Gateway YAML
   │
   ├─ tenancy.enabled=false/absent ───────► Legacy compatibility contract
   │                                           tenant_id=default
   │                                           source=legacy_single_tenant
   │
   └─ tenancy.enabled=true
          │
          ├─ TenantConfig[] ───────┐
          └─ Auth ApiKeyConfig[] ──┼─► startup validator (O(T+K), fail closed)
                                   │         │
                                   │         └─► key -> frozen TenantContext
                                   ▼
Client ─► RequestID ─► Auth/Tenant admission ─► RateLimit ─► Route ─► Provider
                              │
                              ├─ invalid/missing key ─► OpenAI-compatible 401
                              └─ valid/legacy request ─► request.state.tenant_context
                                                         │
                   future v0.3.0 changes consume only ────┘
                   Flow resolution / evidence / resources
```

主要实现边界：

```text
src/z_llm_safety_gateway/
├── tenancy/
│   ├── __init__.py
│   └── context.py          # frozen TenantContext v1.0 + legacy constant
├── config/
│   ├── models.py           # TenancyConfig/TenantConfig + ApiKeyConfig.tenant_id
│   └── validators.py       # cross-field startup failure matrix
├── middleware/auth.py      # trusted key -> TenantContext admission
└── app.py                  # validated tenancy config wiring only
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| API Key 绑定错误造成跨租户身份 | 全部绑定在启动期预编译和校验；运行期无默认跨租户回退 |
| 客户端 Header 伪造租户 | Header 不参与解析；集成测试使用 tenant A key + tenant B Header |
| 旧配置行为被新字段破坏 | tenancy 默认关闭、tenant_id 默认 None；旧 YAML corpus 与 HTTP/SSE 全量回归 |
| 配置错误泄露密钥 | Pydantic 隐藏输入；稳定 reason code；负向测试扫描 key 不出现在异常、响应或日志 |
| 租户 ID 造成无界内存或 label | 64 字符 slug、1024 tenants、4096 keys；请求期字典 O(1) |
| 冻结上下文被下游替换 | 数据对象本身不可变；本 change 不承诺防止任意应用代码重写 request.state 属性 |
| 严格拒绝无 key 租户降低预配置便利性 | 当前无动态控制面；要求配置只表达可实际使用的租户，未来控制面需独立 STDD |
| 认证单点限制未来 OAuth/JWT | Context 契约与 API Key 解耦，后续认证机制只需产出同一版本化 Context |
