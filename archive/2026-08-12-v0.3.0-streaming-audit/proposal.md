# v0.3.0 - Streaming & Audit

## Why

v0.2.0 实现了 Pipeline 引擎和 5 个 MVP 检测器，但仅支持非流式 sync 模式。当客户端发送 `stream=true` 请求时，网关将 Provider 的流式响应当作普通 HTTP 响应处理，无法进行实时安全检测。同时，系统完全没有审计日志——检测器执行结果、请求元数据、安全决策均未被持久化记录，无法满足合规审计需求。

需要实现 SSE 流式代理（滑动窗口检测 + 后审计 + 召回机制）和 JSONL 审计日志系统，使网关具备流式场景下的实时安全检测能力和完整的审计追踪能力。这是生产可用的核心前提：流式是 LLM 应用的主流交互模式，审计日志是企业合规的硬性要求。

## What Changes

- **C1**: 新建 SSE 流式代理——透明转发 Provider 流式响应（StreamingResponse），支持 stream=true 请求分支
- **C2**: 新建滑动窗口检测引擎——字符级窗口（可配置 window_size/overlap），每窗口并行执行输出检测器
- **C3**: 新建流式安全动作处理——block（停止 + safety_block SSE + [DONE]）、flag（继续 + 可选 safety_flag）、modify→flag 降级
- **C4**: 新建流式内存管理——max_response_size 限制（默认 1MB），on_max_size block/truncate 策略
- **C5**: 新建后审计检测——流式完成后对完整累积响应执行深度检测（后台运行）
- **C6**: 新建响应召回机制——safety_recall SSE 事件 + 可选 Webhook 回调（3 次重试，指数退避）
- **C7**: 新建 buffer 模式——缓冲完整响应后检测，再以 SSE 回放（最大安全性）
- **C8**: 新建非流式异步输出检测——async 模式立即返回，后台检测，Webhook 召回
- **C9**: 新建审计日志系统——JSONL 格式，每方向各一条记录，包含完整检测器结果
- **C10**: 新建审计内容策略——content_hash (SHA-256) 始终存储，store_content 配置控制明文
- **C11**: 新建日志输出通道——JSONL 文件（每日轮换）+ stdout 结构化 JSON
- **C12**: 新建日志脱敏——redact API Key、Authorization 头等敏感信息
- **C13**: 新建流式审计日志字段——window_count、post_audit、recalled、recall_method
- **C14**: 重构配置系统——PipelineConfig 增加 streaming 配置块和 output_detection async 模式
- **C15**: 重构配置系统——AuditConfig 扩展（store_content/file/stdout），新增 LoggingConfig
- **C16**: 集成流式到请求流——routes/chat.py 增加 stream=true 分支，Provider 增加 stream_forward 方法
- **C17**: 集成审计日志到请求流——input/output pipeline 完成后写入审计日志

## Capabilities

### New Capabilities

- **sse-streaming**: SSE 流式代理 + 滑动窗口检测 + 流式内存管理 + buffer 模式
- **post-audit-recall**: 后审计检测 + 响应召回（SSE safety_recall + Webhook）+ 非流式异步输出检测
- **audit-logger**: JSONL 审计日志（每日轮换）+ stdout 结构化输出 + content_hash + 日志脱敏

### Modified Capabilities

- **config-system**: 新增 streaming 配置块、output_detection async 模式、audit 配置扩展、logging 配置
- **fastapi-server**: 流式端点集成（StreamingResponse + 滑动窗口 + 后审计）、审计日志集成、异步输出检测

## Impact

**代码层面**：
- 新增 ~15 个源文件（streaming/、post_audit/、audit/ 目录）
- 修改 ~8 个现有文件（routes/chat.py、config/models.py、providers/base.py、app.py 等）
- 预估新增 ~2000 行代码

**配置层面**：
- PipelineConfig 新增 streaming 子配置块
- AuditConfig 扩展为含 file/stdout/store_content 的完整结构
- 新增 LoggingConfig（level/format）
- gateway.yaml 示例配置更新

**基础设施**：
- 无新基础设施依赖（使用 Python 标准库 logging.handlers）
- 日志文件路径需可写权限

## Constraints

- 流式仅支持 SSE（Server-Sent Events），不支持 WebSocket
- 滑动窗口使用字符级计数（非 tokenizer 级），tokenizer 支持留待 v1.1+
- Webhook 召回无持久化队列——网关重启时丢失未完成的召回（v1.1+ 计划持久化）
- Prometheus metrics 和 OpenTelemetry tracing 不在 v0.3.0 范围内（v0.4.0）
- 认证/限流/TLS 不在 v0.3.0 范围内（v0.4.0）
- 日志轮换使用 Python 标准库 TimedRotatingFileHandler（非 logrotate）
- buffer 模式下 post-audit 自动跳过（完整响应已检测）

