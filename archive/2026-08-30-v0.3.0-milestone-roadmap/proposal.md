# v0.3.0 里程碑范围定义与 Roadmap 统一

<!-- source_hash: ca9137241206a1f2 -->
<!-- generated_at: 2026-08-30T12:49:19.023880 -->
<!-- canonical: canonical/proposals/2026-08-30-v0.3.0-milestone-roadmap.yaml -->

## Why

当前公开版本为 v0.2.2，但 v0.3.0 仍只有“下一功能里程碑”的占位描述；同时 DESIGN.md 中的早期内部 v0.0.3、以及多租户、Anthropic/Gemini、多模态、OAuth 等候选项仍带有 相互重叠的 v0.3 标签，缺少单一主题、范围边界、实施顺序和权威路线图来源。

## What Changes

- 将 DESIGN.md 的 Post-v0.1.0 Roadmap 确立为版本路线的权威来源，其他文档仅保留一致摘要与链接。
- 明确区分内部开发阶段 v0.0.3 与新的公共里程碑 v0.3.0，并盘点仓库现存 v0.3/v0.3.0 标记。
- 将公共 v0.3.0 的单一主题确定为“多租户安全策略隔离基础”，定义边界、进入条件和完成条件。
- 将 v0.3.0 拆分为租户身份与配置契约、租户级 Flow/策略/Provider 解析、证据与可观测性隔离、资源边界与兼容性验证等独立后续 STDD changes。
- 将 Anthropic/Gemini、多模态、OAuth、额外检测器等候选能力显式延后，并要求各自通过独立 STDD change 决策。
- 同步 README.md、CHANGELOG.md 及相关公开文档的路线图摘要，不形成第二套权威路线图。

### New Capabilities

- **milestone-scope-governance**：为公共里程碑建立单一、可验证且可追溯的范围契约。

### Modified Capabilities

- **project-docs**：统一版本历史、路线图、候选能力归属及公开文档引用关系。

## Success Criteria

- [ ] DESIGN.md 明确标注唯一的权威路线图来源。
- [ ] 内部 v0.0.3 与公共 v0.3.0 不再混淆。
- [ ] v0.3.0 具有单一主题、明确边界和可验证的完成条件。
- [ ] v0.3.0 被拆成至少三个可独立执行和验证的后续 STDD changes。
- [ ] 仓库中现存的 v0.3/v0.3.0 候选项均被标记为已完成、纳入或延后。
- [ ] README、CHANGELOG 和相关文档与权威路线图一致。
- [ ] 文档没有暗示本 change 已实现多租户或其他新运行时能力。
- [ ] 不改变代码、配置、API、制品版本或已发布历史。
- [ ] 文档检查及路线图一致性检查通过。
