# v0.3.0 租户身份与配置契约切片执行计划

## Dependency Graph Summary

CLI canonical dependency graph 报告 4 个零依赖 capability、0 条边、0 个 cycle。结合实现边界手工补充真实依赖：

```text
S1 Tenant schema + bounds
        │
        ├──────────────┐
        ▼              ▼
S2 Context/Auth     S3 Startup failure matrix
        └──────┬───────┘
               ▼
     S4 Request isolation + spoofing
               │
               ▼
     S5 Production YAML/HTTP compatibility
```

**并行化说明**：

- 组 1：S1 必须先行，建立共享 schema。
- 组 2：S2 与 S3 在 S1 后逻辑可并行；S2 主要修改 Context/Auth，S3 主要修改 validator。
- 组 3：S4 依赖 S2/S3，固定安全中间件和并发行为。
- 组 4：S5 最后贯穿 YAML → create_app → HTTP → downstream，并执行兼容回归。

实际 BUILD 在共享工作树中按拓扑顺序提交 RED/GREEN 证据，避免并行写同一配置模型造成不可审计交叉。

## Capability Risk Analysis

| Capability | 风险分 | 等级 | 依据 |
|------------|-------:|------|------|
| tenant-config-contract | 5 | 高 | 7 Scenarios、认证配置安全边界、EXP-0005 配置契约风险 |
| tenant-identity-context | 4 | 高 | 请求级并发上下文、EXP-0001 上下文贯穿、跨 middleware |
| authentication | 4 | 高 | 修改既有认证接口、fail-closed/secret-safety、中间件顺序 |
| config-system | 5 | 高 | 修改累计 schema、EXP-0008 生产接线缺口、真实 HTTP 兼容 |

## Slice Execution Plan

| # | 优先级 | 风险 | 工作量 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|--------|--------|---------|----------|------|
| S1 | P0/P1 | 高 | M | 组1 | TC-TCC-001/002/003/007 | 严格 tenant schema、slug、上限、identity-only 边界 | 无 |
| S2 | P0/P1 | 高 | M | 组2 | TC-TIC-001/004/005, TC-AUTH-008 | Frozen Context、legacy Context、Auth lookup 与 401 兼容 | S1 |
| S3 | P0 | 高 | M | 组2 | TC-TCC-004/005/006, TC-AUTH-009 | O(T+K) 启动失败矩阵和脱敏 reason code | S1 |
| S4 | P0 | 高 | M | 组3 | TC-TIC-002/003, TC-AUTH-010 | 并发隔离、Header 防伪、中间件顺序 | S2、S3 |
| S5 | P0 | 高 | M | 组4 | TC-CFG-701/702/703 | 文档 YAML、生产 create_app 消费、HTTP/Provider/Flow 兼容 | S2、S3、S4 |

## Rationale

### S1: Tenant schema 与边界

- **依赖关系**：所有后续身份绑定和 middleware 构造都依赖稳定的 TenancyConfig。
- **风险分析**：安全字段必须 strict；非法 Unicode/边界和 cardinality 是配置攻击面。
- **工作量估算**：4 TC，主要覆盖 config models 与 validator 基础，M。

### S2: TenantContext 与兼容认证

- **依赖关系**：依赖 S1 的 tenant_id 字段；不依赖完整 failure matrix，可与 S3 逻辑并行。
- **风险分析**：EXP-0001 指出请求上下文必须贯穿；必须保留旧 401 和 api_key_name。
- **工作量估算**：4 TC，新增 tenancy module 并修改 AuthMiddleware，M。

### S3: 启动期绑定失败矩阵

- **依赖关系**：依赖 S1 schema；为 S4/S5 提供“middleware 只接收已验证配置”的前置保证。
- **风险分析**：配置歧义可直接导致跨租户越权，采用稳定 reason code 和密钥负向扫描。
- **工作量估算**：4 参数化 TC、多类分支但集中于 validator，M。

### S4: 请求隔离、Header 伪造与顺序

- **依赖关系**：只有 Context 和 startup contract 同时稳定后，才能验证真实安全链。
- **风险分析**：认证/授权高风险；并发测试必须确定性，Header 不得成为隐式协议。
- **工作量估算**：3 TC，跨 Auth/RateLimit/ASGI 并发，M。

### S5: 生产 YAML、HTTP 接线与兼容

- **依赖关系**：最终集成切片消费前四片完整契约。
- **风险分析**：直接应用 EXP-0005/0008；防止“配置可解析但 create_app 未消费”。
- **工作量估算**：3 TC，涉及 config example、create_app、HTTP fake Provider 与旧协议回归，M。

## Coverage Check

- 10/10 Requirements 已映射。
- 18/18 Scenarios 与 18/18 TC 各归属一个切片。
- 0 个循环依赖；P0 关键路径先于 P1 边界验证完成。
- 四项原则均保留：核心仅身份机制、失败显式、协议兼容、上下文不含秘密。
