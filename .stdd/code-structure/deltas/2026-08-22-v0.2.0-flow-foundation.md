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
