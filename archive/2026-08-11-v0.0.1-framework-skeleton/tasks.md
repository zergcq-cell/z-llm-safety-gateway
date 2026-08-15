# v0.1.0 任务清单

## 1. config-system（P0）

- [x] 1.1 创建 `src/z_llm_safety_gateway/config/models.py` - Pydantic v2 配置模型（ServerConfig, ProviderConfig, RoutingConfig, PipelineConfig, DetectorConfig, SecurityConfig, AuditConfig, ObservabilityConfig, GatewayConfig）
- [x] 1.2 创建 `src/z_llm_safety_gateway/config/loader.py` - YAML 加载 + ${VAR_NAME} 环境变量插值（递归遍历，os.environ.get 默认空字符串）
- [x] 1.3 创建 `src/z_llm_safety_gateway/config/validators.py` - 跨字段验证（block_threshold > flag_threshold, routing 冲突检测, provider 必填字段检查）
- [x] 1.4 编写测试 `tests/unit/config/test_loader.py` - TC-CONFIG-001~004, 016~017（YAML 加载、环境变量插值）
- [x] 1.5 编写测试 `tests/unit/config/test_models.py` - TC-CONFIG-005~006（Pydantic 验证、类型不匹配）
- [x] 1.6 编写测试 `tests/unit/config/test_validators.py` - TC-CONFIG-007~015（跨字段验证、路由冲突、缺失字段）
- [x] 1.7 编写测试 `tests/unit/config/test_error_handling.py` - TC-CONFIG-012~013（无效配置阻止启动、YAML 语法错误）

## 2. request-id（P0）

- [x] 2.1 创建 `src/z_llm_safety_gateway/middleware/request_id.py` - RequestIDMiddleware（UUID v4 生成、客户端 ID 消毒 ^[a-zA-Z0-9_-]{1,128}$、request.state.request_id 存储）
- [x] 2.2 创建 `src/z_llm_safety_gateway/middleware/safety_headers.py` - SafetyHeadersMiddleware（X-Safety-Action: allow 注入、X-Safety-Risk-Level 不注入）
- [x] 2.3 编写测试 `tests/unit/middleware/test_request_id.py` - TC-REQID-001~004, 008~010（生成、传播、消毒、格式验证）
- [x] 2.4 编写测试 `tests/unit/middleware/test_safety_headers.py` - TC-REQID-005~007（响应头注入、X-Safety-Action）

## 3. content-extractor（P0）

- [x] 3.1 创建 `src/z_llm_safety_gateway/models.py` - ExtractedContent + Modification Pydantic models
- [x] 3.2 创建 `src/z_llm_safety_gateway/content/extractor.py` - extract_content() 函数（role 过滤、字符串/多模态处理、text parts 换行拼接）
- [x] 3.3 创建 `src/z_llm_safety_gateway/content/writeback.py` - apply_modifications() 函数（优先级排序、字符串/多模态写回、image 保留）
- [x] 3.4 编写测试 `tests/unit/content/test_extractor.py` - TC-EXTRACT-001~006（角色过滤、字符串/多模态提取、message_index）
- [x] 3.5 编写测试 `tests/unit/content/test_writeback.py` - TC-EXTRACT-007~010（优先级排序、字符串/多模态写回、空列表）
- [x] 3.6 编写测试 `tests/unit/content/test_models.py` - TC-EXTRACT-011~012（ExtractedContent + Modification 模型字段）

## 4. provider-proxy（P0）（依赖 #1）

