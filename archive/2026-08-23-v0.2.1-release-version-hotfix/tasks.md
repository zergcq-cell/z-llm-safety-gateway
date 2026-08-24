# v0.2.1 独立版本发布热修复任务清单

## 1. Release 版本角色校验（P0）

- [x] 1.1 新增临时发布树测试，证明 Gateway 0.2.1 / SDK 0.1.1 可被接受（TC-REL-008）
- [x] 1.2 参数化验证 Gateway package/runtime 任一错配均硬失败（TC-REL-009）
- [x] 1.3 验证 SDK package/runtime 内部错配硬失败（TC-REL-010、TC-SDK-010）
- [x] 1.4 验证缺失、空白或跨相邻章节的 0.2.1 notes 均不能通过（TC-REL-011）
- [x] 1.5 最小修改 `tools/release_checks.py`，按 Gateway、SDK、CHANGELOG 三种角色校验（依赖 #1.1–#1.4）

## 2. 双版本构建与安装（P0）

- [x] 2.1 先更新构建契约测试，锁定四个产物的名称与版本集合（TC-REL-012、TC-SDK-011）
- [x] 2.2 先新增组合安装测试，锁定三个 CLI 均可运行且 SDK 可独立安装（TC-REL-013）
- [x] 2.3 将 Gateway package/runtime 提升到 0.2.1，同时保持 SDK package/runtime 为 0.1.1（TC-SDK-010，依赖 #1.5）
- [x] 2.4 构建并检查两个 wheel 与两个 sdist，验证 Gateway 0.2.1 / SDK 0.1.1 metadata（依赖 #2.1–#2.3）

## 3. Workflow 与公开版本表面（P0 / P1）

- [x] 3.1 先更新 workflow 契约测试，锁定必填且无静态默认的手动版本输入、tag ref 与三门依赖（TC-REL-014）
- [x] 3.2 先更新文档契约测试，按 Gateway、SDK、双版本与历史证据区分断言（TC-SDK-012、TC-DOCS-008、TC-DOCS-009）
- [x] 3.3 先更新 CHANGELOG 契约测试，锁定非空且不跨节的 v0.2.1 notes（TC-DOCS-010）
- [x] 3.4 最小更新 `.github/workflows/release.yml`，移除静态 dispatch 默认值且保持 tag-only 发布（依赖 #3.1）
- [x] 3.5 按角色更新 Gateway 当前公开表面至 0.2.1，保留 SDK 0.1.1 与所有历史/归档证据（依赖 #3.2–#3.3）

## 4. 本地完整验证与远程发布前置（P0）

- [x] 4.1 验证 16 个 Agent checkpoint 的本地测试节点真实存在并可 collect
- [x] 4.2 运行发布、SDK 与文档定向测试
- [x] 4.3 运行完整 pytest + coverage、Ruff、Mypy 与构建/Twine 检查
- [x] 4.4 全量检查 12 类失败模式与四项项目原则，生成验证报告
- [x] 4.5 在 Gate 3 停止，等待用户确认；不得提前 commit、tag 或 push

## 5. Gate 3 后 Deliver 远程验证（P0）

- [ ] 5.1 提交 hotfix 并 push main，等待同一 SHA 的 Python 3.10/3.11/3.12 CI 全绿（TC-REL-015）
- [ ] 5.2 对比远程 v0.2.0 tag object 与 peeled commit，确认基线未变（TC-REL-017）
- [ ] 5.3 创建并 push 新 annotated v0.2.1 tag，等待 quality/build/audit/release 全绿（TC-REL-016）
- [ ] 5.4 验证 GitHub Release notes 精确、四个 assets 完整，并再次确认 v0.2.0 不可变（TC-REL-016、TC-REL-017）

<!--
优先级说明：
- P0：阻塞性任务，完成前无法进入下一阶段
- P1：重要任务，应在当前阶段完成
- P2：可延后到后续版本的任务
-->
