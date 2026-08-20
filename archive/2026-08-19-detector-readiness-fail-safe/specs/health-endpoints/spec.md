# Health Endpoints

## Requirements

- `REQ-HEALTH-601`：`/health` 纯 liveness；`/ready` 从当前 app 读取 detector-aware 状态。
- `REQ-HEALTH-602`：健康检查并行、有界、脱敏，并在成功后恢复状态。

## Scenarios

| ID | 结果 |
|---|---|
| SC-HEALTH-601 | 无检测器/全健康为 200 ready；多 app 状态隔离；/health 不查 detector |
| SC-HEALTH-602 | required/fail_closed 问题为 503 not_ready |
| SC-HEALTH-603 | 仅 fail_open 问题为 200 ready + degraded 精确 schema |
| SC-HEALTH-604 | 异常/超时有界并用稳定 reason_code |
| SC-HEALTH-605 | 后续健康成功恢复 ready 并只发一次变化事件 |
