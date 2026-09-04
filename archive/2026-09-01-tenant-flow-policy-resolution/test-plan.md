# v0.3.0 租户级 Flow 与安全策略解析测试方案

> 版本：Phase 2 confirmed draft
> 创建日期：2026-09-01
> 对应 Specs：tenant-policy-resolution、tenant-config-contract、default-detector-flow、provider-proxy、config-system

## 一、测试策略

### 1.1 测试金字塔

- 单元测试约 60%：Pydantic schema、跨字段 validator、policy resolver、Router view、冻结与有界性。
- 集成测试约 35%：真实 `create_app`、Flow/Detector bundle、chat sync/SSE/async/post-audit、models endpoint。
- 契约/结构测试约 5%：依赖边界、文档状态、Canonical/TC/Agent checkpoint 一致性。

### 1.2 测试原则

- 每个 TC 先 RED，再以最小实现 GREEN，随后在切片内 REFACTOR。
- 可信身份到 policy/Flow/Provider 的生产接线必须由真实 ASGI 请求证明。
- 同一请求的所有同步、流式和后台阶段必须持有一个冻结 bundle/snapshot。
- 失败测试同时断言稳定 code、无 fallback、无 Provider 调用和无 secret 泄漏。
- 有界性使用操作计数和拒绝迭代 sentinel；wall-clock 性能只作为非插桩补充信号。
- TC-ID 全仓唯一且每个 Agent checkpoint 绑定真实 pytest node。

### 1.3 已有测试资产

| 测试文件 | 类型 | 可复用范围 |
|----------|------|------------|
| `tests/unit/config/test_tenancy.py` | 单元 | 租户 ID、API Key 绑定、启动失败和 legacy compatibility |
| `tests/unit/middleware/test_tenant_identity.py` | 单元/异步 | 可信 TenantContext、并发、Header 防伪 |
| `tests/integration/test_default_detector_flow.py` | 集成 | Flow 编译、snapshot、reducer、SSE 路径 |
| `tests/unit/providers/test_router.py` | 单元 | glob first-match、route miss、Provider factory |
| `tests/integration/test_models_endpoint.py` | 集成 | `/v1/models` passthrough 和 Provider error |
| `tests/integration/test_tenant_identity_contract.py` | 集成 | 真实 YAML、Auth middleware、HTTP compatibility |
| `tests/unit/routes/test_availability_guard.py` | 单元/异步 | fail-open/closed snapshot 与 Provider admission |
| `tests/integration/test_streaming.py` | 集成 | sliding-window、buffer、async、post-audit、SSE order |

## 二、详细测试案例

> 下表“状态”列冻结保存 Phase 2 / Gate 2 时的计划基线（因此仍显示“待 RED”），不作为当前执行状态。
> Phase 4/5 实际结果：TPR 6/6、TCC 7/7、DDF 5/5、PROXY 5/5、CFG 4/4，合计 27/27 已实现并通过 canonical checkpoint；验证期补强后为 49 个 unique pytest nodes，按 checkpoint 分别执行为 60 cases。

### 2.1 tenant-policy-resolution

| ID | 对应 Scenario | 优先级 | 预置条件 / 输入 | 预期结果 | 状态 |
|----|---------------|--------|-----------------|----------|------|
| TC-TPR-001 | SC-TPR-001 | P0 | 两个可信 Context 绑定两个 compiled policies；分别 resolve | 各自获得 frozen safe Context 和正确私有 bundle；发生在 availability/provider 前 | 待 RED |
| TC-TPR-002 | SC-TPR-002 | P0 | acme key 携带 globex tenant/policy/provider hints | 仍选择 acme policy；不建立公开选择协议 | 待 RED |
| TC-TPR-003 | SC-TPR-003 | P0 | 参数化缺 Context、未知 policy、缺 bundle invariant | 503 `tenant_policy_unavailable`；无任何 fallback/secret | 待 RED |
| TC-TPR-004 | SC-TPR-004 | P0 | 旧单租户配置与请求 | 保持全局 engine/router/detectors；legacy Context 保留 | 待 RED |
| TC-TPR-005 | SC-TPR-005 | P0 | 并发屏障 + sync/async/SSE/buffer/post-audit | 每条路径只持 originating bundle/snapshot，无跨请求污染 | 待 RED |
| TC-TPR-006 | SC-TPR-006 | P1 | 1024 policies、每 policy 256 rules/bindings；mapping 禁止迭代 | 一次 mapping lookup，route comparisons ≤256，无声明扫描 | 待 RED |

