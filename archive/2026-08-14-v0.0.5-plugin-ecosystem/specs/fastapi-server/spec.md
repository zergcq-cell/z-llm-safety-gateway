# fastapi-server - 行为规格（Human View）

> **Change**: 2026-08-14-v0.5.0-plugin-ecosystem
> **Capability**: fastapi-server
> **Created**: 2026-08-14T10:30:00+08:00
> **Confidence**: high

## Requirements

### REQ-FSA-501: create_app 初始化路径集成插件加载（entry points + gRPC sidecar）

#### SC-FSA-501: high

- **Given**: create_app(config_path) 被调用，环境含第三方插件与 type=grpc 检测器配置
- **When**: 初始化检测器阶段
- **Then**: 网关 SHALL 在创建默认 registry 后加载 entry point 插件并注册
- **And**: type=grpc 的检测器 SHALL 按配置创建 GRPCDetector 并 initialize
- **And**: 加载失败 SHALL 记录日志且不阻断其他检测器初始化
- **And**: app.state 检测器集合 SHALL 包含内置 + 插件 + gRPC 检测器

### REQ-FSA-502: 插件/gRPC 检测器接入 pipeline 引擎与审计/指标链路

#### SC-FSA-502: high

- **Given**: 请求到达网关，配置含插件检测器与 gRPC 检测器
- **When**: input/output pipeline 运行
- **Then**: 插件与 gRPC 检测器 SHALL 与其他检测器一样被 pipeline 引擎调用
- **And**: 检测结果 SHALL 进入聚合器（block/flag/modify/allow 语义一致）
- **And**: 检测结果 SHALL 写入审计日志（含 detector_name/category/risk_level）
- **And**: 指标埋点 SHALL 覆盖插件检测器（duration/results/errors）

### REQ-FSA-503: app lifespan shutdown 时关闭 gRPC 通道（Shutdown 调用）

#### SC-FSA-503: high

- **Given**: 网关运行中且存在已初始化的 gRPC 检测器
- **When**: 网关收到 SIGTERM 触发 lifespan shutdown
- **Then**: 网关 SHALL 对每个 gRPC 检测器调用 shutdown()（远端 Shutdown + 关闭通道）
- **And**: 单个 gRPC 检测器关闭失败 SHALL 记录日志且不阻断整体关闭

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-FSA-501 | 网关 SHALL 在创建默认 registry 后加载 entry point 插件并注册 |
| CP-2 | SC-FSA-502 | 插件与 gRPC 检测器 SHALL 与其他检测器一样被 pipeline 引擎调用 |
| CP-3 | SC-FSA-503 | 网关 SHALL 对每个 gRPC 检测器调用 shutdown()（远端 Shutdown + 关闭通道） |
| CP-4 | -- | ruff lint 通过 |
| CP-5 | -- | mypy 类型检查通过 |
