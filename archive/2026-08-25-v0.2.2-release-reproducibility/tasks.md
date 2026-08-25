# v0.2.2 发布可复现性任务清单

## 1. Release lock 与 Node 24 Action 锚点（P0）

- [x] 1.1 先补充 TC-REL-018、TC-GH-008、TC-GH-009 的失败契约测试。
- [x] 1.2 新增固定生成器版本的 release-tools input 与完整 hash lock。
- [x] 1.3 将 CI/Release workflows 的官方 Actions 更新为已核验的 Node 24 完整 SHA。
- [x] 1.4 保持 Dependabot 的 root、SDK 与 GitHub Actions 更新范围，并记录 lock 再生成契约。
- [x] 1.5 完成切片测试、全量回归、Ruff、Mypy 与 TC-ID 覆盖核对。

## 2. Release 校验器与 evidence（P0 / P1）

- [x] 2.1 先补充 TC-REL-021～TC-REL-025 的失败单元/契约测试。
- [x] 2.2 扩展确定性 Release payload 校验：状态、notes、四资产、uploaded 与 digest。
- [x] 2.3 增加 peeled tag SHA 校验及只接受明确 404 的 absence 判断。
- [x] 2.4 生成稳定、有界、去敏的 schema v1 release evidence。
- [x] 2.5 建立 Gate 3 后远程验收检查点，不执行 tag/Release 写操作。
- [x] 2.6 完成切片测试、全量回归、Ruff、Mypy 与 TC-ID 覆盖核对。

## 3. Gateway/SDK 版本与路线图（P0 / P1）

- [x] 3.1 先补充 TC-DOCS-011～TC-DOCS-013 的失败文档契约测试。
- [x] 3.2 将 Gateway 当前版本表面更新到 0.2.2，保持 SDK 0.1.1。
- [x] 3.3 增加 Gateway/SDK 兼容矩阵，更新 README、DESIGN、CHANGELOG 与配置/Compose 当前口径。
- [x] 3.4 保护 v0.2.0/v0.2.1 历史、SDK wheel URL、示例依赖及运行时非目标边界。
- [x] 3.5 完成切片测试、全量回归、Ruff、Mypy 与 TC-ID 覆盖核对。

## 4. Draft-first workflow 集成（P0 / P1）

- [x] 4.1 先补充 TC-REL-019、TC-REL-020、TC-GH-010、TC-GH-011 的失败 workflow 契约测试。
- [x] 4.2 让 build/audit 安装同一 hash lock，并以 `build --no-isolation` 构建精确四产物。
- [x] 4.3 实现 tag-only 的 404 → draft → exact verify → publish → public recheck 状态机。
- [x] 4.4 保持顶层只读权限、release job 最小写权限及 workflow_dispatch 只验证边界。
- [x] 4.5 上传 90 天 evidence artifact 并写入 Job Summary，Release assets 保持精确四个。
- [x] 4.6 验证所有 Agent checkpoint 可定位/可执行或明确属于 Gate 3 后远程验收。
- [x] 4.7 完成切片测试、真实四产物构建、全量回归、Ruff、Mypy 与 TC-ID 覆盖核对。

## 5. Phase 5 全量验证

- [x] 5.1 三路只读技术评审全部返回并处理阈值内发现。
- [x] 5.2 完整 pytest、coverage、Ruff、Mypy、四产物/Twine 与 checkpoint collect 全部执行。
- [x] 5.3 逐文件 diff 审查与十二类失败模式检查全部完成。
- [x] 5.4 生成 design-adjustments 与 test-report，暂停在 Gate 3。