### 2.2 tenant-config-contract

| ID | 对应 Scenario | 优先级 | 预置条件 / 输入 | 预期结果 | 状态 |
|----|---------------|--------|-----------------|----------|------|
| TC-TCC-008 | SC-TCC-008 | P0 | 两个完整 policy schema，含显式 null stage 对照 | 严格解析；slug/字段/显式 stage 契约成立 | 待 RED |
| TC-TCC-009 | SC-TCC-009 | P1 | shared policy；1025 policies/257 bindings/257 rules | shared 编译一次；超限精确失败且无 order fallback | 待 RED |
| TC-TCC-010 | SC-TCC-010 | P0 | 空 policies、缺 policy_id、重复/未知 policy | 精确稳定 code；不合成或选择首项 | 待 RED |
| TC-TCC-011 | SC-TCC-011 | P0 | unknown Flow、missing/duplicate/unused binding、nested invalid | 启动失败；每 capability 恰一 binding；保持图限制 | 待 RED |
| TC-TCC-012 | SC-TCC-012 | P0 | unknown provider、exact route conflict、invalid models provider | 三类稳定 code；无 Key；合法 overlap 保持 first-match | 待 RED |
| TC-TCC-013 | SC-TCC-013 | P0 | policies 分别与四类 global selector 共存 | `conflicting_tenant_policy_sources`；声明级 globals 仍允许 | 待 RED |
| TC-TCC-014 | SC-TCC-014 | P0 | disabled tenancy + policy fields；纯 legacy control | 矛盾失败；legacy 完全兼容 | 待 RED |

### 2.3 default-detector-flow

| ID | 对应 Scenario | 优先级 | 预置条件 / 输入 | 预期结果 | 状态 |
|----|---------------|--------|-----------------|----------|------|
| TC-DDF-008 | SC-DDF-008 | P0 | 两租户不同 input/output Flows 处理相同内容 | action/risk/stop/failure 完全来自各自 Flow | 待 RED |
| TC-DDF-009 | SC-DDF-009 | P0 | 同 capability 不同 threshold/word-list/flag escalation | 结果按各自 binding/reducer；Context/日志无原始配置 | 待 RED |
| TC-DDF-010 | SC-DDF-010 | P0 | 全部六类输出路径及 input path | 一个 bundle 贯穿；无 global reintroduction；HTTP/SSE 兼容 | 待 RED |
| TC-DDF-011 | SC-DDF-011 | P0 | 同名 Detector，仅 acme unavailable；required failure 对照 | 状态按 policy 隔离；required 失败阻止 readiness | 待 RED |
| TC-DDF-012 | SC-DDF-012 | P1 | AST/import 与 runtime branch 检查 | Flow core 无 tenant/detector/provider domain 分支；reducer 边界不变 | 待 RED |

### 2.4 provider-proxy

| ID | 对应 Scenario | 优先级 | 预置条件 / 输入 | 预期结果 | 状态 |
|----|---------------|--------|-----------------|----------|------|
| TC-PROXY-013 | SC-PROXY-013 | P0 | 同 model 在 acme/globex rules 指向不同 Provider | 只调用各自 Provider；body/model 原样；adapter 私有复用 | 待 RED |
| TC-PROXY-014 | SC-PROXY-014 | P0 | model 仅匹配 global/其他 tenant | 404 `model_not_found`；零 Provider 调用；无拓扑泄漏 | 待 RED |
| TC-PROXY-015 | SC-PROXY-015 | P0 | Header/body 注入 tenant/policy/provider/routing hints | hints 全忽略；只在 captured policy rules 匹配 model | 待 RED |
| TC-PROXY-016 | SC-PROXY-016 | P0 | tenant `models_provider` 与 global first 不同 | `/models` 只查询显式 Provider并透传；legacy 仍 first | 待 RED |
| TC-PROXY-017 | SC-PROXY-017 | P1 | shared 与 distinct Provider refs | 每 Provider 初始化一次；Context/error/log 无对象、URL、Key、rules | 待 RED |

