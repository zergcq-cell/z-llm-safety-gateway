# v0.3.0 - Streaming & Audit - 技术设计

## Context

v0.2.0 已实现 Pipeline 引擎（并行执行 + 短路 + 结果聚合）、5 个 MVP 检测器、熔断器、语言检测、配置系统重构（input/output 双向分组）、非流式 sync 模式的请求流集成。但存在两个关键缺口：

1. **流式不支持**：当客户端发送 `stream=true` 时，Provider 返回的是 SSE 流式响应。当前 `routes/chat.py` 将 `provider_response.content` 当作普通 HTTP 响应处理，无法对每个 token 做实时检测。
2. **无审计日志**：系统完全没有持久化的安全审计记录，无法满足合规要求。

技术栈：Python 3.10+ / FastAPI / Pydantic v2 / httpx / structlog / pytest + pytest-asyncio / ruff / mypy (strict)

现有代码基础：
- `src/z_llm_safety_gateway/routes/chat.py` — 非流式 sync 模式的完整 pipeline 集成
- `src/z_llm_safety_gateway/providers/base.py` — BaseProvider.forward_request()（仅支持非流式）
- `src/z_llm_safety_gateway/config/models.py` — PipelineConfig（无 streaming 配置）、AuditConfig（仅 enabled/sanitize_logs）
- `src/z_llm_safety_gateway/pipeline/engine.py` — PipelineEngine（并行执行 + 短路）
- `src/z_llm_safety_gateway/language/detector.py` — LanguageDetector

DESIGN.md 参考：Section 3.5 (Non-streaming Output Detection), Section 8 (Streaming & Response Recall), Section 12 (Audit, Logging & Observability), Section 10 (Configuration)

## Decisions

### 1. 流式代理：StreamingResponse + 异步生成器

**方案**：在 `routes/chat.py` 中为 `stream=true` 请求增加独立分支。使用 `httpx.AsyncClient.stream()` 以流式方式接收 Provider 的 SSE 响应，通过 `starlette.responses.StreamingResponse` 将 chunks 转发给客户端。检测逻辑在异步生成器内逐 chunk 处理。

**为什么**：FastAPI/Starlette 原生支持 StreamingResponse，无需额外依赖。httpx 的流式客户端与 asyncio 兼容。逐 chunk 处理允许实时检测。

**备选方案及排除原因**：
- 备选 A：先完整缓冲再返回 — 失去流式的低延迟优势，与 buffer 模式混淆
- 备选 B：WebSocket — DESIGN.md 明确仅支持 SSE
- 备选 C：sse-starlette 库 — 增加依赖，StreamingResponse 已足够

### 2. 滑动窗口：字符级累积 + 步进滑窗

**方案**：实现 `SlidingWindow` 类，维护累积字符缓冲。当缓冲达到 `window_size`（默认 200 字符）时，触发一次窗口检测。检测完成后，窗口向前滑动 `window_size - overlap`（默认 150 字符），保留最后 `overlap`（50 字符）作为与下一窗口的重叠。使用字符级计数（tokenizer-agnostic）。

**为什么**：DESIGN.md Section 8.2 明确要求字符级窗口。重叠确保跨窗口边界的内容（如跨窗口的敏感词）被检测。字符级对中英文都适用。

**备选方案及排除原因**：
- 备选 A：tokenizer 级窗口 — v1.1+ 范围，不同 Provider 用不同 tokenizer
- 备选 B：每次全量重检测 — O(n²) 性能差，浪费

### 3. 流式动作处理：block/flag/modify→flag

**方案**：每个窗口通过输出检测器后，按 DESIGN.md Section 8.2 表格处理：
- `block`：立即停止转发，发送 `safety_block` SSE 事件 + `data: [DONE]`
- `flag`：继续转发；若 `send_flag_events: true`，发送 `safety_flag` SSE 事件（每窗口一条，多检测器聚合为最高 risk_level + 逗号分隔 flagged_by）
- `modify`：降级为 flag（tokens 已转发，无法修改），审计记录 `action: modify, applied: false`
- `allow`：继续转发

**为什么**：DESIGN.md Section 8.2 定义明确。modify 在流式中物理上不可行（token 已发送）。

**备选方案及排除原因**：
- 备选 A：modify 时暂停并回放 — 复杂且用户体验差，不支持
- 备选 B：只支持 block — 缺少 flag 通知能力

### 4. 流式内存管理：max_response_size + on_max_size

**方案**：累积响应时检查 `max_response_size`（默认 1MB）。超限时按 `on_max_size` 策略处理：
- `block`：停止流式，发送 `safety_block`（blocked_by: streaming_limit, category: response_too_long, risk_level: medium, confidence: 1.0）+ `[DONE]`
- `truncate`：停止累积但继续流式；后审计在截断内容上运行，审计记录 `post_audit_truncated: true`

**为什么**：DESIGN.md Section 8.5 要求防止 OOM。字符长度转字节估算（UTF-8 中文 3 字节/字符）。

