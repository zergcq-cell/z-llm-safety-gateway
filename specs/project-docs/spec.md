# Capability: project-docs

## MODIFIED Requirements

- **REQ-DOCS-005**：文档和元数据 SHALL 统一为 v0.1.1、Python 3.10+、推荐 3.12。
- **REQ-DOCS-006**：源码 Quick Start SHALL 在干净环境安装、启动并通过 health 冒烟。
- **REQ-DOCS-007**：本地链接 SHALL 有效，README SHALL 提供安全、贡献、行为准则和反馈入口。


<!-- 合并自 2026-08-23-v0.2.1-release-version-hotfix -->
# Capability: project-docs

## MODIFIED Requirements

### REQ-DOCS-008：公开文档按 Gateway 与 SDK 角色展示 v0.2.1 / v0.1.1

- **SC-DOCS-008 · high**：Gateway README、指南、配置注释与 Compose image SHALL 一致为 0.2.1；历史证据和 Python 支持口径不变。
- **SC-DOCS-009 · high**：SDK 与插件安装表面 SHALL 保持 0.1.1；双版本文档同时标明 Gateway 0.2.1 / SDK 0.1.1。
- **SC-DOCS-010 · high**：CHANGELOG 0.2.1 SHALL 说明独立版本热修复与 SDK 保持 0.1.1；提取结果不得混入相邻版本，也不得把 v0.2.0 描述为成功 Release。

## Verification

- Canonical spec: `canonical/specs/code/project-docs.yaml`
- Agent checkpoints: `canonical/specs/agent/project-docs.yaml`
- Test cases: 3
- Documentation contract anchor: `tests/unit/release/test_documentation_contract.py`
