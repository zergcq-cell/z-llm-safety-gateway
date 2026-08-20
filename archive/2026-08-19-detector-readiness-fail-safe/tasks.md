# Detector Readiness Fail-Safe 任务清单

## 1. 配置与状态基础（P0）

- [x] 1.1 为 `DetectorConfig` 增加向后兼容的 `required` 字段
- [x] 1.2 校验 required/fail_open 与 required/disabled 非法组合
- [x] 1.3 实现 app-scoped `DetectorStatusRegistry`、状态枚举与脱敏原因码
- [x] 1.4 覆盖 TC-CFG-601～603、TC-DLS-001～004

## 2. 统一初始化协调器与 fatal cleanup（P0）

- [x] 2.1 统一 built-in、ML、in-process、gRPC 的初始化状态入口（依赖 #1）
- [x] 2.2 required 初始化失败传播并逆序清理已加载 detector
- [x] 2.3 unavailable 不进入 Pipeline、不参与 health/shutdown
- [x] 2.4 覆盖 TC-DF-601～603、TC-RDP-001～002

## 3. 启动策略矩阵（P0）

- [x] 3.1 将状态注册表和初始化结果接入 FastAPI app state（依赖 #2）
- [x] 3.2 实现 optional fail_closed not-ready 与 optional fail_open degraded 决策
- [x] 3.3 保证多故障取最严格策略并稳定排序
- [x] 3.4 覆盖 TC-RDP-003～005、TC-FAST-601～602

## 4. Detector-aware Readiness（P0/P1）

- [x] 4.1 将 ready 状态从模块全局迁移为 app-scoped（依赖 #3）
- [x] 4.2 并行执行有界 detector health check 并支持恢复
- [x] 4.3 输出兼容且确定的 detector readiness 摘要
- [x] 4.4 保持 `/health` 纯 liveness
- [x] 4.5 覆盖 TC-HEALTH-601～605

## 5. 业务安全准入（P0）

- [x] 5.1 新增 `SafetyUnavailableError` 与 503/header/body 契约（依赖 #3）
- [x] 5.2 Provider 前统一检查 input/output 严格问题
- [x] 5.3 覆盖同步、流式、异步输出路径
- [x] 5.4 fail-open 跳过故障 detector 并传递降级快照
- [x] 5.5 覆盖 TC-FAST-603～605

## 6. 生命周期与请求审计（P0/P1）

- [x] 6.1 初始化审计早于 detector，并在 fatal startup 时 flush/close（依赖 #2）
- [x] 6.2 记录去重的 `detector_lifecycle` 事件
- [x] 6.3 扩展请求审计的 `safety_degraded` 与 `detector_availability`
- [x] 6.4 保证审计关闭时日志兜底并全面脱敏
- [x] 6.5 覆盖 TC-DSV-001～003、TC-AUDIT-601～604

## 7. Prometheus 降级信号（P1/P2）

- [x] 7.1 增加 detector up gauge 与 initialization failure counter（依赖 #1）
- [x] 7.2 增加 degraded request counter（依赖 #5）
- [x] 7.3 保证 bounded labels 与 disabled no-op
- [x] 7.4 覆盖 TC-PROM-601～604

## 8. 全量验证（P0）

- [x] 8.1 36/36 TC-ID 均有自动化测试且通过
- [x] 8.2 全量 pytest 与覆盖率诊断通过
- [x] 8.3 ruff 与 mypy 通过
- [x] 8.4 完成多路评审、diff 审查与 12 类失败模式检查
- [x] 8.5 生成 test-report 与设计调整记录并进入 Gate 3
