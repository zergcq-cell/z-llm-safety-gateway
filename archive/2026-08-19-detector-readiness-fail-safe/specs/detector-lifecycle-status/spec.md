# Detector Lifecycle Status

## Requirements

- `REQ-DLS-001`：注册表必须是 app-scoped，并以 `(direction, detector_name)` 唯一标识配置实例。
- `REQ-DLS-002`：初始化失败使用 `unavailable`；已加载实例的健康失败使用可恢复的 `unhealthy`。

## Scenarios

| ID | Given / When | Then |
|---|---|---|
| SC-DLS-001 | input/output 配置同名检测器并初始化注册表 | 保存两个独立记录 |
| SC-DLS-002 | 检测器成功初始化 | configured → initializing → healthy；仅状态变化发事件 |
| SC-DLS-003 | 初始化抛出异常 | unavailable，原因稳定且脱敏 |
| SC-DLS-004 | 健康检查先失败后成功 | healthy → unhealthy → healthy |
