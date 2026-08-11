# v0.1.0 - Framework Skeleton - 技术设计

## Context

z LLM Safety Gateway 是全新项目，当前无任何源码。Phase 1 需要搭建基础框架骨架，实现 OpenAI 兼容的透明代理。

**技术栈**：Python 3.12+ / FastAPI / Pydantic v2 / httpx / structlog
**约束**：遵循 `.stdd/standards/python.md`（ruff 行宽 100、完整类型注解），pytest + pytest-asyncio 测试框架，mypy 类型检查。
**设计文档**：DESIGN.md 是项目级 master spec，本设计从中提取 Phase 1 相关需求（Section 3/4/9/10/11）。

Phase 1 不包含：检测器 Pipeline（Phase 2）、SSE 流式代理（Phase 3）、认证/限流/TLS（Phase 4）、审计日志（Phase 3）。`/v1/chat/completions` 直接转发请求到 provider，所有响应附带 `X-Safety-Action: allow`。

## Decisions

### 1. 项目结构：src layout

**方案**：使用 `src/` layout，包名为 `z_llm_safety_gateway`。

```
src/
  z_llm_safety_gateway/
    __init__.py
    app.py              # FastAPI app factory
    config/
      __init__.py
      loader.py         # YAML loading + env var interpolation
      models.py         # Pydantic v2 config models
      validators.py     # Cross-field validation rules
    providers/
      __init__.py
      base.py           # Abstract provider interface
      openai.py         # OpenAI provider adapter
      openai_compatible.py  # OpenAI-compatible provider adapter
      azure_openai.py   # Azure OpenAI provider adapter
      router.py         # Model routing (glob pattern matching)
    middleware/
      __init__.py
      request_id.py     # Request ID middleware
      safety_headers.py # X-Safety-Action header injection
    content/
      __init__.py
      extractor.py      # Content extraction from messages
      writeback.py      # Modify writeback to request
    routes/
      __init__.py
      chat.py           # /v1/chat/completions
      models.py         # /v1/models
      health.py         # /health, /ready, /metrics
    models.py           # Shared Pydantic models (ExtractedContent, Modification, etc.)
tests/
  conftest.py
  unit/
    config/
    providers/
    middleware/
    content/
    routes/
  integration/
    test_proxy_flow.py
    test_health.py
```

**为什么**：src layout 防止意外导入未安装的包，是 Python 打包最佳实践。模块化分包使后续 Phase 添加 Pipeline、Streaming 等组件时不破坏现有结构。

**备选方案及排除原因**：
- Flat layout（源码在项目根目录）：不利于大型项目扩展，容易导致导入混乱。
- 单文件应用：无法支撑后续 5 个开发阶段的复杂度。

### 2. FastAPI App Factory 模式

**方案**：使用 app factory 函数 `create_app(config_path: str) -> FastAPI`，在函数内完成配置加载、中间件注册、路由注册。

**为什么**：factory 模式支持测试时传入不同配置，也支持后续 uvicorn 多 worker 部署。配置在 app 启动时加载一次，避免每请求重复加载。

**备选方案及排除原因**：
- 模块级全局 app 实例：无法在测试中替换配置，且全局状态难以管理。
- 基于 settings 的依赖注入：过度设计，Phase 1 配置需求简单。

### 3. 配置系统：Pydantic v2 + YAML + 环境变量插值

**方案**：

1. 使用 `yaml.safe_load()` 加载 YAML 文件
2. 递归遍历 YAML 树，将 `${VAR_NAME}` 模式替换为 `os.environ.get("VAR_NAME", "")`
3. 使用 Pydantic v2 BaseModel 定义配置 schema（`ServerConfig`, `ProviderConfig`, `RoutingConfig`, `PipelineConfig`, `DetectorConfig`, `SecurityConfig`, `AuditConfig`, `ObservabilityConfig`, `GatewayConfig`）
4. 在 Pydantic model 中使用 `@model_validator(mode="after")` 实现跨字段验证（如 `block_threshold > flag_threshold`）
5. 启动时执行额外验证规则（routing 冲突检测、文件引用检查），验证失败抛出 `ConfigValidationError` 阻止启动

**为什么**：Pydantic v2 提供类型安全、自动验证和清晰的错误消息。环境变量插值在 YAML 解析后、Pydantic 验证前执行，确保 secrets 不硬编码在配置文件中。

**备选方案及排除原因**：
- pydantic-settings BaseSettings（从环境变量直接加载）：不支持 YAML 格式，且 DESIGN.md 明确要求 YAML 配置。
- dynaconf：引入额外依赖，且 DESIGN.md 指定 Pydantic v2 验证。

