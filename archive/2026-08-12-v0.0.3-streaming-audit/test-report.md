# v0.3.0 Streaming & Audit — 测试报告

> 版本：v0.3.0
> 创建日期：2026-08-12
> 对应 Phase 2 Spec：design.md + 5 spec.yaml + test-plan.md

## 一、测试执行结果

### 1.1 总体结果

| 指标 | 数值 |
|------|------|
| **总测试数** | 627 |
| **通过** | 627 |
| **失败** | 0 |
| **跳过** | 0 |
| **通过率** | 100% |
| **代码覆盖率** | 94% |
| **执行时间** | ~2.5s |

### 1.2 测试分类统计

| 类别 | 测试文件数 | 测试用例数 | 状态 |
|------|-----------|-----------|------|
| **v0.3.0 新增** | | | |
| streaming/handler | 1 | 12 | PASS |
| streaming/sliding_window | 1 | 6 | PASS |
| streaming/memory | 1 | 5 | PASS |
| streaming/sse | 1 | 4 | PASS |
| audit/logger | 1 | 6 | PASS |
| audit/models | 1 | 5 | PASS |
| audit/sanitizer | 1 | 4 | PASS |
| post_audit/audit | 1 | 4 | PASS |
| recall/webhook | 1 | 4 | PASS |
| recall/sse_recall | 1 | 2 | PASS |
| config/v3_streaming | 1 | 8 | PASS |
| config/v3_audit | 1 | 7 | PASS |
| providers/stream_forward | 1 | 3 | PASS |
| integration/streaming | 1 | 13 | PASS |
| **v0.3.0 新增小计** | **14** | **83** | PASS |
| **v0.2.0 回归** | | | |
| pipeline (engine/aggregator/threshold/flag_escalation) | 4 | 160 | PASS |
| detectors (all 5 + base/registry/models) | 8 | 182 | PASS |
| circuit_breaker | 1 | 18 | PASS |
| language/detector | 1 | 12 | PASS |
| config (v2 models/validators/loader/models) | 4 | 67 | PASS |
| routes (chat_pipeline/health) | 2 | 12 | PASS |
| middleware (request_id/safety_headers) | 3 | 26 | PASS |
| content (extractor/writeback/models) | 3 | 27 | PASS |
| integration (chat/pipeline_flow/block/health/error/models) | 6 | 19 | PASS |
| providers (openai/router/openai_compatible/azure) | 4 | 18 | PASS |
| test_app | 1 | 3 | PASS |
| **v0.2.0 回归小计** | **36** | **544** | PASS |
| **合计** | **50** | **627** | PASS |

### 1.3 代码覆盖率明细

| 模块 | 语句数 | 未覆盖 | 覆盖率 |
|------|--------|--------|--------|
| streaming/handler.py | 79 | 12 | 85% |
| streaming/sliding_window.py | 27 | 4 | 85% |
| streaming/memory.py | 30 | 2 | 93% |
| streaming/sse.py | 15 | 0 | 100% |
| audit/logger.py | 56 | 2 | 96% |
| audit/models.py | 41 | 0 | 100% |
| audit/sanitizer.py | 19 | 0 | 100% |
| post_audit/audit.py | 31 | 0 | 100% |
| recall/webhook.py | 46 | 6 | 87% |
| config/models.py | 185 | 4 | 98% |
| config/validators.py | 114 | 6 | 95% |
| config/loader.py | 42 | 2 | 95% |
| providers/base.py | 57 | 2 | 96% |
| routes/chat.py | 252 | 26 | 90% |
| pipeline/engine.py | 134 | 3 | 98% |
| app.py | 105 | 1 | 99% |
| **总计** | **2287** | **130** | **94%** |

### 1.4 质量门禁

| 检查项 | 结果 | 阈值 |
|--------|------|------|
| pytest 全量通过 | 627/627 PASS | 100% |
| ruff check | 0 errors | 0 errors |
| mypy | 0 errors | 0 errors |
| 代码覆盖率 | 94% | >=80% |

## 二、TC 覆盖矩阵

### 2.1 SSE 流式代理 (sse-streaming)

