# v0.4.0 Security & Observability — 前置 Backlog（跨版本修正清单）

> 版本：v0.4.0
> 创建日期：2026-08-12
> 来源：前三个版本（v0.1.0 / v0.2.0 / v0.3.0）功能 Review + 设计调整建议
> 状态：待纳入 v0.4.0 变更（Phase 2 Spec 时拆分切片）

本 backlog 汇总三个版本中经代码 Review 确认的、需要在 v0.4.0 处理的问题。按严重程度排序：**P0（正确性/安全缺陷）→ P1（配置失效/审计失真）→ P2（不一致/增强）**。

---

## P0 — 正确性/安全缺陷（必须修复）

### B-01 阈值命名空间冲突：count 语义 vs confidence 语义
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.2.0（跨 v0.3.0） |
| **影响范围** | `pipeline/engine.py`、`pipeline/threshold.py`、`detectors/sensitive_words.py`、`config/validators.py` |
| **问题** | `block_threshold`/`flag_threshold` 被两种不同层级复用为两种语义：engine 视为 confidence 阈值（float），SensitiveWordsDetector 视为 count 阈值（int）。同一配置被 engine 用 `ThresholdDecisionEngine.decide()` 无条件覆盖 sensitive_words 的 action，导致：count≥3 本应 block 被降为 flag；count 触发 flag 却因 confidence=0.5 < 默认 flag 阈值而被放行。SensitiveWordsDetector 内部 action 逻辑为死代码。 |
| **建议方案** | 按 DESIGN.md 5.3.1 拆分命名空间：count 阈值用 `count_block_threshold`/`count_flag_threshold`，confidence 阈值用 `block_threshold`/`flag_threshold`（或可选 `confidence_*` 覆盖）。SensitiveWordsDetector 只输出 match_count 证据 + 归一化 confidence，由 engine 统一决策 action。 |
| **优先级** | P0 |

### B-02 PII 检测器命名不一致，导致其配置全部丢失
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.2.0 |
| **影响范围** | `detectors/pii.py`（`name="pii_detector"`）、`detectors/__init__.py`（注册名 `pii_redaction`）、`config/validators.py`、`pipeline/engine.py` |
| **问题** | 注册表与校验器用 `pii_redaction`，但 `PIIDetector.name="pii_detector"`。engine 用 `detector.name` 作为 key 查配置，而 `_extract_detector_configs` 用 YAML 配置名（`pii_redaction`）作 key → 查不到，PII 的 `redaction_mode`/`entity_types` 配置恒被忽略，永远用默认值。 |
| **建议方案** | 统一 `PIIDetector.name` 为 `pii_redaction`（与 registry/validator/DESIGN 对齐），并加测试断言 name 与注册名一致。 |
| **优先级** | P0 |

### B-03 流式 SSE 分片解析导致漏检（chunk 边界）
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `streaming/handler.py::_extract_delta_text`、`providers/base.py::stream_forward`、`routes/chat.py` |
| **问题** | `stream_forward` 用 `aiter_text()` 按网络分片 yield，不保证一个 `data:{json}\n\n` SSE 事件完整落在单个 chunk 内。`_extract_delta_text` 要求 `chunk.startswith("data:")` 且一次解析一个事件，事件被拆分时该窗口内容被判定为空，安全检测漏检（chunk 仍透传）。 |
| **建议方案** | 引入按 `\n\n` 边界的 SSE 行缓冲/重组，跨 chunk 拼接不完整事件后再解析。 |
| **优先级** | P0 |

---

## P1 — 配置失效 / 审计失真（重要，建议 v0.4.0 修复）

