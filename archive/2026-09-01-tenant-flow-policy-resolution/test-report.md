# tenant-flow-policy-resolution 测试报告

> 测试日期：2026-09-03—2026-09-05
> 测试环境：Linux；Python 3.10.21 / 3.11.16 / 3.12.14；pytest 9.1.1
> 被测基线：`e342d39` + 当前 change 工作区

## 一、总体概况

| 指标 | 数值 |
|------|------|
| 覆盖率门收集 | 1191 |
| 通过 | 1190 |
| 失败 | 0 |
| 跳过 | 1 |
| 非跳过用例通过率 | 100% |
| 总覆盖率 | 93.02%（门槛 90%） |
| 执行耗时 | 74.03 秒 |
| Canonical checkpoints | 27/27 通过；49 unique nodes；60 per-checkpoint cases |

覆盖率最低的本 change 新模块是 `tenancy/runtime.py` 83%；其未覆盖分支主要为防御性启动失败组合。身份不匹配、初始化失败、清理、路由缺失、健康超时和请求路径已有定向测试，本轮不再为数字补无效测试。

## 二、执行矩阵

| 环境 / 门 | 结果 | 说明 |
|-----------|------|------|
| Python 3.12 coverage/release gate | 1190 passed, 1 skipped；93.02% | PASS |
| Python 3.10 functional | 1189 passed, 1 skipped, 1 deselected | PASS |
| Python 3.11 functional | 1189 passed, 1 skipped, 1 deselected | PASS |
| Python 3.12 functional | 1189 passed, 1 skipped, 1 deselected | PASS |
| Ruff | 全部源码、测试、SDK、工具和插件示例 | PASS |
| mypy | 104 source files | PASS |
| YAML parse / `git diff --check` | 无错误 | PASS |
| `pip-audit` | 无已知第三方漏洞；本地项目自身不在 PyPI | PASS |
| E2E | `quality.e2e.enabled: false` | N/A |

功能矩阵仅 deselect `tests/unit/pipeline/test_flow_compat.py::test_tc_pe_003`。该历史 wall-clock 微基准在当前桌面宿主单独运行得到 1671.73 req/s，低于历史阈值 7128 req/s；P99 断言通过。它不位于本 change diff，coverage tracing 下按既有设计跳过吞吐断言。SC-TPR-006 使用确定性操作计数，并验证 1024 policies × 每 policy 256 bindings/rules 的最大声明结构，因此该环境信号不被伪报为产品 PASS，也不作为本 change 的结构有界性证据。

## 三、功能与契约覆盖

| Capability | TC | 关键证据 | 结果 |
|------------|----|----------|------|
| tenant-policy-resolution | 6/6 | trusted O(1) lookup、safe Context、503、legacy、真实并发 sync/async/SSE snapshot | PASS |
| tenant-config-contract | 7/7 | strict schema、Flow/binding/provider refs、selector conflict、上限 | PASS |
| default-detector-flow | 5/5 | policy-local engine/config/reducer/status、readiness、Flow core boundary | PASS |
| provider-proxy | 5/5 | tenant router、route miss、hint 防伪、models passthrough、adapter reuse | PASS |
| config-system | 4/4 | documented YAML→create_app、四类 env secret、legacy corpus、roadmap | PASS |

生产路径补强覆盖：同一 ASGI event loop 的两租户请求在 Provider 回调处会合后，acme 同步输出保持 allow、globex 同步输出按本租户策略 422；buffer/sliding-window、async output、recall/post-audit 均消费原请求 snapshot。`/ready` 以全实例 strict 状态 fail-closed，但明细与 degraded 只来自当前租户，健康检查并发批次最多 32 且总刷新截止时间 5 秒。

## 四、多路 Review

首轮三路审查合计 C0/H15/M15/L3，所有 Critical/High 代码与文档问题均经观察失败、修复和聚焦回归。主要闭环包括：不完整 bundle 全局 fallback、tenant readiness、gRPC identity、policy circuit breaker、deep freeze、secret repr/log、SSE event 重组、真实并发 sync output、readiness 信息隔离/总 deadline、启动清理，以及同名 Detector 的 policy-scoped audit/metrics。

