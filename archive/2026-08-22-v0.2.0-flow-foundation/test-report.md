# v0.2.0 Flow Foundation 测试报告

> 测试日期：2026-08-23
> 测试环境：Darwin 25.5.0 arm64 / Python 3.10.20 / pytest 9.1.1
> 被测基线：`f1e26f1` + 当前 Flow Foundation 工作树
> 流程状态：Phase 5 VERIFY 已完成验证，Gate 3 待用户确认；未进入 DELIVER

## 一、总体概况

| 指标 | 结果 |
|---|---|
| 完整配置套件 | 1012 collected |
| 通过 | 1011 |
| 失败 | 0 |
| 跳过 | 1 |
| 通过率 | 100% = 1011 / (1012 - 1) |
| 执行耗时 | 15.46s（无 coverage）/ 20.00s（含 coverage） |
| 覆盖率 | 93% lines（5521 statements / 368 missed） |
| Ruff | PASS |
| Mypy | PASS（99 source files, 0 issues） |
| `git diff --check` | PASS |

### 1.1 受限沙箱与完整环境的区分

- 受限沙箱：`998 passed / 1 skipped / 0 failed / 13 setup errors`。13 个 error 全部是禁止绑定 `127.0.0.1:0`，集中在 3 个既有 gRPC 测试文件。
- 开放本机回环的相同套件：`1011 passed / 1 skipped / 0 failed`。
- 结论：gRPC setup error 是沙箱权限差异，不是产品失败；同一代码和测试在可绑定回环的环境全部通过。

### 1.2 覆盖率诊断

> 覆盖率是诊断信号，不单独作为阻断门。

| 关键变更模块 | 行覆盖率 | 结论 |
|---|---:|---|
| `flow/contracts.py` | 96% | PASS |
| `flow/policy.py` | 98% | PASS |
| `flow/runtime.py` | 94% | PASS |
| `flow/evidence.py` | 95% | PASS |
| `flow/detector_adapter.py` | 90% | PASS |
| `pipeline/flow_reducer.py` | 99% | PASS |
| `pipeline/snapshot.py` | 100% | PASS |
| `pipeline/engine.py` | 94% | PASS |
| `audit/logger.py` | 100% | PASS |
| `audit/streaming_evidence.py` | 89% | 接受；未覆盖为防御性不可表示分支 |
| `observability/flow.py` | 96% | PASS |
| `routes/chat.py` | 90% | PASS |
| `streaming/handler.py` | 88% | 接受；既有异常/可选分支为主 |

## 二、测试与契约执行

| 检查集 | 结果 | 说明 |
|---|---|---|
| 完整单元/集成/SDK/示例套件 | 1011 passed / 1 skipped | 开放本机回环 |
| Flow 聚焦回归 | 122 passed | Flow/config/runtime/audit/observability/HTTP/SSE/benchmark contract |
| Canonical primary node AST | 61/61 | 文件与函数均真实存在 |
| Canonical collect | 61 primary → 74 cases | 参数化展开已收集 |
| Canonical execution | 74/74 passed | 一次组合执行全通过 |
| Agent specs | 12/12 passed | `pipeline-engine/CP-003` 首次顺序运行短暂失败，重试通过 |
| 性能基准 | P99 0.15ms / 8,461 req/s / pending=0 | 门槛 P99 < 200ms / throughput >= 7,128 req/s |
| 文档配置/链接 | 2 passed | 示例经真实 Pydantic 模型校验 |

### 2.1 Test-plan 覆盖

- 计划 TC：61。
- 有 primary checkpoint 的 TC：61（100%）。
- AST 存在：61/61。
- 可收集：61/61，展开为 74 cases。
- 执行：74/74 PASS。
- 零自动化覆盖 Capability：0。

### 2.2 切片完成度

| 切片 | TC | 状态 | 核心验证 |
|---|---:|---|---|
| S1 Flow 契约 | 6/6 | PASS | strict/versioned contracts |
| S2 显式策略 | 6/6 | PASS | 四类独立 failure 维度 |
| S3 证据模型 | 5/5 | PASS | 终态、脱敏、预算 |
| S4 Runtime | 6/6 | PASS | 并发、stop、cancel、nested、deadline |
| S5 Detector adapter | 3/3 | PASS | descriptor/input/output/error mapping |
| S6 Lifecycle/framework | 5/5 | PASS | built-in/ML/entry-point/gRPC |
| S7 新配置模型 | 4/4 | PASS | strict schema/limits/conflicts |
| S8 Legacy compiler | 4/4 | PASS | 旧 YAML 与默认 Flow |
| S9 Reducer/facade | 5/5 | PASS | PipelineEngine 单路径委托 |
| S10 请求快照 | 4/4 | PASS | input/sync/async/stream/buffer/post-audit |
| S11 审计证据 | 5/5 | PASS | 加法字段与 sink failure |
| S12 Streaming 聚合 | 2/2 | PASS | 外层 256 KiB 硬界 |
| S13 Observability | 5/5 | PASS | 低基数、trace、privacy |
| S14 性能/checkpoint | 1/1 | PASS | P99/throughput/task leak/61-node anchor |

