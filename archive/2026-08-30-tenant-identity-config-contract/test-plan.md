# v0.3.0 租户身份与配置契约测试方案

> 版本：v0.3.0 implementation change 1/4
> 创建日期：2026-08-30
> 对应 Phase 2 Spec：tenant-config-contract、tenant-identity-context、authentication、config-system

## 一、测试策略

### 1.1 测试金字塔

- **单元层（12 个 TC）**：Pydantic schema、跨字段失败矩阵、frozen Context、middleware 身份解析、并发隔离与 O(1) 预编译映射。
- **应用集成层（6 个 TC，其中 3 个与 middleware 单元共享真实 ASGI 边界）**：`create_app`、生产中间件顺序、YAML 环境变量、真实 HTTP 请求和 Provider/Flow 兼容。
- **全量回归层**：全部 pytest、Ruff、Mypy、覆盖率，以及 Python 3.10–3.12 质量矩阵。此 change 不访问付费 Provider。

### 1.2 测试原则

- 严格 RED→GREEN→REFACTOR；18 个新 Scenario 均先绑定唯一失败测试节点。
- 参数化失败矩阵必须逐个断言稳定 reason code，不允许“任意异常即通过”。
- 负向测试扫描响应、异常和日志，确保 API Key 原值不泄露。
- 不只证明配置被接受；必须从 YAML 经 `create_app` 到真实请求下游证明 Context 被消费。
- Header 伪造用 tenant A key + tenant B claim，断言服务端绑定胜出且 Provider 语义不变。
- 并发测试使用显式同步边界，不依赖 wall clock 或调度运气。
- Agent checkpoint 必须在实现后通过 `pytest --collect-only` 和全仓 TC-ID 唯一性检查。

### 1.3 已有测试资产

| 测试文件/集合 | 当前用例数 | 类型 | 覆盖范围 |
|---------------|-----------:|------|----------|
| `tests/unit/middleware/test_auth.py` | 7 | 单元/ASGI | Bearer allow/401、密钥脱敏、api_key_name、Request ID 顺序（既有 AUTH 001–007） |
| `tests/unit/config/test_models.py` + `test_v4_security.py` | 8 | 单元 | Gateway/Pydantic 基础模型和 SecurityConfig/AuthConfig |
| `tests/unit/test_v4_fastapi_server.py` | 14 | 单元/应用集成 | `create_app` 中间件接线、认证、限流及请求保护 |
| `tests/integration/test_chat.py` + `test_streaming.py` | 24 | 集成 | 非流式/流式 HTTP 与 Provider 透明代理 |
| 上述选择性 collection 合计 | 53 | 回归基线 | Phase 2 实测 collect-only 结果 |

## 二、详细测试案例

### 2.1 tenant-config-contract

| 字段 | ID | 对应 Scenario | 优先级 | Arrange / Act | Assert / 初始状态 |
|------|----|---------------|--------|---------------|-------------------|
| **ID** | TC-TCC-001 | SC-TCC-001 | P0 | 构造两个合法租户和各自绑定 key，调用 `load_config` | ✅ 严格 schema、slug、绑定均解析；声明顺序不产生默认租户 |
| **ID** | TC-TCC-002 | SC-TCC-002 | P0 | 参数化空值、大小写、空格、Unicode、路径符、首尾分隔符和超长 ID | ✅ 每项启动前失败；字段路径明确且无 key 泄漏 |
| **ID** | TC-TCC-003 | SC-TCC-003 | P1 | 分别构造 1025 tenants 和 4097 keys | ✅ 返回对应 limit reason code；校验只线性遍历声明 |
| **ID** | TC-TCC-004 | SC-TCC-004 | P0 | 参数化 auth 关闭、空租户列表、key 缺 tenant_id | ✅ 精确命中三个稳定 reason code；不自动修复 |
| **ID** | TC-TCC-005 | SC-TCC-005 | P0 | 参数化重复 ID、未知绑定、重复 key、重复/空 name、无 key 租户 | ✅ 精确失败；无 fallback；异常和日志不含密钥 |
| **ID** | TC-TCC-006 | SC-TCC-006 | P0 | tenancy 关闭时分别加入 tenants/tenant_id，并提供纯旧配置对照 | ✅ 矛盾配置失败；旧配置成功 |
| **ID** | TC-TCC-007 | SC-TCC-007 | P1 | 检查 tenancy canonical model 字段并运行有效请求 | ✅ schema 不含后续 policy；全局配置仍生效 |

### 2.2 tenant-identity-context

| 字段 | ID | 对应 Scenario | 优先级 | Arrange / Act | Assert / 初始状态 |
|------|----|---------------|--------|---------------|-------------------|
| **ID** | TC-TIC-001 | SC-TIC-001 | P0 | tenant acme 的有效 key 进入 AuthMiddleware | ✅ Context v1.0/acme/api_key、frozen、无 token；api_key_name 保留 |
| **ID** | TC-TIC-002 | SC-TIC-002 | P0 | 两个租户请求在显式并发屏障后同时进入下游 | ✅ Context 互不覆盖；Rate Limit/route 在身份之后 |
| **ID** | TC-TIC-003 | SC-TIC-003 | P0 | acme key 携带 `X-Tenant-ID: globex` | ✅ Context 仍为 acme；Header 不进入 Context；Provider 语义不变 |
| **ID** | TC-TIC-004 | SC-TIC-004 | P0 | 缺失及错误 Bearer token | ✅ 现有 401；不创建 default/其他 Context；不泄密 |
| **ID** | TC-TIC-005 | SC-TIC-005 | P1 | 以最大合法配置构造 middleware，并用可观察映射执行请求 | ✅ 构造期预编译、请求期字典查找；下游不接触 raw key |

