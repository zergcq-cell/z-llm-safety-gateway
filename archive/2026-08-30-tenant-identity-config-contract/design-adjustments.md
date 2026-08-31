# 设计调整汇总

本 change 有 2 项已闭环的 minor boundary discovery；均无需回到 Phase 2 或 Phase 4。

## ADJ-001 — Roadmap 生命周期进入实施中

- 原始边界：上一项 roadmap-only change 以负向契约证明尚无多租户运行时。
- 最终调整：DESIGN、README、CHANGELOG、AGENTS 统一标记 change 1/4 active；发布版本仍为 v0.2.2，租户级策略隔离仍未完成。
- 原因：首个运行时 change 必须推进生命周期，否则旧负向断言会阻塞 roadmap 自己规划的实现。
- 原则影响：不扩张 Plugin/Flow 范围；状态与版本边界更透明；不新增数据采集。
- 状态：Phase 4 已解决。

## ADJ-002 — 拒绝不可认证的空白 API Key

- 原始边界：启动 failure matrix 未单列空值或首尾空白 key。
- 最终调整：多租户模式以 `invalid_api_key` 在启动期拒绝；legacy 模式保持兼容。
- 原因：缺失环境变量会插值为空串，Bearer 解析会去除首尾空白；接受这些值会制造永远不可达的租户绑定。
- 原则影响：失败显式且脱敏；认证契约保持可达和有界；不记录凭据。
- 状态：Phase 5 已解决，并记录为 EXP-2026-0025。
