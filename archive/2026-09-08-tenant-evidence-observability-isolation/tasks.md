# 实现任务

- [x] S1：实现可信 `TenantObservationContext`、app 私有观测 runtime 与严格配置校验（TC-TEC-001、003、006、TC-TOC-001、002）
- [x] S2：将可信归属写入审计和生命周期证据，并明确 sink 失败行为（TC-TAU-001、003、004、005、006）
- [ ] S3：实现有限租户指标、既有指标投影与独立 app registry（TC-TME-001 至 005）
- [ ] S4：实现请求、日志和 Trace 的可信上下文传播与清理（TC-TEC-002、005、TC-TOB-001 至 005）
- [ ] S5：验证 HTTP、async、SSE 和后台路径，并更新兼容与路线文档（TC-TEC-004、TC-TAU-002、TC-TOC-003、004）

每项必须完成 RED、GREEN、REFACTOR、TC 覆盖核对、聚焦测试和全量回归后才可勾选。
