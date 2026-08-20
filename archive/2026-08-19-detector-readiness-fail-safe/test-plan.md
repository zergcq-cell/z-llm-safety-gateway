# Test Plan — Detector Readiness Fail-Safe

## 1. 策略

严格执行 RED → GREEN → REFACTOR。单元测试覆盖配置、状态机、策略计算、审计模型与指标；集成测试覆盖 FastAPI lifespan、`/health`、`/ready`、chat sync/stream/async 和 Provider 未调用断言；参数化契约测试覆盖 built-in、ML、in-process plugin、gRPC sidecar。

优先级：P0 为安全或启动准入门；P1 为恢复/可观测契约；P2 为禁用模式回归。共 36 个检查点：P0=26、P1=9、P2=1。

## 2. 测试用例

| ID | Spec | P | Arrange | Act | Assert |
|---|---|---:|---|---|---|
| TC-DLS-001 | SC-DLS-001 | P0 | input/output 同名配置 | 注册两项 | 身份不冲突、app 隔离 |
| TC-DLS-002 | SC-DLS-002 | P0 | 成功 factory + event sink | 初始化 | configured→initializing→healthy；无重复事件 |
| TC-DLS-003 | SC-DLS-003 | P0 | 异常含秘密的 factory | 初始化 | unavailable；仅 initialization_error |
| TC-DLS-004 | SC-DLS-004 | P1 | 健康先失败后成功 | 两次 health refresh | unhealthy 后恢复 healthy |
| TC-RDP-001 | SC-RDP-001 | P0 | 四类 required factory 分别失败 | 启动 lifespan | 全部抛启动异常且不接流量 |
| TC-RDP-002 | SC-RDP-002 | P0 | 已创建 detectors + audit sink 后 required 失败 | 中止启动 | 逆序 shutdown，audit flush/close |
| TC-RDP-003 | SC-RDP-003 | P0 | optional fail_closed 初始化失败 | 启动并请求 | 进程存活、ready 503、业务 503 |
| TC-RDP-004 | SC-RDP-004 | P0 | optional fail_open 初始化失败 | 启动并请求 | ready 200 degraded，请求继续且跳过 |
| TC-RDP-005 | SC-RDP-005 | P0 | 混合 required/fail_closed/fail_open 问题 | 计算决策 | 最严格结果；issues 稳定排序 |
| TC-DSV-001 | SC-DSV-001 | P1 | fail-open 故障 + audit capture | 完成请求 | safety_degraded=true；availability 完整 |
| TC-DSV-002 | SC-DSV-002 | P0 | fail-closed 故障 + log/audit capture | 请求 chat | 503 且日志/审计有稳定状态 |
| TC-DSV-003 | SC-DSV-003 | P0 | 异常含 token/endpoint/body | 触发所有信号 | API/log/audit/metric 无敏感原文 |
| TC-CFG-601 | SC-CFG-601 | P0 | required 省略/true/false、双方向 | 加载并提取 | 默认 false；显式值原样保留 |
| TC-CFG-602 | SC-CFG-602 | P0 | required=true + fail_open | 加载配置 | ValidationError 指明组合非法 |
| TC-CFG-603 | SC-CFG-603 | P0 | required=true + enabled=false | 加载配置 | ValidationError 指明不能禁用 |
| TC-DF-601 | SC-DF-601 | P0 | 四类 detector adapter | 初始化 | 同一协调器、相同状态/策略路径 |
| TC-DF-602 | SC-DF-602 | P0 | factory 抛错/返回无实例 | 初始化 | unavailable；无 sentinel 进入 pipeline |
| TC-DF-603 | SC-DF-603 | P1 | loaded 与 unavailable 混合 | health + shutdown | 仅 loaded 收到调用 |
| TC-HEALTH-601 | SC-HEALTH-601 | P0 | 无 detector/全健康，两个 app | 请求 health/ready | liveness 独立；200 ready；app 不串状态 |
| TC-HEALTH-602 | SC-HEALTH-602 | P0 | required/fail_closed issue | GET /ready | 503 not_ready；摘要计数/排序精确 |
| TC-HEALTH-603 | SC-HEALTH-603 | P1 | 仅 fail_open issue | GET /ready | 200 ready，degraded=true，schema 精确 |
| TC-HEALTH-604 | SC-HEALTH-604 | P0 | health 抛错或超时 | GET /ready | 有界返回；exception/timeout reason_code |
| TC-HEALTH-605 | SC-HEALTH-605 | P0 | health 失败后恢复 | 两次 GET /ready | 503→200 或 degraded→ready；状态事件一次 |
| TC-FAST-601 | SC-FAST-601 | P0 | 成功/失败 input/output 配置 | 启动 app | app state 含全部配置状态 |
| TC-FAST-602 | SC-FAST-602 | P0 | required factory 失败 | 启动 lifespan | 异常传播；ready 从未为 true |
| TC-FAST-603 | SC-FAST-603 | P0 | input 严格 issue + provider spy | POST chat | 精确 503 body/header；provider=0 |
| TC-FAST-604 | SC-FAST-604 | P0 | output 严格 issue + sync/stream/async provider spies | 各路径 POST | 全部 provider=0 且精确 503 |
| TC-FAST-605 | SC-FAST-605 | P0 | fail-open issue + detector/provider spies | POST chat | 故障 detector=0；provider=1；快照传递 |
| TC-AUDIT-601 | SC-AUDIT-601 | P1 | lifecycle audit sink | 变化并重复写状态 | 字段精确；重复状态不新增 |
| TC-AUDIT-602 | SC-AUDIT-602 | P0 | required 失败；audit enabled/disabled | 中止启动 | enabled 可读持久事件；disabled 有日志 |
| TC-AUDIT-603 | SC-AUDIT-603 | P1 | 两个 fail-open issues | 完成请求 | degraded true；availability 稳定排序 |
| TC-AUDIT-604 | SC-AUDIT-604 | P0 | 恶意敏感异常 | 写两类审计 | 仅 reason_code/配置元数据 |
| TC-PROM-601 | SC-PROM-601 | P1 | 隔离 registry + 初始化失败 | scrape | counter 名称、值、四标签精确 |
| TC-PROM-602 | SC-PROM-602 | P1 | 状态连续转换 | scrape | up gauge 1→0→1；无异常标签 |
| TC-PROM-603 | SC-PROM-603 | P1 | 两个 fail-open detector + 一次请求 | scrape | 各 detector counter +1，不重复 |
| TC-PROM-604 | SC-PROM-604 | P2 | metrics disabled | 触发全部 metrics API | 不抛错、决策不变、无注册冲突 |