### B-04 per-detector `timeout`/`circuit_breaker` 未传递，配置实际不生效
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.2.0（跨 v0.3.0） |
| **影响范围** | `config/models.py`（`DetectorConfig.timeout`）、`pipeline/engine.py`（读 `timeout_seconds`/`circuit_breaker`）、`app.py::_extract_detector_configs` |
| **问题** | `_extract_detector_configs` 只转发 `**det.config + priority + on_error`，丢弃 `det.timeout` 与 `det.circuit_breaker`；且模型字段名 `timeout` 与 engine 读取的 `timeout_seconds` 不一致。结果单检测器超时与熔断在运行时恒不生效（dead config），安全相关。 |
| **建议方案** | 在 `_extract_detector_configs` 中显式注入 `timeout_seconds`（解析 `det.timeout` 或回退全局 `security.timeout.detector`）与 `CircuitBreaker` 实例（新增 `CircuitBreakerConfig→CircuitBreaker` 工厂，解析 `recovery_timeout` 字符串）。统一字段命名。 |
| **优先级** | P1 |

### B-05 流式输出审计条目 `final_action` 错取输入侧结果
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `routes/chat.py::_build_streaming_response` |
| **问题** | 流式输出审计的 `final_action`/`final_risk_level` 取 `request.state.safety_action`（输入侧赋值），而非输出侧滑动窗口/后置审计实际结果。流中被 `safety_block` 阻断时审计仍记录 allow，阻断事件丢失。 |
| **建议方案** | 为输出侧单独维护 `output_action`/`output_risk_level`，审计条目使用输出侧结果；流中被阻断时记录 block 及对应 detector/category。 |
| **优先级** | P1 |

### B-06 流式审计条目未写入后置审计的 `detectors` 结果与 `window_count`
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `routes/chat.py`、`streaming/handler.py`（`window_count` 恒为占位 0） |
| **问题** | DESIGN 12.1 要求流式输出条目的 `detectors` 数组含后置审计完整结果。当前 sliding_window 路径审计条目未传 `detector_results`，`detectors` 恒空；`window_count` 恒为 0，从未统计。 |
| **建议方案** | 将 `PostAuditRunner.run()` 返回的 `detector_results` 传入审计条目，并在 `process_chunk` 循环中累加窗口计数后填充 `window_count`。 |
| **优先级** | P1 |

### B-07 后置审计未传播 `request_id` / 语言上下文
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `post_audit/audit.py::PostAuditRunner.run`、`streaming/handler.py::_make_context` |
| **问题** | `PostAuditRunner.run()` 硬编码 `request_id=""`，未透传当前请求 request_id；handler 上下文不含 `language`。DESIGN 6.6 要求流式输出复用输入侧语言用于滑动窗口与后置审计，实现完全未复用。 |
| **建议方案** | 让 `PostAuditRunner.run()` 与 handler 接收并透传 `request_id` 与输入侧 `language`。 |
| **优先级** | P1 |

### B-08 非流式同步输出检测 `sync_timeout` 未强制
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.2.0 / v0.3.0 |
| **影响范围** | `routes/chat.py` 同步输出检测路径、`pipeline/engine.py` |
| **问题** | DESIGN 3.5 定义 `sync_timeout` 为 pipeline 级超时，当前 `chat.py` 直接 `await engine.run(...)`，无 `asyncio.wait_for` 包裹，超时未生效；全局 `security.timeout.detector`（默认 5s）缺失，engine 无默认超时（None=不限时）。 |
| **建议方案** | 同步输出检测调用加 `asyncio.wait_for`，超时后对未完成检测器按 `on_error` 处理；补全局 `security.timeout.detector` 默认 5s。 |
| **优先级** | P1 |

### B-09 审计字段与 DESIGN 12.1 不一致（duration/user_id/post_audit/applied）
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `audit/models.py`、`routes/chat.py::_build_audit_entry` |
| **问题** | `total_duration_ms` 全项目无赋值点（恒 0）；`user_id` 从未从请求提取；`DetectorAuditRecord` 未填 `duration_ms`/`error`；`post_audit` 字典键名与 DESIGN 不一致（`effective_action` vs `result`，缺 `category`）；流式 modify 降级未记录 `applied:false`（模型无此字段）。 |
| **建议方案** | 补齐各字段赋值；统一 `post_audit` schema 与 DESIGN 一致；为 `DetectorAuditRecord` 增加可选 `applied` 字段。 |
| **优先级** | P1 |

