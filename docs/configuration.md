# Configuration Reference

> 适用版本：Gateway v0.2.2（兼容 v0.1.1 legacy 配置）
> 配置加载顺序：YAML 文件（支持 `${VAR}` 环境变量插值）→ 默认值

## Flow Foundation（v0.2.0）

新 Flow 配置使用严格 schema；未知字段、版本不兼容、引用缺失、循环、资源超限或策略冲突会在启动阶段失败。显式 `flows` 不可与显式 `pipeline.detectors` 同时配置。以下示例由真实 `GatewayConfig` 模型在测试中解析：

<!-- FLOW_CONFIG_EXAMPLE_START -->
```yaml
server:
  host: 127.0.0.1
  port: 8080
providers:
  - name: local
    type: openai_compatible
    base_url: http://localhost:11434/v1
    api_key: ""
routing:
  rules:
    - pattern: "*"
      provider: local
flow_runtime:
  max_depth: 8
  max_nodes: 256
  max_concurrency: 64
  default_timeout: 30
  absolute_timeout: 120
  max_evidence_size: 262144
capabilities:
  - capability_id: detector.prompt_injection
    detector_name: prompt_injection
    config:
      block_threshold: 0.85
      flag_threshold: 0.50
flows:
  - contract_version: "1.0"
    flow_id: input-safety
    version: 1.0.0
    input_schema: safety.text.v1
    output_schema: safety.detector-result.v1
    reducer_capability_id: detector-result-reducer
    nodes:
      - kind: capability
        contract_version: "1.0"
        node_id: prompt-injection
        capability_id: detector.prompt_injection
        input_schema: safety.text.v1
        output_schema: safety.detector-result.v1
        policy:
          timeout:
            seconds: 5
            action: fail_closed
          failure:
            action: fail_closed
          availability:
            required: true
            on_unavailable: fail_closed
            on_circuit_open: fail_closed
          degradation:
            allowed: true
            emit_evidence: true
            emit_metrics: true
          stop:
            signals: [safety.block]
pipeline:
  input_flow:
    flow_id: input-safety
    version: 1.0.0
```
<!-- FLOW_CONFIG_EXAMPLE_END -->

## 顶层结构

```yaml
server:          # HTTP 服务
providers:       # 上游 LLM 提供商
routing:         # 模型路由规则
flow_runtime:    # Flow 执行与证据硬限制（v0.2.0）
capabilities:    # 显式 Flow 的实现绑定/私有配置（v0.2.0，可选）
flows:           # 显式版本化 Flow 定义（v0.2.0，可选）
pipeline:        # 安全检测管线
security:        # 认证/限流/TLS/超时
observability:   # 指标/追踪
audit:           # 审计日志（顶层块）
```

`pipeline.input_flow` / `pipeline.output_flow` 选择精确的 `flow_id + version`。
显式 `flows` 至少需要一个阶段引用；当前版本只装配 `detector.<name>` 能力与
`detector-result-reducer`，未知能力或 reducer 会在启动时明确拒绝。
需要 detector 私有配置时，在独立的 `capabilities` 中绑定实现；Flow Node
继续只负责组合与执行策略。`config` 可承载 ML、entry-point 或 gRPC 参数，
不会进入 Flow/Node 证据：

```yaml
capabilities:
  - capability_id: detector.acme_guard
    detector_name: acme_guard
    type: grpc
    config:
      endpoint: 127.0.0.1:50051
      api_key: ${ACME_GUARD_API_KEY}
```

`flow_runtime.max_evidence_size` 在 v0.2.0 固定为 `262144` 字节；更小的值
无法保证最大合法 Flow 的核心 Node 终态完整可表示，因此会在启动时拒绝。
当最大合法图的可选摘要、signal 与长身份压缩后仍超限时，每个 Node
的完整 stop-signal tuple 会以确定性 SHA-256 指纹表示；Node 终态、status、
reason、策略 action 和 source 均保留，并显式标记证据已压缩。

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
    type: openai              # openai | azure_openai | openai_compatible (also anthropic | gemini)
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}   # 支持环境变量引用
    # Azure 额外配置：
    # api_version: "2024-02-01"
    # deployment_name: "gpt-4"
    # 上游超时统一在 security.timeout.upstream 配置
