# Detector Lifecycle Status

## Requirements

- `REQ-DLS-001`：注册表必须是 app-scoped，并以 `(direction, detector_name)` 唯一标识配置实例。
- `REQ-DLS-002`：初始化失败使用 `unavailable`；已加载实例健康失败使用可恢复的 `unhealthy`。

| 场景 | 结果 |
|------|------|
| SC-DLS-001 | input/output 同名 detector 保存为两个独立记录 |
| SC-DLS-002 | configured → initializing → healthy，只在变化时发事件 |
| SC-DLS-003 | 初始化异常进入 unavailable，并保存稳定脱敏原因 |
| SC-DLS-004 | 健康失败后成功可恢复 healthy |
