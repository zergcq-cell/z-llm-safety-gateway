# Phase Context — 2026-08-30-tenant-identity-config-contract

> 阶段交接摘要。冲突时以各 Phase 正式产出物为准。

---

## Phase 1: UNDERSTAND (completed 2026-08-30T21:50:10+08:00)

### 关键决策

- **需求边界**：按 v0.3.0 roadmap 顺序，只实施 `tenant-identity-config-contract`。
- **安全目标**：先建立可信租户身份、配置 schema、启动校验和单租户兼容入口。
- **执行规模**：安全关键、L3 锚定、复杂度 14/17，采用 thorough 规格深度。

### 用户关注点

- 用户要求继续 v0.3.0，并明确确认 Gate 1。
- 既有长程执行习惯不自动继承到本 change；Gate 2 后重新选择 Phase 3–5 模式。

### 被否决的方向

- 同时实现四个 v0.3.0 changes：范围过大，违反 roadmap 的独立 Gate 约束。
- 在本 change 实现租户 Flow、证据或资源隔离：分别属于后续三个 change。
- 顺带加入 OAuth/JWT、Provider 或 Detector 能力：不属于当前里程碑单元。

### 产出物清单

- `proposal.md` — Gate 1 已确认。
- `canonical/proposals/2026-08-30-tenant-identity-config-contract.yaml` — 权威提案。

## Phase 2: SPEC (completed 2026-08-30T23:41:16+08:00)

### 关键技术决策

- 顶层 `tenancy` 显式 opt-in，默认关闭；新 tenancy 模型严格拒绝未知字段。
- tenant ID 为 1–64 位小写 ASCII slug；最多 1024 tenants、4096 API Keys。
- 多租户 v1 只信任服务端 API Key 绑定；auth 必须启用，每个 key 与 tenant 必须完整可达。
- `X-Tenant-ID` 等客户端 Header 不参与身份解析，也不形成公开选择协议。
- 启动期拒绝重复、悬空、未知、空名、无 key tenant 和关闭模式矛盾配置；错误稳定且脱敏。
- 放行请求获得 frozen `TenantContext v1.0`；旧配置获得内部 `default / legacy_single_tenant` Context。
- 保留 `api_key_name`、HTTP/SSE、Provider、Flow、Detector 与公开 401 契约。
- Phase 1 的 `api-key-authentication` 名称映射到仓库已有 `authentication` capability，不改变范围。

### 经验触发记录

- EXP-2026-0001：请求级上下文必须贯穿后续阶段 — 通过 frozen request Context 与并发隔离 Scenario 覆盖。
- EXP-2026-0005：安全配置示例必须由运行时模型反向校验 — 通过文档 YAML `load_config` 案例覆盖。
- EXP-2026-0008：配置接受不等于生产链消费 — 通过 `create_app` 真实双租户 HTTP 案例覆盖。
- EXP-2026-0022：TC-ID 必须全局唯一并绑定真实节点 — 18 个唯一 TC 与 18 个 agent checkpoint。
- EXP-2026-0023：异步测试不能被追溯器漏掉 — Phase 4/5 将以 collect-only 与 canonical checkpoint 交叉验证。

### 已知坑点 / 注意事项

- `stdd canon generate --type spec` 当前只调用 proposal renderer；已保留 canonical-first YAML，并机械生成一致工作副本和 Human View，不在本 runtime change 修改 STDD CLI。
- Gate CLI 的前序 Gate 路径检查存在既有嵌套路径缺陷；用户确认通过 `GATE1_APPROVED` / `GATE2_APPROVED` token 与 `.stdd.yaml` 双重记录。
- Cardinality 和 O(1) Scenario 为 medium confidence，需要在 Phase 4 用确定性、非 wall-clock 测试验证。

### 未解决问题（待 Phase 4 验证）

- Pydantic 与跨字段 validator 的错误边界是否能在所有矩阵分支保持 reason code 稳定且不回显 key。
- AuthMiddleware 的预编译映射如何以最小改动支持 legacy Context，同时保持现有中间件顺序。
- 最大合法配置的测试成本需要避免形成慢或脆弱的 CI 用例。

### 产出物清单

- `design.md` — Gate 2 已确认。
- `specs/*/spec.md` — 4 个 capability、10 Requirements、18 Scenarios。
- `canonical/specs/code/*.yaml` — 4 个权威行为规格。
- `canonical/specs/agent/*.yaml` — 18 个验证 checkpoint。
- `test-plan.md` — 18 个唯一 TC，P0 15 / P1 3。

