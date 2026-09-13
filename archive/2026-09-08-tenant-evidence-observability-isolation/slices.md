# 切片执行计划

## Dependency Graph Summary

CLI 将五项 capability 都列为零依赖，未发现环。实现依赖经人工补充如下：

```text
S1 配置与 ObservationContext
  ├── S2 审计与生命周期证据
  ├── S3 指标投影与基数边界
  └── S4 日志、Trace 与请求作用域
          └── S5 HTTP/SSE/后台集成与兼容回归
```

S2–S4 在设计上可并行，但会共同修改 app 装配、路由和测试夹具；为避免共享工作区冲突，按拓扑顺序串行执行。每个切片完成后运行聚焦测试和全量回归。

## 风险与工作量

| Capability | 场景 | 风险 | 工作量 | 依据 |
|---|---:|---:|---:|---|
| tenant-evidence-context | 6 | 5/5 高 | L | 认证、contextvars、流式和后台任务；EXP-0001、0026、0027 |
| audit-logger | 6 | 5/5 高 | L | 证据隐私、sink 故障与 SSE；EXP-0002、0010、0028 |
| prometheus-metrics | 5 | 5/5 高 | L | 基数、双 app 隔离和计数去重 |
| observability | 5 | 5/5 高 | L | Trace/log 投影、隐私与生命周期 |
| config-system | 4 | 4/5 高 | M | 启动校验、旧配置兼容；EXP-0005、0008 |

## Slice Execution Plan

| Slice | TC | 实现目标 | 风险 | 工作量 | parallel_group |
|---|---|---|---|---|---:|
| S1 Context and config | TEC-001, TEC-003, TEC-006, TOC-001, TOC-002 | `tenancy/observation.py`、严格观测配置、app 私有 runtime 和稳定失败映射 | 高 | L | 1 |
| S2 Audit evidence | TAU-001, TAU-003–006 | AuditEntry/DetectorLifecycleEvent 归属、序列化边界和 sink 故障诊断 | 高 | L | 2 |
| S3 Metric projection | TME-001–005 | 白名单聚合、有限计数器、旧指标投影与 app 隔离 | 高 | L | 3 |
| S4 Request/log/trace propagation | TEC-002, TEC-005, TOB-001–005 | 请求作用域、日志/Trace 安全投影、取消清理 | 高 | L | 4 |
| S5 End-to-end paths | TEC-004, TAU-002, TOC-003–004 | sync/async/SSE/background 真实接线、单租户兼容和路线文档 | 高 | L | 5 |

每个切片拥有至少一个新增自动化测试；S5 对所有路径做参数化集成验证。S1–S4 的单元测试不能代替 S5 的真实 ASGI 验证。

## Anchoring

S1 锚定可信身份和租户策略解析；S2/S3/S4 锚定 FlowEvidence v1.0 与既有审计/观测契约；S5 锚定既有 tenant policy HTTP/SSE 集成测试。所有切片保持 proposal 的 L3 参考 change 可追溯。