### 2.3 authentication

| 字段 | ID | 对应 Scenario | 优先级 | Arrange / Act | Assert / 初始状态 |
|------|----|---------------|--------|---------------|-------------------|
| **ID** | TC-AUTH-008 | SC-AUTH-008 | P0 | 旧 auth key/name 无 tenant_id，发送有效请求 | ✅ 原 allow/api_key_name/响应不变；内部 Context 为 default/legacy |
| **ID** | TC-AUTH-009 | SC-AUTH-009 | P0 | 已验证的多租户 auth 配置构造 middleware | ✅ key→Context 只编译一次；重复 key 不会覆盖 |
| **ID** | TC-AUTH-010 | SC-AUTH-010 | P0 | 真实中间件链分别发送有效和无效请求 | ✅ 中间件顺序、401/request ID 兼容且无秘密 |

### 2.4 config-system

| 字段 | ID | 对应 Scenario | 优先级 | Arrange / Act | Assert / 初始状态 |
|------|----|---------------|--------|---------------|-------------------|
| **ID** | TC-CFG-701 | SC-CFG-701 | P0 | 加载 gateway.yaml、prod YAML、旧 fixtures 并复跑 HTTP/SSE 用例 | ✅ 无迁移；协议行为不变；只新增内部 default Context |
| **ID** | TC-CFG-702 | SC-CFG-702 | P0 | 文档多租户 YAML 使用环境变量 key，经 `load_config` 加载 | ✅ 路径与模型一致；配置有效；输出/日志不含插值 key |
| **ID** | TC-CFG-703 | SC-CFG-703 | P0 | `create_app` 加载 acme/globex YAML，各发送真实 HTTP 请求 | ✅ 下游看到对应 Context；身份不共享；全局行为不变 |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 应用集成 | 全量回归 | 状态 |
|----------|----------|----------|----------|------|
| Tenancy schema 与 identifier | schema/格式/上限案例 | 文档配置加载 | config-system | ✅ 已实现 |
| 启动期失败矩阵 | 必填/歧义/关闭模式案例 | create_app invalid-config | startup/config | ✅ 已实现 |
| 请求 TenantContext | 绑定/并发/查找案例 | 双租户真实请求 | auth/rate-limit/routes | ✅ 已实现 |
| Header 伪造与 401 | 伪造/无效凭据案例 | 生产中间件顺序 | HTTP/SSE | ✅ 已实现 |
| 单租户兼容 | legacy auth 案例 | 旧配置与协议回归 | 全量 pytest + Python 矩阵 | ✅ 已验证 |
| 范围边界 | identity-only schema 案例 | Provider/Flow 行为断言 | diff/架构审查 | ✅ 已验证 |

## 四、回归风险矩阵

| 风险区域 | v0.3.0 change 1 改动 | 已有回归保护 | 风险等级 |
|----------|----------------------|--------------|----------|
| API Key 认证 | 增加 tenant_id 与 Context 编译 | 既有 AUTH 001–007、test_v4_fastapi_server | 🔴 高 |
| 中间件顺序 | Auth 在 Rate Limit 前注入 Context | Request ID/Auth/Rate Limit tests | 🔴 高 |
| 配置启动 | 新增顶层 tenancy 与跨字段 validator | config models/validators/startup tests | 🔴 高 |
| 单租户兼容 | 每个放行请求增加内部 default Context | chat/streaming/provider/Flow 全量回归 | 🔴 高 |
| 秘密保护 | 新错误矩阵可能接触 raw key | 现有 401 no-leak + 新负向扫描 | 🔴 高 |
| Provider/Flow/Detector | 本 change 不应改变解析和执行 | 集成、Flow、streaming suites | 🟡 中 |
| 性能/资源 | 构造 O(T+K)，请求 O(1) | cardinality 与 lookup 定向案例 | 🟡 中 |

## 五、建议补充顺序

1. **P0 — 配置信任根**：先完成合法 schema、非法 ID、必填项、歧义绑定和关闭模式案例。
2. **P0 — 请求身份**：再完成绑定、并发隔离、Header 伪造、401 和认证兼容案例。
3. **P0 — 生产接线与兼容**：完成旧配置、文档示例和双租户真实 HTTP 案例。
4. **P1 — 边界与成本**：最后完成 cardinality、identity-only 边界和 O(1) 查找案例。
5. **最终质量门**：18/18 TC、pytest 全量、Ruff、Mypy、覆盖率、Python 3.10–3.12、canonical checkpoints 和 TC-ID 全局唯一性。
