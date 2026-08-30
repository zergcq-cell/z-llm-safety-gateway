# v0.3.0 里程碑范围定义与 Roadmap 统一 - 技术设计

## Context

Gateway 当前公开版本为 v0.2.2，Detector SDK 当前独立版本为 v0.1.1。内部开发阶段
v0.0.1–v0.0.5 已完成 Framework、Pipeline、Streaming/Audit、Security/Observability 和
Plugin Ecosystem，v0.1.0 随后成为首个公开测试版；公共 v0.2.0 又交付了 Flow Foundation。`DESIGN.md` 的
Post-v0.1.0 Roadmap 仍把 v0.3.0 写成待独立确认的占位项，但同一文件和其他当前表面仍把
多租户、Provider 扩展、多模态、OAuth 及额外检测器分别标成 v0.3/v0.3.0。

本 change 是 documentation 任务，只建立版本范围契约和持久化文档验证。允许修改现有文档
契约测试，但不修改 Gateway/SDK 运行时代码、配置、API、制品版本、发布流程或历史归档。
Canonical proposal 是结构化需求权威来源；`extract-proposal` 对生成后 Human View 的
Capabilities 提取存在已知缺口，本 change 不顺带修复 STDD 工具链。

## Project Principle Check

| 原则 | 本设计如何满足 | 风险或取舍 | 验证方式 |
|------|---------------|-----------|---------|
| Plugin / Flow；核心最小 | v0.3.0 只定义租户如何选择 Flow、策略、插件能力和 Provider；领域检测仍在插件，组合仍在 Flow，核心只承担身份上下文、解析、隔离与证据等运行机制 | 多租户需要少量核心上下文机制，但不得承载租户专属检测逻辑 | Roadmap 目标与后续 change 边界契约检查 |
| 策略显式；失败不静默 | 未知租户、缺失或矛盾配置、隔离失败、资源耗尽和兼容回退必须由后续规格显式定义，禁止静默落入其他租户或默认策略 | 暂不选择具体 fail-open/fail-closed 默认值，留给对应实施 change 逐项确认 | v0.3.0 进入/完成条件与四个后续 STDD change 清单检查 |
| 边界透明；契约稳定 | 现有 HTTP/SSE、Provider 和单租户配置语义在本 change 中不变；后续租户解析必须有显式兼容策略和有界成本 | 将 Provider 协议扩展延后，减少身份隔离与协议转换同时变化的风险 | 版本、API、配置、runtime diff 与文档负向契约 |
| 决策有证据；数据默认保护 | 后续证据能说明租户、Flow、策略来源，但不记录 API Key、原始内容或无界租户标签 | 租户可追踪性与隐私之间的具体标识方案尚未决定 | Roadmap 隐私完成条件及后续 evidence/observability change Gate 验证 |

**原则取舍**：公共 v0.3.0 优先建立多租户安全策略隔离基础，Anthropic/Gemini、多模态、
OAuth 和额外检测器延后。这样先稳定身份、策略和证据边界，再扩展协议与数据类型；无原则偏离。

## Decisions

### 1. DESIGN.md 是唯一权威版本 Roadmap

**方案**：`DESIGN.md` 的 `Post-v0.1.0 Roadmap` 维护版本、主题、状态、进入条件、完成条件和
候选项分类。README 只提供当前版本、下一里程碑摘要和锚点链接；CHANGELOG 只记录本次规划
文档变更，不复制完整路线；AGENTS.md 的项目阶段表改为与公共/内部版本语义一致。

**为什么**：集中维护可防止不同文档独立漂移，同时让用户仍能从 README 快速发现路线。

**备选方案及排除原因**：

- 新建 `ROADMAP.md`：会与已有 master spec 的 Roadmap 章节形成两个潜在权威来源。
- 在 README 维护完整路线：项目门面会重复大量设计内容，且更容易与 DESIGN 漂移。
- 只改 DESIGN、不增加验证：无法阻止后续文档重新产生冲突。

### 2. 用明确分类区分版本历史与未来承诺

**方案**：当前文档中的 v0.3 引用按 `completed-internal`、`in-scope-public-v0.3.0`、
`deferred-independent-change`、`immutable-historical-reference` 四类盘点。内部 Streaming & Audit
使用 v0.0.3；公共 v0.3.0 只表示新的多租户里程碑。archive、canonical 历史提案、已合并 spec
和既有 Release Notes 不批量改写，由 Roadmap 分类表解释其历史语义。

**为什么**：历史材料是审计证据，不能为了当前命名整洁而改写；同时当前承诺必须无歧义。

**备选方案及排除原因**：

- 全仓替换 v0.3：会破坏历史证据并改变已发布说明。
- 保留所有旧标签且只加脚注：无法明确哪些功能属于新的公共 v0.3.0。

### 3. 公共 v0.3.0 采用单一主题：多租户安全策略隔离基础

