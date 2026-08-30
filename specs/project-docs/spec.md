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


<!-- 合并自 2026-08-25-v0.2.2-release-reproducibility -->
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


<!-- 合并自 2026-08-30-v0.3.0-milestone-roadmap -->
# Capability: project-docs

> Canonical verification spec: `canonical/specs/agent/project-docs.yaml`

## Modified Requirements

### REQ-DOCS-014：当前项目文档 SHALL 一致呈现 v0.3.0 规划状态

#### SC-DOCS-014 · high

- **Given**：README 是用户进入项目的首要门面
- **When**：用户查看当前版本和下一里程碑
- **Then**：README **SHALL** 准确摘要 v0.3.0 的多租户安全策略隔离主题并链接 DESIGN 的权威 Roadmap 锚点
- **And**：README SHALL 明确该能力仍处于规划状态而非已实现状态

#### SC-DOCS-015 · high

- **Given**：CHANGELOG 记录显著变更，AGENTS 记录当前项目开发记忆
- **When**：本 documentation change 完成
- **Then**：CHANGELOG Unreleased **SHALL** 只记录范围定义和文档统一事实
- **And**：AGENTS 的阶段表 SHALL 使用正确的内部/公共版本语义并指向权威 Roadmap
- **And**：两者 SHALL NOT 声称多租户、Anthropic/Gemini、多模态或 OAuth 已交付

### REQ-DOCS-015：Roadmap 统一 SHALL 不改变产品、版本或历史契约

#### SC-DOCS-016 · high

- **Given**：Gateway v0.2.2、SDK v0.1.1 和当前 runtime/config/API 基线
- **When**：应用本 change 的文档与文档契约测试 diff
- **Then**：Gateway/SDK 版本、运行时源码、YAML 配置契约和公共 API **SHALL** 保持不变
- **And**：允许的非文档修改 SHALL 仅限持久化文档契约测试

#### SC-DOCS-017 · high

- **Given**：更新后的 DESIGN、README、CHANGELOG、AGENTS 和文档契约测试
- **When**：运行 active Markdown 链接检查、Roadmap 契约和完整 documentation contract suite
- **Then**：全部检查 **SHALL** 通过
- **And**：测试 SHALL 证明权威来源、范围分类、历史保护和未实现能力负向声明
