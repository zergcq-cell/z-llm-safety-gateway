# v0.2.0 Flow Foundation — 设计调整说明

> 原始设计基线：Phase 2 的 `design.md`、`specs/`、canonical specs 与 `test-plan.md`
> 调整来源：Phase 5 多路技术评审、完整证据预算验证与性能 checkpoint

## 调整汇总

| # | 类型 | 调整 | 严重程度 | 阶段 | 影响 TC | 用户授权 |
|---|------|------|----------|------|---------|----------|
| ADJ-001 | design_change | 增加独立 Capability 实现绑定区 | Major | VERIFY | TC-CFG-001/005/006、TC-DCA-004、TC-DF-701/703、TC-DDF-005/006 | 全自动长程预授权；Gate 3 待确认 |
| ADJ-002 | boundary_discovery | Evidence 预算固定为可表示最大核心 envelope 的 256 KiB | Major | VERIFY | TC-CFG-005、TC-FR-006、TC-NEC-001/005/006、TC-AUD-704 | 全自动长程预授权；Gate 3 待确认 |
| ADJ-003 | test_change | 性能 checkpoint 与 coverage 插桩隔离并采用多轮容量测量 | Minor | VERIFY | TC-PE-003 | 全自动长程预授权；Gate 3 待确认 |

## ADJ-001：独立 Capability 实现绑定

- **原始设计**：显式 `flows` 与 `pipeline.detectors` 互斥，但没有为 gRPC endpoint、ML 模型参数或 entry-point 插件私有配置定义来源。
- **调整内容**：新增顶层 `capabilities`。它只绑定实现与私有配置，不决定执行顺序；Flow Node 继续唯一决定组合和策略。绑定身份严格校验，未使用或重复绑定在启动期拒绝，私有配置不进入 repr、证据或可观测属性。
- **原因**：缺少该边界时，显式 Flow 无法可靠使用已有四类 Detector，违反兼容目标。
- **原则影响**：能力仍归插件、顺序仍归 Flow；配置冲突显式失败；既有 HTTP/SDK/gRPC 契约不变；秘密默认不暴露。
- **重新规格判断**：无需回到 Phase 2。调整在原兼容需求范围内，已同步 change design、主 DESIGN、配置文档和自动化测试。

## ADJ-002：Evidence 预算的可表示性下界

- **原始设计**：锁定 256 KiB 总预算，但未明确是否接受更小的自定义值。
- **调整内容**：v0.2.0 仅接受 256 KiB。完整 envelope 超限时先删除可选摘要和 signals，再对长身份做确定性 SHA-256 缩写；极端合法图的完整 stop-signal tuple 仍过大时，以不可逆指纹保留其策略身份。最多 256 个 Node 终态、其他策略事实/source、状态与 reason 均保留；streaming 摘要为外层 envelope 预留字节，post-audit 主证据仍独立保留。
- **原因**：1 KiB 等较小预算无法容纳合法核心证据；同时 256×32×128 字符的合法 stop policy 以原字符串重复记录时也不可表示。两者都可导致请求在安全决定完成后返回 500。
- **原则影响**：资源上界不变；不可表示配置提前失败；核心安全证据不被静默丢弃；压缩身份不可逆且不增加敏感数据。
- **重新规格判断**：无需回到 Phase 2。它是已确认 256 KiB 硬限制的启动期可满足性收紧。

## ADJ-003：性能 checkpoint 测量方法

- **原始设计**：吞吐基线来自无插桩同机测量，但单轮测试可能在 coverage 或宿主调度暂停下比较。
- **调整内容**：coverage 仅诊断覆盖率；无 trace 时执行五轮短容量测量并取 best-of-five，P99 使用全部样本。硬门保持 P99 `< 200 ms`、吞吐 `>= 7,128 req/s`、pending Flow task `= 0`。
- **原因**：coverage line tracing 与单次调度暂停不是产品开销，直接比较会产生假回归。
- **原则影响**：门槛未放宽；测量条件更透明、可复现，性能和资源成本仍有界。
- **重新规格判断**：无需回到 Phase 2；仅修正验证方法。

## 结论

`requires_re_spec=false`，`requires_re_build=false`。三项调整均已实现、文档化并有自动化验证；最终接受仍由 Gate 3 确认。
