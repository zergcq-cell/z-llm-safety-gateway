# v0.3.0 任务清单

## 1. config-system 扩展（P0）

- [ ] 1.1 修改 `src/z_llm_safety_gateway/config/models.py` — 新增 StreamingConfig (mode/window_size/overlap/send_flag_events/max_response_size/on_max_size/post_audit/recall), OutputDetectionConfig (mode/recall), AuditConfig 扩展 (store_content/file/stdout), FileConfig, LoggingConfig
- [ ] 1.2 修改 `src/z_llm_safety_gateway/config/validators.py` — streaming.mode/on_max_size 校验、output_detection async 缺 webhook_url 校验、向后兼容校验
- [ ] 1.3 编写测试 `tests/unit/config/test_v3_streaming.py` — TC-CONF-001~006（streaming/output_detection 配置）
- [ ] 1.4 编写测试 `tests/unit/config/test_v3_audit.py` — TC-CONF-007~009（audit/logging 配置 + 向后兼容）

## 2. audit-logger（P0）

- [ ] 2.1 创建 `src/z_llm_safety_gateway/audit/models.py` — AuditEntry (Pydantic)，含 direction/detectors/final_action/streaming 字段
- [ ] 2.2 创建 `src/z_llm_safety_gateway/audit/sanitizer.py` — Sanitizer 脱敏 API Key/Authorization 头
- [ ] 2.3 创建 `src/z_llm_safety_gateway/audit/logger.py` — AuditLogger (JSONL 文件 + stdout 双通道, content_hash, store_content)
- [ ] 2.4 创建 `src/z_llm_safety_gateway/audit/__init__.py` — 包初始化 + 导出
- [ ] 2.5 编写测试 `tests/unit/audit/test_models.py` — TC-AUD-001~005（记录字段/hash）
- [ ] 2.6 编写测试 `tests/unit/audit/test_sanitizer.py` — TC-AUD-010~011（脱敏开关）
- [ ] 2.7 编写测试 `tests/unit/audit/test_logger.py` — TC-AUD-006~009, 012~013（存储策略/双通道/异步/开关）

## 3. sse-streaming 核心（P0）

- [ ] 3.1 创建 `src/z_llm_safety_gateway/streaming/sliding_window.py` — SlidingWindow (字符级累积 + 滑窗)
- [ ] 3.2 创建 `src/z_llm_safety_gateway/streaming/sse.py` — SSE 事件构造 (data/event: safety_block/safety_flag/[DONE])
- [ ] 3.3 创建 `src/z_llm_safety_gateway/streaming/memory.py` — 流式内存管理 (max_response_size/on_max_size)
- [ ] 3.4 创建 `src/z_llm_safety_gateway/streaming/handler.py` — StreamingHandler (逐 chunk 检测 + 动作处理)
- [ ] 3.5 创建 `src/z_llm_safety_gateway/streaming/__init__.py` — 包初始化 + 导出
- [ ] 3.6 编写测试 `tests/unit/streaming/test_sliding_window.py` — TC-SSE-003~004（滑窗）
- [ ] 3.7 编写测试 `tests/unit/streaming/test_sse.py` — TC-SSE-012（事件格式）
- [ ] 3.8 编写测试 `tests/unit/streaming/test_memory.py` — TC-SSE-009~010（内存管理）
- [ ] 3.9 编写测试 `tests/unit/streaming/test_handler.py` — TC-SSE-001,002,005~008,011,013（流式处理/动作/短路）

## 4. post-audit-recall（P0）

- [ ] 4.1 创建 `src/z_llm_safety_gateway/post_audit/audit.py` — PostAuditRunner (后台完整响应深度检测)
- [ ] 4.2 创建 `src/z_llm_safety_gateway/post_audit/__init__.py` — 包初始化 + 导出
- [ ] 4.3 创建 `src/z_llm_safety_gateway/recall/webhook.py` — WebhookRecall (POST + 重试/退避)
- [ ] 4.4 创建 `src/z_llm_safety_gateway/recall/__init__.py` — 包初始化 + 导出
- [ ] 4.5 编写测试 `tests/unit/post_audit/test_audit.py` — TC-PAR-001~004（后审计/降级/触发召回）
- [ ] 4.6 编写测试 `tests/unit/recall/test_webhook.py` — TC-PAR-007~008（重试/退避/失败）
- [ ] 4.7 编写测试 `tests/unit/recall/test_sse_recall.py` — TC-PAR-005~006（SSE 召回/断开）

## 5. provider stream_forward（P0）

- [ ] 5.1 修改 `src/z_llm_safety_gateway/providers/base.py` — 新增 stream_forward() 异步生成器
- [ ] 5.2 编写测试 `tests/unit/providers/test_stream_forward.py` — TC-FAST-001（流式转发）

## 6. fastapi-server 集成（P0）

- [ ] 6.1 修改 `src/z_llm_safety_gateway/routes/chat.py` — 增加 stream=true 分支（StreamingResponse + 滑动窗口 + 后审计 + 召回）+ 审计日志集成 + async 输出检测
- [ ] 6.2 修改 `src/z_llm_safety_gateway/app.py` — 初始化 AuditLogger + StreamingHandler
- [ ] 6.3 编写测试 `tests/unit/routes/test_chat_streaming.py` — TC-FAST-002~006, 012~015（流式分支/窗口/后审计/async）
- [ ] 6.4 编写测试 `tests/unit/routes/test_audit_integration.py` — TC-FAST-016~017（审计集成/开关）
- [ ] 6.5 编写测试 `tests/integration/test_streaming_flow.py` — 完整流式请求流
- [ ] 6.6 更新 `config/gateway.yaml` — 添加 streaming/output_detection/audit/logging 示例配置

## 7. 测试与验证

- [ ] 7.1 全量 pytest 通过（v0.1.0 + v0.2.0 回归 + v0.3.0 新测试）
- [ ] 7.2 `ruff check src/ tests/` 无错误
- [ ] 7.3 `mypy src/` 无错误
