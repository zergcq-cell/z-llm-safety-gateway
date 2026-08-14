# v0.4.0 设计调整记录

> 变更：2026-08-12-v0.4.0-security-observability
> 阶段：Phase 5 VERIFY Step 4
> 日期：2026-08-12

## ADJ-001: 配置系统类型化子模型重构（Build 阶段）

- **状态**：已接受
- **来源阶段**：Build (Slice 1)
- **原始设计**：proposal C1/C2 声明 SecurityConfig 拆分为类型化子模型、ObservabilityConfig 重构为嵌套子模型、ServerConfig 补 workers/stop_timeout。
- **实际变更**：配置结构破坏性变更：`security.timeout` 由 `dict[int,int]` 改为 `TimeoutConfig`（字符串时长 + `upstream_seconds` property，兼容旧 int 值）；`observability` 由扁平布尔改为嵌套 `MetricsConfig`/`TracingConfig`；`ServerConfig` 新增字段。
- **原因**：现有 v0.1.0 测试及多个集成测试使用旧结构（`security.timeout` 为 int、`observability.metrics_enabled` 扁平布尔），与 DESIGN 10.2 文档不符。为对齐 DESIGN 与支持 v0.4.0 新安全能力，必须更新配置模型及其引用。
- **影响**：更新 `tests/unit/config/test_models.py`；`router.py` 与 `routes/models.py` 改用 `security.timeout.upstream_seconds`。旧 int 配置自动兼容。

## ADJ-002: 优雅停机从 signal.signal 改为 FastAPI lifespan（Verify 阶段）

- **状态**：已接受
- **来源阶段**：Verify Step 0（技术评审 C 级问题修复）
- **原始设计**：`__main__.py` 中 `install_signal_handlers(app)` 使用 `signal.signal(SIGTERM, handler)` 注册自定义信号处理器，在 uvicorn 启动前冲刷审计日志。
- **实际变更**：移除 `install_signal_handlers`/`_handle_shutdown`/`SHUTDOWN_SIGNALS`，在 `app.py` 中添加 `@asynccontextmanager lifespan(app)` 上下文管理器，通过 `FastAPI(lifespan=lifespan)` 注册。uvicorn 收到 SIGTERM/SIGINT 时自动触发 lifespan shutdown，在其中冲刷审计日志。
- **原因**：`signal.signal()` 安装的处理器会被 `uvicorn.run()` 覆盖（uvicorn 自行安装 SIGTERM/SIGINT 处理器），导致审计日志冲刷逻辑永远不会被执行。FastAPI lifespan 是官方推荐的启动/关闭生命周期管理方式，uvicorn 会在收到信号时触发 lifespan shutdown。
- **影响**：
  - `app.py`：新增 `lifespan` 函数和 `AsyncIterator` 导入
  - `__main__.py`：移除 `signal`/`Callable`/`FrameType` 导入，移除 `_parse_seconds`（改用 `_parse_duration`），移除信号处理器函数
  - `tests/unit/test_main_tls.py`：TC-GS-001 测试从 `install_signal_handlers` 改为 `lifespan` 上下文测试
- **验证**：744 passed, 1 skipped；ruff pass；mypy pass

## ADJ-003: detector_results[0] 改为 find_result_by_action 共享工具（Verify 阶段）

- **状态**：已接受
- **来源阶段**：Verify Step 0（技术评审 H 级问题修复）
- **原始设计**：`routes/chat.py`、`streaming/handler.py`、`post_audit/audit.py` 中使用 `result.detector_results[0]` 获取触发 block/flag 的检测器结果。
- **实际变更**：在 `models.py` 中新增 `find_result_by_action(results, actions)` 工具函数，按 action 匹配返回第一个触发了该 action 的 DetectionResult（而非列表第一个，可能为 allow）。替换全部 4 处 `detector_results[0]` 用法。
- **原因**：`detector_results[0]` 返回的是检测器列表中的第一个结果，可能是返回 `allow` 的检测器，而非实际触发 block/flag 的检测器。这会导致 `blocked_by`、`category`、`confidence` 等元数据指向错误的检测器。
- **影响**：
  - `models.py`：新增 `find_result_by_action` 函数
  - `routes/chat.py`：4 处替换（含 `_find_block_result` 委托到共享函数）
  - `streaming/handler.py`：2 处替换（block + flag）
  - `post_audit/audit.py`：1 处替换
  - `tests/unit/test_find_result_by_action.py`：新增 5 个单元测试
- **验证**：744 passed, 1 skipped；ruff pass；mypy pass

## ADJ-004: _parse_seconds 统一为 _parse_duration（Verify 阶段）

- **状态**：已接受
- **来源阶段**：Verify Step 0（技术评审 H 级问题修复）
- **原始设计**：`__main__.py` 中自定义 `_parse_seconds(value)` 函数，仅支持 `s` 后缀和纯数字。
- **实际变更**：移除 `_parse_seconds`，改用 `config/models.py` 中已有的 `_parse_duration(value)` 函数（支持 `s` 和 `ms` 后缀），通过 `int(_parse_duration(...))` 转为整数秒。
- **原因**：`_parse_seconds` 不支持 `ms` 后缀，且重复了 `_parse_duration` 的逻辑。统一使用 `_parse_duration` 消除重复并扩展兼容性。
- **影响**：`__main__.py` 导入变更；`build_server_kwargs` 中 `_parse_seconds` → `int(_parse_duration(...))`
- **验证**：744 passed, 1 skipped

## ADJ-005: 版本号统一为 0.4.0（Verify 阶段）

- **状态**：已接受
- **来源阶段**：Verify Step 0（技术评审 C 级问题修复）
- **原始设计**：pyproject.toml 版本应与 __init__.py 版本一致，反映当前变更版本。
- **实际变更**：`pyproject.toml` 0.3.0 → 0.4.0；`__init__.py` 0.1.0 → 0.4.0
- **原因**：版本号不一致导致 `__version__` 与包元数据不匹配。
- **验证**：版本号一致

## ADJ-006: OpenTelemetry 可选依赖组（Verify 阶段）

- **状态**：已接受
- **来源阶段**：Verify Step 0（技术评审 M 级问题修复）
- **原始设计**：observability/tracing.py 使用 `opentelemetry.*` 但仅通过 mypy `ignore_missing_imports` 跳过，未声明可选依赖。
- **实际变更**：在 `pyproject.toml` 的 `[project.optional-dependencies]` 中新增 `otel` 组，包含 `opentelemetry-api`、`opentelemetry-sdk`、`opentelemetry-exporter-otlp`。
- **原因**：用户安装 `pip install z-llm-safety-gateway[otel]` 时应自动安装 OTel 依赖，否则运行时 `import opentelemetry` 会失败。
- **验证**：pyproject.toml 结构正确

## 总结

| ADJ | 级别 | 阶段 | 状态 |
|-----|------|------|------|
| ADJ-001 | 设计偏离 | Build | 已接受 |
| ADJ-002 | 设计偏离 | Verify | 已接受 |
| ADJ-003 | Bug 修复 | Verify | 已接受 |
| ADJ-004 | 代码质量 | Verify | 已接受 |
| ADJ-005 | 一致性 | Verify | 已接受 |
| ADJ-006 | 完整性 | Verify | 已接受 |

所有调整均不影响已确认的 Gate 2 设计决策（60 条 DESIGN.md 决策），均为实现层面的偏差或修复。
