# 项目代码结构索引

## 2026-08-19-detector-readiness-fail-safe

# Code Structure Delta — 2026-08-19-detector-readiness-fail-safe

## 变更文件

- `DESIGN.md`
- `archive/2026-08-19-detector-readiness-fail-safe/.stdd.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/design-adjustments.md`
- `archive/2026-08-19-detector-readiness-fail-safe/design-adjustments.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/design.md`
- `archive/2026-08-19-detector-readiness-fail-safe/phase-context.md`
- `archive/2026-08-19-detector-readiness-fail-safe/proposal.md`
- `archive/2026-08-19-detector-readiness-fail-safe/proposal.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/slices.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/audit-logger/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/audit-logger/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/audit-logger/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/config-system/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/config-system/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/config-system/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/degraded-safety-visibility/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/degraded-safety-visibility/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/degraded-safety-visibility/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/detector-framework/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/detector-framework/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/detector-framework/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/detector-lifecycle-status/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/detector-lifecycle-status/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/detector-lifecycle-status/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/fastapi-server/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/fastapi-server/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/fastapi-server/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/health-endpoints/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/health-endpoints/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/health-endpoints/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/prometheus-metrics/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/prometheus-metrics/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/prometheus-metrics/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/required-detector-policy/agent_spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/required-detector-policy/spec.md`
- `archive/2026-08-19-detector-readiness-fail-safe/specs/required-detector-policy/spec.yaml`
- `archive/2026-08-19-detector-readiness-fail-safe/tasks.md`
- `archive/2026-08-19-detector-readiness-fail-safe/test-plan.md`
- `archive/2026-08-19-detector-readiness-fail-safe/test-report.md`
- `docs/api-spec.md`
- `docs/configuration.md`
- `specs/audit-logger/spec.md`
- `specs/audit-logger/spec.yaml`
- `specs/config-system/spec.md`
- `specs/config-system/spec.yaml`
- `specs/degraded-safety-visibility/spec.md`
- `specs/degraded-safety-visibility/spec.yaml`
- `specs/detector-framework/spec.md`
- `specs/detector-framework/spec.yaml`
- `specs/detector-lifecycle-status/spec.md`
- `specs/detector-lifecycle-status/spec.yaml`
- `specs/fastapi-server/spec.md`
- `specs/fastapi-server/spec.yaml`
- `specs/health-endpoints/spec.md`
- `specs/health-endpoints/spec.yaml`
- `specs/prometheus-metrics/spec.md`
- `specs/prometheus-metrics/spec.yaml`
- `specs/required-detector-policy/spec.md`
- `specs/required-detector-policy/spec.yaml`
- `src/z_llm_safety_gateway/app.py`
- `src/z_llm_safety_gateway/audit/logger.py`
- `src/z_llm_safety_gateway/audit/models.py`
- `src/z_llm_safety_gateway/config/models.py`
- `src/z_llm_safety_gateway/config/validators.py`
- `src/z_llm_safety_gateway/detectors/__init__.py`
- `src/z_llm_safety_gateway/detectors/registry.py`
- `src/z_llm_safety_gateway/detectors/status.py`
- `src/z_llm_safety_gateway/exceptions.py`
- `src/z_llm_safety_gateway/observability/metrics.py`
- `src/z_llm_safety_gateway/plugins/grpc/client.py`
- `src/z_llm_safety_gateway/routes/chat.py`
- `src/z_llm_safety_gateway/routes/health.py`
- `tests/integration/test_health_headers.py`
- `tests/unit/audit/test_detector_availability_audit.py`
- `tests/unit/config/test_detector_required.py`
- `tests/unit/detectors/test_registry.py`
- `tests/unit/detectors/test_status_registry.py`
- `tests/unit/observability/test_detector_availability_metrics.py`
- `tests/unit/plugins/grpc/test_client.py`
- `tests/unit/routes/test_availability_guard.py`
- `tests/unit/routes/test_detector_readiness.py`
- `tests/unit/routes/test_health.py`
- `tests/unit/test_detector_initialization.py`
- `tests/unit/test_startup_policy.py`

## 2026-08-20-v0.1.1-release-hardening (2026-08-22)
> Git commit: 4464e26

# Code Structure Delta — 2026-08-20-v0.1.1-release-hardening
> 生成时间: 2026-08-22T20:42:26.001163 | Git commit: 4464e26
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `.github/dependabot.yml`
- `pyproject.toml`
- `sdk/pyproject.toml`
- `sdk/src/z_llm_safety_gateway_sdk/cli.py`
- `src/z_llm_safety_gateway/__init__.py`
- `Dockerfile`
- `docker-compose.prod.yml`
- `config/gateway.prod.yaml`
- `examples/plugins/python-grpc/Dockerfile`
- `examples/plugins/python-grpc/src/acme_grpc_detector/server.py`
- `tests/unit/release/`
- `tests/unit/stdd/`
- `tools/benchmark_report.py`
- `tools/release_checks.py`
- `tools/stdd_backfill.py`
- `bin/stdd`
- `stdd/cli/`

---

## 2026-08-22-v0.2.0-flow-foundation (2026-08-23)
> Git commit: f1e26f1

# Code Structure Delta — 2026-08-22-v0.2.0-flow-foundation
> 生成时间: 2026-08-22T22:28:06.021973 | Git commit: f1e26f1
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

### 新增运行时与边界模块

