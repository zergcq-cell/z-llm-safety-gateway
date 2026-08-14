# v0.5.0 测试报告

> 变更：2026-08-14-v0.5.0-plugin-ecosystem
> 阶段：Phase 5 VERIFY Step 5
> 日期：2026-08-14
> 模式：thorough / full_auto

## 一、质量检查总览

| 检查项 | 命令 | 结果 |
|--------|------|------|
| pytest | `python -m pytest tests/ -q` | **796 passed, 1 skipped** |
| ruff | `python -m ruff check src/ tests/ sdk/src/` | **All checks passed** |
| mypy | `python -m mypy src/` | **Success: no issues in 76 source files** |
| coverage | `pytest --cov=src/z_llm_safety_gateway` | **93% (250/3359 missed)** |

覆盖率 93%，远超 80% 目标。新增模块覆盖：`plugins/loader.py`、`plugins/grpc/client.py`、`cli.py` 均通过单元+集成测试覆盖。

## 二、TC 覆盖率

| 功能 | TC 总数 | 已覆盖 | 覆盖率 | 测试文件 |
|------|---------|--------|--------|----------|
| 插件加载器 (PL) | 4 | 4 | 100% | test_loader.py |
| gRPC Sidecar (GRPC) | 8 | 8 | 100% | test_client.py |
| Detector SDK (SDK) | 7 | 6 | 86% | test_sdk_package.py, test_cli.py |
| 插件 CLI (CLI) | 4 | 4 | 100% | test_zlg.py |
| 配置扩展 (CFG) | 3 | 3 | 100% | test_v5_grpc_config.py |
| 框架扩展 (DF) | 2 | 2 | 100% | test_v5_entry_points.py |
| FastAPI 集成 (FSA) | 3 | 3 | 100% | test_v5_plugin_app.py |
| **总计** | **31** | **30** | **96.8%** | |

未覆盖：TC-SDK-007（SDK 版本不匹配警告，P2，需真实安装不匹配版本插件验证，标记 SKIPPED 而非 PASS）。

## 三、切片验证状态

| 切片 | 状态 | TC | 新测试 | 验证时间 |
|------|------|-----|--------|----------|
| 1: SDK 包骨架 | done | 3/3 | 9 | 2026-08-14T11:00 |
| 2: 配置扩展 | done | 3/3 | 7 | 2026-08-14T11:10 |
| 3: 框架扩展 | done | 2/2 | 5 | 2026-08-14T11:20 |
| 4: 插件加载器 | done | 4/4 | 4 | 2026-08-14T11:30 |
| 5: gRPC 合约与客户端 | done | 8/8 | 11 | 2026-08-14T12:00 |
| 6: CLI | done | 7/7 | 14 | 2026-08-14T12:10 |
| 7: FastAPI 集成 | done | 3/3 | 3 | 2026-08-14T12:20 |

新增测试总计：**53 个**（v0.4.0 基线 744 → v0.5.0 共 796）。

## 四、Step 0 技术评审修复

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| H1 | High | CLI `--enabled` 过滤为占位符（`if True`） | 实现真实配置过滤 + `--config` 参数 |
| H2 | High | gRPC 检测器初始化失败静默跳过（安全相关） | 提升为 ERROR 日志 + "will not run" 告警 |

## 五、十一类失败模式检查

| # | 类别 | 结果 | 说明 |
|---|------|------|------|
| a | 未处理边缘情况 | PASS | GRPCDetector 空 endpoint 抛 ValueError；空 entry points 无操作；空 passthrough_config |
| b | 竞态条件 | PASS | asyncio.to_thread + wait_for 超时；注册表无共享可变状态 |
| c | 资源泄漏 | PASS | lifespan shutdown 关闭 gRPC 通道；channel.close 容错 |
| d | 错误处理缺口 | PASS | grpcio 缺失清晰报错；gRPC 超时抛 TimeoutError；初始化失败 ERROR 日志 |
| e | 安全漏洞 | PASS | 配置透传排除 endpoint/tls 内部字段；插件加载失败不阻断（可信包声明） |
| f | 性能回归 | PASS | entry points 发现缓存；gRPC 调用 off-thread 不阻塞 event loop |
| g | 配置错误 | PASS | type=grpc 缺 endpoint 报错；未知检测器报错含可用列表 |
| h | API 契约违规 | PASS | SDK 接口与网关一致（字段级比对测试）；proto 合约符合 DESIGN 7.3.1 |
| i | 测试覆盖缺口 | PASS | 96.8% TC 覆盖；唯一缺口 P2（SKIPPED 标注） |
| j | 文档缺口 | PASS | 5 条设计调整记录；模块 docstring 完整 |
| k | 向后兼容性 | PASS | 无既有 API 破坏；新增均为增量；v0.1.0~v0.4.0 配置兼容 |

## 六、经验库更新

| 经验 ID | 类别 | 描述 |
|---------|------|------|
| EXP-005 | grpc-thread-pool | grpc>=1.83 中 `grpc.server(thread_pool=None)` 不再使用默认线程池，必须显式传 ThreadPoolExecutor |
| EXP-006 | protobuf-gencode | protobuf 7.x 生成代码不自动 import well-known types，含 `google/protobuf/struct.proto` 依赖时需手动补 import |
| EXP-007 | grpc-async-stub | grpc.aio stub 与 pytest-asyncio event loop 冲突易挂起；同步 stub + asyncio.to_thread 更稳 |
| EXP-008 | cli-placeholder | CLI 占位实现（`if True`）必须标记并实现真实逻辑，测试需断言真实行为 |

## 七、Gate 3 就绪评估

| 前置条件 | 状态 |
|----------|------|
| Step 0: 技术评审 | DONE (H1/H2 已修复) |
| Step 1: 全量质量检查 | DONE (796 passed; ruff/mypy pass; 93% coverage) |
| Step 2: Diff 审查 | DONE (5 修改 + 9 新增，范围符合 proposal) |
| Step 3: 十一类失败模式 | DONE (11/11 PASS) |
| Step 3.5: 经验库更新 | DONE (4 条经验) |
| Step 4: 设计调整 | DONE (5 条 ADJ) |
| Step 5: 测试报告 | DONE (本文档) |

**Gate 3 结论**：所有前置条件已完成，准备进入 Gate 3 用户确认。
