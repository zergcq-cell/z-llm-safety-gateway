# Configuration Reference

> 适用版本：v0.1.0
> 配置加载顺序：YAML 文件 → 环境变量覆盖（`ZLG_` 前缀）→ 默认值

## 顶层结构

```yaml
server:          # HTTP 服务
providers:       # 上游 LLM 提供商
routing:         # 模型路由规则
pipeline:        # 安全检测管线
security:        # 认证/限流/TLS/超时
observability:   # 指标/追踪/审计
```

## server

```yaml
server:
  host: 0.0.0.0
  port: 8080
  workers: 1              # uvicorn worker 数
  stop_timeout: 30s       # 优雅停机超时（字符串时长，默认 "30s"）
```

## providers

```yaml
providers:
  - name: openai              # 唯一名称，被 routing 引用
    type: openai              # openai | azure | compatible
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}   # 支持环境变量引用
    timeout_seconds: 60       # 上游超时（可选）
    # Azure 额外配置：
    # api_version: "2024-02-01"
    # deployment_name: "gpt-4"
```

## routing

```yaml
routing:
  rules:
    - pattern: gpt-4*          # 通配符匹配请求的 model
      provider: openai
    - pattern: gpt-3.5*        # 第一条匹配生效（顺序优先）
      provider: openai
  flag_escalation:             # 可选：flag 升级为 block 的策略
    enabled: false
    threshold: 2               # 触发升级的 flag 次数
```

## pipeline

### detectors

```yaml
pipeline:
  detectors:
    input:      # 输入侧检测（请求内容）
      - name: prompt_injection
        enabled: true
        required: false              # true: 初始化失败时拒绝启动；默认 false
        priority: 1                # 数字越小越先聚合（默认 100）
        on_error: fail_open        # fail_open | fail_closed
        timeout: 5s                # 检测超时（可选，默认 security.timeout.detector）
        config:                    # 检测器私有配置
          # prompt_injection: min_confidence / max_confidence / escalation
          # pii_redaction: redaction_mode(mask|replace|hash) / entity_types
          # sensitive_words: block_threshold / flag_threshold (count)
          # secret_leak: block_threshold / flag_threshold (confidence)
          # toxicity: model_name / model_cache_dir / offline_mode / thresholds
    output:     # 输出侧检测（响应内容）
      - name: toxicity
        enabled: true
        config: { model_name: "unitary/toxic-bert", offline_mode: true }
    # gRPC sidecar 检测器：
    # - name: acme_guard
    #   type: grpc
    #   enabled: true
    #   config:
    #     endpoint: "localhost:50051"
    #     api_key: "sk-..."         # 透传（endpoint/tls_* 为网关内部字段，不透传）
```

`required` 与 `on_error` 分工如下：`required: true` 只允许搭配
`on_error: fail_closed`，初始化失败会清理已加载检测器并拒绝启动；optional
`fail_closed` 允许诊断实例启动，但 `/ready` 和业务请求均返回 503；optional
`fail_open` 会跳过故障检测器并以 degraded 状态继续。`required: true` 与
`enabled: false` 的组合也会在配置校验时被拒绝。规则同时适用于 input、output、
built-in、ML、in-process plugin 和 gRPC sidecar。

### 阈值语义（重要）

- **confidence 阈值**（block_threshold/flag_threshold）：0~1 浮点，用于 prompt_injection、secret_leak、toxicity 等
- **count 阈值**（count_block_threshold/count_flag_threshold）：整数，用于 sensitive_words（命中词数）
- 未配置时使用检测器内置默认值

### circuit_breaker（外部检测器推荐）

```yaml
pipeline:
  circuit_breaker:
    - detector_name: acme_guard
      failure_threshold: 5        # 连续失败次数
      reset_timeout_seconds: 30   # 半开重试间隔
      fallback_action: allow      # 熔断后动作（fail_open）
```

### streaming（流式检测）

```yaml
pipeline:
  streaming:
    mode: sliding_window         # sliding_window | buffer
    window_size: 200             # 窗口字符数
    overlap: 50
    send_flag_events: false
    max_response_size: 1MB
    on_max_size: block           # block | truncate
    post_audit: true             # 流结束后全响应深检
    recall:
      method: sse                # sse | webhook | both
      webhook_url: ""            # method 含 webhook 时必填
      webhook_timeout_seconds: 5
```

### output_detection（非流式输出检测）

```yaml
pipeline:
  output_detection:
    mode: sync                   # sync | async
    sync_timeout: 10s            # sync 模式强制超时
```

## security

```yaml
security:
  auth:
    enabled: false
    api_keys:
      - key: "sk-gateway-..."        # 启用后请求需 Authorization: Bearer <key>
        name: "ops"                  # 可选：密钥名称
  rate_limit:
    enabled: false
    limit: 100                    # 请求数
    window_seconds: 60
    key_by: api_key               # api_key | ip
  request_size:
    max_request_size: 1MB         # 请求体上限
  request_id:
    header: X-Request-ID
    generate: true                # 缺失时自动生成
  tls:
    enabled: false                # 原生 TLS 终止
    cert_file: ""
    key_file: ""
  cors:
    enabled: false
    allow_origins: ["*"]
    allow_methods: ["*"]
    allow_headers: ["*"]
  timeout:
    upstream_seconds: 60          # 上游请求超时
    detector_seconds: 5           # 检测器默认超时
    output_seconds: 10
```

## observability

```yaml
observability:
  metrics:
    enabled: true                 # Prometheus /metrics
  tracing:
    enabled: false
    exporter: otlp
    endpoint: ""                  # OTLP 端点
    service_name: z-safety-gateway
    sampling_ratio: 0.1
  audit:
    jsonl_path: "logs/audit.jsonl"   # 审计日志（JSONL，按日轮转）
    redact_keys: ["api_key", "authorization"]
```

## 环境变量覆盖

任何标量配置可用 `ZLG_` 前缀环境变量覆盖（路径用 `__` 分隔）：

```bash
export ZLG_SERVER__PORT=9000
export ZLG_PROVIDERS__0__API_KEY=sk-xxx
```

## 配置校验

配置加载时自动校验；非法配置启动即失败（exit 非 0）并输出明确错误，例如：
- 未知检测器名 → 提示"ensure the package is installed or use type: grpc"
- `type: grpc` 缺 `endpoint` → 阻断启动
- 阈值反转（block < flag）→ 报错
