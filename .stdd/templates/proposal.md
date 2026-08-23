# <变更标题>

<!-- STDD-MARKER: title — 变更标题，同时作为 change 目录名的基础 -->

## Why

<问题陈述：用户视角，为什么需要这个变更>

## What Changes

<!-- STDD-MARKER: what_changes — 每项为一条变更描述，bullet list -->
- <变更项 1>
- <变更项 2>

## Capabilities

### New Capabilities

<!-- STDD-MARKER: new_capabilities — 格式: - **<名称>**：<描述> -->
- **<capability-name>**：<新增描述>

### Modified Capabilities

<!-- STDD-MARKER: modified_capabilities — 格式: - **<名称>**：<描述> -->
- **<capability-name>**：<修改描述>

## Impact

<!-- STDD-MARKER: impact — 按层面分类的受影响文件/资源清单 -->

**代码层面**：
- <文件变更数量和范围>

**配置层面**：
- <配置变更>

**基础设施**：
- <基础设施变更>

## Constraints

<!-- STDD-MARKER: constraints — 技术/资源/时间约束 -->
- <约束项 1>
- <约束项 2>

## Stakeholders

<!-- STDD-MARKER: stakeholders — 受影响方或相关角色 -->
- <利益相关者 1>
- <利益相关者 2>

## Risk Areas

<!-- STDD-MARKER: risk_areas — 格式: - capability: <name> — <风险描述> -->
- capability: <capability-name> — <风险描述>

## NonGoals

<!-- STDD-MARKER: non_goals — 明确不在此变更范围内的事项 -->
- <非目标项 1>
- <非目标项 2>

## Critical

<!-- STDD-MARKER: critical — 是否关键变更（V2.6新增）。true 时 Phase 2 须通过锚定评估 -->
- [ ] 非关键变更（默认）
- [ ] 关键变更 — 涉及安全/金融/核心基础设施，需 L3/L4 锚定

## Risk Assessment

<!-- STDD-MARKER: risk_assessment — 风险分类评估（V2.6新增） -->
- **safety_critical**：<是否涉及认证/授权/加密/数据保护 — true/false>
- **financial**：<是否涉及金融交易或资金流转 — true/false>
- **cross_system**：<是否涉及多系统协调 — true/false>

## Anchoring

<!-- STDD-MARKER: anchoring — 锚定策略（V2.6新增） -->
- **level**：L<1-4>（L1 行为锚定 / L2 接口锚定 / L3 模式锚定 / L4 基准锚定）
- **reference_changes**：<L3 时引用的已有 Change ID，逗号分隔>
- **anchor_implementations**：<L4 时附参考代码路径，逗号分隔>

## Project Principle Check

> 逐项对照项目根目录 `PRINCIPLES.md`。不得留空；不适用时必须简述理由。原则存在张力时，记录取舍与需要用户确认的事项。

1. **Plugin / Flow**：<领域能力是否仍在插件中，组合是否仍由 Flow 负责，核心是否保持最小>
2. **显式策略 / 失败**：<策略、默认值、失败、绕过和降级是否显式且可观测>
3. **透明边界 / 稳定契约**：<是否保持协议语义和兼容性，延迟与资源成本是否有界>
4. **证据 / 数据保护**：<结果是否可解释、可审计，是否避免不必要的敏感数据采集>

**原则取舍或偏离**：<无；或说明取舍、理由及待确认事项>

## Success Criteria

<!-- STDD-MARKER: success_criteria — 可验证的完成条件 -->
- [ ] <可验证的成功条件 1>
- [ ] <可验证的成功条件 2>
