# 令牌桶确定性并发测试报告

> 测试日期：2026-08-28
> 测试环境：Linux 7.0.0-30-generic x86_64；Python 3.10.21 / 3.11.16 / 3.12.14；pytest 9.1.1（主环境）
> 被测基线：`aaf14c69d41c7ccbc0ba9b95094a21cb0bc6aec8` + 当前工作树 change

## 一、总体概况

最终 CI 等价命令在三个真实 uv 隔离环境中分别运行主测试集、两个示例插件测试集和
90% coverage gate。

| Python | 总数 | 通过 | 失败 | 跳过 | 通过率 | 覆盖率 |
|--------|------|------|------|------|--------|--------|
| 3.10.21 | 1078 | 1077 | 0 | 1 | 100% | 93.34% |
| 3.11.16 | 1078 | 1077 | 0 | 1 | 100% | 92.47% |
| 3.12.14 | 1078 | 1077 | 0 | 1 | 100% | 93.34% |

通过率按 `通过 / (总数 - 跳过)` 计算。三版本合计 3231 次通过、0 次失败、3 次跳过。

### 1.1 覆盖率诊断（变更源码）

| 变更文件 | 行覆盖率 | 分支覆盖率 | 状态 |
|----------|----------|------------|------|
| `src/z_llm_safety_gateway/ratelimit/token_bucket.py` | 92% | 未单独采集 | ✅ |

未覆盖的是既有输入/重试估算分支；本 change 新增的时钟选择、初始化和 refill 路径均被
TC-RL-005、008～010 覆盖。覆盖率不是独立阻断门，但三版本项目门均超过 90%。

## 二、按模块与切片统计

| 模块/切片 | TC | 自动化证据 | 状态 |
|-----------|----|------------|------|
| S1 可控时钟 | 005、008、009、010 | 4 个精确 pytest 节点；rate-limit 文件 10 passed | ✅ 4/4 |
| S2 锁序列化 | 007 | 1 个精确 pytest 节点；持锁等待与 token 不变式 | ✅ 1/1 |
| S3 多版本矩阵 | 011 | 可执行程序化 checkpoint；三版本各 3 次定向 + 完整矩阵 | ✅ 1/1 |

定向稳定性证据：Python 3.10、3.11、3.12 各重复 3 次完整 rate-limit 文件，每个版本
30/30 passed。原 Python 3.11 的 `期望 5 / 实际 6` 时序失败未再出现。

## 三、E2E 测试结果

**N/A（未执行，不标记为 PASS）**。`.stdd/config.d/quality.yaml` 明确配置
`quality.e2e.enabled: false`；本 change 是内部令牌桶时间边界，现有 middleware 轻集成
测试和三版本完整回归用于保护公开 HTTP 行为。

## 四、失败项与已知限制

### 4.1 非覆盖率 plain pytest 的既有吞吐门

- **测试**：`tests/unit/pipeline/test_flow_compat.py::test_tc_pe_003`
- **现象**：Build 阶段 plain pytest 为 1070 passed / 1 skipped / 1 failed；隔离复跑吞吐约 1.65k req/s，低于 7,128 门。
- **原因**：宿主机微基准环境，与本 change 的限流代码无调用路径；同一节点在项目规定的三版本 CI 等价 coverage 命令中通过。
- **影响**：不影响 TokenBucket 正确性；提示项目仍需保持微基准与功能覆盖环境分离。
- **补完计划**：沿用 `EXP-2026-0011` 的测量隔离方案，在无 trace、受控负载环境单独验证性能基线。

### 4.2 既存 `consume(amount <= 0)` 输入缺口

- **来源**：代码审查发现；基线与本 change 前后均存在。
- **原因**：`consume` 未显式拒绝零或负 amount；当前 middleware 仅调用默认 `amount=1`。
- **影响**：当前公开 HTTP 路径不可达，本 change 未扩大可达性；若未来直接暴露该内部 API，负数可能增加 token。
- **补完计划**：作为独立安全加固 STDD change，先规格化 amount 正数契约，再补 RED 测试和最小校验；不在本 change 静默扩范围。

### 4.3 STDD traceability CLI 对 async pytest 的假缺口