**方案**：v0.3.0 锁定五项结果边界：可信租户身份、租户级 Flow/策略/Detector/Provider 解析、
租户级证据和隐私隔离、显式失败与资源边界、现有单租户和协议兼容。Roadmap 不预先锁定存储、
缓存、控制面、标识格式或具体失败默认值。

**为什么**：多租户是当前 Open Question 中最基础的跨能力缺口，也直接依赖已交付的 Flow、
认证、审计和可观测性基础。只锁定用户可验证结果，可避免 Roadmap 越权替代后续规格设计。

**备选方案及排除原因**：

- 以 Anthropic/Gemini 为主题：先扩展协议不能解决每租户策略和隔离边界。
- 将多租户、Provider、多模态和 OAuth 全部打包：跨身份、协议和敏感数据域，无法形成可控切片。
- 只做 OAuth：认证机制不等于租户配置、策略和证据隔离。

### 4. v0.3.0 由四个独立 STDD changes 顺序交付

**方案**：Roadmap 记录以下实施单元，每个单元重新经过三道 Gate：

1. `tenant-identity-config-contract`：租户身份、配置 schema、启动期校验和单租户兼容入口。
2. `tenant-flow-policy-resolution`：租户级 Flow、Detector 配置、阈值、词表和 Provider 路由解析。
3. `tenant-evidence-observability-isolation`：审计证据、日志、trace、metrics 的隔离、脱敏和有界性。
4. `tenant-resource-failure-compatibility`：容量边界、并发隔离、失败矩阵、兼容和整体验收。

前三项依赖租户身份契约，第四项依赖前三项完成。只有全部 Deliver 且整体质量门通过，才能把
v0.3.0 标为完成或进入发布流程。

**为什么**：每个切片都能独立验收，又保留身份 → 解析 → 证据 → 整体验收的依赖顺序。

**备选方案及排除原因**：

- 一个巨型 STDD change：Gate 审核面过大，失败定位和回滚困难。
- 四项完全并行：身份契约未稳定前会造成字段和失败语义分叉。

### 5. 候选能力延后不等于承诺新目标版本

**方案**：Anthropic/Gemini、多模态、OAuth、Bias Detection、Malicious URL Detection、
Factual Consistency 从公共 v0.3.0 范围移出，统一标为“独立 STDD change 决定目标版本”。不在
本 change 中擅自改排到 v0.4.0 或其他具体版本。

**为什么**：延后是范围决策，不等于已经完成产品优先级和依赖分析。

**备选方案及排除原因**：

- 全部移到 v0.4.0：会制造未经确认的新版本承诺。
- 删除未来候选：会丢失已有设计线索和用户可见方向。

### 6. 以持久化文档契约验证 Roadmap

**方案**：严格 RED→GREEN 更新 `tests/unit/release/test_documentation_contract.py`：先把现有
v0.3 占位断言改为新规范并观察失败，再最小修改 DESIGN、README、CHANGELOG 和 AGENTS。
测试覆盖权威来源、版本区分、范围、拆分、候选分类、历史保护、版本/API/配置不变和链接有效。

**为什么**：已有测试正是 v0.2.2 路线图契约锚点，增量扩展比临时 grep 更稳定，也命中
EXP-2026-0019 和 EXP-2026-0022。

**备选方案及排除原因**：

- 仅人工审阅：无法在未来提交中自动发现 Roadmap 漂移。
- 新增独立验证脚本：与现有文档契约测试重复。
- 修改运行时测试或代码：超出本 change 范围。

## Architecture

```text
历史证据（只读） ───────────────┐
当前 DESIGN 候选引用 ───────────┼─> v0.3 引用分类清单
已发布 v0.2.x 事实 ─────────────┘          │
                                           v
                     DESIGN.md / Post-v0.1.0 Roadmap
                         │          │           │
                         │          │           └─> 延后候选（无新版本承诺）
                         │          └─> v0.3.0 四个独立 STDD changes
                         └─> 版本历史、进入条件、完成条件
                                      │
                     ┌────────────────┼────────────────┐
                     v                v                v
               README 摘要       CHANGELOG 事实     AGENTS 项目记忆
                     └────────────────┼────────────────┘
                                      v
                   documentation_contract.py 持久化验证
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| Roadmap 把技术建议误写成稳定 API 承诺 | 只锁定结果、边界和实施依赖；具体字段、存储和默认策略留给后续 Gate |
| 全仓 v0.3 扫描误改历史材料 | 建立四类引用模型；archive、canonical、已合并 spec 和 Release Notes 只读 |
| README、CHANGELOG、AGENTS 形成第二套路线 | 只保留摘要和权威锚点；契约测试禁止复制冲突明细 |
| 多租户主题范围扩张到 OAuth、Provider 或控制面 | NonGoals 与延后分类明确；每个新增方向必须独立启动 STDD |
| 现有测试仍锁定旧占位文本 | Phase 4 先更新测试进入 RED，再最小修改文档进入 GREEN |
| `extract-proposal` 丢失 Capability | Phase 2 使用 canonical proposal；记录工具缺口但不在本 change 修复 |
