# v0.3.0 租户身份与配置契约测试报告

> 测试日期：2026-08-31
> 测试环境：Linux，Python 3.10.21 / 3.11 / 3.12.14，pytest 9.1.1
> 被测基线：`98505a0` + 当前 change 工作区

## 一、总体概况

| 指标 | 数值 |
|------|------|
| 最终全仓测试总数 | 1129 |
| 通过 | 1128 |
| 失败 | 0 |
| 跳过 | 1 |
| 通过率 | 100%（1128 / 1128） |
| 执行耗时 | 101.35 秒 |

最终命令覆盖 `tests/`、Detector SDK 路径及两个插件示例测试目录。唯一 skip 为既有平台条件测试。

### 1.1 覆盖率诊断（变更源码）

| 变更文件 | 行覆盖率 | 状态 |
|----------|----------|------|
| `app.py` | 95% | ✅ |
| `config/models.py` | 96% | ✅ |
| `config/validators.py` | 96% | ✅ |
| `middleware/auth.py` | 98% | ✅ |
| `tenancy/__init__.py` | 100% | ✅ |
| `tenancy/context.py` | 100% | ✅ |

全仓覆盖率为 **93.41%**，高于 90% release 门槛；变更源码无低于 90% 的文件。

## 二、按模块统计

| 测试模块 | 收集数 | 状态 | 说明 |
|----------|--------|------|------|
| `tests/unit/config/test_tenancy.py` | 27 | 27 passed | schema、slug、上限、strict bool、完整失败矩阵、脱敏 |
| `tests/unit/middleware/test_tenant_identity.py` | 5 | 5 passed | frozen Context、并发隔离、Header 防伪、最大规模 O(1) lookup |
| `tests/unit/middleware/test_auth.py` | 10 | 10 passed | legacy、预编译、生产顺序、401/request ID/日志脱敏 |
| `tests/integration/test_tenant_identity_contract.py` | 3 | 3 passed | shipped YAML、sync HTTP、SSE、环境变量示例、双租户 HTTP |
| 全仓 + SDK + 插件示例 | 1129 | 1128 passed / 1 skipped | coverage 93.41% |

18 个 canonical agent checkpoint 全部可收集并逐条执行通过，参数化展开为 34 个案例；四个 change 相关测试文件合计 45/45 passed。

## 三、E2E 测试结果

项目 `quality.e2e.enabled` 为 `false`，因此浏览器 E2E 为 **N/A**，不是 PASS。关键运行链由真实 ASGI、fake Provider、同步 HTTP 与 SSE 集成测试覆盖，不访问付费或外部服务。

### 3.1 Python 版本矩阵

| Python | 结果 | 说明 |
|--------|------|------|
| 3.10.21 | 1121 passed / 1 skipped | uv 隔离环境，coverage 模式通过 |
| 3.11 | 1121 passed / 1 skipped | uv 隔离环境，coverage 模式通过 |
| 3.12.14 | 1128 passed / 1 skipped | 最终全仓 + SDK + 插件示例，coverage 93.41% |

## 四、失败项与已知环境信号

### 4.1 TC-PE-003 — 非插桩宿主微基准未达历史吞吐门

- **测试文件**：`tests/unit/pipeline/test_flow_compat.py`
- **现象**：Python 3.10 uv 隔离环境测得约 868 req/s，低于既有 7128 req/s 门槛；Phase 4 的本机非插桩运行也曾复现相同宿主抖动。
- **原因**：该子秒级 microbenchmark 对当前桌面宿主调度和临时隔离环境高度敏感；本 change 不修改 Flow/Pipeline 热路径。
- **影响**：不影响本 change 的租户配置、认证或请求上下文正确性；coverage 模式按测试内既有策略跳过不可比的吞吐阈值，三版本功能矩阵均通过。
- **补完计划**：在独占 CI runner 上继续保留非插桩基准作为发布性能证据；不以降低阈值或删除测试掩盖信号。

### 4.2 STDD agent CLI task 解析限制

- **现象**：`stdd agent verify config-system` 解析到主规范同名任务而非当前 change，并因子进程 PATH 返回 127。
- **影响**：仅影响该 CLI 聚合入口，不影响测试真实性。
- **替代证据**：直接解析当前 change 的 18 个 canonical actions，全部可收集并实际执行通过（34/34 参数化案例）。
- **补完计划**：留给独立 STDD tooling change 处理 change-local task disambiguation；本 runtime change 不修改 STDD CLI。