### 4. Provider 代理：httpx AsyncClient + glob 路由

**方案**：

1. 定义 `BaseProvider` 抽象基类，包含 `forward_request(request: dict, headers: dict) -> httpx.Response` 方法
2. 实现 `OpenAIProvider`、`OpenAICompatibleProvider`、`AzureOpenAIProvider` 三个具体类
3. `ModelRouter` 在启动时编译 routing 规则（glob pattern），运行时按 `model` 字段匹配，first match wins
4. 使用 `httpx.AsyncClient` 转发请求，支持超时配置（`security.timeout.upstream`）
5. Provider 错误统一包装为 OpenAI 兼容错误格式（HTTP 502 `provider_error`）
6. `/v1/models` 透传第一个配置 provider 的响应

**为什么**：httpx 是 FastAPI 生态推荐的异步 HTTP 客户端，支持 HTTP/2 和连接池。glob 模式匹配是 DESIGN.md Section 9.3 指定的路由方式。抽象基类为后续 Phase 添加 failover 提供扩展点。

**备选方案及排除原因**：
- aiohttp：与 httpx 相比 API 不如 httpx 直观，且 httpx 与 FastAPI/Pydantic 生态更紧密。
- requests（同步）：不支持 async，会阻塞事件循环。

### 5. 内容提取器：独立模块 + ExtractedContent 模型

**方案**：

1. 定义 `ExtractedContent` Pydantic model：`message_index: int`, `role: str`, `text: str`
2. 定义 `Modification` Pydantic model：`detector_name: str`, `modified_content: str`, `priority: int`, `message_index: int`
3. `extract_content(messages: list[dict]) -> list[ExtractedContent]`：遍历 messages，提取 role 为 user/system/developer 的文本
4. 支持字符串内容（直接提取）和多模态内容（提取 text parts，跳过 image_url）
5. `apply_modifications(request: dict, modifications: list[Modification]) -> dict`：按 priority 排序后写回，多模态时保留 image parts
6. Phase 1 中内容提取器作为独立模块实现和测试，不接入请求处理流程（Phase 2 接入 Pipeline）

**为什么**：DESIGN.md Section 3.4 提供了完整的提取逻辑伪代码，直接实现。独立模块便于 Phase 2 集成时无需重构。

**备选方案及排除原因**：
- 内联在请求处理中：不利于测试和复用。
- 使用 OpenAI SDK 解析：引入额外依赖，且提取逻辑简单无需完整 SDK。

### 6. Request ID 中间件：ASGI 中间件

**方案**：

1. 实现 `RequestIDMiddleware`（继承 `starlette.middleware.base.BaseHTTPMiddleware`）
2. 请求进入时检查 `X-Request-ID` 头：
   - 存在且合法（`^[a-zA-Z0-9_-]{1,128}$`）：使用客户端值
   - 不存在或不合法：生成 UUID v4
3. 将 request_id 存储在 `request.state.request_id` 供后续使用
4. 响应时注入 `X-Request-ID` 和 `X-Safety-Action: allow` 头
5. 中间件注册顺序：RequestID -> SafetyHeaders -> 路由处理

**为什么**：DESIGN.md Section 11.7 明确要求 UUID v4 生成、客户端 ID 消毒（防止 log injection 和 header injection）。ASGI 中间件是 FastAPI 标准扩展点。

**备选方案及排除原因**：
- FastAPI 依赖注入（`Depends`）：无法在所有路由中统一注入，且中间件更适合横切关注点。
- uvicorn 层面中间件：不够灵活，无法访问 FastAPI 配置。

### 7. 健康检查端点

**方案**：

1. `/health`（GET）：liveness probe，返回 `{"status": "healthy"}`，HTTP 200。不检查任何依赖。
2. `/ready`（GET）：readiness probe，返回 `{"status": "ready"}`，HTTP 200。检查配置已加载、provider 客户端已初始化。未就绪时返回 HTTP 503。
3. `/metrics`（GET）：Phase 1 占位端点，返回 HTTP 200 和空 Prometheus 格式文本（`# z LLM Safety Gateway metrics placeholder\n`）。Phase 4 实现完整指标。

**为什么**：DESIGN.md Section 4.1 定义了这三个端点。liveness/readiness 分离是 K8s 标准实践。

**备选方案及排除原因**：
- 合并为单一 `/health` 端点：不符合 DESIGN.md 规范，也不利于 K8s 部署。
- Phase 1 实现完整 Prometheus 指标：超出 Phase 1 范围（NonGoal）。

### 8. Docker 设置

**方案**：

