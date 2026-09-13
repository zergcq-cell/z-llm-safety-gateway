# Phase 2 review

结论：文档审查通过，等待 Gate 2。没有执行 Phase 3–5，没有源码变更。

- 需求覆盖：5 项能力均有 Canonical code/agent spec 和 Human View；10 requirements、26 scenarios、26 唯一 TC/CP 一一对应。
- 完备性：每个场景有 GIVEN/WHEN/SHALL THEN，AND 不超过 5；19 high、7 medium、0 low；P0=23、P1=3。
- 契约审查：四个 modified capability 均存在于主 specs；FlowEvidence v1.0 保持不变；新增配置、身份字段和指标在设计与规格中一致。
- 工具检查：STDD validate 通过；YAML 与 Human View hash/内容一致；88 个现有用例仅 collect-only 成功，新增测试全部明确 planned。
- 工具局限：系统 Python 无 PyYAML，改用项目环境；canon spec 渲染未生效，采用 Canonical 确定性渲染；extract-proposal 未读取 prose Impact，使用 canonical impact 补足。无工具链源码修改。
- 修订记录：见 design-adjustments.md，包括严格 schema、Gauge 状态、ASGI 生命周期、app 作用域及指标身份上界；无待处理审查问题。
- 锚定：L3 满足 safety_critical 的最低要求，参考三项已交付 change。

## 经验交叉检查

| 经验 | 预防落点 |
|---|---|
| EXP-2026-0001：快照贯穿全部阶段 | SC-TEC-004/005、SC-TAU-002 |
| EXP-2026-0002：外部只暴露稳定原因 | SC-TAU-005、SC-TOB-002/005 |
| EXP-2026-0005：安全配置示例需要运行时验证 | SC-TOC-001/003 |
| EXP-2026-0006：checkpoint 必须指向真实节点 | test-plan 第六节；Build 后 collect-only，当前不声称已存在 |
| EXP-2026-0008：配置解析不等于请求接线 | SC-TEC-002/004、SC-TOC-003 |
| EXP-2026-0010：完整 envelope 预算 | SC-TAU-004；512-byte 增量 + 既有 Flow 预算 |
| EXP-2026-0011：插桩不能替代真实性能基线 | test-plan 测试原则与第六节 |
| EXP-2026-0026：禁止缺失 runtime 回退全局 | SC-TEC-003 |
| EXP-2026-0027：阶段枚举不能替代真实多路径 | SC-TEC-004；真实 HTTP、SSE 和后台参数化 |
| EXP-2026-0028：SSE 网络 chunk 与 event 边界不同 | SC-TAU-002；合并/拆分 event 集成夹具 |

## 需要 Gate 2 审阅的取舍

精确审计归属与指标聚合并存；最多 32 租户指标明细，默认全部聚合。共享策略生命周期使用 policy scope。审计 sink 失败沿用显式 best-effort，不改变安全响应。多租户旧指标自由文本标签归并，单租户兼容。共享管理员 sinks 的访问隔离由部署负责，本次不提供租户查询 API 或物理分库。

Gate 2 明确批准后进入模式选择和 Phase 3 切片；Gate 3 不自动通过。