## 3. 失败模式矩阵

| 阶段 | 类型 | required/fail_closed | optional fail_closed | optional fail_open |
|---|---|---|---|---|
| 初始化 | built-in / ML / in-process / gRPC | 启动失败、清理、审计 | 存活诊断、ready 503、业务 503 | ready 200 degraded、跳过 |
| 健康检查 | loaded detector exception/timeout | ready 503、业务 503、可恢复 | ready 503、业务 503、可恢复 | ready 200 degraded、跳过、可恢复 |
| 请求 detect 瞬时异常 | 任意 | 既有 fail-closed Pipeline 行为 | 既有 fail-closed Pipeline 行为 | 既有 fail-open Pipeline 行为 |

## 4. 回归范围

- 现有配置省略 `required` 时仍能加载。
- `/health` 响应与 liveness 语义不变。
- 正常 `/ready` 的 `status=ready` 保持兼容。
- 正常 input/output Pipeline、同步/流式/异步响应不回归。
- 插件发现、gRPC 同步 stub/off-thread、circuit breaker 算法不变。
- audit disabled、metrics disabled 路径不改变业务行为。

## 5. 执行顺序与门槛

1. 配置与状态模型单元测试（RED/GREEN）。
2. 共同初始化协调器与 fatal cleanup（RED/GREEN）。
3. readiness 健康检查与恢复（RED/GREEN）。
4. chat preflight、错误契约与 Provider 未调用（RED/GREEN）。
5. 审计/日志/指标（RED/GREEN）。
6. 相关测试 → 全量 pytest + coverage → ruff → mypy。

任一 P0 未通过、Provider 在严格故障下被调用、敏感异常泄露、覆盖率下降或 Gate 3 失败模式检查未完成，均不得进入 Deliver。