## Stakeholders

- 网关使用者（应用程序开发者）——需要流式 SSE 支持
- 安全合规团队——需要审计日志满足合规要求
- 系统运维工程师——需要日志输出到 stdout 供外部采集器收集

## Risk Areas

- capability: sse-streaming — 滑动窗口检测引入流式延迟，影响首 token 时间（缓解：并行执行 + 短路 + 可配置窗口大小）
- capability: sse-streaming — max_response_size 内存累积导致 OOM（缓解：max_response_size 限制 + on_max_size 策略）
- capability: post-audit-recall — 后审计在客户端断开后无法发送 SSE 召回（缓解：回退到 Webhook 召回）
- capability: audit-logger — 审计日志写入失败影响请求处理（缓解：异步写入，失败时 warning 不阻塞）
- capability: config-system — 配置结构扩展破坏 v0.2.0 向后兼容（缓解：新字段均有默认值）

## NonGoals

- Prometheus metrics 暴露（v0.4.0）
- OpenTelemetry distributed tracing（v0.4.0）
- API Key 认证（v0.4.0）
- 限流（v0.4.0）
- TLS 终止（v0.4.0）
- gRPC sidecar 检测器（v0.5.0）
- Tokenizer 级滑动窗口（v1.1+）
- Webhook 召回持久化队列（v1.1+）
- 热重载配置（不支持，需重启）

## Critical

- [x] 非关键变更（默认）
- [ ] 关键变更 — 涉及安全/金融/核心基础设施，需 L3/L4 锚定

## Risk Assessment

- **safety_critical**：false
- **financial**：false
- **cross_system**：false

## Anchoring

- **level**：L1（行为锚定）
- **reference_changes**：2026-08-11-v0.2.0-pipeline-detectors
- **anchor_implementations**：（无）

## Success Criteria

- [ ] stream=true 请求通过 StreamingResponse 透明转发 Provider SSE chunks
- [ ] 滑动窗口检测在每个窗口（默认 200 字符，50 字符重叠）上并行执行输出检测器
- [ ] 窗口检测 block 时立即停止转发，发送 safety_block SSE 事件 + data: [DONE]
- [ ] 窗口检测 flag 时继续流式，send_flag_events=true 时发送 safety_flag SSE 事件（每窗口一条，多检测器聚合）
- [ ] 窗口检测 modify 降级为 flag（tokens 已转发），审计日志记录 action: modify, applied: false
- [ ] buffer 模式缓冲完整 Provider 响应后执行检测，再以 SSE chunks 回放给客户端
- [ ] max_response_size 超限时触发 block 或 truncate 策略
- [ ] 后审计在流式完成后对完整累积响应执行深度检测（后台运行，不阻塞客户端）
- [ ] 后审计发现 risk 时发送 safety_recall SSE 事件（含 request_id/risk_level/reason/category）
- [ ] 后审计 modify 降级为 flag，审计日志记录 original_action: modify, effective_action: flag
- [ ] 非流式 async 模式立即返回响应，后台执行输出检测，风险发现时通过 Webhook 召回
- [ ] Webhook 召回支持重试（3 次，指数退避 1s/2s/4s，5s 超时，HTTP 2xx 为成功）
- [ ] buffer 模式下 post-audit 自动跳过，审计日志记录 post_audit.executed: false, reason: buffer_mode
- [ ] JSONL 审计日志每个方向（input/output）各写一条记录，通过 request_id 关联
- [ ] 审计日志包含所有检测器结果（name/action/confidence/risk_level/duration_ms/error）
- [ ] 审计日志包含流式特定字段（streaming/window_count/post_audit/recalled/recall_method）
- [ ] content_hash (SHA-256) 始终存储在审计日志中
- [ ] store_content=true 时存储明文内容，store_content=false（默认）仅存储 hash
- [ ] stdout 输出结构化 JSON 供外部采集器收集
- [ ] 日志脱敏 redact API Key、Authorization 头等敏感信息（sanitize_logs=true 时生效）
- [ ] JSONL 文件支持每日轮换，可配置路径和保留天数
- [ ] 全量测试通过（v0.1.0 + v0.2.0 回归 + v0.3.0 新测试），ruff/mypy 无错误
