# Capability: project-docs

## MODIFIED Requirements

### REQ-DOCS-011：当前版本表面明确 Gateway 0.2.2 与 SDK 0.1.1 的独立兼容关系

- **SC-DOCS-011 · high**：Gateway metadata/runtime、README、指南、config comments 与 Compose SHALL 一致为 0.2.2；SDK README、CLI template、wheel URL 与示例依赖 SHALL 保持 0.1.1；兼容矩阵明确两者组合，Python 3.10–3.12 口径不变。

### REQ-DOCS-012：项目路线图与实际 v0.2.x 发布历史一致

- **SC-DOCS-012 · high**：DESIGN 与 README SHALL 区分 v0.2.0“tag 已发布但 Release workflow 失败”、v0.2.1“Release 成功”和 v0.2.2“当前源码 / release candidate”；在 Deliver 成功前不得把 v0.2.2 声称为已发布 Release，不再声明 current v0.1.0；v0.3.0 范围由独立 STDD change 确认，不声称本 change 实现非目标能力。

### REQ-DOCS-013：v0.2.2 发布说明精确描述维护范围并保留历史

- **SC-DOCS-013 · high**：v0.2.2 notes SHALL 只描述 Node 24、锁定工具链、draft-first、确定性证据和 Gateway 0.2.2 / SDK 0.1.1；不混入相邻正文、不改写 v0.2.0/v0.2.1，并明确运行时能力不变。

## Verification

- Canonical spec: `canonical/specs/code/project-docs.yaml`
- Agent checkpoints: `canonical/specs/agent/project-docs.yaml`
- Test cases: 3
- Documentation contract anchor: `tests/unit/release/test_documentation_contract.py`
