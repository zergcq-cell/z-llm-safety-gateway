# config-system - 行为规格（Human View）

> **Change**: 2026-08-14-v0.5.0-plugin-ecosystem
> **Capability**: config-system
> **Created**: 2026-08-14T10:30:00+08:00
> **Confidence**: high

## Requirements

### REQ-CFG-501: DetectorConfig.type 支持 'grpc'，配置透传字段与网关内部字段分离

#### SC-CFG-501: high

- **Given**: detector 配置 name=acme_guard, type=grpc, config={endpoint: localhost:50051, api_key: x, sensitivity: high}
- **When**: GatewayConfig 加载该配置
- **Then**: DetectorConfig SHALL 接受 type='grpc' 且保留 config 全部字段
- **And**: endpoint/tls_enabled/tls_ca_file SHALL 标记为网关内部字段（不透传）
- **And**: 其余 config 字段（api_key/sensitivity 等）SHALL 标记为透传字段

### REQ-CFG-502: type=grpc 缺 endpoint 时启动报错

#### SC-CFG-502: high

- **Given**: detector 配置 type=grpc 但 config 不含 endpoint（或为空）
- **When**: 配置校验运行
- **Then**: 校验 SHALL 报错：gRPC detector 'xxx' is missing required config: endpoint

### REQ-CFG-503: type=grpc 无 circuit_breaker 时提示 Info

#### SC-CFG-503: high

- **Given**: detector 配置 type=grpc 且未配置 circuit_breaker
- **When**: 网关启动处理该检测器
- **Then**: 网关 SHALL 记录 Info 日志：gRPC detector 'xxx' has no circuit_breaker configured. Recommended for external detectors.
- **And**: 该提示 SHALL 不阻断启动

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-CFG-501 | DetectorConfig SHALL 接受 type='grpc' 且保留 config 全部字段 |
| CP-2 | SC-CFG-502 | 校验 SHALL 报错：gRPC detector 'xxx' is missing required config:  |
| CP-3 | SC-CFG-503 | 网关 SHALL 记录 Info 日志：gRPC detector 'xxx' has no circuit_break |
| CP-4 | -- | ruff lint 通过 |
| CP-5 | -- | mypy 类型检查通过 |
