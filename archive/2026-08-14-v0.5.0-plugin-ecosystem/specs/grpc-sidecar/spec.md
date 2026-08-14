# grpc-sidecar - 行为规格（Human View）

> **Change**: 2026-08-14-v0.5.0-plugin-ecosystem
> **Capability**: grpc-sidecar
> **Created**: 2026-08-14T10:30:00+08:00
> **Confidence**: high

## Requirements

### REQ-GRPC-001: GRPCDetector 实现 Detector 接口，initialize 执行 HealthCheck + Initialize 并读取 DetectorInfo

#### SC-GRPC-001: high

- **Given**: type=grpc 检测器已配置 endpoint，sidecar 服务健康且就绪
- **When**: GRPCDetector.initialize(config) 被调用
- **Then**: GRPCDetector SHALL 先调用 HealthCheck，确认 status='serving' 后调用 Initialize
- **And**: Initialize SHALL 携带 detector_name 与配置透传字段（除 endpoint/tls_enabled/tls_ca_file）
- **And**: Initialize 成功返回后 SHALL 从 DetectorInfo 读取 name/category/description/version 并更新实例属性
- **And**: HealthCheck 返回非 serving 或 Initialize 失败 SHALL 抛出异常（初始化失败）

### REQ-GRPC-002: detect 将 DetectionContext 映射为 DetectRequest，DetectResponse 映射为 DetectionResult

#### SC-GRPC-002: high

- **Given**: GRPCDetector 已初始化，内容 'content-x' 与上下文（direction=input, request_id=req-1, user_id=u1, language=en, message_index=0, metadata={k:v}）
- **When**: detect(content, context) 被调用
- **Then**: GRPCDetector SHALL 构造 DetectRequest（content/direction/request_id/user_id/language/message_index/metadata）并调用 Detect
- **And**: DetectResponse SHALL 映射为 DetectionResult（detector_name/category/action/confidence/risk_level/message）
- **And**: action='modify' 时 SHALL 透传 modified_content
- **And**: details (google.protobuf.Struct) SHALL 转换为 dict 写入 DetectionResult.details

### REQ-GRPC-003: shutdown 调用 Shutdown 并关闭通道；health_check 返回 serving 状态

#### SC-GRPC-003: high

- **Given**: GRPCDetector 已初始化并完成若干次检测
- **When**: shutdown() 与 health_check() 被调用
- **Then**: shutdown() SHALL 调用远端 Shutdown 并关闭 gRPC 通道
- **And**: health_check() SHALL 调用 HealthCheck 并返回 status=='serving' 时 True，否则 False
- **And**: gRPC 调用异常 SHALL 不抛出未捕获异常（shutdown 容错）

### REQ-GRPC-004: gRPC 调用超时处理：复用 per-detector timeout 或全局 detector timeout

#### SC-GRPC-004: high

- **Given**: per-detector timeout='3s'（或未配置时全局 security.timeout.detector='5s'），sidecar 响应超时
- **When**: Detect 调用超过配置超时
- **Then**: GRPCDetector SHALL 在超时后中止调用并抛出超时异常
- **And**: 超时异常 SHALL 携带检测器名与超时时长，供 on_error 策略处理

### REQ-GRPC-005: TLS 支持：tls_enabled=true 时 secure_channel，tls_ca_file 加载 CA

#### SC-GRPC-005: high

- **Given**: config 含 tls_enabled=true 且 tls_ca_file 指向有效 CA 文件
- **When**: GRPCDetector 建立 gRPC 通道
- **Then**: GRPCDetector SHALL 使用 grpc.secure_channel 并加载 CA 证书构建凭证
- **And**: tls_ca_file 未配置时 SHALL 使用系统默认根证书（无自定义 CA）
- **And**: tls_enabled=false（默认）时 SHALL 使用 insecure_channel

### REQ-GRPC-006: grpcio 未安装时导入/使用报清晰错误

#### SC-GRPC-006: high

- **Given**: 环境未安装 grpcio（未 pip install ...[grpc]）
- **When**: 实例化 GRPCDetector 或导入 grpc 插件模块
- **Then**: SHALL 抛出带指引的错误：安装 grpcio 或 pip install z-llm-safety-gateway[grpc]

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-GRPC-001 | GRPCDetector SHALL 先调用 HealthCheck，确认 status='serving' 后调用 I |
| CP-2 | SC-GRPC-002 | GRPCDetector SHALL 构造 DetectRequest（content/direction/reques |
| CP-3 | SC-GRPC-003 | shutdown() SHALL 调用远端 Shutdown 并关闭 gRPC 通道 |
| CP-4 | SC-GRPC-004 | GRPCDetector SHALL 在超时后中止调用并抛出超时异常 |
| CP-5 | SC-GRPC-005 | GRPCDetector SHALL 使用 grpc.secure_channel 并加载 CA 证书构建凭证 |
| CP-6 | SC-GRPC-006 | SHALL 抛出带指引的错误：安装 grpcio 或 pip install z-llm-safety-gateway[ |
| CP-7 | -- | ruff lint 通过 |
| CP-8 | -- | mypy 类型检查通过 |
