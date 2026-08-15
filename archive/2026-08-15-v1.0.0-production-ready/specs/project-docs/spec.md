# project-docs — 行为规格（Human View）

> 变更：2026-08-15-v1.0.0-production-ready | 置信度：high

## Requirements

### REQ-DOCS-001: 根目录 LICENSE 文件为 Apache License 2.0 全文

**SC-DOCS-001**（置信度 high）— evidence: proposal.yaml -> what_changes C1; DESIGN.md 19.1

- GIVEN: 仓库根目录
- WHEN: 检查 LICENSE 文件内容
- THEN: LICENSE 文件 SHALL 存在且内容为 Apache License 2.0 官方全文（包含 9 个条款章节）
- AND: LICENSE 首行 SHALL 为 'Apache License' 且包含 'Version 2.0'
- AND: LICENSE SHALL 与 pyproject.toml 的 license 声明（Apache-2.0）一致

### REQ-DOCS-002: README.md 提供完整项目门面与文档导航

**SC-DOCS-002**（置信度 high）— evidence: proposal.yaml -> what_changes C2

- GIVEN: 仓库根目录 README.md
- WHEN: 阅读 README.md 内容
- THEN: README SHALL 包含：项目介绍、核心功能特性列表、快速开始步骤、配置示例、文档导航（链接 docs/ 各指南）与许可声明
- AND: 快速开始 SHALL 包含可执行的安装与启动命令（pip install / uvicorn 或 docker）
- AND: 文档导航 SHALL 链接 docs/getting-started.md、docs/configuration.md、docs/api-spec.md、docs/deployment.md 及插件文档
- AND: README SHALL 不包含虚构或不存在的命令

### REQ-DOCS-003: docs/ 包含 getting-started/configuration/api-spec/deployment 四份指南且与实现一致

**SC-DOCS-003**（置信度 high）— evidence: proposal.yaml -> what_changes C3

- GIVEN: docs/ 目录
- WHEN: 检查四份指南文件
- THEN: docs/ SHALL 包含 getting-started.md、configuration.md、api-spec.md、deployment.md 四个文件
- AND: getting-started SHALL 覆盖安装、最小配置、启动、curl 冒烟调用
- AND: configuration SHALL 覆盖所有配置区块（server/providers/routing/pipeline/security/observability）并给出示例
- AND: api-spec SHALL 覆盖 /v1/chat/completions 与健康/指标端点，字段与实现一致
- AND: deployment SHALL 覆盖 docker compose 部署、生产建议、sidecar 集成与故障排查
- AND: 指南中的命令与配置 SHALL 与 v0.5.x 实现一致（逐条实测验证）

### REQ-DOCS-004: v1.0.0 Definition of Done 清单记录并随交付物可勾选

**SC-DOCS-004**（置信度 high）— evidence: proposal.yaml -> what_changes C8

- GIVEN: 变更交付物（proposal.md 与 test-report.md）
- WHEN: 检查 DoD 清单
- THEN: DoD 清单 SHALL 逐项列出 v1.0.0 完成标准，每项可明确勾选是/否
