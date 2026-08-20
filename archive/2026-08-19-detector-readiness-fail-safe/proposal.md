# 检测器初始化失败与 Readiness Fail-Safe 加固

> Change ID：`2026-08-19-detector-readiness-fail-safe`  
> Gate 1：已确认  
> 建议模式：thorough（复杂度评分 15/17）

## Why

当前配置中的检测器初始化失败时，网关捕获异常并跳过该检测器，随后仍将实例标记为
ready。这可能造成配置要求执行安全检测、实际检测器未运行、负载均衡器却继续分发流量的
静默安全降级。

现有设计、规格和实现也存在冲突：

- `DESIGN.md` 要求 fail-closed 检测器不健康时 `/ready` 返回 503。
- detector-framework spec 只规定初始化失败的检测器不参与检测。
- fastapi-server spec 规定插件加载失败不阻断其他检测器。
- 当前实现没有保存失败检测器的状态，无法在 readiness、审计或指标中反映降级。

LLM Safety Gateway 必须在安全能力缺失时提供确定、可观测且可验证的 fail-safe 行为。
本变更将启动准入、请求期错误策略和运行期健康状态分离，确保 required 或 fail-closed
检测器失效时不会静默绕过，同时保留显式 fail-open 的可用性选择。

## What Changes

- `DetectorConfig` 新增 `required` 字段，默认 `false`。
- `required` 控制启动准入；`on_error` 控制非 required 检测器失败时的安全策略。
- `required: true` 必须配合 `on_error: fail_closed`，矛盾配置在加载阶段拒绝。
- required 检测器初始化失败时，网关启动失败，不监听业务流量。
- 非 required、fail-closed 检测器初始化失败时，网关保持 not-ready，受影响方向的请求
  按 fail-closed 阻断。
- 非 required、fail-open 检测器初始化失败时，网关可 degraded 启动；请求可以继续，
  但 readiness、审计和指标必须明确暴露降级。
- 为 built-in、ML、已配置的 in-process plugin 和 gRPC sidecar 建立统一生命周期状态模型。
- `/ready` 返回 loaded、healthy、unhealthy、degraded 检测器摘要；`/health` 保持纯
  liveness。
- 初始化失败和降级请求接入脱敏结构化日志、审计记录及 Prometheus 指标。
- 更新 detector-framework、config-system、health-endpoints、fastapi-server 和
  observability 相关 specs 与文档。

## Capabilities

### New Capabilities

- **detector-lifecycle-status**：统一记录 configured、initializing、healthy、unavailable、
  unhealthy 状态及脱敏后的失败原因。
- **required-detector-policy**：支持声明启动必需检测器并阻止静默缺失。
- **degraded-safety-visibility**：通过 readiness、日志、审计和指标暴露安全能力降级。

### Modified Capabilities

- **config-system**：新增 `required` 字段及组合校验。
- **detector-framework**：统一四类检测器的初始化、健康和失败状态。
- **health-endpoints**：readiness 纳入检测器状态及 `on_error` 策略。
- **fastapi-server**：启动阶段不再无条件吞掉安全关键初始化失败。
- **audit-logger**：记录不可用检测器和降级请求，避免审计误示为完整检测。
- **prometheus-metrics**：暴露初始化失败、健康状态和降级请求信号。

## Impact

**代码层面**：

- 预计影响配置模型、应用初始化、检测器生命周期状态、health route、pipeline fallback、
  审计和 metrics。
- 预计修改约 8–15 个源码文件及相应测试，变更约 300–800 行。

**配置层面**：

- 新增向后兼容字段 `required: false`。
- 旧配置继续加载；默认 `fail_open + required=false` 保持现有可用性行为。
- `required=true + on_error=fail_open` 被视为无效配置。

**基础设施**：

- readiness 语义变化可能使 Kubernetes、Compose 或负载均衡器摘除安全能力不完整的实例。
- required 检测器初始化失败时，进程以启动失败状态交由 supervisor 重启或告警。

## Constraints

