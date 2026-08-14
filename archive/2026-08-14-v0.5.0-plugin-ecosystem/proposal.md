# v0.5.0 变更提案 — Plugin Ecosystem

> 变更：2026-08-14-v0.5.0-plugin-ecosystem
> 状态：已确认（Gate 1）
> 模式：thorough

## Why（背景与动机）

第三方检测器目前只能以内置方式接入，需要修改网关代码才能集成新检测器。这限制了生态扩展：开源检测器无法通过标准 Python 包分发接入，商业/闭源检测器（非 Python 实现）无法以进程隔离方式部署。

DESIGN.md Section 7 规划了成熟的插件系统（in-process + gRPC sidecar + SDK）。v0.5.0 落地该设计，使第三方与商业检测器可通过 SDK 开发、entry points 或 gRPC sidecar 接入，无需修改网关代码，实现开放的检测器生态。

## What Changes

| ID | 变更 | 类型 |
|----|------|------|
| C1 | **In-process 插件加载器**：`importlib.metadata` 发现 `z_llm_safety_gateway.detectors` entry points，注册到 DetectorRegistry；未知检测器名报错信息增强（含可用列表与提示） | new |
| C2 | **gRPC Sidecar 检测器**：protobuf 合约（detector/v1：Initialize/Detect/HealthCheck/Shutdown）、gRPC 客户端封装为 Detector、生命周期管理、超时处理、TLS 支持、配置透传 | new |
| C3 | **Detector SDK 独立包**（`sdk/` 目录，`z_llm_safety_gateway_sdk`）：Detector 基类、DetectionContext、DetectionResult、Modification、test_utils、CLI 脚手架（`zlg-sdk new/validate/test`），独立语义化版本管理 | new |
| C4 | **配置系统扩展**：`DetectorConfig.type` 支持 `"grpc"`，gRPC 缺 `endpoint` 启动报错，type=grpc 无 circuit_breaker 时提示 Info | modified |
| C5 | **Gateway 插件管理 CLI**：`zlg detectors list/info/test/check-connection` | new |
| C6 | **文档与示例**：`docs/detector-development.md`、`docs/grpc-plugin-guide.md`、`examples/plugins/python_detector/`、`examples/plugins/grpc_detector_python/` | new |

## Capabilities

- **NEW**：`plugin-loader`、`grpc-sidecar`、`detector-sdk`、`plugin-cli`
- **MODIFIED**：`config-system`、`detector-framework`、`fastapi-server`

## Constraints

- gRPC 为可选依赖组（`[grpc]`），核心包保持轻量
- SDK 包独立版本管理（`>=1.0, <2.0` 兼容范围）
- 向后兼容：v0.1.0~v0.4.0 配置无需修改即可加载
- gRPC 网关内部字段（`endpoint`/`tls_enabled`/`tls_ca_file`）不透传给插件

## Risk & Mitigation

| 风险 | 缓解 |
|------|------|
| gRPC 生成代码复杂度与构建可重复性 | 提交 .proto 源文件 + 生成 _pb2.py，构建时校验一致性 |
| entry points 加载第三方代码的安全风险 | 文档声明只安装可信包；加载失败不阻断启动（skip + log） |
| 配置透传含密钥泄露到日志 | 沿用审计脱敏：日志中 api_key/license_key redacted |
| SDK 与网关接口漂移 | SDK 独立 semver，网关声明兼容范围，不匹配时警告 |

## Non-Goals

- Go 语言 gRPC 示例（后续文档阶段补充）
- 插件热加载与自动升级
- gRPC 流式检测（仅 unary）
- 商业检测器计费/许可（DESIGN 明确 gateway 不参与）
- 多 worker 下插件状态同步

## Success Criteria

1. 安装示例 in-process 插件包后，网关通过 entry points 自动发现并可在 config 启用，检测结果正确（block/flag/allow）
2. gRPC sidecar 示例可启动，网关连接后检测结果正确映射
3. 未知检测器名报错含可用列表与第三方提示（DESIGN 10.4 表 2004 行）
4. `type: grpc` 缺 `endpoint` 时启动报错（DESIGN 10.4 表 2009 行）
5. SDK 包可独立 `pip install`，`zlg-sdk new` 生成可运行项目模板
6. `zlg detectors list/info/test/check-connection` 正常工作
7. 全量测试通过（新增约 80+ 用例），覆盖率 ≥ 80%，ruff/mypy 全绿

## Anchoring

- 等级：L2
- 参考变更：2026-08-12-v0.4.0-security-observability
