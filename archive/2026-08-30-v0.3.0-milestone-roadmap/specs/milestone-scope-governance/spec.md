# Capability: milestone-scope-governance

> Canonical verification spec: `canonical/specs/agent/milestone-scope-governance.yaml`

## New Requirements

### REQ-RMAP-001：项目 SHALL 维护单一权威版本 Roadmap

#### SC-RMAP-001 · high

- **Given**：DESIGN、README、CHANGELOG 和 AGENTS 中存在版本与路线信息
- **When**：维护者寻找 v0.3.0 的范围、状态、进入条件和完成条件
- **Then**：`DESIGN.md` 的 Post-v0.1.0 Roadmap **SHALL** 被明确标为唯一权威来源
- **And**：权威章节 SHALL 包含公共版本、主题、状态和范围契约

#### SC-RMAP-002 · high

- **Given**：README、CHANGELOG 和 AGENTS 需要向不同读者提供版本信息
- **When**：这些次级表面描述 v0.3.0
- **Then**：它们 **SHALL** 只提供与 DESIGN 一致的有界摘要或链接
- **And**：它们 SHALL NOT 维护冲突的完整 Roadmap、完成条件或候选版本承诺

### REQ-RMAP-002：内部阶段、公共里程碑和发布事实 SHALL 保持可区分

#### SC-RMAP-003 · high

- **Given**：历史 Streaming & Audit 曾使用 v0.3.0 标题但实际属于内部开发序列
- **When**：读取当前 Roadmap 和项目阶段说明
- **Then**：Streaming & Audit **SHALL** 明确归属内部 `v0.0.3`
- **And**：公共 `v0.3.0` SHALL 仅表示新的多租户安全策略隔离基础里程碑

#### SC-RMAP-004 · high

- **Given**：v0.2.0、v0.2.1 和 v0.2.2 具有不同 tag/workflow/Release 事实
- **When**：更新 v0.3.0 Roadmap
- **Then**：v0.2.x 的已核验状态 **SHALL** 保持逐项准确且不可被压平
- **And**：archive、canonical、已合并历史 spec 和 Release Notes SHALL NOT 被改写

### REQ-RMAP-003：公共 v0.3.0 SHALL 具有单一主题和可验证完成边界

#### SC-RMAP-005 · high

- **Given**：多租户、Provider、多模态、OAuth 和额外检测器都曾是 v0.3 候选
- **When**：确定公共 v0.3.0 范围
- **Then**：v0.3.0 **SHALL** 只采用“多租户安全策略隔离基础”主题
- **And**：范围 SHALL 覆盖可信租户身份、租户级解析、证据/隐私隔离、显式失败/资源边界和单租户兼容
- **And**：Roadmap SHALL NOT 预先锁定存储、缓存、控制面、标识格式或失败默认值

#### SC-RMAP-006 · high

- **Given**：公共 v0.3.0 不能通过单一巨型 change 安全交付
- **When**：检查其交付计划和完成条件
- **Then**：Roadmap **SHALL** 列出至少四个独立、按依赖排序且各自经过 Gate 1/2/3 的 STDD changes
- **And**：v0.3.0 只有在全部 change Deliver 且整体验收通过后才能标记完成或进入发布流程

### REQ-RMAP-004：全部 v0.3 候选引用 SHALL 被显式分类

#### SC-RMAP-007 · medium

- **Given**：当前设计文档包含 Streaming、Audit、多租户、Provider、多模态、OAuth 和额外检测器等 v0.3 引用
- **When**：扫描所有非历史的当前 Roadmap 与设计候选表面
- **Then**：每项引用 **SHALL** 被分类为已完成、纳入公共 v0.3.0 或延后独立 STDD
- **And**：延后项 SHALL NOT 被擅自承诺到 v0.4.0 或其他新版本

#### SC-RMAP-008 · medium

- **Given**：archive、canonical、已合并 spec 和 Release Notes 中包含历史 v0.3 文本
- **When**：完成全仓引用盘点
- **Then**：这些引用 **SHALL** 被记录为 immutable-historical-reference 并保持字节语义不变
- **And**：当前 Roadmap SHALL 提供足够说明，使历史标签不被误读为新的公共范围