## 三、E2E 与多版本矩阵

| 项目 | 状态 | 原因与替代证据 |
|---|---|---|
| 独立 E2E runner | N/A（配置禁用） | `quality.e2e.enabled=false`；本 change 无 UI |
| HTTP/Provider/header | PASS | 真实 FastAPI/TestClient 集成回归 |
| SSE/window/buffer | PASS | SSE 顺序、原 chunk replay、block/recall |
| async/post-audit | PASS | immediate return 和 post-audit recall |
| fail-closed admission | PASS | Provider 前 503，Provider 调用数为 0 |
| Python 3.10.20 | PASS | 完整套件 1011 passed / 1 skipped |
| Python 3.11 | SKIPPED | 当前环境无解释器 |
| Python 3.12 | SKIPPED | 当前环境无解释器 |

## 四、多路 Review 与自动修复

### 4.1 最终只读复审发现

| 维度 | Critical | High | Medium | Low | 修复后未关闭 |
|---|---:|---:|---:|---:|---:|
| 代码质量 | 0 | 3 | 2 | 0 | 0 |
| 测试/配置 | 0 | 0 | 2 | 1 | 1（Python 3.11/3.12 环境） |
| 文档/Skills | 0 | 0 | 1 | 3 | 0 |
| 合计 | 0 | 3 | 5 | 4 | 1 |

### 4.2 本轮关闭的实质问题

| # | 原严重性 | 问题 | 修复与证据 |
|---|---|---|---|
| 1 | H | Nested Flow STOPPED/PARTIAL 证据计数崩溃并丢 child block | partial 终态可核对；reducer 收敛 child result；33 定向 PASS |
| 2 | H | 256×32 个最长 stop signals 令合法最大图超 256 KiB | 最终压缩层对 stop tuple 做确定指纹；256 终态保留；258,602 bytes |
| 3 | H | 生产 logging handler 内部吞 I/O 失败，误报 persisted=true | 专用 handler 上抛稳定内部信号；AuditEntry/返回/请求证据均为 false |
| 4 | M | near-limit post-audit 使 streaming 外层超预算 | 预留外层字节并二次压缩；不可表示时仅省略重复副本 |
| 5 | M | 正式 benchmark 报告器可用 1,000 req/s 误判 PASS | 锁定 7,128 req/s；50 warmup + 5×750 best-of-five；8 契约测试 PASS |
| 6 | M | 小于 256 KiB 的启动拒绝缺回归 | 1024/262143/262145 参数化启动校验 PASS |
| 7 | M/L | 阶段标题、TOC、artifact path、历史基线数不一致 | 已统一并通过文档链接/配置契约测试 |

## 五、十二类失败模式检查

| 模式 | 检查结果 | 证据/处置 |
|---|---|---|
| (a) 幻觉行为 | HIT → FIXED | RED 期对不存在 `GetDetectorInfo` 的假设已按真实 gRPC v1 proto 纠正；路径/符号/文档链接复核通过 |
| (b) 范围蔓延 | CHECKED / PASS | 无 K8s、Redis、Provider、UI 或新 detector；STDD/原则文件是项目强制治理边界 |
| (c) 级联错误 | HIT → FIXED | cancel cleanup 保留；审计 handler 吞错修为显式 unpersisted |
| (d) 上下文丢失 | HIT → RECORDED | 实现对 Phase 2 的三项偏差已全部进入 ADJ-001～003 |
| (e) 工具误用 | HIT → FIXED | coverage trace 不再与无插桩微基准直接比较；正式报告器锁定 change 门 |
| (f) 运行时行为偏差 | HIT → FIXED | 显式 Flow/capability binding 从 YAML 贯穿 app→engine→runtime→HTTP |
| (g) 管线断链 | HIT → FIXED | 六条执行路径共享 snapshot；Nested partial 结果现可跨 reducer 收敛 |
| (h) 内容质量偏差 | HIT → FIXED | 完整 Flow envelope 与 streaming outer envelope 均受 256 KiB 限制 |
| (i) 指令衰减 | CHECKED / PASS | thorough、RED→GREEN、12 类模式、7 强制 Step、Gate 3 停门均实际执行 |
| (j) 覆盖真空 | HIT → FIXED | checkpoint cwd/空集合风险已消除；61/61 AST、74 collect、74 PASS |
| (k) 契约断层 | HIT → FIXED | error/timeout/unavailable/circuit-open 独立到 reducer；Nested partial 输出契约修复 |
| (l) 锚定缺失 | CHECKED / PASS | 4 个 L3 reference changes 均存在；PipelineEngine/SDK/config/audit 锚点映射到 design/tasks/tests/diff |