**备选方案及排除原因**：
- 备选 A：无限制累积 — OOM 风险
- 备选 B：只支持 block — 缺乏灵活性

### 5. 后审计：完整响应深度检测

**方案**：流式完成且 `[DONE]` 发送后，启动后台任务对完整累积响应执行一次深度检测（复用 PipelineEngine，所有启用 output 检测器，方向 output）。`modify` 结果降级为 flag（响应已发送）。若检测到 block，触发召回机制。

**为什么**：DESIGN.md Section 8.3。后台运行不阻塞客户端连接。可捕获滑动窗口漏检的跨窗口风险（如跨 chunk 的密钥泄露）。

**备选方案及排除原因**：
- 备选 A：前台同步后审计 — 增加响应完成延迟
- 备选 B：无后审计 — 漏检跨窗口风险

### 6. 响应召回：SSE + Webhook

**方案**：后审计发现 risk 时发送召回信号：
- **SSE**（默认，`recall.method: sse`）：在同一条 SSE 连接上发送 `safety_recall` 事件（若连接仍活跃）
- **Webhook**（`recall.method: webhook/both`）：POST 到 `webhook_url`，5s 超时，3 次重试（指数退避 1s/2s/4s），HTTP 2xx 为成功，全部失败记录 `recall_delivery: failed`
- 审计记录 `recalled: true` + `recall_method`

**为什么**：DESIGN.md Section 8.4。SSE 实时但客户端断开时丢失；Webhook 独立可靠（有重试）。

**备选方案及排除原因**：
- 备选 A：仅 SSE — 客户端断开后丢失召回
- 备选 B：持久化队列 — v1.1+ 范围，增加基础设施

### 7. buffer 模式：完整缓冲 + 检测 + SSE 回放

**方案**：当 `streaming.mode: buffer` 时，缓冲 Provider 完整响应后执行一次检测，安全则按原始顺序以 SSE chunks 回放给客户端（保持 SSE 协议契约）。block 时不发送内容 chunks，直接 `safety_block` + `[DONE]`。post-audit 自动跳过（完整响应已检测），审计记录 `post_audit.executed: false, reason: buffer_mode`。

**为什么**：DESIGN.md Section 8.2 明确要求 buffer 模式为最大安全性。回放保持 SSE 契约。

**备选方案及排除原因**：
- 备选 A：buffer 后以 JSON 返回 — 破坏 SSE 协议契约（客户端期望 data: 事件）
- 备选 B：无 buffer 模式 — 失去最大安全性选项

### 8. 非流式异步输出检测：async 模式 + Webhook 召回

**方案**：当 `output_detection.mode: async` 且非流式时，立即返回 LLM 响应，后台任务执行输出检测。若发现 risk，通过 Webhook 召回。写入**两条**审计记录：initial（`async_detection: pending`）+ completion（`async_detection: completed`），共享 request_id。

**为什么**：DESIGN.md Section 3.5。async 模式降低响应延迟，适用于低风险场景。双审计记录追踪检测完成状态。

**备选方案及排除原因**：
- 备选 A：async 模式用 SSE 召回 — 非流式无活跃 SSE 连接，仅能 Webhook
- 备选 B：无 async 模式 — 失去性能优化选项

### 9. 审计日志：JSONL + 双通道输出

**方案**：实现 `AuditLogger` 类，每方向（input/output）写入一条 JSONL 记录。支持两个输出通道：
- **JSONL 文件**：使用 `logging.handlers.TimedRotatingFileHandler` 每日轮换，可配置路径和保留天数
- **stdout**：structlog JSON 输出，供外部采集器收集

内容策略：`content_hash`（SHA-256）始终存储，`store_content`（默认 false）控制是否存明文。`sanitize_logs`（默认 true）脱敏 API Key/Authorization 头。

**为什么**：DESIGN.md Section 12。JSONL 每行一条 JSON 记录，便于采集器解析。双通道满足本地留存 + 云端采集。

**备选方案及排除原因**：
- 备选 A：单文件追加 — 无轮换，日志无限增长
- 备选 B：仅 stdout — 本地无留存
- 备选 C：数据库存储 — 过重，JSONL 足够

### 10. 配置系统扩展

**方案**：
- `PipelineConfig` 新增 `streaming: StreamingConfig`（mode/window_size/overlap/send_flag_events/max_response_size/on_max_size/post_audit/recall）
- `PipelineConfig` 新增 `output_detection: OutputDetectionConfig`（mode: sync/async, recall.webhook_url/webhook_auth_header）
- `AuditConfig` 扩展：store_content/file（enabled/path/rotation/retention_days）/stdout
- 新增 `LoggingConfig`（level/format）

所有新字段均有默认值，保持 v0.2.0 向后兼容（旧配置无需修改）。

**为什么**：DESIGN.md Section 10.2。默认值保证向后兼容。

**备选方案及排除原因**：
- 备选 A：破坏性变更 — 破坏 v0.2.0 配置
- 备选 B：扁平字段 — 配置层次混乱

