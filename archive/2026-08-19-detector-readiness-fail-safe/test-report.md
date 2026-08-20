# Detector Readiness Fail-Safe 测试报告

> 测试日期：2026-08-20  
> 测试环境：macOS 26.5.2，Python 3.10.20，pytest 9.1.1  
> 被测基线：`a57a13a` + 当前工作区 change  
> Change：`2026-08-19-detector-readiness-fail-safe`（thorough / safety-critical）

## 一、总体概况

| 指标 | 数值 |
|------|------|
| 测试总数 | 863 |
| 通过 | 862 |
| 失败 | 0 |
| 跳过 | 1 |
| 有效通过率 | 100%（862 / 862） |
| 最终执行耗时 | 9.55 秒 |
| 计划 TC 覆盖 | 36 / 36（100%） |

最终全量命令：`.venv/bin/pytest tests/ -q`。13 条 warning 均为既有的 Starlette TestClient 弃用提示、gRPC circuit breaker 建议以及旧 detector 配置格式弃用提示，无新增失败或安全告警。

### 1.1 覆盖率诊断

全量源代码行覆盖率为 **93%**（3674 statements，262 missing）。本 change 的核心变更文件均不低于 90%。

| 变更文件 | 行覆盖率 | 状态 |
|----------|----------|------|
| `src/z_llm_safety_gateway/app.py` | 97% | ✅ |
| `src/z_llm_safety_gateway/audit/logger.py` | 100% | ✅ |
| `src/z_llm_safety_gateway/audit/models.py` | 100% | ✅ |
| `src/z_llm_safety_gateway/config/models.py` | 97% | ✅ |
| `src/z_llm_safety_gateway/config/validators.py` | 95% | ✅ |
| `src/z_llm_safety_gateway/detectors/registry.py` | 93% | ✅ |
| `src/z_llm_safety_gateway/detectors/status.py` | 98% | ✅ |
| `src/z_llm_safety_gateway/exceptions.py` | 100% | ✅ |
| `src/z_llm_safety_gateway/observability/metrics.py` | 91% | ✅ |
| `src/z_llm_safety_gateway/plugins/grpc/client.py` | 94% | ✅ |
| `src/z_llm_safety_gateway/routes/chat.py` | 90% | ✅ |
| `src/z_llm_safety_gateway/routes/health.py` | 97% | ✅ |

没有 change 核心文件低于项目 80% 诊断目标。

## 二、按模块统计

下表为本 change 的主要专项测试；它们同时包含在 862 个全量通过项中。

| 测试模块 | 收集数 | 结果 | 覆盖重点 |
|----------|--------|------|----------|
| `config/test_detector_required.py` | 3 | 3 passed | required 默认值、双向提取、非法组合 |
| `detectors/test_status_registry.py` | 4 | 4 passed | app-scoped 身份、状态转换、恢复 |
| `test_detector_initialization.py` | 14 | 14 passed | 四类初始化、factory None、fatal/partial/bounded cleanup |
| `test_startup_policy.py` | 5 | 5 passed | required、optional strict/open、真实 `/ready` 与业务请求 |
| `routes/test_detector_readiness.py` | 8 | 8 passed | liveness/readiness、并发、超时、恢复、duck plugin |
| `routes/test_availability_guard.py` | 6 | 6 passed | 精确 503、sync/stream/async、请求级过滤 |
| `audit/test_detector_availability_audit.py` | 8 | 8 passed | lifecycle、真实文件 sink、disabled fallback、脱敏 |
| `observability/test_detector_availability_metrics.py` | 7 | 7 passed | up/init/degraded 指标与 disabled no-op |
| 既有 gRPC client/registry 套件 | 30 | 30 passed | health error、cancellation close、in-process partial cleanup |

## 三、质量门禁

