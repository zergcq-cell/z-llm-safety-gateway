# Phase context

- Baseline: d2b3634 on main, synchronized from origin/main.
- Gate 1: 用户明确回复“确认gate 1 提案”；已记录，未继承其他 change 的长程或 Git 授权。
- Phase 2: 规格、设计、测试方案已起草，等待 Gate 2；没有源码或运行时测试修改。
- 五项 capability、10 requirements、26 scenarios/TC；19 high、7 medium、0 low；P0=23，P1=3。
- 关键取舍：精确审计归属；指标默认聚合、最多 32 个租户明细；共享策略 lifecycle 用 policy scope；审计 sink 失败延续显式 best-effort。
- FlowEvidence v1.0 不修改；归属位于 AuditEntry 外层。新 registry/观测配置按 app 隔离。
- Gate 2 批准后选择 Phase 3–5 执行模式。Gate 3 独立确认，Git 提交/推送未授权。
- 系统 python3 是 Python 3.9 且缺 PyYAML；项目 .venv/bin/python 3.10.20 可运行 STDD。
- STDD CLI extract-proposal 漏读生成 Human View 的 capabilities/impact；canon generate --type spec 实际仅重生成 proposal。已按 canonical 数据确定性渲染 Human Views 并直接校验，不修改工具链源码。
