# v0.2.0 Flow Foundation 任务清单

> 执行模式：thorough + full-auto long-range
> 规则：每个切片严格执行 RED → GREEN → REFACTOR；精确 pytest node 必须先产生可观察失败，再以最小实现转绿。
> 覆盖：38 Requirements / 61 Scenarios / 61 TC。

## 通用切片门禁

- [ ] RED：先创建本切片所有 canonical agent checkpoints 对应的精确测试节点，并证明因缺少目标行为而失败。
- [ ] GREEN：仅实现本切片规格要求，使精确节点全部通过。
- [ ] REFACTOR：运行本切片、受影响既有回归、Ruff 与 Mypy；不得以删除断言或放宽兼容预期转绿。
- [ ] 状态：把测试证据、调整与回归结果写回本 change；一个切片验证完成后才能进入其下游切片。

## S1. 版本化 Flow 契约（P0）

- [x] S1.1 实现 `REQ-FC-001`：严格的 Flow/Node/Capability 契约版本、SemVer、ID 与未知字段校验（TC-FC-001～003）。
- [x] S1.2 实现 `REQ-FC-002`：CapabilityNode/NestedFlowNode 判别、引用、schema 与图限制（TC-FC-004～005，依赖 S1.1）。
- [x] S1.3 实现 `REQ-FC-003`：有序 FlowInput 与不可变请求上下文（TC-FC-006，依赖 S1.1）。

## S2. 显式策略解析（P0）

- [x] S2.1 实现 `REQ-FP-001`：解析完整 resolved policy 与来源（TC-FP-001，依赖 S1）。
- [x] S2.2 实现 `REQ-FP-002`：异常与 Node timeout 独立 fallback（TC-FP-002～003，依赖 S2.1）。
- [x] S2.3 实现 `REQ-FP-003`：unavailable 与 circuit-open 独立策略（TC-FP-004，依赖 S2.1）。
- [x] S2.4 实现 `REQ-FP-004`：Flow deadline 收敛与 policy conflict 启动拒绝（TC-FP-005～006，依赖 S2.1）。

## S3. 核心证据模型与保护（P0）

- [x] S3.1 实现 `REQ-NEC-001`：版本化 FlowEvidence/NodeEvidence、父子关联与确定顺序（TC-NEC-001～002，依赖 S1、S2）。
- [x] S3.2 实现 `REQ-NEC-002`：六种 Node 终态、partial 与 degraded 正交语义（TC-NEC-003，依赖 S3.1）。
- [x] S3.3 实现 `REQ-NEC-003`：证据字段白名单、稳定 reason、脱敏和 256KB 预算（TC-NEC-004～005，依赖 S3.1）。

## S4. Flow Runtime 调度、嵌套与取消（P0）

- [x] S4.1 实现 `REQ-FR-001`：有界并发、延迟创建任务、确定结果排序与空执行（TC-FR-001～002，依赖 S1～S3）。
- [x] S4.2 实现 `REQ-FR-002`：stop signal 触发、pending 取消与完整终态（TC-FR-003，依赖 S4.1）。
- [x] S4.3 实现 `REQ-FR-003`：Nested Flow 复用 snapshot、deadline 与证据语义（TC-FR-004，依赖 S4.1）。
- [x] S4.4 实现 `REQ-FR-004`：外层取消传播、finally 清理、硬限制与 deadline 收敛（TC-FR-005～006，依赖 S4.1）。

## S5. Detector Capability 契约与映射（P0）

- [x] S5.1 实现 `REQ-DCA-001`：四类 Detector 的统一 CapabilityDescriptor（TC-DCA-001，依赖 S1）。
- [x] S5.2 实现 `REQ-DCA-002`：DetectionContext、DetectorResult、signal 与内存 modification 精确映射，并保持 SDK 0.1.x 接口（TC-DCA-002～003，依赖 S5.1）。

## S6. Detector 生命周期与框架兼容（P0）

- [x] S6.1 实现 `REQ-DCA-003`：复用协调器状态、一次性 lifecycle、稳定异常与 cancellation/finally（TC-DCA-004～005，依赖 S2、S3、S5）。
- [x] S6.2 实现 `REQ-DF-701`：built-in、ML、entry-point 与 gRPC Detector 走统一 adapter/lifecycle/snapshot（TC-DF-701～702，依赖 S6.1）。
- [x] S6.3 实现 `REQ-DF-702`：SDK import、entry point group 与 gRPC proto 保持兼容（TC-DF-703，依赖 S6.2）。

## S7. 新 Flow 配置与启动验证（P0）

