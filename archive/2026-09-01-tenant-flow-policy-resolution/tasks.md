# v0.3.0 租户级 Flow 与安全策略解析任务清单

## 1. Tenant policy schema 与基础身份引用（P0）

- [x] 1.1 为 TC-TCC-008/009/010/014 编写 RED：strict policy schema、显式 stage、共享/上限、identity reference 和 legacy 边界。
- [x] 1.2 实现 policy/result/routing Pydantic models、tenant `policy_id` 和 declaration limits。（依赖 #1.1）
- [x] 1.3 实现基础 tenant → policy 一致性 validator 与稳定、脱敏 reason codes。（依赖 #1.2）
- [x] 1.4 运行 S1 聚焦测试及 config/tenant identity 回归。

## 2. Flow、Capability、Provider 与 source 交叉验证（P0）

- [x] 2.1 为 TC-TCC-011/012/013 编写 RED：Flow/binding refs、route/models Provider refs 和 global selector 冲突。
- [x] 2.2 实现所选 Flow 展开、每 capability 恰一 policy-local binding 和 nested Flow 限制复用。（依赖 #1.3、#2.1）
- [x] 2.3 实现 tenant routing 引用、精确 pattern conflict、models Provider allow 和 256 rule bound。（依赖 #1.3、#2.1）
- [x] 2.4 实现 raw-source tenant/global execution selector 冲突验证。（依赖 #2.1）
- [x] 2.5 运行 S2 聚焦测试及现有 Flow/config/provider validator 回归。

## 3. Trusted policy resolver 与 safe Context（P0 / P1）

- [x] 3.1 为 TC-TPR-001～004/006 编写 RED：trusted lookup、防伪、503 invariant、legacy、operation bounds。
- [x] 3.2 实现 frozen `TenantPolicyContext v1.0`、私有 bundle contract 和 O(1) `TenantPolicyResolver`。（依赖 #2.5、#3.1）
- [x] 3.3 将 resolver 接到 Auth 后、availability/provider 前；实现 503 `tenant_policy_unavailable` 边界。（依赖 #3.2）
- [x] 3.4 运行 S3 聚焦测试及 Auth/TenantContext 回归。

## 4. Per-policy Flow runtime bundle 与 Detector 生命周期（P0 / P1）

- [x] 4.1 为 TC-DDF-008/009/011/012 编写 RED：不同 Flow/config/result、同名 Detector status 隔离、core boundary。
- [x] 4.2 启动期按 policy 编译 PipelineEngine、Detector instances/configs/policies 和独立 status registry。（依赖 #3.4、#4.1）
- [x] 4.3 shared policy 只初始化一次，required Detector failure 继续阻止 readiness。（依赖 #4.2）
- [x] 4.4 保持 Flow core/reducer 依赖边界并运行 S4 聚焦与 Flow Foundation 回归。

## 5. Tenant Router view 与 models endpoint（P0 / P1）

- [x] 5.1 为 TC-PROXY-013～017 编写 RED：same-model distinct routing、route miss、hint 防伪、models Provider、adapter reuse。
- [x] 5.2 重构 ModelRouter 以共享 Provider adapters 并生成 immutable bounded tenant Router views。（依赖 #3.4、#5.1）
- [x] 5.3 chat 只在 captured policy rules 中 route；无匹配保持 404 且零 Provider 调用。（依赖 #5.2）
- [x] 5.4 `/v1/models` 使用 explicit models Provider，legacy 保持 first provider passthrough。（依赖 #5.2）
- [x] 5.5 运行 S5 聚焦测试及现有 provider/chat/models regressions。

## 6. 全路径 request snapshot 收敛（P0）

- [x] 6.1 为 TC-TPR-005/TC-DDF-010 编写 RED，覆盖 input、sync/async output、sliding-window、buffer、post-audit。
- [x] 6.2 扩展 `FlowExecutionSnapshot` 与 route 装配，使全部阶段消费 captured policy bundle。（依赖 #4.4、#5.5、#6.1）
- [x] 6.3 修正 background closure、StreamingHandler、PostAuditRunner 和 availability stage 的 global fallback。（依赖 #6.2）
- [x] 6.4 运行 S6 聚焦测试及 streaming/async/audit/availability regressions。

## 7. Production wiring、文档与整体验收（P0 / P1）

- [x] 7.1 为 TC-CFG-704～707 编写 RED：真实 YAML→ASGI、env secrets、legacy corpus、roadmap state。
- [x] 7.2 更新 multi-tenant example，并完成真实 `create_app` 两租户 policy/Flow/Provider 接线。（依赖 #6.4、#7.1）
- [x] 7.3 更新 DESIGN/README/CHANGELOG/AGENTS，准确呈现 change 1 delivered、2 active，3/4 pending。（依赖 #7.1）
- [x] 7.4 运行 27/27 checkpoints、AST/collect-only traceability、全量 pytest、ruff、mypy、YAML 和 diff checks。

## 8. Phase 4/5 记录与质量门

- [x] 8.1 S1–S6 已记录 RED→GREEN→REFACTOR 证据；S7 原始 RED 结果缺失并已在状态、Phase Context 与 Gate 3 材料中如实披露。
- [x] 8.2 生成 code-structure delta、design-adjustments/pending-adjustments（如触发）。
- [x] 8.3 Phase 5 完成 12 类失败模式、多轮 review、Python 3.10/3.11/3.12 矩阵和测试报告。
- [x] 8.4 Gate 3 前确认全部 agent checkpoint 指向真实 pytest node，测试通过率 ≥95%。
