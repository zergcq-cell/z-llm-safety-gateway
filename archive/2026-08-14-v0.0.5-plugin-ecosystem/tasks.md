# v0.5.0 实现任务清单

> 变更：2026-08-14-v0.5.0-plugin-ecosystem
> 依据：Phase 2 specs（7 capabilities / 28 SC / 32 TC）

## Slice 1: Detector SDK 包骨架

- [ ] 创建 `sdk/pyproject.toml`（独立版本 1.0.0，不依赖网关）
- [ ] `sdk/src/z_llm_safety_gateway_sdk/base.py`：Detector 抽象基类（TC-SDK-002）
- [ ] `sdk/src/z_llm_safety_gateway_sdk/context.py`：DetectionContext（TC-SDK-002）
- [ ] `sdk/src/z_llm_safety_gateway_sdk/result.py`：DetectionResult（TC-SDK-002）
- [ ] `sdk/src/z_llm_safety_gateway_sdk/modification.py`：Modification（TC-SDK-002）
- [ ] `sdk/src/z_llm_safety_gateway_sdk/testing.py`：make_context + 断言辅助（TC-SDK-006）
- [ ] `sdk/src/z_llm_safety_gateway_sdk/__init__.py`：re-export（TC-SDK-001）
- [ ] 测试：`tests/unit/sdk/test_sdk_package.py`（TC-SDK-001/002/006）

## Slice 2: 配置系统扩展

- [ ] `config/models.py`：DetectorConfig.type 支持 grpc（TC-CFG-501）
- [ ] `config/validators.py`：type=grpc 缺 endpoint 报错（TC-CFG-502）
- [ ] `config/validators.py`：type=grpc 无 circuit_breaker Info 提示（TC-CFG-503）
- [ ] 测试：`tests/unit/config/test_v5_grpc_config.py`

## Slice 3: 检测器框架扩展

- [ ] `detectors/registry.py`：register_from_entry_points 方法（TC-DF-501）
- [ ] 插件注册路径：同名不覆盖（内置优先）（TC-DF-501）
- [ ] GRPCDetector 创建路径接入 registry（TC-DF-503）
- [ ] 测试：`tests/unit/detectors/test_v5_entry_points.py`

## Slice 4: 插件加载器

- [ ] `plugins/loader.py`：entry points 发现与注册（TC-PL-001/002）
- [ ] 未知检测器名报错增强（含可用列表 + 第三方提示）（TC-PL-003）
- [ ] 加载失败不阻断内置检测器（TC-PL-004）
- [ ] 测试：`tests/unit/plugins/test_loader.py`

## Slice 5: gRPC 合约与客户端

- [ ] `proto/detector/v1/detector.proto`（DESIGN 7.3.1 合约）
- [ ] 生成 `_pb2.py`/`_pb2_grpc.py` 提交（grpc-tools）
- [ ] `plugins/grpc/client.py`：GRPCDetector（initialize/detect/shutdown/health_check）（TC-GRPC-001/002/003/005）
- [ ] 请求/响应映射（含 details Struct 转换、modify 透传）（TC-GRPC-003/004）
- [ ] 超时处理（per-detector/全局回退）（TC-GRPC-006）
- [ ] TLS 支持（secure_channel + CA）（TC-GRPC-007）
- [ ] grpcio 可选导入与错误提示（TC-GRPC-008）
- [ ] `pyproject.toml`：[grpc] 可选依赖组
- [ ] 测试：`tests/unit/plugins/grpc/test_client.py`（in-process gRPC server）
- [ ] 测试：`tests/unit/plugins/grpc/test_mapping.py`

## Slice 6: CLI

- [ ] `z_llm_safety_gateway/cli.py`：zlg detectors list/info/test/check-connection（TC-CLI-001~004）
- [ ] `sdk/.../cli.py`：zlg-sdk new/validate（TC-SDK-003/004/005）
- [ ] `pyproject.toml`：zlg + zlg-sdk 脚本入口
- [ ] 测试：`tests/unit/cli/test_zlg.py`
- [ ] 测试：`tests/unit/sdk/test_cli.py`

## Slice 7: FastAPI 集成

- [ ] `app.py`：create_app 集成插件加载 + gRPC 初始化（TC-FSA-501/DF-502）
- [ ] 插件/gRPC 检测器接入 pipeline 引擎与审计/指标（TC-FSA-502）
- [ ] lifespan shutdown 关闭 gRPC 通道（TC-FSA-503）
- [ ] 测试：`tests/integration/test_v5_plugin_app.py`
- [ ] 全量回归：pytest / ruff / mypy / coverage