最后一轮成功回执为：文档 C0/H0/M1/L0（仅 checkpoint 计数陈旧，已按实际 collect 的 49/60 修正）；代码 C0/H1/M2/L0（总 deadline、degraded 隔离、policy metrics 归因，均已修复并通过聚焦及全量门）。测试 reviewer 的追加回执因账户用量限制中断；其上一轮 H 项（并发 sync output 与 S7 证据）分别由真实 ASGI 屏障闭环、作为 Gate 3 流程偏差披露。中断属于审查工具限制，不伪报为独立复审通过。

## 五、十二类失败模式检查

| 类别 | 证据与结论 | 状态 |
|------|------------|------|
| 幻觉路径 / 环境 / API | YAML 实际加载、create_app、真实 pytest node 与三版本解释器执行 | PASS |
| Scope creep | diff 对照授权路径；调整集中记录；未实现控制面/数据库/后续资源隔离 | PASS |
| 级联 / 静默 fallback | 不完整 bundle、missing policy/router 均稳定 503/404 且 Provider 零调用 | PASS（命中并修复） |
| Context loss / spec mismatch | 14 Requirements、27 Scenarios、27 TC 和 canonical action 逐项对照 | PASS |
| Tool misuse | 27 action 逐条 subprocess 执行，非字符串或 stage-name 代替 | PASS |
| Runtime deviation | readiness、gRPC identity、circuit breaker 真实生产接线测试 | PASS（命中并修复） |
| Pipeline break | 多事件 SSE chunk 曾绕过 buffer 检测，现由 SSEBuffer 重组并回归 | PASS（命中并修复） |
| Content quality | 文档链接、roadmap 唯一权威、示例环境变量和状态契约测试 | PASS |
| Instruction decay | S1–S6 有 RED 记录；S7 Phase 4 原始 RED 未留存，未追溯伪造 | GATE 3 偏差确认 |
| Coverage vacuum | checkpoint 改为真实 sync/async/SSE/readiness/router/factory 路径 | PASS（命中并修复） |
| Contract gap | 精确 upstream body、raw models bytes/content-type、HTTP/SSE error 断言 | PASS |
| Anchoring gap | L3 引用三个已交付 change；原则、spec、design、test-plan 一致 | PASS |

## 六、设计调整与经验

五项调整详见 [design-adjustments.md](design-adjustments.md)。新增经验：EXP-2026-0026（不完整租户 bundle 不得回落全局）、EXP-2026-0027（stage-name 测试不等于生产路径证据）、EXP-2026-0028（SSE buffer 必须按事件边界重组）。复用 EXP-2026-0001、0002、0005、0008、0011、0025。

## 七、项目原则复核

| 原则 | 实际结果与证据 | 状态 |
|------|---------------|------|
| Plugin / Flow；核心最小 | tenant 只在编译/装配边界选择 plugin binding；Flow core AST 与 reducer/runtime 测试禁止 tenant/Detector/Provider domain import | PASS |
| 策略显式；失败不静默 | nullable stage、routing、availability、circuit breaker 均显式；缺 bundle、超时、route miss、初始化失败均稳定失败 | PASS |
| 边界透明；契约稳定 | trusted identity 与私有 bundle 分离；legacy、Provider body、models bytes、HTTP/SSE 均回归 | PASS |
| 决策有证据；数据默认保护 | snapshot/status/audit 有证据；deep freeze；key/config/word-list 不进入 repr、错误、routine logs 或文档产物 | PASS |

原则之间无未记录取舍。Policy ID 加入生命周期 audit/metrics 只解决本 change 同名状态归因，不实现 change 3/4 的请求级 evidence/trace 隔离。

## 八、结论

实现与可修复的质量问题已完成，推荐进入 Gate 3。Gate 3 必须显式知悉并接受两项非隐藏信号：

1. S7 的 Phase 4 原始 RED 结果未留存，属于不可追溯修复的流程证据偏差；Phase 5 的所有修复均保留实际 RED→GREEN。
2. 既有 TC-PE-003 wall-clock 吞吐在当前桌面宿主低于历史 release baseline；本 change 的结构性能结论来自确定性 operation-count，不以该环境信号替代正式独占 runner benchmark。

Gate 3 通过前不归档、不合并 specs、不 commit、不 push。