| 门禁 | 结果 | 备注 |
|------|------|------|
| 全量 pytest | ✅ | 862 passed / 1 skipped |
| Ruff | ✅ | `All checks passed!` |
| mypy | ✅ | 77 source files，0 issues |
| diff check | ✅ | 无空白错误 |
| Python 3.10 | ✅ | 当前虚拟环境 3.10.20 |
| Python 3.11 | SKIPPED | 工作区未安装对应解释器/依赖环境 |
| Python 3.12 | SKIPPED | 工作区未安装对应解释器/依赖环境 |
| E2E | N/A | `.stdd/config.d/quality.yaml` 明确 `e2e.enabled: false` |

多版本跳过不影响当前 3.10 门禁结论，但在 Phase 6 CI/发布前应由矩阵环境补跑 3.11 与 3.12。

## 四、功能与 TC 覆盖

| Capability | TC 数 | 自动化 | 结果 |
|------------|-------|--------|------|
| detector-lifecycle-status | 4 | 4 | ✅ |
| required-detector-policy | 5 | 5 | ✅ |
| degraded-safety-visibility | 3 | 3 | ✅ |
| config-system | 3 | 3 | ✅ |
| detector-framework | 3 | 3 | ✅ |
| health-endpoints | 5 | 5 | ✅ |
| fastapi-server | 5 | 5 | ✅ |
| audit-logger | 4 | 4 | ✅ |
| prometheus-metrics | 4 | 4 | ✅ |
| **合计** | **36** | **36** | **100%** |

9 份 `agent_spec.yaml` 共 36 个 checkpoint 均已收紧为具体 pytest node；最终复核确认所有 node 可收集，新增关键回归也已纳入对应 checkpoint。

## 五、切片完成度

| Slice | 内容 | TC | Phase 4 状态 | Phase 5 复验 |
|-------|------|----|--------------|--------------|
| S1 | 配置与状态基础 | 7/7 | completed | ✅ |
| S2 | 初始化协调器与 fatal cleanup | 5/5 | completed | ✅（含有界与部分初始化 cleanup） |
| S3 | 启动策略矩阵 | 5/5 | completed | ✅ |
| S4 | Detector-aware Readiness | 5/5 | completed | ✅（含真实并发与 duck plugin） |
| S5 | 业务安全准入 | 3/3 | completed | ✅（sync/stream/async） |
| S6 | 生命周期与请求审计 | 7/7 | completed | ✅（真实 JSONL sink） |
| S7 | Prometheus 降级信号 | 4/4 | completed | ✅ |

## 六、多路技术评审

### 6.1 迭代历史

| 轮次 | Critical | High | Medium | Low | 结论 |
|------|----------|------|--------|-----|------|
| 1 | 0 | 8 | 8 | 2 | 发现初始化、过滤、测试真实性与文档契约问题 |
| 2 | 0 | 2 | 8 | 2 | 第一轮 High 已修；发现 gRPC health 与 duck plugin 边界 |
| 3 | 0 | 0 | 2 | 0 | 仅剩 cleanup 竞争与 checkpoint 归因 |
| 最终 | 0 | 0 | 0 | 0 | 三维复审全部通过 |

### 6.2 已修复的代表性问题

| 严重性 | 问题 | 修复结果 |
|--------|------|----------|
| High | 配置名与 runtime detector 名不一致导致 fail-open 过滤失效 | 改为按请求所持 detector 实例身份过滤 |
| High | streaming post-audit 重用全局 runner，可能重新引入故障 detector | 改为请求级过滤后的 runner |
| High | factory 返回 `None` 被标记 healthy | 视为初始化失败并进入 unavailable |
| High | async/fatal/脱敏测试为稻草人 | 改为真实配置、真实异常、真实启动与真实文件 sink |
| High | gRPC health 日志泄露 endpoint/异常 | 异常上抛给 readiness，外部仅稳定 reason code |
| High | duck-typed plugin 无 `health_check` 被误判 unhealthy | 缺失可选 health 方法时保留当前健康状态 |
| Medium | cleanup 可挂死且部分初始化资源泄漏 | per-detector timeout + gRPC/in-process best-effort cleanup |
| Medium | gRPC 外层取消可能跳过 channel close | `finally` 强制本地 channel close，保持取消语义 |
| Medium | readiness 并发测试依赖墙钟 | 改为事件栅栏并断言无 degraded/全部 healthy |
| Medium | checkpoint 只跑整文件导致假阳性 | 36 项全部绑定具体 pytest node |