## Phase 3: SLICE (completed 2026-08-31T20:26:07+08:00)

### 切片方案

- S1（先行）：Tenant schema、slug、cardinality 和 identity-only 边界 — 4 TC。
- S2（组 2）：Frozen Context、legacy Auth、O(1) lookup — 4 TC，依赖 S1。
- S3（组 2）：启动期 fail-closed 绑定矩阵 — 4 TC，依赖 S1。
- S4（组 3）：并发隔离、Header 防伪、中间件顺序 — 3 TC，依赖 S2/S3。
- S5（组 4）：YAML → create_app → HTTP 生产接线与兼容 — 3 TC，依赖 S2/S3/S4。

### 风险提示

- 四个 capability 均为高风险；认证、配置和生产接线必须逐切片保存 RED/GREEN 证据。
- CLI dependency graph 无显式边；`slices.md` 已补充真实实现依赖且无循环。
- S2/S3 逻辑可并行，但共享工作树中按拓扑顺序执行以保持 TDD 审计清晰。

### 产出物清单

- `slices.md` — 5 个切片、18/18 TC、0 cycle。
- `tasks.md` — 6 组实现和验证任务。

## Phase 4: BUILD（completed 2026-08-31T21:30:00+08:00）

### S1 完成 — Tenant schema 与边界

- TC 覆盖：4/4；新增参数化测试：12；定向：34 passed。
- 全量：1096 passed / 1 skipped，coverage 93%；Ruff、Mypy 通过。
- 新增/修改：`tests/unit/config/test_tenancy.py`、`config/models.py`。
- 边界发现：ADJ-001 将 roadmap 从 planning-only 推进为 change 1/4 active；更新 DESIGN 和文档契约。
- 已知环境证据：非插桩 TC-PE-003 在当前宿主吞吐门失败；覆盖率插桩命令按既有策略跳过该微基准阈值并通过全部功能回归。

### 当前状态

- Gate 1 / Gate 2 已确认；全自动长程模式已启用。
- Phase 3、Phase 4 完成；五个切片、18/18 TC 均已实现。
- S2：4/4 TC；11 个定向测试通过；全量 1100 passed / 1 skipped，coverage 93.37%；Ruff、Mypy 通过。
- `TenantContext v1.0` 为 frozen/slots 值对象；AuthMiddleware 仅使用预编译 key 映射，legacy 请求使用内部 default Context，无效凭据不创建 Context。
- S3：4/4 TC；11 个 failure-matrix 分支全部命中稳定脱敏 reason code；全量 1111 passed / 1 skipped，coverage 93.41%。
- S4：3/3 TC；并发隔离、Header 防伪和真实生产中间件顺序通过；全量 1114 passed / 1 skipped，coverage 93.41%。
- S5：3/3 TC；legacy 配置、环境变量示例和 create_app 双租户 HTTP 通过；全量 1117 passed / 1 skipped，coverage 93.41%。

### 下一步

- Phase 5 已完成并等待 Gate 3。最终全仓 1128 passed / 1 skipped、coverage 93.41%；Ruff/Mypy 和 Python 3.10/3.11/3.12 功能矩阵通过。
- 18/18 TC、18/18 canonical checkpoints、5/5 slices 均通过；三路 Review 最终 C0/H0/M0/L0。
- 12 类失败模式全部执行，4 类命中后修复，0 skipped；设计调整 2 项，无需 re-spec/re-build。
- Gate 3 确认后才可进入 Phase 6 DELIVER；当前没有 Git commit/push 授权。

## Phase 6: DELIVER（completed 2026-09-01）

- Gate 3 已于 2026-08-31T22:40:00+08:00 确认。
- change 已归档到 `archive/2026-08-30-tenant-identity-config-contract/`。
- Human specs、Canonical proposal/code/agent specs、canon index 与 code-structure index 已合并。
- 本 change 没有 deposited experience，社区上传步骤无需执行；EXP-2026-0025 保持 discovered。
- 归档后全仓回归：1128 passed / 1 skipped，coverage 93.41%；Ruff、Mypy、YAML 与 diff 检查通过。
- `stdd status <change>` 当前不能定位 archive 中的 change；归档 state 已直接核验为 `status: archived`。
- 用户已确认 Git 交付；提交信息为 `feat(tenancy): add trusted tenant identity contract`。
- 按里程碑边界不创建 `v0.3.0` tag；push 未授权，保留为后续独立操作。