| TC ID | 描述 | 状态 |
|-------|------|------|
| TC-SSE-001 | stream=true StreamingResponse 转发 | PASS |
| TC-SSE-002 | 滑动窗口字符累积与窗口切割 | PASS |
| TC-SSE-003 | 窗口检测 block 停止转发 + safety_block | PASS |
| TC-SSE-004 | 窗口检测 flag 继续 + safety_flag | PASS |
| TC-SSE-005 | max_response_size block 策略 | PASS |
| TC-SSE-006 | max_response_size truncate 策略 | PASS |
| TC-SSE-007 | buffer 模式安全内容重放 | PASS |
| TC-SSE-008 | buffer 模式阻断发送 safety_block | PASS |
| TC-SSE-009 | send_flag_events=false 不发 flag 事件 | PASS |
| TC-FAST-002 | 流式响应返回 SSE chunks | PASS |
| TC-FAST-003 | 输入阻断 stream=true 返回 400 | PASS |
| TC-FAST-004 | Provider 错误发送 error event + DONE | PASS |
| TC-FAST-005 | 滑窗 block 停止转发 + safety_block | PASS |
| TC-FAST-006 | 滑窗 flag 继续 + safety_flag | PASS |
| TC-FAST-010 | Buffer 模式安全重放 | PASS |
| TC-FAST-011 | Buffer 模式阻断 | PASS |
| TC-FAST-016b | 流式响应包含 X-Request-ID | PASS |

### 2.2 Post-audit 召回 (post-audit-recall)

| TC ID | 描述 | 状态 |
|-------|------|------|
| TC-PA-001 | Post-audit 全量内容检测 | PASS |
| TC-PA-002 | Post-audit block 触发 SSE recall 事件 | PASS |
| TC-PA-003 | Post-audit block 触发 webhook 召回 | PASS |
| TC-PA-004 | Post-audit allow 不触发召回 | PASS |
| TC-PA-005 | Webhook 重试退避（3次重试） | PASS |
| TC-FAST-012 | Post-audit recall SSE 事件 | PASS |
| TC-FAST-014 | 非流式 async 输出检测立即返回 | PASS |

### 2.3 审计日志 (audit-logger)

| TC ID | 描述 | 状态 |
|-------|------|------|
| TC-AL-001 | AuditEntry 模型字段验证 | PASS |
| TC-AL-002 | JSONL 文件写入 + 日轮转 | PASS |
| TC-AL-003 | stdout 结构化 JSON 输出 | PASS |
| TC-AL-004 | store_content=false 仅存 hash | PASS |
| TC-AL-005 | sanitize_logs=true 脱敏 | PASS |
| TC-AL-006 | 审计禁用时不产生记录 | PASS |
| TC-AL-007 | 内容哈希 SHA-256 计算 | PASS |
| TC-FAST-016 | 流式审计日志写入 | PASS |
| TC-FAST-017 | 审计禁用无记录 | PASS |

### 2.4 配置系统扩展 (config-system)

| TC ID | 描述 | 状态 |
|-------|------|------|
| TC-CFG-001 | streaming 配置节解析 | PASS |
| TC-CFG-002 | audit 配置节解析 | PASS |
| TC-CFG-003 | output_detection 配置节解析 | PASS |
| TC-CFG-004 | 向后兼容（旧配置无需修改） | PASS |
| TC-CFG-005 | 默认值正确 | PASS |

### 2.5 FastAPI 服务器集成 (fastapi-server)

| TC ID | 描述 | 状态 |
|-------|------|------|
| TC-FAST-001 | stream=true 路由分支 | PASS |
| TC-FAST-007 | 非流式 sync 输出检测 | PASS |
| TC-FAST-008 | 非流式 async 输出检测 | PASS |
| TC-FAST-009 | audit 日志集成 | PASS |
| TC-FAST-013 | post-audit 集成 | PASS |
| TC-FAST-015 | webhook recall 集成 | PASS |
| TC-FAST-016b | 非流式 sync 审计日志 | PASS |

## 三、失败模式检查

### 3.1 已验证的失败模式

| 失败模式 | 验证方式 | 结果 |
|----------|---------|------|
| Provider 流式响应中途断开 | ProviderError 捕获 + error 事件 | PASS |
| 窗口检测阻断后继续转发 | blocked 标志阻止后续 chunk | PASS |
| 审计文件目录不存在 | 自动创建，失败则降级 stdout | PASS |
| Webhook 召回失败 | 3次重试 + 指数退避 | PASS |
| max_response_size 超限 | block/truncate 策略 | PASS |
| 配置缺失 streaming 节 | 使用默认值 | PASS |
| 审计禁用 | record() 直接返回 | PASS |
| 空检测器列表 | 透明转发 | PASS |

### 3.2 已知限制

| 限制 | 影响 | 缓解措施 |
|------|------|---------|
| Docker 构建未验证 | Docker 环境未安装 | 需手动 `docker compose up --build` |
| `__main__.py` 覆盖率 0% | CLI 入口未测试 | 低风险，仅启动入口 |
| `routes/models.py` 覆盖率 76% | 模型列表端点 | 低风险，v0.1.0 遗留 |