1. `Dockerfile`：基于 `python:3.12-slim`，多阶段构建（builder + runtime），使用 `uv` 或 `pip` 安装依赖
2. `docker-compose.yml`：单服务配置，映射端口 8080，挂载 `config/gateway.yaml`，设置环境变量
3. `.dockerignore`：排除 `.stdd/`, `tests/`, `.git/`, `__pycache__/`

**为什么**：slim 镜像减小体积，多阶段构建分离构建依赖和运行时。docker-compose 便于本地开发。

**备选方案及排除原因**：
- `python:3.12` 完整镜像：体积过大（~1GB vs ~150MB）。
- 不提供 Docker：DESIGN.md Phase 1 明确要求 Docker setup。

### 9. 错误处理：OpenAI 兼容错误格式

**方案**：

1. 定义 `OpenAIError` Pydantic model，包含 `message`, `type`, `param`, `code`, 可选 `safety` 和 `details` 字段
2. 实现全局异常处理器（`@app.exception_handler`）：
   - `ProviderError` -> HTTP 502 `provider_error`
   - `ConfigError` -> HTTP 500 `internal_error`
   - 通用 `Exception` -> HTTP 500 `internal_error`
3. 所有错误响应包含 `X-Request-ID` 和 `X-Safety-Action` 头（通过中间件）

**为什么**：DESIGN.md Section 4.4 和 9.7 定义了完整的错误码和格式。OpenAI 兼容格式确保标准 OpenAI SDK 客户端能正确解析错误。

**备选方案及排除原因**：
- FastAPI 默认错误格式：不符合 OpenAI API 规范。
- 手动在每个路由中处理错误：代码重复，容易遗漏。

## Architecture

### 请求处理流程（Phase 1 - 无安全检测）

```
Client Request
    │
    ▼
[RequestIDMiddleware]
    │  生成/传播 X-Request-ID
    │  存入 request.state.request_id
    ▼
[SafetyHeadersMiddleware]
    │  注入 X-Safety-Action: allow 到响应
    ▼
[/v1/chat/completions 路由]
    │  解析请求 body
    │  提取 model 字段
    ▼
[ModelRouter]
    │  glob 匹配 model -> provider
    │  无匹配 -> 404 model_not_found
    ▼
[Provider.forward_request()]
    │  httpx.AsyncClient 转发请求
    │  超时/错误 -> ProviderError
    ▼
[Provider Response]
    │
    ▼
[Client Response]
    │  + X-Request-ID 头
    │  + X-Safety-Action: allow 头
```

### 组件依赖关系

```
app.py
  ├── config/loader.py (加载 YAML + env var)
  ├── config/models.py (Pydantic schema)
  ├── config/validators.py (校验规则)
  ├── middleware/request_id.py
  ├── middleware/safety_headers.py
  ├── routes/chat.py
  │     └── providers/router.py
  │           └── providers/openai.py / openai_compatible.py / azure_openai.py
  ├── routes/models.py
  │     └── providers/router.py
  ├── routes/health.py
  └── content/extractor.py (独立模块，Phase 1 不接入路由)
      └── content/writeback.py
```

### 配置加载流程

```
gateway.yaml
    │
    ▼
yaml.safe_load()
    │
    ▼
env_var_interpolation()  # ${VAR_NAME} -> os.environ
    │
    ▼
GatewayConfig(**parsed)  # Pydantic v2 验证
    │
    ▼
validate_config()  # 额外校验规则
    │  - routing 冲突检测
    │  - 文件引用检查
    │  - threshold 逻辑检查
    ▼
Config loaded ✓  (失败 -> ConfigValidationError, 阻止启动)
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| Provider 代理转发不正确破坏 OpenAI 兼容性 | 使用 mock provider 进行端到端测试；验证请求头、请求体、响应体完整透传 |
| 环境变量插值遗漏导致 secrets 泄露到日志 | 插值仅替换 `${VAR}` 模式；structlog 配置 redact filter；`audit.sanitize_logs: true` |
| glob 路由匹配结果与预期不符 | 编写覆盖各种 pattern 的单元测试（`gpt-4*`, `gpt-3.5*`, `llama*` 等）；启动时检测重叠规则并告警 |
| 内容提取器与 Phase 2 Pipeline 集成时需重构 | 提取器接口设计为纯函数（输入 messages，输出 ExtractedContent），无副作用，便于集成 |
| Docker 镜像构建失败或运行时依赖缺失 | CI 中验证 Docker build；`.dockerignore` 排除非必要文件；multi-stage build 减少层级 |
| Phase 1 无认证，provider API key 可能泄露 | Phase 1 仅用于开发/测试环境；配置文件中 API key 通过环境变量注入，不硬编码；生产部署在 Phase 4 添加认证 |
