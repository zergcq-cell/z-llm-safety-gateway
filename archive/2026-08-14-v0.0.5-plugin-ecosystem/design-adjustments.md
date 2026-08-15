# v0.5.0 设计调整记录

> 变更：2026-08-14-v0.5.0-plugin-ecosystem
> 阶段：Phase 5 VERIFY Step 4
> 日期：2026-08-14

## ADJ-001: GRPCDetector 使用同步 stub + asyncio.to_thread（Build 阶段）

- **状态**：已接受
- **来源阶段**：Build (Slice 5)
- **原始设计**：design.md Decision 5 描述 gRPC 客户端封装，未明确 aio/同步 stub。
- **实际变更**：`GRPCDetector` 使用同步 `DetectorServiceStub`，阻塞调用经 `asyncio.to_thread` 卸载到线程池，并用 `asyncio.wait_for` 实现超时（DESIGN 7.3.4）。
- **原因**：grpc.aio stub 与 pytest-asyncio 的 event loop 生命周期冲突导致测试挂起（首次实现验证失败）；同步 stub + to_thread 方案与 `asyncio.wait_for` 超时语义一致，且无需在 event loop 中管理 aio 通道。
- **影响**：`client.py` 的 `_call()` 封装；无公共接口变化。
- **验证**：TC-GRPC-001~008 全绿（11 tests）。

## ADJ-002: 测试环境 grpc.server 线程池适配（Build 阶段）

- **状态**：已接受
- **来源阶段**：Build (Slice 5)
- **原始设计**：测试用 `grpc.server(thread_pool=None)`（旧版默认线程池语义）。
- **实际变更**：显式传 `ThreadPoolExecutor(max_workers=10)`。
- **原因**：grpc>=1.83 中 `thread_pool=None` 不再使用默认线程池，请求处理时抛 `AttributeError: 'NoneType' object has no attribute 'submit'`（环境实测）。
- **影响**：仅测试 fixture；网关代码不受影响。

## ADJ-003: protobuf 生成代码 struct.proto 依赖补丁（Build 阶段）

- **状态**：已接受
- **来源阶段**：Build (Slice 5)
- **原始设计**：提交 protoc 生成的 `detector_pb2.py`，期望开箱即用。
- **实际变更**：在 `detector_pb2.py` imports 区手动补 `from google.protobuf import struct_pb2`，确保 well-known type 先注册到 descriptor pool。
- **原因**：protobuf 7.35 生成代码（"NO CHECKED-IN PROTOBUF GENCODE" 新格式）不再自动 import 依赖的 well-known types，直接 import 报 `Depends on file 'google/protobuf/struct.proto', but it has not been loaded`。
- **影响**：重新生成代码后需重新应用此补丁；已注释标记。
- **验证**：全量测试 796 passed。

## ADJ-004: CLI --enabled 需加载配置过滤（Verify 阶段修复）

- **状态**：已接受
- **来源阶段**：Verify Step 0
- **原始设计**：`zlg detectors list --enabled` 占位实现（`[n for n in names if True]`），未真实过滤。
- **实际变更**：`--enabled` 时加载 gateway 配置，仅输出配置中启用的检测器名；新增 `--config` 参数指定配置路径。
- **原因**：TC-CLI-001b 要求真实过滤，占位实现违反 spec。
- **影响**：cli.py `_cmd_list`；测试 `test_detectors_list_enabled` 更新为真实断言。

## ADJ-005: gRPC 初始化失败日志级别提升（Verify 阶段修复）

- **状态**：已接受
- **来源阶段**：Verify Step 0
- **原始设计**：所有检测器初始化失败统一 `logger.exception`（内置检测器既有行为）。
- **实际变更**：type=grpc 检测器初始化失败改为 `logger.error`，消息明确标注"will not run"。
- **原因**：gRPC sidecar 不可用时检测器被静默跳过（与内置一致），但安全相关——sidecar 检测器失效意味着安全能力缺失，应以 ERROR 级别显著告警，避免运维无感知。
- **影响**：app.py `_initialize_detectors`；无测试变化（行为保持 skip）。

## 总结

| ADJ | 级别 | 阶段 | 状态 |
|-----|------|------|------|
| ADJ-001 | 实现偏离 | Build | 已接受 |
| ADJ-002 | 测试适配 | Build | 已接受 |
| ADJ-003 | 兼容补丁 | Build | 已接受 |
| ADJ-004 | Bug 修复 | Verify | 已接受 |
| ADJ-005 | 安全增强 | Verify | 已接受 |

所有调整不影响 Gate 2 确认的设计决策，均为实现层面偏差或质量修复。