### 2.5 config-system

| ID | 对应 Scenario | 优先级 | 预置条件 / 输入 | 预期结果 | 状态 |
|----|---------------|--------|-----------------|----------|------|
| TC-CFG-704 | SC-CFG-704 | P0 | 真实 YAML + 两 keys + distinct policy/Flow/config/route；ASGI sync/SSE | production path 端到端消费各自 policy，无隔离漂移 | 待 RED |
| TC-CFG-705 | SC-CFG-705 | P0 | 文档示例 + 真实 env Gateway/Provider Keys | load/create 成功；字段可达；所有文档/错误/log/repr/Context 无 secret | 待 RED |
| TC-CFG-706 | SC-CFG-706 | P0 | 全部 legacy YAML 与 HTTP/SSE/Flow/Provider corpus | 配置、状态、body、headers、payload、SSE order 完全兼容 | 待 RED |
| TC-CFG-707 | SC-CFG-707 | P1 | 当前 DESIGN/README/CHANGELOG/AGENTS/spec/index | 准确呈现 change 1 delivered、2 active/delivered、3/4 pending；不 release/tag | 待 RED |

## 三、测试执行矩阵

> 本节表格同样保留 Gate 2 基线。当前五个模块均已实现并进入 Phase 5 全量验证，执行证据见 `test-report.md`（生成中）与 `.stdd.yaml`。

| 功能模块 | 单元测试 | 集成测试 | E2E/契约 | 状态 |
|----------|----------|----------|----------|------|
| Trusted policy resolution | TPR-001～006 | TPR-005 路径组合 | CFG-704 | 待实现 |
| Policy schema/validation | TCC-008～014 | CFG-705 | YAML 文档契约 | 待实现 |
| Tenant Flow/Detector | DDF-009/011/012 | DDF-008～011 | CFG-704/706 | 待实现 |
| Tenant Provider routing | PROXY-013～015/017 | PROXY-016 | CFG-704/706 | 待实现 |
| Compatibility/roadmap | CFG-705/707 | CFG-704/706 | 全量质量门 | 待实现 |

## 四、回归风险矩阵

| 风险区域 | 本 change 改动 | 已有回归保护 | 风险等级 |
|----------|---------------|--------------|----------|
| Auth → route 顺序 | TenantContext 后新增 policy resolve | tenant identity middleware/integration | 高 |
| Pipeline app wiring | global engine/detectors 扩展为 per-policy bundle | default Flow、availability、chat pipeline | 高 |
| Async/SSE/post-audit | 捕获 request-specific engine/snapshot | streaming、post-audit、recall | 高 |
| Provider chat/models | Router view 与 explicit models Provider | router/chat/models endpoint | 高 |
| Config compatibility | strict policies 与 source conflict | config loader/validators/legacy corpus | 高 |
| Secret protection | safe Context 与 private bundle 分离 | config/auth/audit sanitization | 高 |
| Flow core boundary | 新 resolver 不得侵入 runtime | dependency boundary/reducer tests | 中 |
| Roadmap/docs | 进度从 1/4 更新到 2/4 | documentation contract | 中 |

## 五、建议补充顺序

1. **P0**：先完成 TCC-008/010～014 和 TPR-001～004，锁定 schema、信任与 fail-closed 边界。
2. **P0**：完成 DDF-008～011、PROXY-013～016 和 TPR-005，贯穿真实执行路径。
3. **P0**：完成 CFG-704～706，建立 YAML→HTTP/SSE→Provider 的整体证据。
4. **P1**：完成 TPR-006、TCC-009、DDF-012、PROXY-017、CFG-707，锁定有界性、依赖边界和项目状态。

总计：27 TC；P0 22，P1 5，P2 0。每个 Scenario 恰好映射一个全仓唯一 TC。