## 六、设计调整

| ID | 调整 | 重新 Spec/Build |
|---|---|---|
| ADJ-001 | 顶层 `capabilities` 只绑定实现/私有配置，顺序与策略仍属 Flow | false / false |
| ADJ-002 | Evidence 固定 256 KiB；长身份/极端 stop tuple 确定性指纹；保留 256 终态 | false / false |
| ADJ-003 | 性能门与 coverage 隔离；warmup + best-of-five；硬门不变 | false / false |

详见 [design-adjustments.md](design-adjustments.md)。

## 七、经验库更新

| 类型 | 结果 |
|---|---|
| 本 change 新增 | 6 条（EXP-2026-0008～0013） |
| 复用既有 | 5 条（snapshot、稳定 reason、cancel cleanup、docs contract、checkpoint anchor） |
| 项目总计 | 13 条 |

新增经验覆盖 runtime deviation、contract gap、content quality、tool misuse、cascading errors 与 nested-result contract。

## 八、项目原则复核

| 原则 | 实际结果与证据 | 状态 |
|---|---|---|
| Plugin / Flow；核心最小 | Detector 领域语义在 adapter/reducer，组合/嵌套在 Flow；`flow.__init__` 不重导出 detector domain | PASS |
| 策略显式；失败不静默 | 五维 resolved policy、四类独立 fallback、稳定 reason、sink failure 明确可观测 | PASS |
| 边界透明；契约稳定 | HTTP/SSE/Provider/SDK/entry-point/gRPC/YAML/PipelineEngine 回归通过；时间/节点/并发/证据有硬界 | PASS |
| 决策有证据；数据默认保护 | 每 Node/Flow 有终态；原文/秘密/endpoint/raw exception 不进 evidence/trace；极端变长策略仅保留不可逆指纹 | PASS |

原则取舍均记录在 ADJ-001～003；无静默偏离。

## 九、强制 Verify Step 完成情况

| Step | 状态 |
|---|---|
| Step 0 三路技术评审 | 完成 |
| Step 1 全量质量检查 | 完成 |
| Step 2 Diff 审查 | 完成 |
| Step 3 十二类失败模式 | 完成（12/12） |
| Step 3.5 经验库 | 完成（6 新增 / 5 复用 / 13 总计） |
| Step 4 设计调整 | 完成（3 项） |
| Step 5 测试报告 | 完成（本文） |

## 十、剩余限制与 Gate 3 建议

| 严重性 | 项目 | 原因 | 影响 | 补完计划 |
|---|---|---|---|---|
| Medium | Python 3.11/3.12 未运行 | 当前环境无该解释器 | 本地无法独立证明完整支持矩阵 | 在 CI/可用环境运行 3.10–3.12 矩阵；当前如实记 SKIPPED |
| Low | 独立 E2E runner 禁用 | 项目 `quality.e2e.enabled=false`，本 change 无 UI | 无浏览器级额外信号 | 已用 HTTP/SSE/Provider 集成套件覆盖关键路径；后续可启用独立 E2E |
| Low | 性能 checkpoint 对宿主调度敏感 | 12-spec 顺序运行时首次短暂低于门槛 | 可能产生假回归，未观察到产品持续退化 | 重试 PASS，单节点 8/8 PASS，组合 74/74 PASS，正式基准 8,461 req/s；持续保留 warmup + best-of-five |
| Low | 受限沙箱 13 个 gRPC setup error | 平台禁止 loopback bind | 沙箱内套件退出非 0 | 已在可绑定回环的相同套件 1011/1011 通过；不修改产品或测试来掩盖权限问题 |

## 十一、结论

Flow Foundation 的产品实现、兼容契约、证据/隐私边界和性能硬门均已通过。终审发现的 3 High + 5 Medium + 4 Low 已关闭所有产品/文档问题；剩余为 1 个 Medium 环境矩阵缺口和 3 个已有替代证据的 Low 限制。

**建议：可提交 Gate 3 确认；用户明确确认前不进入 DELIVER。**
