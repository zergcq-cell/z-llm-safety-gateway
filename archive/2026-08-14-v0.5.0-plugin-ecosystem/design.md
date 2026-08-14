# v0.5.0 Plugin Ecosystem — 技术设计

> 变更：2026-08-14-v0.5.0-plugin-ecosystem
> 日期：2026-08-14
> 对应 proposal：C1~C6

## Context

当前网关（v0.4.0）的检测器全部为内置实现（`src/.../detectors/`），通过 `create_default_registry()` 静态注册。`Detector` 抽象基类与 `DetectorRegistry`（register/get/list/initialize_all/shutdown_all）已具备扩展基础。`DetectorConfig.type` 字段已存在（默认 `""`，DESIGN 预留 `"grpc"` 语义）。

v0.5.0 的目标：让第三方检测器无需修改网关代码即可接入，支持两种模式——in-process（Python entry points）与 gRPC sidecar（任意语言、进程隔离），并提供独立 SDK 包降低开发门槛。

技术栈约束：Python 3.10+、FastAPI、Pydantic v2、structlog；代码走 TDD，质量门禁 ruff + mypy。

## Decisions

### 1. SDK 包位置与结构

**方案**：仓库内 `sdk/` 目录作为独立 Python 包（`sdk/pyproject.toml` + `sdk/src/z_llm_safety_gateway_sdk/`），独立版本 1.0.0（semver）。

**为什么**：SDK 需独立于网关发布（DESIGN 7.4.4），但同仓库管理便于接口同步演进与 CI 统一验证。独立 `pyproject.toml` 允许独立版本号与依赖声明。

**备选方案及排除原因**：
- 与网关同包（`z_llm_safety_gateway.sdk`）：第三方需安装完整网关，违反"轻量 SDK"设计（DESIGN 7.4 明确 separate package）。
- 独立远端仓库：接口变更需跨仓库协调，v0.5.0 阶段无必要。

### 2. In-process 插件发现机制

**方案**：`importlib.metadata.entry_points(group="z_llm_safety_gateway.detectors")` 扫描已安装包，值格式 `<module>:<ClassName>`，注册进现有 `DetectorRegistry`。

**为什么**：Python 标准库机制（Python 3.10+ 支持 `entry_points(group=...)` 选择性查询），无需额外依赖，pip 安装即自动注册（DESIGN 7.2.2/7.6.1）。

**备选方案及排除原因**：
- 扫描目录/约定目录加载：不安全且非标准，放弃。
- setuptools entry points 旧 API：3.10 已提供新 API，用新的。

### 3. gRPC 依赖策略

**方案**：核心依赖不含 gRPC；新增可选依赖组 `[grpc] = ["grpcio>=1.60", "protobuf>=4.25"]`，`[dev]` 加 `grpcio-tools>=1.60`（仅生成代码用）。`GRPCDetector` 在 import 时对 `grpcio` 做可选导入，未安装时抛清晰错误。

**为什么**：保持核心包轻量（DESIGN 未强制 gRPC 为核心）；用户按需 `pip install z-llm-safety-gateway[grpc]`。

**备选方案及排除原因**：
- 核心依赖直接引入 grpcio：增加所有用户安装体积，且仅 gRPC 用户需要，放弃。

### 4. protobuf 合约与生成代码管理

**方案**：`proto/detector/v1/detector.proto` 源文件 + 提交生成的 `_pb2.py`/`_pb2_grpc.py` 到 `src/z_llm_safety_gateway/plugins/grpc/proto/`；CI/验证脚本校验 proto 与生成代码一致（`grpc_tools.protoc` 重新生成后 diff）。

**为什么**：提交生成代码保证安装即用（无需 protoc 工具链）；保留 .proto 源文件供文档与第三方参照（DESIGN 7.3.1）。

**备选方案及排除原因**：
- 仅运行时动态生成：需 grpcio-tools 运行时依赖，违反轻量原则，放弃。

### 5. GRPCDetector 适配 Detector 接口

**方案**：`GRPCDetector(Detector)` 包装 gRPC 通道：
- `initialize()`：health check → `Initialize()`，从 `DetectorInfo` 覆盖实例 `name/category/description/version`
- `detect()`：`Detect()` 调用，将 `DetectionContext` 映射为 `DetectRequest`，`DetectResponse` 映射为 `DetectionResult`
- `shutdown()`：`Shutdown()` 调用 + 关闭通道
- `health_check()`：`HealthCheck()` 调用，返回 `status == "serving"`
- 周期健康检查（30s）由网关生命周期管理（app lifespan）驱动

**为什么**：复用现有 `Detector` 接口与 pipeline 引擎，检测器实现细节对引擎透明（DESIGN 7.1 "Both modes share the same Detector interface contract"）。

