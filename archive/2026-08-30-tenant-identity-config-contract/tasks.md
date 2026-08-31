# v0.3.0 租户身份与配置契约任务清单

## 1. Tenant schema 与边界（P0）

- [x] 1.1 为 TC-TCC-001/002 编写租户 schema 与 ID 格式 RED 测试
- [x] 1.2 实现严格 `TenantConfig` / `TenancyConfig`、slug 约束与 GatewayConfig 接线
- [x] 1.3 为 TC-TCC-003 编写 cardinality RED 测试并实现 1024/4096 上限
- [x] 1.4 为 TC-TCC-007 编写 identity-only 边界测试，确认未引入后续 policy 字段
- [x] 1.5 运行 Slice 1 定向与既有 config 回归

## 2. TenantContext 与兼容认证（P0）

- [x] 2.1 为 TC-TIC-001/004/005 与 TC-AUTH-008 编写 RED 测试（依赖 #1）
- [x] 2.2 新增 frozen `TenantContext v1.0` 与 legacy default Context
- [x] 2.3 扩展 AuthMiddleware，保留 `api_key_name` 与既有 401，预编译 key lookup
- [x] 2.4 证明无效凭据不创建 Context、Context 不含 raw key、请求期不扫描配置
- [x] 2.5 运行 Slice 2 定向及既有 auth/rate-limit 回归

## 3. 启动期绑定失败矩阵（P0）

- [x] 3.1 为 TC-TCC-004/005/006 与 TC-AUTH-009 编写参数化 RED 测试（依赖 #1）
- [x] 3.2 实现 tenancy/auth 跨字段 O(T+K) validator 与稳定 reason code
- [x] 3.3 拒绝 auth 关闭、空租户、缺失/未知绑定、重复租户/key/name、无 key 租户
- [x] 3.4 拒绝 disabled tenancy 的矛盾字段并保护纯 legacy 配置
- [x] 3.5 验证异常与日志不包含 API Key 值

## 4. 请求隔离、Header 伪造与中间件顺序（P0）

- [x] 4.1 为 TC-TIC-002/003 与 TC-AUTH-010 编写并发和真实 ASGI RED 测试（依赖 #2、#3）
- [x] 4.2 确保 `RequestID → Auth/TenantContext → RateLimit → route` 顺序
- [x] 4.3 验证两个并发请求 Context 隔离且 frozen
- [x] 4.4 验证 `X-Tenant-ID` 不覆盖服务端绑定、不形成公开协议
- [x] 4.5 验证 401/request ID/secret-safety 兼容

## 5. 生产 YAML、HTTP 接线与兼容（P0）

- [x] 5.1 为 TC-CFG-701/702/703 编写真实 `load_config` / `create_app` RED 测试（依赖 #2、#3、#4）
- [x] 5.2 增加可运行的环境变量多租户配置示例
- [x] 5.3 将 validated tenancy 传入生产 AuthMiddleware
- [x] 5.4 验证 acme/globex 请求下游 Context、全局 Provider/Flow 不变
- [x] 5.5 回归现有 gateway.yaml、gateway.prod.yaml、chat 与 streaming 行为

## 6. 全量验证（P0）

- [x] 6.1 校验 18/18 TC 与 18/18 canonical checkpoints 真实可收集
- [x] 6.2 校验 TC-ID 全仓唯一与 sync/async pytest traceability
- [x] 6.3 全量 pytest + coverage 通过且覆盖率不下降
- [x] 6.4 Ruff 与 Mypy 通过
- [x] 6.5 Python 3.10、3.11、3.12 质量矩阵通过
- [x] 6.6 完成 12 类失败模式检查、安全/性能审查和 Gate 3 材料