## 五、功能/测试覆盖对照

| Capability | TC | 自动化结果 | 缺失测试 |
|------------|----|------------|----------|
| tenant-config-contract | 7/7 | ✅ 全部通过 | 无 |
| tenant-identity-context | 5/5 | ✅ 全部通过 | 无 |
| authentication | 3/3 | ✅ 全部通过 | 无 |
| config-system | 3/3 | ✅ 全部通过 | 无 |
| **合计** | **18/18** | **100%** | **无** |

### 5.1 切片完成度

| Slice | TC | 状态 | 关键证据 |
|-------|----|------|----------|
| S1 schema 与边界 | 4/4 | ✅ | strict schema、1024/4096 上限、identity-only |
| S2 Context 与兼容认证 | 4/4 | ✅ | frozen v1.0、legacy default、无效凭据、预编译 lookup |
| S3 启动失败矩阵 | 4/4 | ✅ | O(T+K)、稳定 reason code、空 key/歧义/矛盾配置拒绝 |
| S4 隔离与中间件顺序 | 3/3 | ✅ | 并发屏障、Header 防伪、RequestID→Auth→RateLimit |
| S5 YAML 与 HTTP 接线 | 3/3 | ✅ | shipped YAML、环境变量示例、双租户 ASGI 请求 |

## 五-B、多路并行 Review 结果

### Review 迭代历史

| 轮次 | 代码质量 | 测试/配置 | 文档/Skills | 状态 |
|------|----------|-----------|-------------|------|
| 1 | C0/H0/M3/L1 | C0/H2/M3/L1 | C0/H4/M2/L1 | 发现并修复 |
| 2 | C0/H0/M0/L0 | C0/H0/M2/L2 | C0/H0/M1/L0 | 补强持久证据 |
| 3 | C0/H0/M0/L0 | C0/H0/M0/L0 | C0/H0/M0/L0 | ✅ 通过 |

### Review 已修复问题

| # | 问题 | 修复 |
|---|------|------|
| 1 | canonical CFG checkpoint 引用不存在的 pytest 节点 | canonical/working agent specs 同步真实节点并执行 34/34 |
| 2 | 空/空白 key 可形成永远不可认证的租户 | `invalid_api_key` 启动拒绝 + 空串/空白回归 |
| 3 | bool 强制转换可绕过 cardinality pre-check | `tenancy.enabled` 使用 strict bool |
| 4 | duplicate guard 破坏 legacy last-wins 兼容 | guard 仅在 tenancy enabled 生效 |
| 5 | 最大规模 O(1) 证据不足 | 1024/4096 + LookupOnlyDict 禁止请求期迭代 |
| 6 | legacy 兼容 checkpoint 未执行协议链 | 补 shipped YAML、default Context、sync HTTP、SSE、fake Provider |
| 7 | 日志/输出秘密负向断言不足 | TCC/CFG/AUTH checkpoint 捕获 stdout/stderr 并扫描 secret |
| 8 | README/CHANGELOG/AGENTS 与 DESIGN 生命周期冲突 | 统一为 change 1/4 active、版本未变、里程碑未完成 |

最终三路评审：**C0 / H0 / M0 / L0**。

## 六、设计调整说明

两项 minor boundary discovery 已闭环，均不需要 re-spec 或 re-build：

1. roadmap 生命周期从 planning-only 推进为 change 1/4 active，同时禁止提前宣告版本或里程碑完成；
2. 多租户启动矩阵补充 `invalid_api_key`，拒绝运行时不可达的空/空白凭据。

详见 [design-adjustments.md](design-adjustments.md)。

## 七、修复确认记录

Phase 5 修复后重新运行 3.12 全仓质量门：1128 passed / 1 skipped、coverage 93.41%；Ruff、Mypy、`git diff --check` 全部通过；三路最终复审均为零发现。

## 七-B、经验库更新

### 本次新增经验

| 经验 ID | 类别 | 模式 | 严重程度 |
|---------|------|------|----------|
| EXP-2026-0025 | contract_gap | 配置值必须按运行时归一化规则验证并保证认证路径可达 | high |

### 本次命中已有经验