- 严格 TDD，先覆盖失败矩阵再修改实现。
- 不得改变 `/health` 的 liveness 语义。
- 不得在 readiness、日志、审计或指标中暴露密钥、endpoint 凭据或原始敏感异常。
- 四种检测器接入方式必须行为一致。
- 默认配置必须保持向后兼容。
- fail-closed 状态下，即使客户端绕过负载均衡直接访问实例，也不得静默放行受影响请求。

## Stakeholders

- 网关部署与运维人员。
- 应用与平台团队。
- 安全策略维护者。
- 内置、ML、in-process 与 gRPC 检测器开发者。

## Risk Areas

- capability: **required-detector-policy** — 过严的启动策略可能降低可用性；通过默认关闭、
  明确策略矩阵和迁移说明缓解。
- capability: **health-endpoints** — 状态切换错误可能导致实例错误摘除或继续接流量；通过
  初始化、运行期不健康、恢复和并发测试缓解。
- capability: **detector-lifecycle-status** — 四类初始化路径可能产生状态遗漏；在共同编排层
  集中记录，并以参数化契约测试覆盖。
- capability: **degraded-safety-visibility** — 错误详情可能泄密或造成高基数；仅使用稳定状态码
  和脱敏摘要，禁止原始异常进入指标标签。

## NonGoals

- 不实现检测器热加载或配置热更新。
- 不实现无限自动重试或自动拉起 gRPC sidecar。
- 不修改 Provider readiness、重试或 failover。
- 不新增检测器。
- 不引入 Redis、Kubernetes Operator 或独立控制面。
- 不重新设计正常请求期的阈值、聚合和熔断算法。
- 未配置的损坏 entry point 仍按既有插件发现策略记录警告并跳过。

## Critical

- [ ] 非关键变更（默认）
- [x] 关键变更 — 涉及安全网关的核心 fail-safe 与部署准入语义，需 L3 锚定

## Risk Assessment

- **safety_critical**：true
- **financial**：false
- **cross_system**：true

## Anchoring

- **level**：L3（模式锚定）
- **reference_changes**：
  - `2026-08-11-v0.0.2-pipeline-detectors`
  - `2026-08-12-v0.0.4-security-observability`
  - `2026-08-14-v0.0.5-plugin-ecosystem`
- **anchor_implementations**：无；Phase 2 基于现有 detector lifecycle、`on_error` 与 readiness
  设计完成接口锚定。

## Success Criteria

- [ ] `required` 默认值为 `false`，现有配置无需修改即可加载。
- [ ] `required=true` 与 `on_error=fail_open` 的组合在配置阶段被拒绝并给出明确错误。
- [ ] required 检测器初始化失败时，网关启动失败且不会接受业务流量。
- [ ] 非 required、fail-closed 检测器初始化失败时，`/ready` 返回 503，受影响请求按
  fail-closed 阻断。
- [ ] 非 required、fail-open 检测器初始化失败时，网关可用但 `/ready` 明确标记 degraded。
- [ ] built-in、ML、in-process plugin、gRPC sidecar 均通过同一行为矩阵测试。
- [ ] `/ready` 报告 loaded、healthy、unhealthy、degraded 检测器；`/health` 保持纯 liveness。
- [ ] 初始化失败和降级请求产生脱敏结构化日志、审计记录及 Prometheus 指标。
- [ ] 不存在“配置了检测器、初始化失败、请求静默绕过且无可观测信号”的路径。
- [ ] 新增单元、集成和失败路径测试，全量 pytest、ruff、mypy 通过，覆盖率不下降。

## Complexity & Mode

复杂度评分：15/17。

| 维度 | 得分 |
|------|------|
| 预估文件数（8–20） | 2 |
| 预估行数（200–1000） | 2 |
| Capability 数（4+） | 2 |
| 风险等级（高） | 4 |
| 配置/API 变化 | 2 |
| 安全关键 | 3 |

执行模式：**thorough**。使用完整 Spec、Slice、严格 RED→GREEN→REFACTOR、全量失败模式检查
及三道强制 Gate。