- **现象**：`stdd diff` 报告 5/6（83%），把 TC-RL-005 错映射到前一个同步测试，其余 async 节点函数名为空。
- **原因**：解析器只识别 `def test_`，不识别 `async def test_`；程序化矩阵也没有独立模型。
- **影响**：只影响工具展示，不影响真实测试。AST、pytest collect、Canonical checkpoints 证明 5 个 pytest 节点 + 1 个程序化矩阵为 6/6。
- **补完计划**：`EXP-2026-0023` 已记录；后续 STDD tooling change 使用 AST 并建模程序化 TC。

### 4.4 Verify Skill 的 Python 别名可移植性

- **现象**：Skill 示例硬编码 `python bin/stdd`，当前环境没有 `python` 别名；项目规定的 `python3 bin/stdd` 正常。
- **影响**：若逐字使用错误别名会假阻塞；本次所有 CLI 桥接均以 `python3` 成功执行。
- **补完计划**：`EXP-2026-0024` 已记录；后续 overlay/upgrade change 从项目配置解析解释器。

### 4.5 Gate 2 测试计划状态说明

`test-plan.md` 的“测试缺/待实现”是 Gate 2 锁定时的基线状态，不是当前结果。当前完成状态
以 `tasks.md`、`.stdd.yaml`、`phase-context.md` 和本报告为准；未回写锁定规格以避免静默
修改 Gate 2 文档。

## 五、功能/测试覆盖对照

| Requirement | Scenarios | TC | 实现/证据 | 缺口 |
|-------------|-----------|----|-----------|------|
| REQ-RL-006 确定性单调时间 | 007～010 | 005、008～010 | 实例 clock + 4 pytest 节点 | 无 |
| REQ-RL-007 并发序列化 | 011 | 007 | asyncio.Lock 持锁等待节点 | 无 |
| REQ-RL-008 三版本稳定性 | 012 | 011 | 可执行 uv 三版本 checkpoint | 无 |

总计：3/3 Requirements、6/6 Scenarios、6/6 TC 自动化覆盖。5 个 pytest 节点和 1 个
程序化矩阵均可重放；不存在手工验收冒充 PASS。

## 五-B、多路并行 Review 结果

### Review 迭代历史

| 轮次 | C | H | M | L | 状态 |
|------|---|---|---|---|------|
| 1 | 0 | 4 | 9 | 3 | 修复 change 内问题；去重后 3 个 H |
| 2 | 0 | 0 | 2 | 0 | 通过；2 个既存工具限制已记录 |

### 最终 Review 汇总

| 维度 | Critical | High | Medium | Low | 结论 |
|------|----------|------|--------|-----|------|
| 代码质量 | 0 | 0 | 0 | 0 | change 代码无发现；既存 amount 缺口列入后续 |
| 测试/配置 | 0 | 0 | 0 | 0 | 6/6 追踪链闭合 |
| 文档/Skills | 0 | 0 | 2 | 0 | CLI async 解析与 Python 别名限制 |

### Review 已修复问题

| 严重性 | 问题 | 修复 |
|--------|------|------|
| H | CP-RL-012 是自然语言、不可执行 | 改为真实 uv 三版本 shell checkpoint，并通过 bash 语法及运行验证 |
| H | proposal Human View 被 dry-run 意外缩短 | 恢复 Impact、Constraints、Risk/L3、Non-goals 和四项原则检查 |
| M | 默认时钟测试 monkeypatch 共享 stdlib `time.monotonic` | 改为实例时钟身份与行为断言，无全局 patch |
| M | Verify 活跃阶段、5+1 traceability 落后 | `.stdd.yaml` 更新为 verify 和 5 pytest + 1 programmatic |
| M | code-structure delta 未展示工作树 Python diff | 刷新并增加经 git/符号核对的手工补充 |

## 六、设计调整说明

无设计调整。详见 [design-adjustments.md](design-adjustments.md)。

## 七、十二类失败模式检查

