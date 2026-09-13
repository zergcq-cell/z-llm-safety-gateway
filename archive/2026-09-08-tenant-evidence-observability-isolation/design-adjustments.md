# Design adjustments

已生成 Canonical 汇总 `design-adjustments.yaml`。以下调整不改变已批准的安全语义：

1. 将 payload-free 观测契约放入 Flow core module，由 tenancy 重新导出，避免配置导入循环。
2. 内建 PipelineEngine 使用显式归属参数；自定义引擎保留旧调用形状，保持兼容。

Phase 2 自审澄清：

1. FlowEvidence strict v1.0 不能直接增加字段；改为 AuditEntry 外层归属和显式观测参数。
2. 指标身份通过 scope 区分保留字，最大组合由 35 修正为包含 policy/system 的 37，总新 counter samples 上限 1332。
3. 状态 Gauge 不归并不同 detector；Counter/Histogram 配置 ID 归并不改变 Gauge 状态语义。
4. contextvars 不能替代跨 ASGI 任务/流式/后台的显式快照。
5. app 级观测状态不能存入现有模块级“最近 app”变量。
6. CLI 渲染/提取存在既有局限，使用 canonical-first 确定性投影并记录直接校验。

以上均在 Gate 1 的归属、隐私、基数与兼容范围内，随 Gate 2 设计一并审阅；没有源码变更。