### 11. Provider 流式转发

**方案**：`BaseProvider` 新增 `stream_forward(request, headers)` 异步生成器方法，使用 `httpx.AsyncClient.stream()` 逐 chunk yield Provider 的 SSE 数据。各 Provider 子类无需重复实现（统一走 `_build_url/_build_headers/_build_params`）。

**为什么**：流式转发逻辑统一，子类只需复用现有钩子。httpx stream() 原生支持 asyncio 生成器。

**备选方案及排除原因**：
- 备选 A：各子类单独实现 — 重复代码
- 备选 B：复用 forward_request — 无法流式

### 12. 审计日志异步写入

**方案**：审计日志写入通过 `asyncio.create_task` 异步执行，避免阻塞请求流。写入失败时捕获异常，记录 warning，不阻断请求处理。

**为什么**：DESIGN.md 要求审计不增加请求延迟。异步写入隔离日志故障。

**备选方案及排除原因**：
- 备选 A：同步写入 — 增加每请求延迟
- 备选 B：后台队列（asyncio.Queue）— 复杂，MVP 用 create_task 足够

## Architecture

### 模块结构

```
src/z_llm_safety_gateway/
├── streaming/
│   ├── __init__.py
│   ├── sliding_window.py        # SlidingWindow (字符级滑窗)
│   ├── sse.py                   # SSE 事件构造 + 格式化
│   ├── handler.py               # 流式处理核心（逐 chunk 检测）
│   └── memory.py                # 流式内存管理 (max_response_size/on_max_size)
├── post_audit/
│   ├── __init__.py
│   └── audit.py                 # PostAuditRunner (后台深度检测)
├── recall/
│   ├── __init__.py
│   └── webhook.py               # Webhook recall (重试/退避)
├── audit/
│   ├── __init__.py
│   ├── logger.py                # AuditLogger (JSONL + 双通道)
│   ├── sanitizer.py             # 日志脱敏 (API Key/Authorization)
│   └── models.py                # 审计记录模型 (Pydantic)
├── providers/
│   └── base.py                  # + stream_forward() 异步生成器
├── config/
│   ├── models.py                # + StreamingConfig, OutputDetectionConfig, AuditConfig 扩展, LoggingConfig
│   └── validators.py            # + 新配置校验
├── routes/
│   └── chat.py                  # + stream=true 分支 + 审计集成
└── app.py                       # 初始化 AuditLogger
```

### 流式请求流（stream=true, sliding_window 模式）

```
Client (stream=true)
    │
    ▼
[chat.py: POST /v1/chat/completions]
    │
    ├─ 1. Input Pipeline（同非流式，block 则 400）
    │
    ├─ 2. provider.stream_forward(request)  ← httpx AsyncClient.stream()
    │      逐 chunk 产生 Provider SSE 数据
    │
    ├─ 3. StreamingResponse(generator)
    │      generator 对每个 chunk:
    │      ├─ 提取 token 文本 → SlidingWindow 累积
    │      ├─ 窗口满 → 输出检测器并行检测
    │      │   ├─ block → 发 safety_block + [DONE]，终止
    │      │   ├─ flag → 继续（可选 safety_flag 事件）
    │      │   └─ allow → 继续
    │      ├─ max_response_size 检查 → block/truncate
    │      └─ 转发 chunk 给客户端
    │
    ├─ 4. 流式完成 + [DONE] 发送
    │
    ├─ 5. Post-Audit（后台任务）
    │      ├─ 完整响应深度检测
    │      ├─ risk → Recall (SSE safety_recall / Webhook)
    │      └─ 写入审计 completion 记录
    │
    └─ 6. 写入审计日志（input + output）
```

### 审计日志流程

```
[Input Pipeline 完成]
    │
    ├─ 构造 AuditEntry(direction=input, detectors, final_action, ...)
    ├─ content_hash = sha256(content)
    ├─ store_content=true ? 存明文 : 仅 hash
    ├─ sanitize_logs=true ? 脱敏 : 原样
    └─ async write → JSONL file + stdout
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 滑动窗口检测引入流式延迟 | 窗口检测并行执行 + 短路 + 可配置窗口大小（默认 200 字符） |
| max_response_size 内存累积导致 OOM | max_response_size（默认 1MB）+ on_max_size block/truncate |
| 后审计在客户端断开后无法发送 SSE 召回 | 可选回退到 Webhook 召回（recall.method: webhook/both） |
| 审计日志写入失败影响请求 | 异步写入 + 失败仅 warning 不阻塞 |
| 配置扩展破坏 v0.2.0 向后兼容 | 新字段均有默认值，旧配置无需修改 |
| Webhook 召回丢失（网关重启） | v1.1+ 持久化队列；MVP 记录 recall_delivery: failed |
| 流式 chunk 解析错误（非 SSE 格式） | 捕获异常，记录 warning，降级为透传 |
| 并发流式请求消耗连接 | httpx AsyncClient 复用 + asyncio 原生并发 |