---

## P2 — 配置/文档不一致与增强（v0.4.0 顺带处理）

### B-10 SecurityConfig 严重缺失，需按 DESIGN 10.2 重建
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.1.0 |
| **影响范围** | `config/models.py::SecurityConfig` |
| **问题** | 当前仅 `timeout: dict[str,int]`，DESIGN 10.2 的 `auth`/`tls`/`rate_limit`/`max_request_size`/`cors`/`request_id` 全部缺失。v0.4.0 需重建整个 security 配置树（类型化子模型）。 |
| **建议方案** | 拆分为 `AuthConfig`/`TLSConfig`/`RateLimitConfig`/`CORSConfig`/`RequestIDConfig`，纳入 `SecurityConfig`。 |
| **优先级** | P2（v0.4.0 核心范围） |

### B-11 timeout / observability / server 配置与 DESIGN 不一致
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.1.0 |
| **影响范围** | `config/models.py`（`SecurityConfig.timeout`、`ObservabilityConfig`、`ServerConfig`）、`config/gateway.yaml` |
| **问题** | `timeout` 用 int 秒而 DESIGN 用 `"120s"` 字符串且缺 `detector`；`ObservabilityConfig` 扁平布尔而 DESIGN 为嵌套 `metrics`/`tracing`（缺 endpoint/exporter/sample_rate）；`ServerConfig` 缺 `workers`/`stop_timeout`。 |
| **建议方案** | 引入类型化 `TimeoutConfig`、`MetricsConfig`/`TracingConfig`、补 `ServerConfig.workers`/`stop_timeout`，与 DESIGN 对齐并更新 `gateway.yaml`。 |
| **优先级** | P2（v0.4.0 核心范围） |

### B-12 request_id 配置未接线 + CORS 未实现
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.1.0 |
| **影响范围** | `middleware/request_id.py`、`create_app` |
| **问题** | request_id 中间件硬编码读取 `x-request-id`，不读取 `security.request_id.header/generate` 配置；CORS 完全未实现（无 CORSMiddleware、config 无 `cors` 字段）。 |
| **建议方案** | 让中间件从 `app.state.config.security.request_id` 读取；按 `security.cors` 接入 CORSMiddleware。 |
| **优先级** | P2（v0.4.0 核心范围） |

### B-13 `/ready` 未反映检测器健康；`/health` 响应体与 DESIGN 不一致
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.1.0 |
| **影响范围** | `routes/health.py` |
| **问题** | `/ready` 仅用模块级 `_ready` 布尔（静态 true），未聚合检测器 `health_check()`；DESIGN 13.3 要求 loaded/healthy/unhealthy 且在 fail_closed 检测器不健康时返回 503。`/health` 返回 `healthy` 而 DESIGN 为 `ok`。 |
| **建议方案** | `/ready` 改为聚合检测器健康状态按 `on_error` 判定 200/503；统一 `/health` 响应体；就绪状态改 `app.state` 而非模块级全局。 |
| **优先级** | P2 |

### B-14 `/metrics` 仍为占位，需落地 DESIGN 12.5 指标
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.1.0 |
| **影响范围** | `routes/health.py`、`ObservabilityConfig` |
| **问题** | `/metrics` 只返回占位文本，`metrics_enabled` 未接入任何实现。 |
| **建议方案** | v0.4.0 落地 Prometheus 指标（gateway/detector/provider/recall），`/metrics` 由 `metrics_enabled` 开关控制。 |
| **优先级** | P2（v0.4.0 核心范围） |

### B-15 流式 `on_max_size: truncate` 逻辑缺陷 + `post_audit_truncated` 未实现
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `streaming/handler.py::process_chunk` |
| **问题** | truncate 分支置空 `_accumulated`，但下个 chunk 又追加，实际未"停止累积"；后置审计检测到的是"最后一次超限后的残留段"，截断语义失真。`post_audit_truncated` 字段无赋值点。 |
| **建议方案** | truncate 时设持久 `_truncated` 标志，达上限后停止追加，审计写入 `post_audit_truncated=True`。 |
| **优先级** | P2 |

