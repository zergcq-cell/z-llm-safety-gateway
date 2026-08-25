# v0.2.2 设计调整汇总

> 汇总日期：2026-08-26
> 结论：3 项轻量调整均已在 Verify 阶段收口；无需重新 Spec 或重新 Build。

## ADJ-001：锁生成纳入 pip unsafe package

- **原设计**：`pip-compile` 命令未包含 `--allow-unsafe --strip-extras`。
- **最终调整**：Python 3.12 生成命令增加两个参数，确保 `pip==26.2.1` 与全部传递依赖进入 hash lock。
- **原因**：pip-tools 默认排除 pip，原命令生成的环境仍会漂移。
- **影响**：仅影响 release tool lock 的维护命令；Gateway runtime、API 和发布状态机不变。

## ADJ-002：区分 tag、workflow 与 Release 历史状态

- **原设计**：路线图把 v0.2.0～v0.2.2 概括为已发布状态。
- **最终调整**：明确 v0.2.0 是 tag 已发布但 Release workflow 失败，v0.2.1 Release 成功，v0.2.2 在 Deliver 前是当前源码 / release candidate。
- **原因**：既有 v0.2.1 审计证据和当前远程状态不允许把失败或尚未发生的 Release 写成成功。
- **影响**：仅修正文档与规格事实，不改变任何运行时行为。

## ADJ-003：增加 pre-tag 远程时序证据

- **原设计**：TC-REL-025 试图用发布后的远程检查证明 dry-run 没有发布。
- **最终调整**：在同 SHA main CI 与 dry-run 成功后、创建 tag 前执行独立 checkpoint；它必须同时观察 v0.2.2 Release 明确 404 和远程 tag 不存在。发布后另行验证 public Release、evidence 与历史 refs。
- **原因**：终态无法证明中间时点没有越权写入，证据必须在状态改变前采集。
- **影响**：远程 checkpoint 从 2 个增为 3 个；GitHub workflow 发布行为和权限不变。

## 项目原则复核

1. **Plugin / Flow**：三项调整均位于发布工具、文档和验证层；Flow、插件和核心 runtime 不变。
2. **显式策略 / 失败**：pip 锁定、失败发布历史和 pre-tag absence 均由隐含假设改为显式失败条件。
3. **透明边界 / 稳定契约**：Gateway 0.2.2 / SDK 0.1.1、四资产和既有 tag 不变性继续保持。
4. **证据 / 数据保护**：新增证据仅含公开 repository、HEAD、run ID、HTTP 404 与 tag absence，不含 token、用户内容或完整环境。

无原则偏离，也没有需要用户追加批准的重大取舍。
