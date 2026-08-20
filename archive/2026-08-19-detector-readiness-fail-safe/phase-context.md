# Phase Context

## Change

- ID: `2026-08-19-detector-readiness-fail-safe`
- 模式: thorough
- 风险: safety-critical / cross-system
- 锚定级别: L3
- 当前结论: Gate 1 与 Gate 2 已确认；Phase 2 设计锁定。

## Intent

阻止任何“已配置安全检测器初始化或健康失败，但实例仍无信号地接受并放行业务流量”的路径。`required` 控制启动准入；`on_error` 控制非 required 故障策略。

## Locked Decisions

1. `required` 默认 false；与 `fail_open` 或 `enabled=false` 的组合非法。
2. required 初始化失败中止启动并清理已创建资源。
3. optional fail-closed 问题让 `/ready` 返回 503，并在 Provider 前阻断请求。
4. optional fail-open 问题返回 200 degraded，跳过检测器并产生审计/指标。
5. 状态注册表与 ready 标志是 app-scoped；身份为 `(direction, detector_name)`。
6. `/health` 仍是纯 liveness；`/ready` 并行执行有界健康检查并支持恢复。
7. 统一状态：configured、initializing、healthy、unavailable、unhealthy。
8. 业务错误是独立的 `SafetyUnavailableError`，HTTP 503 和 `X-Safety-Action: block`。
9. 原始异常不得进入 API、审计或指标标签。
10. gRPC 保持同步 stub + off-thread；不新增热加载、自动重试或 Provider failover。

## Anchors

- `2026-08-11-v0.0.2-pipeline-detectors`
- `2026-08-12-v0.0.4-security-observability`
- `2026-08-14-v0.0.5-plugin-ecosystem`
- 经验约束 EXP-001：清理由 app lifecycle/init 边界管理。
- 经验约束 EXP-007：不迁移 grpc.aio。

## Build Guardrails

- 修改任何实现前先写会失败的测试。
- 每个 slice 都单独通过目标测试、ruff 与相关 mypy。
- readiness、guard、audit、metrics 复用同一状态快照，不能各自推导。
- 不使用 sentinel/fake Detector 表示初始化失败。
- fail-closed 测试必须断言 Provider 未调用。
- Gate 3 前执行完整失败模式检查，不得自动通过。

## Primary Touchpoints

- `src/z_llm_safety_gateway/config/models.py`
- `src/z_llm_safety_gateway/config/validators.py`
- `src/z_llm_safety_gateway/detectors/`
- `src/z_llm_safety_gateway/app.py`
- `src/z_llm_safety_gateway/routes/health.py`
- `src/z_llm_safety_gateway/audit/`
- `src/z_llm_safety_gateway/observability/metrics.py`
- 对应 `tests/unit/` 与 `tests/integration/`

## Verification Contract

共 20 条 Requirements、36 条场景/agent checkpoints：P0 26、P1 9、P2 1。测试清单见 `test-plan.md`，机器规格位于 `specs/*/spec.yaml` 与 `agent_spec.yaml`。

## Phase 4 Progress

- S1 配置与状态基础：completed；TC 7/7；新增测试 7；全量回归 811 passed / 1 skipped。新增 `detectors/status.py` 与两组单元测试。经验约束 EXP-001 已用于 app-scoped 生命周期设计。
- S2 初始化协调器与 fatal cleanup：completed；TC 5/5；新增参数化测试 11；全量回归 822 passed / 1 skipped。四类 detector 共用状态协调器；required 失败逆序 shutdown 并 flush/close 审计。EXP-007 保持 gRPC 同步 stub 模型。
- S3 启动策略矩阵：completed；TC 5/5；新增测试 5；全量回归 827 passed / 1 skipped。状态注册表和 ready 决策进入 app state；optional fail-closed/not-ready 与 fail-open/degraded 已分离；审计初始化提前到 detector 之前。
- S4 Detector-aware Readiness：completed；TC 5/5；新增测试 5；全量回归 832 passed / 1 skipped。移除模块级 ready 状态；`/ready` 并行执行 per-detector timeout 健康检查，支持 unhealthy 恢复并输出确定摘要；`/health` 保持纯 liveness。
- S5 业务安全准入：completed；TC 3/3；新增参数化测试 5；全量回归 837 passed / 1 skipped。新增专用 `SafetyUnavailableError`；input/output 严格问题在 Provider route 前统一返回 503；fail-open 故障 detector 被请求级过滤。
- S6 生命周期与请求审计：completed；TC 7/7；新增测试 5；全量回归 842 passed / 1 skipped。状态变化写去重 lifecycle event；fatal startup flush/close；fail-open 和 fail-closed 请求均记录脱敏 availability，审计关闭时结构化日志仍保留。
- S7 Prometheus 降级信号：completed；TC 4/4；新增测试 4；全量回归 846 passed / 1 skipped。新增 detector up、initialization failure 与 degraded request 指标，全部使用 bounded labels，disabled 时 no-op。

Phase 4 状态：completed。全部 7 个切片通过独立 RED→GREEN→REFACTOR 与全量回归；test-plan TC-ID 自动化覆盖 36/36。

## Phase 5 Verification

- 最终全量：862 passed / 1 skipped；全源覆盖率 93%，change 核心文件均 ≥ 90%。
- Ruff、mypy（77 个源文件）与 `git diff --check` 全部通过。
- 36/36 TC 与 36/36 agent checkpoint 均可执行；最终三路复审 C0/H0/M0/L0。
- 十二类失败模式全部检查，未留存未修复命中；L3 三个 reference change 均存在并完成锚定核对。
- 设计调整 0 项；Gate 3 pending。
- Step 3.5 经验库写入 SKIPPED：项目缺少 `bin/stdd`（exit 2）。已在 `test-report.md` 记录影响与补完计划。