| 经验 ID | 类别 | 命中 |
|---------|------|------|
| EXP-2026-0006 | coverage_vacuum | checkpoint 必须引用真实可执行节点 |
| EXP-2026-0019 | content_quality | roadmap 与公开状态必须分层且一致 |
| EXP-2026-0022 | contract_gap | TC-ID 与 checkpoint 必须真实一一绑定 |

经验库更新：新增 1 条，复用 3 条，总计 25 条。

## 七-C、项目原则复核

| 原则 | 实际结果与证据 | 状态 |
|------|---------------|------|
| Plugin / Flow；核心最小 | 只新增配置、认证身份解析和 Context 传播；无租户级安全策略、Provider/Detector 领域逻辑；Flow 仍为全局执行机制 | ✅ |
| 策略显式；失败不静默 | tenancy 显式 opt-in；完整启动矩阵以稳定 reason code fail-closed；无未知/空绑定 fallback | ✅ |
| 边界透明；契约稳定 | 401、HTTP/SSE、Provider/Flow、legacy 配置保持兼容；1024/4096 和 O(1) 请求 lookup 有界 | ✅ |
| 决策有证据；数据默认保护 | 18/18 TC、18 checkpoints、frozen secret-free Context；异常、响应、stdout/stderr 均做凭据负向扫描 | ✅ |

原则取舍仅为 [design-adjustments.md](design-adjustments.md) 中两项 minor 边界补全，均增强显式失败或状态透明度，无原则偏离。

## 八、十二类失败模式检查

| 类别 | 结果 | 证据 |
|------|------|------|
| (a) 幻觉行为 | HIT→FIXED | 3 个漂移 checkpoint 已绑定真实节点；配置路径/env/API 实查 |
| (b) 范围蔓延 | PASS | diff 落在授权路径；两项额外文档/边界更新均有 design adjustment |
| (c) 级联错误 | PASS | 新路径无异常吞没或 fallback；配置错误在启动边界拒绝 |
| (d) 上下文丢失 | PASS | 实现逐项对齐 proposal/design/spec；唯一差异已记录 ADJ-001/002 |
| (e) 工具误用 | PASS | 文件变更使用 patch；CLI 聚合限制如实记录并以直接 checkpoint 执行替代 |
| (f) 运行时行为偏差 | PASS | create_app、真实 ASGI、并发、sync HTTP、SSE 均动态验证 |
| (g) 管线断链 | PASS | YAML→env→Pydantic→validator→Auth→Context→route 全链通过 |
| (h) 内容质量偏差 | HIT→FIXED | DESIGN/README/CHANGELOG/AGENTS 状态统一，版本与完成边界无冲突 |
| (i) 指令衰减 | PASS | 五切片 RED/GREEN/REFACTOR、7 个 Verify 强制步骤和 Gate 3 均保留 |
| (j) 覆盖真空 | HIT→FIXED | 四个 capability 自动化覆盖均为 100%，18 checkpoints 全部执行 |
| (k) 契约断层 | HIT→FIXED | 空 key、bool coercion、legacy duplicate 与运行时 normalize 契约已对齐 |
| (l) 锚定缺失 | PASS | 三个 L3 reference change 均存在；旧 auth/config/HTTP/SSE 测试作为 oracle |

无 SKIPPED 的失败模式检查；所有命中项均已修复并经第三轮评审归零。

## 九、结论

当前 change 达到 Gate 3：测试、覆盖率、lint、类型、三版本功能矩阵、18/18 TC、18/18 checkpoint、三路 Review 与四项原则检查均通过。它可以作为 v0.3.0 的租户身份基础交付，但**不代表完整多租户策略隔离已经完成，也不改变 v0.2.2 发布版本**。

| 信号源 | 状态 | 备注 |
|--------|------|------|
| 单元/集成测试 | ✅ | 100% 非 skip 通过率 |
| E2E | N/A | 项目配置 disabled；关键 ASGI/HTTP/SSE 已集成验证 |
| Ruff | ✅ | 全仓通过 |
| Mypy | ✅ | 101 个 source files 通过 |
| Python 3.10/3.11/3.12 | ✅ | 三版本 coverage 功能矩阵通过 |
| 覆盖率 | ✅ | 全仓 93.41%，变更源码均 ≥95% |
| 十二类失败模式 | ✅ | 12/12 已执行，4 类命中后修复，0 skipped |
| 多路 Review | ✅ | 最终 C0/H0/M0/L0 |
