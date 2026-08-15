# github-setup — 行为规格（Human View）

> 变更：2026-08-15-v1.0.0-production-ready | 置信度：high

## Requirements

### REQ-GH-001: .github/workflows/ci.yml 定义 CI pipeline（ruff+mypy+pytest+coverage）

**SC-GH-001**（置信度 high）— evidence: proposal.yaml -> what_changes C7; design.md D6

- GIVEN: .github/workflows/ci.yml
- WHEN: 检查 workflow 内容
- THEN: workflow SHALL 在 push 与 pull_request 时触发
- AND: job SHALL 使用 Python 3.10 与 3.11 矩阵
- AND: 步骤 SHALL 依次执行：依赖安装、ruff check、mypy、pytest
- AND: pytest 步骤 SHALL 设置 coverage gate ≥ 80%
- AND: workflow SHALL 包含 sdk 包路径（PYTHONPATH）或安装步骤，确保 sdk 测试可运行

### REQ-GH-002: CI 内容与本地等价验证一致（无真实仓库时可离线验证）

**SC-GH-002**（置信度 high）— evidence: proposal.yaml -> risk_areas github-setup

- GIVEN: 本地仓库
- WHEN: 手动执行 CI 中相同命令（ruff check / mypy / pytest --cov）
- THEN: 所有命令 SHALL 成功（exit 0）

### REQ-GH-003: CONTRIBUTING.md 与 issue/PR 模板存在且可用

**SC-GH-003**（置信度 high）— evidence: proposal.yaml -> what_changes C7; DESIGN.md 19.2

- GIVEN: 仓库根目录与 .github/ 目录
- WHEN: 检查文件存在性
- THEN: CONTRIBUTING.md SHALL 存在并覆盖：开发环境搭建、代码风格、commit 格式、PR 流程
- AND: .github/ISSUE_TEMPLATE/ SHALL 存在且含至少 1 个模板（bug_report 或 feature_request）
- AND: .github/PULL_REQUEST_TEMPLATE.md SHALL 存在且含检查清单
- AND: 模板内容 SHALL 与 DESIGN 19.2 贡献模型（Fork + PR）一致
