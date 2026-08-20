# Design — 检测器初始化失败与 Readiness Fail-Safe 加固

## 1. 目标与边界

本变更消除“检测器配置存在但初始化失败，网关仍 ready 且请求静默绕过检测”的路径。它统一 built-in、ML、已配置的 in-process plugin 与 gRPC sidecar 的启动、健康、readiness、业务准入和可观测语义。

不在本变更中实现热加载、无限重试、sidecar 自动拉起、Provider failover、新检测器或检测算法重构。未配置的损坏 entry point 继续沿用既有发现告警与跳过策略。

## 2. 设计原则

1. `required` 决定启动准入，`on_error` 决定非 required 检测器故障时的请求策略；两者不得混为一谈。
2. 安全状态由应用实例持有，不使用模块全局变量，也不伪造占位 Detector。
3. `/health` 只表示进程存活；`/ready` 表示实例能否安全接流量，并显式报告降级。
4. fail-closed 约束必须在业务入口执行，即使客户端绕过负载均衡直接访问实例，也不能静默放行。
5. 所有外部可见原因使用稳定、脱敏、低基数的 `reason_code`；原始异常不得进入 API、审计或指标标签。

## 3. 配置模型与策略矩阵

`DetectorConfig` 新增 `required: bool = false`。

配置阶段拒绝：

- `required=true` 且 `on_error=fail_open`；
- `required=true` 且 `enabled=false`。

| required | on_error | 初始化或持续健康失败 | 启动/存活 | `/ready` | 业务请求 |
|---|---|---|---|---|---|
| true | fail_closed | 初始化失败 | 启动失败并清理 | 不提供 | 不接受 |
| false | fail_closed | unavailable/unhealthy | 进程保留供诊断 | 503 not_ready | Provider 调用前返回 503 |
| false | fail_open | unavailable/unhealthy | 允许降级运行 | 200 ready + degraded | 跳过该检测器并记录降级 |

正常请求期 `detect()` 的瞬时异常继续由既有 Pipeline Engine 的 `on_error` 逻辑处理；本变更不改变该算法。

## 4. 生命周期状态模型

新增应用级 `DetectorStatusRegistry`，身份键为 `(direction, detector_name)`，记录 detector type、required、on_error、状态和稳定 reason code。

```text
configured -> initializing -> healthy <-> unhealthy
                         \-> unavailable
```

- `unavailable`：初始化阶段没有可用实例，只能通过重启/重新初始化恢复；不得调用 shutdown。
- `unhealthy`：实例已经加载，但运行期健康检查失败或超时；后续健康检查成功后回到 `healthy`。
- 状态写入必须是并发安全、幂等的；只有状态变化才产生生命周期事件。

初始化由共同编排层执行。成功创建的检测器按既有优先级进入 Pipeline；失败时登记状态，再应用上表策略。required 失败会对此前已成功创建的资源执行逆序清理，并在抛出启动异常前刷新/关闭审计资源。

## 5. 应用生命周期与组件顺序

应用初始化顺序调整为：基础配置 → 指标 → 审计 → 状态注册表/检测器 → Pipeline/Provider/路由就绪。审计先于检测器初始化，使致命启动失败也可留下生命周期证据。

`DetectorStatusRegistry`、ready 状态和协调器放入当前 FastAPI app state；多个 app 实例互不污染。生命周期清理由 FastAPI lifespan 边界完成，不新增自定义 signal handler。

gRPC sidecar 保持现有同步 stub + off-thread 调用模型，不在本变更中迁移 `grpc.aio`。

## 6. Readiness 与健康检查

`/ready` 从当前 app state 读取状态，并对已加载检测器执行并行、有界健康检查。单个检查使用该检测器配置的 timeout；异常与超时分别映射为稳定 reason code，不返回异常正文。无检测器或全部健康时保持兼容的 ready 响应。

响应为加法扩展：

```json
{
  "status": "ready",
  "degraded": true,
  "detectors": {
    "configured": 3,
    "loaded": 2,
    "healthy": 2,
    "unavailable": 1,
    "unhealthy": 0,
    "degraded": 1,
    "issues": [
      {"name": "toxicity", "direction": "input", "state": "unavailable", "reason_code": "initialization_error"}
    ]
  }
}
```

顶层 `status` 继续只使用 `ready`/`not_ready`。fail-open 问题返回 HTTP 200、`status=ready`、`degraded=true`；required 或 fail-closed 问题返回 HTTP 503、`status=not_ready`。状态恢复后 readiness 自动恢复。

`/health` 不查询检测器，保持纯 liveness。

## 7. 业务准入

聊天入口在解析请求与模型后、任何 Provider 路由或调用前，对 input/output 两个方向统一执行状态 guard。该 guard 覆盖同步、流式和异步输出路径。

存在 required/fail-closed 的 unavailable 或 unhealthy 时返回：

- HTTP 503；
- `X-Safety-Action: block`；
- `SafetyUnavailableError`，不得复用 `SafetyBlockError`；
- 响应：

```json
{"error":{"message":"Safety detection is temporarily unavailable","type":"safety_unavailable","code":"safety_detector_unavailable","safety":{"affected_directions":["input"],"detectors":["pii_redaction"]}}}
```

detector 与 direction 排序固定，避免非确定响应。fail-open 问题允许请求继续，但该检测器必须被跳过，并把降级快照交给请求审计与指标。

## 8. 审计、日志与指标

请求审计新增：

- `safety_degraded: bool`；
- `detector_availability[]`，元素为 `{name, direction, state, required, on_error, reason_code}`。

生命周期事件使用 `event_type=detector_lifecycle`，包含 `detector_name`、`direction`、`detector_type`、`old_state`、`new_state`、`required`、`on_error`、`reason_code`。只在状态变化时记录；审计关闭时仍写脱敏结构化日志。

Prometheus 新增：

- `safety_detector_up{detector_name,direction,detector_type}` Gauge；
- `safety_detector_initialization_failures_total{detector_name,direction,detector_type,policy}` Counter；
- `safety_gateway_degraded_requests_total{direction,detector_name}` Counter。

标签只来自配置枚举和检测器名称；不得把异常正文、endpoint、凭据或请求内容作为标签。

## 9. 失败与恢复

- required 初始化失败：登记/记录 → 清理已初始化资源 → 刷新审计 → 抛出启动异常。
- optional fail-closed 初始化失败：实例可存活诊断，但 not-ready，所有业务入口 fail-closed。
- optional fail-open 初始化失败：ready degraded，显式跳过并记录每个降级请求。
- loaded detector 健康失败：转 unhealthy；后续成功转 healthy。
- 状态注册、readiness 计算、业务 guard、审计和指标共享同一枚举与字段含义，防止契约漂移。

## 10. 兼容性与迁移

`required` 默认 false，现有合法配置可直接加载。正常 ready 状态保留既有 `status` 值；新增字段为加法兼容。唯一有意收紧的行为是：现有 optional fail-closed 检测器初始化失败时，不再静默 ready/放行。

## 11. 验证标准

严格按 RED → GREEN → REFACTOR 实现。参数化覆盖四类检测器和 input/output 两个方向；验证 Provider 在 fail-closed 情况下从未被调用；验证 fatal cleanup、app 隔离、健康恢复、审计脱敏与指标低基数。最终必须通过全量 pytest、ruff、mypy，覆盖率不得下降。
