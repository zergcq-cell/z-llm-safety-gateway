# detector-framework - 行为规格（Human View）

> **Change**: 2026-08-14-v0.5.0-plugin-ecosystem
> **Capability**: detector-framework
> **Created**: 2026-08-14T10:30:00+08:00
> **Confidence**: high

## Requirements

### REQ-DF-501: DetectorRegistry 支持 register_from_entry_points 方法

#### SC-DF-501: high

- **Given**: DetectorRegistry 实例，环境存在已安装插件的 entry points
- **When**: registry.register_from_entry_points(group='z_llm_safety_gateway.detectors') 被调用
- **Then**: DetectorRegistry SHALL 发现并注册全部 entry point 检测器类
- **And**: 已存在的同名注册 SHALL 不被覆盖（内置优先）
- **And**: 注册后 list() SHALL 包含新插件名称

### REQ-DF-502: create_default_registry 返回的 registry 已包含插件发现（通过 app 初始化路径注入）

#### SC-DF-502: high

- **Given**: 网关通过 create_app 启动
- **When**: 初始化默认 registry 后加载插件
- **Then**: 内置检测器 SHALL 全部注册，且 SHALL 尝试发现并注册 entry point 插件
- **And**: 插件发现失败 SHALL 不影响内置检测器（日志记录）

### REQ-DF-503: GRPCDetector 通过 DetectorRegistry 创建路径（type=grpc 配置映射到 GRPCDetector）

#### SC-DF-503: high

- **Given**: config 中检测器 type=grpc 且 endpoint 已配置
- **When**: 初始化该检测器
- **Then**: SHALL 创建 GRPCDetector 实例并通过其 initialize() 完成侧车握手
- **And**: GRPCDetector SHALL 满足 Detector 接口（可被 pipeline 引擎直接调用）

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-DF-501 | DetectorRegistry SHALL 发现并注册全部 entry point 检测器类 |
| CP-2 | SC-DF-502 | 内置检测器 SHALL 全部注册，且 SHALL 尝试发现并注册 entry point 插件 |
| CP-3 | SC-DF-503 | SHALL 创建 GRPCDetector 实例并通过其 initialize() 完成侧车握手 |
| CP-4 | -- | ruff lint 通过 |
| CP-5 | -- | mypy 类型检查通过 |
