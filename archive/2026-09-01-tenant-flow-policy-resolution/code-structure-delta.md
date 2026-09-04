# Code Structure Delta — 2026-09-01-tenant-flow-policy-resolution
> 生成时间: 2026-09-01T23:09:39.835478 | Git commit: e342d39
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

### 新增

- `src/z_llm_safety_gateway/tenancy/policy.py` — safe policy Context、私有 runtime bundle 与 O(1) resolver。
- `src/z_llm_safety_gateway/tenancy/runtime.py` — per-policy Flow/Detector/status 编译及有界清理。
- `src/z_llm_safety_gateway/middleware/policy_resolution.py` — Auth 后、admission 前的 fail-closed 解析层。
- `tests/unit/tenancy/`、`tests/unit/providers/test_tenant_router.py`、`tests/unit/routes/test_tenant_policy_snapshot.py`、`tests/integration/test_tenant_policy_runtime.py` — policy/runtime/router/snapshot 证据。

### 修改

- `src/z_llm_safety_gateway/config/` — strict tenant policy schema、上限、引用与 source conflict 验证，secret repr 保护。
- `src/z_llm_safety_gateway/app.py` — production bundle 编译、Router view 装配、生命周期 evidence 与 cleanup。
- `src/z_llm_safety_gateway/routes/` — chat sync/async/SSE/buffer/post-audit 与 models 使用同一 captured bundle；readiness 聚合 tenant registries。
- `src/z_llm_safety_gateway/providers/router.py` — immutable、bounded tenant Router view，复用 Provider adapters。
- `src/z_llm_safety_gateway/pipeline/snapshot.py` — policy-local Flow/config/status 的递归不可变 snapshot。
- `src/z_llm_safety_gateway/flow/detector_adapter.py` — health-check 原因码与生命周期区分。
- `src/z_llm_safety_gateway/plugins/grpc/client.py`、内置 Detector 日志 — 配置身份和 routine-log 数据最小化。
- `config/gateway.multi-tenant.example.yaml` 与项目文档 — 两租户可执行示例和 v0.3.0 2/4 进度。

### 架构边界

- Flow core 不导入 tenancy、Detector、Provider 域；租户选择停留在 tenancy/app/route 装配边界。
- Provider adapter 仍为 app-scoped 私有对象；tenant view 仅持允许的规则与显式 models Provider。
- legacy single-tenant path 保持原有 global runtime；仅 tenancy enabled 时强制完整 bundle。