- [x] S7.1 实现 `REQ-CFG-001`：严格解析 `flow_runtime`、`flows` 与 stage refs，拒绝双重事实来源（TC-CFG-001～002，依赖 S1、S2）。
- [x] S7.2 实现 `REQ-CFG-003`：未知引用、循环、版本、上限和策略冲突的确定启动诊断（TC-CFG-005，依赖 S7.1）。
- [x] S7.3 实现 `REQ-CFG-004`：文档 YAML 示例由真实 runtime models 验证（TC-CFG-006，依赖 S7.1）。

## S8. Legacy YAML 编译（P0）

- [x] S8.1 实现 `REQ-CFG-002`：旧 YAML 保持加载并解析 legacy defaults（TC-CFG-003～004，依赖 S5、S7）。
- [x] S8.2 实现 `REQ-DDF-001`：确定性生成 legacy input/output Flow、策略来源与安全指纹（TC-DDF-001～002，依赖 S8.1）。

## S9. 默认 Reducer 与 PipelineEngine facade（P0）

- [x] S9.1 实现 `REQ-DDF-002`：保持 action/risk/modification/flag escalation 与 short-circuit 语义（TC-DDF-003～004，依赖 S4、S5、S8）。
- [x] S9.2 实现 `REQ-DDF-004`：注册版本化 detector-result-reducer，禁止 Flow core 导入 detector domain（TC-DDF-007，依赖 S9.1）。
- [x] S9.3 实现 `REQ-PE-001`：PipelineEngine 公共签名与结果兼容，只委托一次 Flow Runtime（TC-PE-001～002，依赖 S9.1～S9.2）。

## S10. 请求级默认 Flow 与公共边界（P0）

- [x] S10.1 实现 `REQ-DDF-003`：immutable FlowExecutionSnapshot 穿过 input、sync/async output、sliding-window、buffer 与 post-audit（TC-DDF-005～006，依赖 S6、S9）。
- [x] S10.2 实现 `REQ-DSV-701`：fail-open snapshot 一致降级及 fail-closed Provider 前 admission（TC-DSV-701～702，依赖 S10.1）。

## S11. 审计证据与持久化故障（P0）

- [x] S11.1 实现 `REQ-AUD-701`：AuditEntry 加法扩展 Flow/Node 字段并记录实际策略/终态（TC-AUD-701～702，依赖 S3、S4）。
- [x] S11.2 实现 `REQ-AUD-702`：证据与现有 content storage 分离，默认不保存敏感数据（TC-AUD-703，依赖 S11.1）。
- [x] S11.3 实现 `REQ-AUD-703` 的 sink 故障部分与 `REQ-NEC-004` 的持久化失败部分：决策不变、`evidence_persisted=false`、warning/metric（TC-AUD-705、TC-NEC-007，依赖 S11.1）。

## S12. Streaming 有界证据聚合（P0）

- [x] S12.1 完成 `REQ-AUD-703` 的 streaming 部分与 `REQ-NEC-004` 的聚合部分：window 运行时产证、默认有界聚合、post-audit 独立保存（TC-AUD-704、TC-NEC-006，依赖 S10、S11）。

## S13. 降级可观测性与隐私（P0）

- [x] S13.1 实现 `REQ-DSV-702`：所有降级原因使用稳定、受限、可解释且不泄密的 reason code（TC-DSV-703，依赖 S10、S11）。
- [x] S13.2 实现 `REQ-OBS-701`：低基数 Flow/Node metrics 与 disabled no-op（TC-OBS-701～702，依赖 S13.1）。
- [x] S13.3 实现 `REQ-OBS-702`：request→flow→node→nested-flow trace 层级与真实终态（TC-OBS-703，依赖 S13.1）。
- [x] S13.4 实现 `REQ-OBS-703`：配置 ID/enum 白名单、长度限制与 sanitization signal（TC-OBS-704，依赖 S13.2～S13.3）。

## S14. 性能、任务泄漏与 checkpoint 收口（P1）

- [x] S14.1 实现 `REQ-PE-002`：P99 < 200ms、throughput ≥ 7,128 req/s、pending Flow task=0（TC-PE-003，依赖 S1～S13）。
- [x] S14.2 用 AST 和 `pytest --collect-only` 验证 61 个 canonical agent checkpoint 均对应真实精确测试节点，禁止空 glob。
- [x] S14.3 运行全部 61 个 TC、既有 HTTP/SSE/Provider/SDK/entry-point/gRPC/YAML/PipelineEngine 回归、Ruff、Mypy 与 benchmark。

## Phase 5 验证与 Gate 3（P0）

- [ ] V1 逐项回答 `PRINCIPLES.md` Required Principle Check，并记录所有取舍或偏离。
- [ ] V2 执行 L3 锚定与全量失败模式检查，生成 `test-report.md` 和 `design-adjustments.md`。
- [ ] V3 审查完整 diff、未提交用户改动保护、隐私边界、公开兼容契约与任务/资源清理。
- [ ] V4 Gate 3 强制等待用户确认；不得自动进入 Deliver。
