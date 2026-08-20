# Config System

## Requirements

- `REQ-CFG-601`：`required: bool = false` 向后兼容，并通过 input/output 配置提取路径传递。
- `REQ-CFG-602`：拒绝 `required + fail_open` 和 `required + disabled`。

## Scenarios

| ID | Given | Then |
|---|---|---|
| SC-CFG-601 | required 省略或显式设置 | 默认 false，显式值不丢失 |
| SC-CFG-602 | required=true + fail_open | 配置验证失败并给出明确错误 |
| SC-CFG-603 | required=true + enabled=false | 配置验证失败并给出明确错误 |