### 6. gRPC 超时处理

**方案**：复用 v0.4.0 `timeout_seconds` 注入机制（per-detector `timeout` 优先，回退全局 `security.timeout.detector`），作为 gRPC 调用的 deadline（`grpc.channel_ready_future` + `futures` timeout）。

**为什么**：DESIGN 7.3.4 明确超时解析顺序；与既有检测器超时体系一致。

### 7. gRPC TLS 支持

**方案**：`config.tls_enabled=true` 时用 `grpc.secure_channel(endpoint, credentials)`；`tls_ca_file` 提供时加载 CA 证书构建 `grpc.ssl_channel_credentials(root_certificates=...)`；默认 `grpc.insecure_channel`。

**为什么**：DESIGN 7.3.2 配置示例含 tls_enabled/tls_ca_file；安全默认（远程检测器应启用 TLS）。

### 8. 配置透传与脱敏

**方案**：`config` 中除网关内部字段（`endpoint`/`tls_enabled`/`tls_ca_file`）外全部透传（值字符串化，`map<string,string>`）；日志与审计沿用既有脱敏（`api_key`/`license_key` → `***`）。

**为什么**：DESIGN 7.5.1 配置透传契约；DESIGN 安全章节要求密钥脱敏。

### 9. 配置校验扩展

**方案**：在配置校验器（`config/validators.py`）增加：
- `type == "grpc"` 且 `config` 缺 `endpoint`（或空）→ 启动 Error：`gRPC detector 'xxx' is missing required config: endpoint`
- `type == "grpc"` 且无 `circuit_breaker` → Info 日志：`gRPC detector 'xxx' has no circuit_breaker configured. Recommended for external detectors.`
- 未知检测器名（非内置、非 entry point、非 grpc type）→ Error：`Unknown detector 'xxx'. Available: [list]. For third-party detectors, ensure the package is installed or use type: grpc.`

**为什么**：DESIGN 10.4 校验规则表（2004/2009/2013 行）逐条落地。

### 10. CLI 结构

**方案**：
- `zlg` 脚本 → `z_llm_safety_gateway.cli.main()`：子命令 `detectors`（list/info/test/check-connection）
- `zlg-sdk` 脚本 → `z_llm_safety_gateway_sdk.cli.main()`：子命令 `new`/`validate`/`test`
- 两者均用标准库 `argparse` 子命令实现（不引入新 CLI 框架）

**为什么**：DESIGN 7.4.3/7.6.3 定义的 CLI 界面；argparse 零依赖。

## Architecture

```
                     ┌─────────────────────────────────────────────┐
                     │              Gateway (FastAPI)              │
                     │                                             │
  gateway.yaml ────► │  Config (type=grpc / name=entrypoint)       │
                     │        │                                    │
                     │        ▼                                    │
                     │  DetectorRegistry ◄──── PluginLoader        │
                     │     │  │  │           (entry points)        │
                     │     │  │  └── built-in detectors            │
                     │     │  └───── in-process plugins  ◄── pip install pkg
                     │     └──────── GRPCDetector (sidecar)        │
                     │              │                              │
                     │              │ gRPC (DetectorService v1)    │
                     │              │ Initialize/Detect/           │
                     │              │ HealthCheck/Shutdown         │
                     │              ▼                              │
                     │  PipelineEngine ──► detect() per detector   │
                     │              │                              │
                     │              ▼                              │
                     │  Audit / Metrics / CircuitBreaker           │
                     └─────────────────────────────────────────────┘
                                          ▲
                     ┌────────────────────┴───────────────────┐
                     │  Sidecar (any language, DESIGN contract)│
                     │  python/grpc_detector_python example    │
                     └─────────────────────────────────────────┘

 SDK (z_llm_safety_gateway_sdk, sdk/)
   Detector base / DetectionContext / DetectionResult / Modification
   testing utils / cli (zlg-sdk new|validate|test)
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| gRPC 生成代码与 proto 漂移 | 提交 .proto + 生成 _pb2.py；验证脚本重新生成后 diff 校验 |
| grpcio 未安装时 import 失败 | 可选导入 + 清晰错误提示（指向 `pip install ...[grpc]`） |
| entry points 加载第三方代码安全 | 文档声明只安装可信包；初始化失败 skip + log，不阻断启动 |
| 配置透传含密钥泄露 | 沿用既有脱敏（api_key/license_key → `***`） |
| SDK 与网关接口漂移 | SDK 独立 semver（1.0.0）；网关声明 `>=1.0,<2.0` 兼容范围 |
| gRPC sidecar 不可用导致级联 | 复用 v0.4.0 circuit_breaker + on_error（fail_open/fail_closed） |
| CLI 测试依赖真实 gRPC 服务 | check-connection 通过 fake/in-process gRPC server 测试 |