- `src/z_llm_safety_gateway/flow/contracts.py` — 版本化 Flow/Node/Capability 契约与图校验
- `src/z_llm_safety_gateway/flow/policy.py` — 启动期完整策略解析与稳定失败分类
- `src/z_llm_safety_gateway/flow/runtime.py` — 有界调度、嵌套、停止、取消与 reducer 时限
- `src/z_llm_safety_gateway/flow/evidence.py` — Node/Flow 证据、隐私过滤、长身份/策略指纹与完整 envelope 预算
- `src/z_llm_safety_gateway/flow/detector_adapter.py` — Detector SDK 到 Capability 的边界适配
- `src/z_llm_safety_gateway/flow/legacy.py` — legacy YAML 到默认 Flow 的确定性编译
- `src/z_llm_safety_gateway/pipeline/flow_reducer.py` — detector 领域结果 reducer
- `src/z_llm_safety_gateway/pipeline/snapshot.py` — 请求级不可变执行/可用性快照
- `src/z_llm_safety_gateway/audit/streaming_evidence.py` — streaming 证据有界聚合
- `src/z_llm_safety_gateway/observability/flow.py` — Flow/Node 指标与隐私受限 trace 投射

### 主要修改边界

- `app.py` / `config/models.py` — 显式 Flow 装配、legacy 配置兼容、启动校验与资源上限
- `pipeline/engine.py` — 公开 facade 保持不变，内部单一路径委托 Flow Runtime
- `routes/chat.py` / `streaming/handler.py` / `post_audit/audit.py` — 六条执行路径复用同一 snapshot 并传递证据
- `audit/models.py` / `audit/logger.py` — 加法式 Flow 字段、真实 file-handler I/O 失败与 sink 可见性
- `observability/metrics.py` — 低基数 Flow、Node、降级与持久化失败指标
- `tools/benchmark_report.py` / `tests/benchmarks/bench_pipeline.py` — Flow Foundation 锁定性能门、warmup 与 best-of-five 测量
- `tests/unit/flow/`、`tests/unit/pipeline/`、`tests/unit/audit/`、`tests/integration/` — 契约、策略、运行时、HTTP/SSE 与兼容回归

未新增 K8s、Redis、Provider、UI 或新 detector 产品能力。

---

## 2026-08-23-v0.2.1-release-version-hotfix (2026-08-24)
> Git commit: d67d573

# Code Structure Delta — 2026-08-23-v0.2.1-release-version-hotfix
> 生成时间: 2026-08-24T22:51:23.921438 | Git commit: d67d573
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

---

## 2026-08-25-v0.2.2-release-reproducibility (2026-08-26)
> Git commit: c8daffc

# Code Structure Delta — 2026-08-25-v0.2.2-release-reproducibility
> 生成时间: 2026-08-25T21:46:31.482791 | Git commit: c8daffc
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

---

## 2026-08-28-codex-only-stdd-adaptation (2026-08-28)
> Git commit: 3f358ec

# Code Structure Delta — 2026-08-28-codex-only-stdd-adaptation
> 生成时间: 2026-08-28T14:43:23.340482 | Git commit: 3f358ec
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

- `GATE1_APPROVED`
- `GATE2_APPROVED`
---

## 2026-08-28-codex-only-stdd-adaptation (2026-08-28)
> Git commit: 3f358ec

# Code Structure Delta — 2026-08-28-codex-only-stdd-adaptation
> 生成时间: 2026-08-28T14:43:23.340482 | Git commit: 3f358ec
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

- `GATE1_APPROVED`
- `GATE2_APPROVED`
---

## 2026-08-28-rate-limit-deterministic-concurrency (2026-08-28)
> Git commit: aaf14c6

# Code Structure Delta — 2026-08-28-rate-limit-deterministic-concurrency
> 生成时间: 2026-08-28T19:37:15.359138 | Git commit: aaf14c6
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

- `GATE1_APPROVED`
- `GATE2_APPROVED`

## Verify 手工复核补充

> `stdd structure delta` 当前只枚举 change 目录中的结构标记，未识别工作树里的 Python
> 修改；以下列表由 `git diff --name-only` 与实际符号检查补充，不替代生成器输出。

- `src/z_llm_safety_gateway/ratelimit/token_bucket.py`
  - `TokenBucket.__init__` 新增 keyword-only `clock` 依赖，默认保持 `time.monotonic`。
  - `_refill` 改用实例时钟；消费锁与公开方法不变。
- `tests/unit/middleware/test_rate_limit.py`
  - 新增 `_FakeClock`。
  - 重写 `test_concurrent_safety`，新增 4 个可收集的确定性检查点。

---

## 2026-08-30-v0.3.0-milestone-roadmap (2026-08-30)
> Git commit: 0c3b876

# Code Structure Delta — 2026-08-30-v0.3.0-milestone-roadmap
> 生成时间: 2026-08-30T16:46:06.795412 | Git commit: 0c3b876
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

本 change 仅修改项目文档和文档契约测试，不改变运行时代码结构；无模块结构 delta。

---

## 2026-08-30-tenant-identity-config-contract (2026-08-31)
> Git commit: 98505a0

# Code Structure Delta — 2026-08-30-tenant-identity-config-contract
> 生成时间: 2026-08-31T20:27:52.640437 | Git commit: 98505a0
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

- `GATE1_APPROVED`
- `GATE2_APPROVED`
---

## 2026-09-01-tenant-flow-policy-resolution (2026-09-05)
> Git commit: e342d39 (pre-delivery baseline)

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

---

## 2026-09-08-tenant-evidence-observability-isolation (2026-09-13)
> Git commit: d2b3634

# Code Structure Delta — 2026-09-08-tenant-evidence-observability-isolation
> 生成时间: 2026-09-12T19:29:49.170745 | Git commit: d2b3634
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

- `review/existing-test-assets.txt`
- `review/experiences.json`
- `review/extracted-proposal.json`
- `review/validation.json`
---
