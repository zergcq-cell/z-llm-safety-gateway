# API Specification

> 适用版本：v0.1.0
> 基础路径：所有端点位于网关监听地址（默认 `http://localhost:8080`）

## 认证

`security.auth.enabled: true` 时，请求需携带：

```
Authorization: Bearer <api_key>
```

缺失/无效 → `401 {"detail": "Invalid or missing API key"}`。

## 端点总览

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/v1/chat/completions` | 聊天补全（经安全检测转发） | 可选 |
| GET | `/v1/models` | 可用模型列表 | 可选 |
| GET | `/health` | 存活探针（进程活着即 200） | 否 |
| GET | `/ready` | 就绪探针（200 就绪 / 503 未就绪） | 否 |
| GET | `/metrics` | Prometheus 指标（未启用时 404） | 否 |

## POST /v1/chat/completions

### 请求体

OpenAI 兼容格式：

```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "stream": false
}
```

- `stream: true` → SSE 流式响应（见下）
- 额外支持 `metadata` 对象（透传到检测上下文，可选）

### 成功响应（非流式）

OpenAI 兼容：

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1720000000,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "Hello! How can I help?"},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}
}
```

响应头包含 `X-Request-ID`（`security.request_id.header` 配置，默认 `X-Request-ID`）。

### 安全阻断响应

检测触发 `block` 时，网关返回错误响应（输入阻断 → `400 safety_input_blocked`；输出阻断 → `422 safety_output_blocked`），响应体为 OpenAI 兼容错误 + `safety` 扩展字段：

```json
{
  "error": {
    "message": "Content blocked by safety policy",
    "type": "content_blocked",
    "code": "safety_block"
  },
  "safety": {
    "request_id": "req-...",
    "final_action": "block",
    "detectors": [
      {"detector": "prompt_injection", "action": "block",
       "risk_level": "high", "confidence": 0.97, "message": "..."}
    ]
  }
}
```

### 流式响应（SSE）

`stream: true` 时返回 `text/event-stream`：

```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"},"index":0}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{},"index":0,"finish_reason":"stop"}]}

data: [DONE]
```

检测事件（`send_flag_events: true` 时）以 `event: safety` 发送：

```
event: safety
data: {"type":"flag","detector":"sensitive_words","risk_level":"medium"}
```

流式阻断：以 `event: safety` 事件发送阻断详情后结束流（`data: [DONE]`）；输入侧流式请求阻断同非流式（400 `safety_input_blocked`）。

### 错误码

| HTTP | 场景 |
|------|------|
| 400 | 请求体非法（缺 messages/model） |
| 400 | 输入内容被安全策略阻断（`safety_input_blocked`） |
| 401 | 认证失败（auth 启用时） |
| 404 | 无匹配 routing 规则（`model_not_found`） |
| 413 | 请求体超过 `max_request_size` |
| 422 | 输出内容被安全策略阻断（`safety_output_blocked`） |
| 429 | 限流触发（`Retry-After` 头） |
| 502 | 上游 provider 错误（含 `provider_error` 字段） |
| 504 | 上游超时 |

错误响应体（OpenAI 兼容）：

```json
{"error": {"message": "...", "type": "invalid_request_error", "code": "..."}}
```

## GET /v1/models

代理到上游 provider 的模型列表（按 routing 规则选择 provider）：

```json
{"object": "list", "data": [{"id": "gpt-4", "object": "model", "owned_by": "openai"}]}
```

上游不可达时返回 `502 {"error": {"message": "Network error connecting to provider ...", "type": "provider_error"}}`。

## GET /health

```json
{"status": "healthy"}
```

始终 200（进程存活）。不检查外部依赖。

## GET /ready

```json
{"status": "ready"}
```

- 就绪 → 200
- 未就绪（初始化中/失败）→ 503 `{"status": "not_ready"}`

## GET /metrics

启用 `observability.metrics.enabled` 时返回 Prometheus 文本格式；未启用 → 404。

主要指标：`zlg_http_requests_total`、`zlg_detector_*`、`zlg_provider_*`、`zlg_recall_*` 等。

## 限流

`security.rate_limit.enabled` 时，超限请求返回：

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

```json
{"error": {"message": "Rate limit exceeded", "type": "rate_limit", "code": "rate_limited"}}
```
