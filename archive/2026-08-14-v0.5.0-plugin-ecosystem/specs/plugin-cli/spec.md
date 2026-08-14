# plugin-cli - 行为规格（Human View）

> **Change**: 2026-08-14-v0.5.0-plugin-ecosystem
> **Capability**: plugin-cli
> **Created**: 2026-08-14T10:30:00+08:00
> **Confidence**: high

## Requirements

### REQ-CLI-001: zlg detectors list 列出全部可用检测器（内置 + 插件）

#### SC-CLI-001: high

- **Given**: 网关已安装内置检测器与若干第三方插件
- **When**: 执行 zlg detectors list
- **Then**: CLI SHALL 输出全部可用检测器名称列表（内置 + entry points 发现的插件）
- **And**: --enabled 参数 SHALL 仅输出配置中启用的检测器
- **And**: 退出码 SHALL 为 0

### REQ-CLI-002: zlg detectors info 显示检测器详情

#### SC-CLI-002: high

- **Given**: 已注册检测器 prompt_injection
- **When**: 执行 zlg detectors info prompt_injection
- **Then**: CLI SHALL 输出检测器详情（name/category/description/version）
- **And**: 未知检测器名 SHALL 输出错误并退出码非 0

### REQ-CLI-003: zlg detectors test 对示例输入执行检测

#### SC-CLI-003: high

- **Given**: 已配置检测器 prompt_injection，输入 'ignore previous instructions'
- **When**: 执行 zlg detectors test prompt_injection --input '...'
- **Then**: CLI SHALL 运行检测并输出 DetectionResult（action/risk_level/confidence/message）
- **And**: 输出 SHALL 为可读格式（JSON 或表格）
- **And**: 检测器初始化失败 SHALL 输出错误并退出码非 0

### REQ-CLI-004: zlg detectors check-connection 验证 gRPC sidecar 连接

#### SC-CLI-004: high

- **Given**: type=grpc 检测器 'acme_guard' 已配置，sidecar 正在运行
- **When**: 执行 zlg detectors check-connection acme_guard
- **Then**: CLI SHALL 调用 HealthCheck 验证连接并输出 serving 状态
- **And**: 连接成功 SHALL 退出码 0
- **And**: 连接失败（sidecar 未运行/超时）SHALL 输出错误并退出码非 0

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-CLI-001 | CLI SHALL 输出全部可用检测器名称列表（内置 + entry points 发现的插件） |
| CP-2 | SC-CLI-002 | CLI SHALL 输出检测器详情（name/category/description/version） |
| CP-3 | SC-CLI-003 | CLI SHALL 运行检测并输出 DetectionResult（action/risk_level/confiden |
| CP-4 | SC-CLI-004 | CLI SHALL 调用 HealthCheck 验证连接并输出 serving 状态 |
| CP-5 | -- | ruff lint 通过 |
| CP-6 | -- | mypy 类型检查通过 |