### B-16 `safety_recall` 在 `[DONE]` 之后发送的协议问题
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `routes/chat.py`（sliding_window）、`streaming/sse.py` |
| **问题** | 先 `yield [DONE]` 再执行 post-audit 并发送 `safety_recall`，多数客户端收到 `[DONE]` 即关闭连接，recall 实际收不到。 |
| **建议方案** | 明确 recall 时序（`[DONE]` 前发送，或文档声明可能晚于 `[DONE]` 并依赖 webhook 可靠投递），在测试中固化。 |
| **优先级** | P2 |

### B-17 streaming/recall 配置结构与 DESIGN 8.4 不一致
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `config/models.py::StreamingConfig`、`DESIGN.md 8.4` |
| **问题** | DESIGN 8.4 将 `recall` 嵌套在 `post_audit` 下，实现为 `post_audit: bool` 与 `recall` 平级。文档自相矛盾，实现取平级。 |
| **建议方案** | 统一 DESIGN 与实现（推荐平级结构），保持文档、校验、运行时一致。 |
| **优先级** | P2 |

### B-18 `_extract_delta_text` 解析能力过窄（多 choice/reasoning/tool delta）
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.3.0 |
| **影响范围** | `streaming/handler.py::_extract_delta_text` |
| **问题** | 仅解析 `choices[0].delta.content`，不处理多 choice（n>1）、tool/function call delta、`reasoning_content`。 |
| **建议方案** | 遍历 `choices` 合并 `delta.content`（可选 `reasoning_content`），对非 content 事件保持透传。 |
| **优先级** | P2 |

### B-19 Toxicity 冗余阈值读取 + engine 默认阈值不一致
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.2.0 |
| **影响范围** | `detectors/toxicity.py` |
| **问题** | ToxicityDetector 读取 `block_threshold`/`flag_threshold` 但从不用于决策（仅日志）；engine 默认 confidence 阈值 1.0/1.0，toxicity 类内默认 0.90/0.60，YAML 未显式配置时 toxicity 几乎永不 block。 |
| **建议方案** | 随 B-01 一起重命名；删除 toxicity 内无用阈值存储；对齐 engine 默认阈值与各 detector 语义默认值。 |
| **优先级** | P2 |

### B-20 `_validate_thresholds` 未区分阈值语义
| 字段 | 内容 |
|------|------|
| **涉及版本** | v0.2.0 |
| **影响范围** | `config/validators.py::_validate_thresholds` |
| **问题** | 对所有 detector 统一校验 `block > flag`，未感知 count 语义（sensitive_words 用 3/1），无法在配置层发现语义错配。 |
| **建议方案** | 阈值校验随命名空间拆分而区分：count 阈值与 confidence 阈值分别校验。 |
| **优先级** | P2 |

---

## 与 v0.4.0 新能力的归属

以下 backlog 项直接属于 v0.4.0 "Security & Observability" 的新增范围（非缺陷，是新功能配置模型）：
- B-10 SecurityConfig 重建（auth/tls/rate_limit/cors/request_id）
- B-11 timeout/observability/server 配置对齐（含 graceful shutdown）
- B-12 request_id 接线 + CORS
- B-14 Prometheus 指标 + OpenTelemetry

其余 P0/P1 项（B-01~B-09）与 P2 项（B-13、B-15~B-20）为对前三个版本已有功能的修正，纳入 v0.4.0 时建议作为独立切片，与新安全能力解耦，避免互相阻塞。

## 处理建议

1. 在 Phase 2 Spec 时将上述 backlog 项拆分为切片，P0 项（B-01/B-02/B-03）优先。
2. B-01 的命名空间分离已同步落实到 `DESIGN.md` 5.3.1。
3. 每个修正项遵循严格 TDD（RED→GREEN→REFACTOR），并有对应回归测试。