- [x] 4.1 创建 `src/z_llm_safety_gateway/providers/base.py` - BaseProvider 抽象基类（forward_request 方法）
- [x] 4.2 创建 `src/z_llm_safety_gateway/providers/openai.py` - OpenAIProvider（httpx.AsyncClient, Bearer auth, base_url 转发）
- [x] 4.3 创建 `src/z_llm_safety_gateway/providers/openai_compatible.py` - OpenAICompatibleProvider（无格式转换，无 api_key 要求）
- [x] 4.4 创建 `src/z_llm_safety_gateway/providers/azure_openai.py` - AzureOpenAIProvider（api-version 查询参数）
- [x] 4.5 创建 `src/z_llm_safety_gateway/providers/router.py` - ModelRouter（glob 模式匹配, first match wins, 冲突检测告警）
- [x] 4.6 编写测试 `tests/unit/providers/test_router.py` - TC-PROXY-001~004, 012（glob 匹配、first match、无匹配 404、冲突告警）
- [x] 4.7 编写测试 `tests/unit/providers/test_openai.py` - TC-PROXY-005, 008~011（OpenAI 转发、超时、4xx/5xx、网络错误、无重试）
- [x] 4.8 编写测试 `tests/unit/providers/test_openai_compatible.py` - TC-PROXY-006（兼容 provider 转发）
- [x] 4.9 编写测试 `tests/unit/providers/test_azure_openai.py` - TC-PROXY-007（Azure 转发 + api-version）

## 5. health-endpoints（P0）（依赖 #2）

- [x] 5.1 创建 `src/z_llm_safety_gateway/routes/health.py` - /health (liveness), /ready (readiness), /metrics (占位)
- [x] 5.2 编写测试 `tests/unit/routes/test_health.py` - TC-HEALTH-001~006（liveness、readiness 就绪/未就绪、metrics 占位、无需认证）
- [x] 5.3 编写测试 `tests/integration/test_health_headers.py` - TC-HEALTH-007~009（X-Request-ID 头注入）

## 6. fastapi-server（P0）（依赖 #1, #2, #4, #5）

- [x] 6.1 创建 `src/z_llm_safety_gateway/app.py` - create_app() factory（配置加载、中间件注册、路由注册、异常处理器注册）
- [x] 6.2 创建 `src/z_llm_safety_gateway/routes/chat.py` - /v1/chat/completions 端点（解析 body、model 路由、provider 转发、响应返回）
- [x] 6.3 创建 `src/z_llm_safety_gateway/routes/models.py` - /v1/models 端点（透传第一个 provider）
- [x] 6.4 扩展 `src/z_llm_safety_gateway/exceptions.py` - OpenAIError model + ConfigError + 全局异常处理器
- [x] 6.5 编写测试 `tests/unit/test_app.py` - TC-FASTAPI-001~002, 008（app factory、配置不存在、无副作用）
- [x] 6.6 编写测试 `tests/integration/test_chat.py` - TC-FASTAPI-003~005, 009~011（正常转发、无匹配路由、无效 JSON、provider 错误包装）
- [x] 6.7 编写测试 `tests/integration/test_models_endpoint.py` - TC-FASTAPI-006（/v1/models 透传）
- [x] 6.8 编写测试 `tests/integration/test_error_handling.py` - TC-FASTAPI-007, 012~013（服务器启动、ConfigError、未处理异常）

## 7. Docker setup（P0）（依赖 #6）

- [x] 7.1 创建 `Dockerfile` - Python 3.10-slim 多阶段构建
- [x] 7.2 创建 `docker-compose.yml` - 开发环境单服务配置
- [x] 7.3 创建 `.dockerignore` - 排除 .stdd/, tests/, .git/, __pycache__/
- [x] 7.4 创建 `pyproject.toml` - 项目依赖、ruff/mypy/pytest 配置
- [x] 7.5 创建 `config/gateway.yaml` - 示例配置文件（基于 DESIGN.md Section 10.2）

## 8. 测试与验证

- [x] 8.1 全量 pytest 通过（102 tests, 73 TC 100% 覆盖）
- [x] 8.2 `ruff check src/ tests/` 无错误
- [x] 8.3 `mypy src/` 无错误
- [ ] 8.4 Docker 容器构建并运行成功（待手动验证）
