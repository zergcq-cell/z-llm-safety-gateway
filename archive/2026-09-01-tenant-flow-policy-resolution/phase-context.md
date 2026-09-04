# Phase Context — 2026-09-01-tenant-flow-policy-resolution

## Phase 1: UNDERSTAND（completed 2026-09-01T22:01:48+08:00）

### 关键决策

- v0.3.0 roadmap 第 2/4 个实施 change，仅处理 tenant Flow/policy/Detector config/provider routing resolution。
- 多租户策略解析失败 fail-closed；旧单租户保持现有行为。
- Evidence/observability 和 resource/failure aggregate isolation 分别保留给第 3/4、4/4 change。
- 模式建议 `thorough`，复杂度初评 17/17。

### 用户确认

- Gate 1 已于 2026-09-01 明确确认。

## Phase 2: SPEC（completed 2026-09-01T22:58:16+08:00）

### 关键技术决策

- tenant 通过 `policy_id` 引用具名严格 policy；shared policy 显式允许并只编译一次。
- policy 显式声明 nullable input/output Flow、policy-local capability bindings、flag escalation 和 tenant routing。
- providers/flows 保持全局定义；Detector config/word-list 位于 binding，Provider secrets 不进入 policy Context。
- 启动编译私有 `TenantRuntimeBundle`；请求传播 frozen、secret-free `TenantPolicyContext v1.0`。
- 每 policy 独立 PipelineEngine 与 DetectorStatusRegistry；全部同步/流式/后台阶段使用同一 request snapshot。
- tenant Router view 复用全局 Provider adapters，只扫描本 policy 最多 256 条规则。
- `/v1/models` 使用显式 `models_provider`；legacy 继续全局首 Provider。
- tenant/global execution selectors 冲突时启动失败；不设静默优先级。
- runtime invariant failure 为 503 `tenant_policy_unavailable`；route miss 保持 404 `model_not_found`。
- streaming/output mode、安全、审计和资源治理仍为全局或后续 change 边界。

### 经验与工具限制

- 使用 EXP-2026-0001/0002/0005/0008/0009/0022/0023/0025 约束 snapshot、接线、失败、脱敏和追溯。
- 补充应用 EXP-2026-0011：有界性使用 deterministic operation count，不依赖 coverage 微基准。
- `extract-proposal` 未识别生成 Human View 的三级 capability headings；canonical proposal 作为权威来源。
- `canon generate --type spec` 在当前 STDD CLI 中存在已知渲染路由限制；Phase 2 使用 canonical-first 文件和确定性 Human Views，交付前执行 YAML/一致性等价校验。

### 产出物

- `design.md`
- 5 个 canonical code specs + 5 个 canonical agent specs
- 5 个 Human View specs
- `test-plan.md`：14 Requirements、27 Scenarios、27 TC；high 22 / medium 5 / low 0；P0 22 / P1 5。

### Gate 与执行模式

- Gate 2 已于 2026-09-01 明确确认。
- 用户选择全自动长程模式，并明确将本 change Phase 3–5 的在范围决策与操作全权授权给 Codex。
- Gate 3 仍依项目强制门等待用户明确确认；Git commit/push 不包含在本次预授权中。

## Phase 3: SLICE（completed 2026-09-01T23:07:54+08:00）

- CLI graph：5 nodes、0 edges、5 zero-dependency、0 cycles；因 spec 无机器可读 dependency fields，不能代表实现依赖。
- 人工依赖：schema → cross validation → resolver → Flow bundle/Router → all-path snapshot → production integration。
- 7 个切片覆盖 14/14 Requirements、27/27 Scenarios 和 27/27 TC；无循环。
- S4/S5 逻辑可并行，但都修改 app bundle boundary，当前单 agent 按 S4→S5 顺序执行。
- 所有 Capability 风险评分为高；P0 位于关键路径，5 个 P1 与同一安全 contract 紧密实施。

## Phase 4: BUILD（completed 2026-09-03T08:48:33+08:00）

- S1 完成：strict tenant policy schema、显式 stage、声明上限、tenant → policy 引用与 disabled/legacy 边界。
- S2 完成：所选 Flow/capability binding、tenant Provider routing 和 raw-source selector 冲突验证。
- S3 完成：`TenantPolicyContext v1.0`、私有 bundle、O(1) resolver、Auth 后 policy middleware 与安全 503。
- 聚焦回归和静态检查均通过；全量回归唯一信号为既有 TC-PE-003 wall-clock 吞吐微基准受当前主机负载影响，确定性 operation-count 仍为权威，Phase 5 将复测并记录环境证据。
- S4/S5 并行完成 per-policy runtime 与 tenant Router core，随后完成 `create_app`、chat、models 共享接线。
- S6 将 policy-local Flow identities、Detector/config、Node policy 与 status 冻结进同一 request snapshot；六类执行 stage 均不重读全局 runtime。
- S7 完成可执行双租户示例、roadmap 状态和 27/27 canonical checkpoint；Phase 4 于 2026-09-03 完成。

## Phase 5: VERIFY（completed 2026-09-05T00:22:01+08:00）

- 三路独立审查首轮结果：代码 C0/H5/M3/L1；测试 C0/H5/M7/L2；文档 C0/H5/M5/L0。
- 验证期 RED→GREEN 修复：bundle fail-open、tenant readiness、gRPC identity、circuit breaker、深冻结、健康原因码、secret repr/log，以及 buffer SSE 多事件解析。
- 最终 Python 3.12 覆盖率门为 1190 passed / 1 skipped / 93.02%；27/27 canonical checkpoints、49 个 unique nodes、60 个逐 checkpoint cases 全部通过。
- Python 3.10/3.11/3.12 功能矩阵均为 1189 passed / 1 skipped / 1 deselected；唯一单独失败是当前主机上的既有 TC-PE-003 wall-clock 吞吐信号（1671.73 < 7128 req/s），确定性 operation-count 仍为本 change 权威证据。
- S7 的 Phase 4 RED 结果未写入当时状态文件；该证据缺口保留，不以追溯性文字伪造历史结果。Phase 5 新增问题均已实际观察 RED 后修复。
- 三路审查的 Critical/High 已全部闭环；测试报告与 12 类失败模式检查完成，当前等待用户明确确认 Gate 3。
