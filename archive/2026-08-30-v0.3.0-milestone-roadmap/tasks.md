# v0.3.0 里程碑范围定义与 Roadmap 统一任务清单

## 1. milestone-scope-governance（P0）

- [x] 1.1 为权威来源、版本区分、单一主题、四个后续 change 和候选分类编写 RED 文档契约测试。
- [x] 1.2 更新 `DESIGN.md` Post-v0.1.0 Roadmap，加入权威声明、v0.3.0 范围、进入/完成条件和分类表。（依赖 #1.1）
- [x] 1.3 修正 `AGENTS.md` 内部阶段版本语义并指向 DESIGN 权威 Roadmap。（依赖 #1.2）
- [x] 1.4 执行 TC-RMAP-001/003/005/006/007 聚焦 GREEN 验证。

## 2. project-docs（P0 / P1）

- [x] 2.1 为次级摘要、v0.2.x 历史、历史引用保护、README、CHANGELOG 和项目记忆编写 RED 测试。（依赖 #1.2）
- [x] 2.2 更新 `README.md`，增加有界的 v0.3.0 规划摘要和 DESIGN 锚点链接。（依赖 #2.1）
- [x] 2.3 更新 `CHANGELOG.md` Unreleased，只记录规划文档与契约变更。（依赖 #2.1）
- [x] 2.4 执行 TC-RMAP-002/004/008、TC-DOCS-014/015 聚焦 GREEN 验证。

## 3. 契约边界与全量验证（P0 / P1）

- [x] 3.1 增加产品版本、runtime/config/API 和允许路径的负向契约，形成 TC-DOCS-016 RED。（依赖 #1、#2）
- [x] 3.2 完成链接与完整文档契约 TC-DOCS-017，并重构重复解析 helper。（依赖 #3.1）
- [x] 3.3 验证 12 个 TC-ID 全局唯一且 8 个 Agent checkpoints 绑定真实 pytest 节点。
- [x] 3.4 运行文档契约、全量 pytest、Ruff、Mypy 和 canonical/status 校验。

## 4. 阶段证据

- [x] 4.1 更新 `design-adjustments.md`，记录 Phase 5 的 minor boundary discovery。
- [x] 4.2 更新 `phase-context.md`、`.stdd.yaml` 和切片完成证据。