最终代码、测试/配置、文档/Skills 三路复审均为 **C0/H0/M0/L0**。

## 七、Diff 与十二类失败模式检查

Diff 审查覆盖本 change 的实现、测试、DESIGN 与用户文档。工作区中同时存在用户先前的 README、CI、发布配置等其他改动；这些未被本 change 覆盖或改写，审查结论仅针对本 change 范围。

| # | 失败模式 | 结果 | 验证摘要 |
|---|----------|------|----------|
| a | 幻觉行为 | ✅ | 源码、文档和 36 个 action 的路径/node 全部存在并可收集 |
| b | 范围蔓延 | ✅ | 额外 registry/gRPC 改动均为初始化与 readiness 边界所必需 |
| c | 级联错误 | ✅ | fail-open 显式降级；strict 在 Provider 前拒绝；清理有界且不吞 fatal |
| d | 上下文丢失 | ✅ | required/on_error、app scope、状态机与 Phase 2 锁定决策一致 |
| e | 工具误用 | ✅ | 使用受控 patch 与只读诊断；无破坏性操作 |
| f | 运行时行为偏差 | ✅ | 真实 sync/stream/async、gRPC、readiness 恢复与 cancellation 路径均执行 |
| g | 管线断链 | ✅ | config → init → status → ready/guard → audit/metrics 链路端到端覆盖 |
| h | 内容质量偏差 | ✅ | DESIGN、配置/API/部署文档经独立复审，精确 503 契约一致 |
| i | 指令衰减 | ✅ | 三 Gate 保留；Phase 4 各切片按 RED→GREEN→REFACTOR；Gate 3 未自动越过 |
| j | 覆盖真空 | ✅ | 9 个 capability 均有自动化，36/36 TC 覆盖 |
| k | 契约断层 | ✅ | `/ready`、503 header/body、audit schema、metrics label 与消费者一致 |
| l | 锚定缺失 | ✅ | 三个 L3 reference change 均存在于 archive；EXP-001/EXP-007 约束已核对 |

检查过程中命中的运行时、契约与级联边界均已修复并重新通过全量门禁；最终无未处理命中项。

## 八、设计调整

没有产品语义调整。详见 [design-adjustments.md](design-adjustments.md) 与 canonical [design-adjustments.yaml](design-adjustments.yaml)。

## 九、经验库更新

| 项目 | 结果 |
|------|------|
| 新增经验 | SKIPPED |
| 正式复用计数 | SKIPPED |
| 设计中人工核对的既有经验 | EXP-001、EXP-007 |

**未完成项：STDD 经验库 CLI 更新**

- 原因：仓库不存在强制入口 `bin/stdd`；`.venv/bin/python bin/stdd --help` 返回 exit 2。
- 影响：本次发现的“请求级 detector 过滤”“健康检查日志脱敏”“取消时本地资源 finally 释放”等模式尚未写入 `.stdd/experiences/` 索引；不影响代码、测试或运行时安全结论，但降低后续 change 的自动经验复用能力。
- 补完计划：恢复与 STDD 2.9.5 匹配的 `bin/stdd` 后，执行 `experience add/list/stats`，将新增模式去重写入；Phase 6 交付前可完成。

依据 Verify 长程规则，此处只有 1 类 SKIPPED（少于降级阈值 3），并已如实列出，不标记为 PASS。

## 十、结论

本 change 已满足进入 Gate 3 的代码质量条件：全部自动化测试通过，TC 覆盖 100%，核心变更覆盖率 90% 以上，lint/typecheck/diff-check 全绿，最终三路复审无残留问题，十二类失败模式全部完成。

建议用户确认 Gate 3 后进入 Phase 6。交付前的流程性跟进为：恢复 STDD CLI 并补写经验库；在 CI 矩阵补跑 Python 3.11/3.12。二者均不改变当前功能验收结论。