| 类别 | 检查证据 | 结论 |
|------|----------|------|
| (a) 幻觉行为 | 所有文件、符号、解释器、uv extras、checkpoint 路径真实存在 | ✅ |
| (b) 范围蔓延 | 产品 diff 仅 TokenBucket + 对应测试；其余为强制 STDD 产物/经验 | ✅ |
| (c) 级联错误 | 未新增 try/except、fallback 或异常吞没 | ✅ |
| (d) 上下文丢失 | 实现逐项匹配 design Decisions 1～4 和 SC-RL-007～012 | ✅ |
| (e) 工具误用 | 文件编辑均用 apply_patch；发现 Python 别名限制并记录 EXP-0024 | ⚠️ 已规避 |
| (f) 运行时偏差 | 10 个 rate-limit 测试、锁等待与三版本完整矩阵真实执行 | ✅ |
| (g) 管线断链 | 已检查；本 change 无格式转换链，middleware→bucket 既有链完整 | ✅ N/A |
| (h) 内容质量 | Canonical/Human、state/report 指标交叉核对；Gate 2 状态语义已解释 | ✅ |
| (i) 指令衰减 | 三 Gate、RED/GREEN、逐切片验证、三代理和 12 类检查均执行 | ✅ |
| (j) 覆盖真空 | 真实 6/6；CLI 假缺口由 AST/collect 复核并记录 EXP-0023 | ✅ |
| (k) 契约断层 | 无 HTTP/config 字段变化；middleware 全回归通过 | ✅ N/A |
| (l) 锚定缺失 | L3 reference change、主 spec、实现、测试和 CI matrix 均存在并有测试映射 | ✅ |

检查完成度：12/12，SKIPPED 0，产品失败模式未解决项 0。

## 七-B、经验库更新

| 经验 ID | 类别 | 模式 | 严重度 |
|---------|------|------|--------|
| EXP-2026-0023 | coverage_vacuum | async pytest 导致错误 TC 映射与假覆盖缺口 | medium |
| EXP-2026-0024 | tool_misuse | 硬编码 python 别名导致可移植性假阻塞 | medium |

复用：EXP-2026-0006、0011、0014、0022，共 4 条。经验库当前总计 24 条；新增条目
保持 `discovered`，未伪造 verified/settled 状态。

## 七-C、项目原则复核

| 原则 | 实际结果与证据 | 状态 |
|------|---------------|------|
| Plugin / Flow；核心最小 | 只为既有限流 runtime 增加实例时钟边界，无插件、Flow 或领域策略扩张 | ✅ |
| 策略显式；失败不静默 | 冻结并发、补充公式、容量、锁、环境失败分别形成显式 Scenario/checkpoint | ✅ |
| 边界透明；契约稳定 | 两参数构造保持兼容；middleware/config/429/Retry-After 不变，三版本完整回归通过 | ✅ |
| 决策有证据；数据默认保护 | 6/6 可重放证据；不采集、记录或持久化请求内容 | ✅ |

**原则取舍、偏离及批准记录**：无。

## 八、结论

本 change 达到 Gate 3 条件。原 Python 3.11 时序失败已通过可控单调时钟消除，生产连续
补充和公开契约保持不变。三版本最终矩阵、覆盖率、Ruff、Mypy、Canonical、L3 锚定和
12 类失败模式检查均闭环。

| 信号源 | 状态 | 备注 |
|--------|------|------|
| 单元/集成测试 | ✅ | 三版本各 1077 passed / 1 skipped，失败 0 |
| E2E | N/A | 配置禁用，未伪装为 PASS |
| Ruff | ✅ | 项目/SDK/tools/examples 全范围 |
| Mypy | ✅ | 99 source files / 0 issues |
| 多版本 | ✅ | Python 3.10、3.11、3.12 |
| 覆盖率 | ✅ | 92.47%～93.34%，门槛 90% |
| 多路 Review | ✅ | 最终 C0/H0/M2/L0，M 为既存工具限制 |
| 十二类失败模式 | ✅ | 12/12，SKIPPED 0 |
| TC traceability | ✅ | 6/6（5 pytest + 1 programmatic） |

**交付建议**：可以进入 Phase 6；交付前保持 Gate 3 人工确认。既存 amount 输入缺口、
STDD async trace parser 和 Python 别名问题应分别进入后续独立 change，不在本次静默扩范围。