```

## routing

```yaml
routing:
  rules:
    - pattern: gpt-4*          # 通配符匹配请求的 model
      provider: openai
    - pattern: gpt-3.5*        # 第一条匹配生效（顺序优先）
      provider: openai
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
    #   circuit_breaker:
    #     enabled: true
    #     failure_threshold: 5
    #     recovery_timeout: "30s"
    #     fallback_action: fail_open
  flag_escalation:                    # 可选：按聚合结果将 flag 升级为 block
    enabled: false
    rule: "flag_count >= 2"
    action: block
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
  detectors:
    input:
      - name: acme_guard
        type: grpc
        config:
          endpoint: "acme-guard:50051"
        circuit_breaker:
          enabled: true
          failure_threshold: 5        # 连续失败次数
          recovery_timeout: "30s"     # 半开重试间隔
          fallback_action: fail_open  # 熔断后动作（fail_open）
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
      webhook_auth_header: ""    # 可选：回调认证头
```

### output_detection（非流式输出检测）

```yaml
pipeline:
  output_detection:
    mode: sync                   # sync | async
    sync_timeout: 5s             # sync 模式强制超时（默认 5s）
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
    strategy: token_bucket           # token_bucket（MVP 仅此一种）
    rate: 100                        # 每秒补充令牌数
    burst: 200                       # 桶容量（允许突发）
    per: api_key                     # api_key | ip
    storage: memory                  # memory（MVP）| redis（v0.2.0+ 路线图）
  max_request_size: "10MB"           # 请求体上限（位于 security 顶层）
  request_id:
    header: X-Request-ID
    generate: true                   # 缺失时自动生成
  tls:
    enabled: false                   # 原生 TLS 终止
    cert_file: ""
    key_file: ""
  cors:
    enabled: false
    origins: ["*"]                   # 允许来源列表
  timeout:
    upstream: "120s"                 # 上游请求超时（时长字符串，支持 s/ms）
    detector: "5s"                   # 检测器默认超时
```

## tenant_resources

```yaml
tenant_resources:
  max_concurrency: 16          # 每租户同时执行的请求数，1–4096
  queue_limit: 32              # 等待队列上限，0–4096
  request_timeout_seconds: 120 # 单请求资源 deadline，最多 3600 秒
  max_streams: 16              # 每租户流式连接上限
  max_background_tasks: 32     # 每租户后台任务上限
```

资源限制默认采用进程内有界闸门；达到队列或并发上限时返回稳定的 `tenant_resource_exhausted`，等待超时返回 `tenant_resource_timeout`。未启用租户模式时，旧配置行为保持不变。

## observability

```yaml
observability:
  metrics:
    enabled: true                 # Prometheus /metrics
    endpoint: /metrics            # 指标端点路径
  tenancy:
    # Only configured, non-secret tenant IDs retain metric detail. At most 32.
    # All other authenticated tenants aggregate as tenant_other/other.
    metric_tenant_ids: [acme]
  tracing:
    enabled: false
    exporter: otlp                # otlp | jaeger | zipkin
    endpoint: ""                  # OTLP 端点
    sample_rate: 0.1              # 采样率
```

Tenant observability is disabled unless metrics are enabled. The gateway exports
`safety_tenant_decisions_total` and `safety_tenant_observability_events_total`.
These metrics never contain policy IDs, request IDs, request content, credentials,
or provider models. Audit records keep exact trusted attribution when audit is
enabled; audit sink failures do not change the safety decision.

## audit（审计日志，顶层块）

```yaml
audit:
  enabled: false                  # 总开关
  sanitize_logs: true             # 脱敏 API Key / 认证头
  store_content: false            # 是否存储明文内容
  file:
    enabled: true
    path: "logs/"                 # JSONL 审计目录（默认 /var/log/safety-gateway）
    rotation: daily               # daily | midnight | weekly
    retention_days: 90
  stdout: true                    # 同时输出结构化日志到 stdout
```

## logging

```yaml
logging:
  level: INFO                     # DEBUG | INFO | WARNING | ERROR
  format: json                    # json | text
```

## 环境变量插值

YAML 字符串值可使用 `${VAR}` 引用进程环境变量；未设置的变量会插值为空字符串，
因此密钥应在启动前显式设置，并由 Compose/Kubernetes 的 required 语法阻止缺失值：

```bash
export OPENAI_API_KEY=sk-xxx
# YAML: api_key: "${OPENAI_API_KEY}"
```

## 配置校验

配置加载时自动校验；非法配置启动即失败（exit 非 0）并输出明确错误，例如：
- 未知检测器名 → 提示"ensure the package is installed or use type: grpc"
- `type: grpc` 缺 `endpoint` → 阻断启动
- 阈值反转（block < flag）→ 报错
