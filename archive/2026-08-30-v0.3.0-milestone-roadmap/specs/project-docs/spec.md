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
