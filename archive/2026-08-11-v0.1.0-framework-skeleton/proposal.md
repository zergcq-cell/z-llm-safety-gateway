# v0.1.0 - Framework Skeleton

## Why

LLM Safety Gateway 项目需要一个基础框架骨架来支撑后续所有开发阶段。Phase 1 建立核心 HTTP 服务器、配置系统、Provider 代理和内容提取基础设施，这是 Pipeline（Phase 2）、流式检测（Phase 3）、安全与可观测性（Phase 4）的前置依赖。没有这个骨架，后续阶段的检测器、流式处理和安全层都无处挂载。

作为全新项目，需要先搭建可运行的基础框架，实现 OpenAI 兼容的透明代理功能，再在此基础上逐步添加安全检测能力。Phase 1 确保"请求能正常转发"这个最小可用路径打通。

## What Changes

- C1: 创建 FastAPI 应用，实现 OpenAI 兼容端点 `/v1/chat/completions` 和 `/v1/models`
- C2: 实现 YAML 配置系统，使用 Pydantic v2 进行 schema 验证，支持 `${VAR_NAME}` 环境变量覆盖
- C3: 实现 Provider 代理层，支持模型路由（glob 模式匹配）和请求转发，支持 `openai`、`openai_compatible`、`azure_openai` 三种 provider 类型
- C4: 实现内容提取器，从 OpenAI messages 数组提取文本，支持多模态内容（text parts），支持 modify writeback
- C5: 添加健康检查端点 `/health`（liveness）、`/ready`（readiness）、`/metrics`（占位）
- C6: 实现 Request ID 中间件：UUID v4 生成、`X-Request-ID` 头传播、响应头注入
- C7: 创建 Docker 设置（Dockerfile + docker-compose.yml）
- C8: 搭建项目结构（pyproject.toml、src/ 目录、tests/ 目录）

## Capabilities

### New Capabilities

- **fastapi-server**：FastAPI HTTP 服务器，监听配置的 host:port，提供 OpenAI 兼容 API 端点
- **config-system**：YAML 配置加载，Pydantic v2 schema 验证，环境变量覆盖，启动时配置校验（无效配置阻止启动）
- **provider-proxy**：透明 HTTP 代理，基于 `model` 字段通过 glob 路由规则将请求转发到对应 LLM provider，返回响应
- **content-extractor**：从 OpenAI messages 数组提取检测文本（role: user/system/developer），支持字符串和多模态内容，支持 modify writeback 到原始请求
- **health-endpoints**：liveness (`/health`)、readiness (`/ready`)、metrics 占位端点 (`/metrics`)
- **request-id**：请求 ID 生成（UUID v4）或从客户端 `X-Request-ID` 头传播，所有响应注入 `X-Request-ID` 和 `X-Safety-Action: allow`（Phase 1 无检测，始终为 allow）

### Modified Capabilities

无（全新项目）

## Impact

**代码层面**：
- 新增约 12-15 个源文件（`src/` 目录），包含 app、config、provider、content_extractor、health、middleware 等模块
- 新增约 8-10 个测试文件（`tests/` 目录），覆盖各模块单元测试

**配置层面**：
- 新增 `pyproject.toml`（项目依赖、ruff/mypy 配置）
- 新增示例 `config/gateway.yaml`（基于 DESIGN.md Section 10.2）
- 新增 `pytest.ini` 或 pyproject.toml 中的 pytest 配置

**基础设施**：
- 新增 `Dockerfile`（Python 3.12 基础镜像）
- 新增 `docker-compose.yml`（开发环境）

## Constraints

- 技术栈：Python 3.12+ / FastAPI / Pydantic v2 / httpx / structlog
- 代码规范：遵循 `.stdd/standards/python.md`（ruff 行宽 100、完整类型注解）
- 测试：pytest + pytest-asyncio，覆盖率目标 80%
- 类型检查：mypy 必须通过
- Lint：ruff check 必须通过
- Phase 1 不包含检测器 Pipeline（Phase 2）
- Phase 1 不包含 SSE 流式代理（Phase 3）
- Phase 1 不包含认证、限流、TLS（Phase 4）
- `/v1/chat/completions` 在 Phase 1 直接转发请求到 provider（无安全检测），所有响应附带 `X-Safety-Action: allow`
- 内容提取器作为独立模块实现和测试，Phase 2 时接入 Pipeline

## Stakeholders

- 项目开发者（主要开发者和测试者）
- 未来用户（使用 Gateway 的应用程序开发者）

## Risk Areas

- capability: provider-proxy - 请求转发不正确会破坏 OpenAI API 兼容性，影响所有后续请求。缓解：完整的端到端测试，使用 mock provider 验证请求转发和响应返回
- capability: config-system - 验证规则错误会阻止合法配置或放行非法配置。缓解：针对每条验证规则编写单元测试，覆盖合法和非法配置场景
- capability: content-extractor - 文本提取不正确会影响后续检测准确性。缓解：覆盖各种消息格式（字符串、多模态、不同角色）的单元测试

## NonGoals

- 检测器 Pipeline 引擎和检测器实现（Phase 2）
- SSE 流式代理和滑动窗口检测（Phase 3）
- API Key 认证、限流、TLS 终止（Phase 4）
- Prometheus 指标采集实现（Phase 4，Phase 1 仅占位端点）
- 审计日志（Phase 3）
- Provider failover（v1.1+）
- gRPC sidecar 插件系统（Phase 5）
- 输出检测（Phase 2/3）

## Critical

- [x] 非关键变更（默认）
- [ ] 关键变更 - 涉及安全/金融/核心基础设施，需 L3/L4 锚定

## Risk Assessment

- **safety_critical**：false（Phase 1 不涉及认证/授权/加密/数据保护）
- **financial**：false
- **cross_system**：false（单一系统，无多系统协调）

## Anchoring

- **level**：L1（行为锚定 - 全新项目，通过功能测试验证行为）
- **reference_changes**：[]
- **anchor_implementations**：[]

## Success Criteria

- [ ] FastAPI 服务器启动并监听配置的 host:port
- [ ] `/v1/chat/completions` 接受请求并透明转发到配置的 provider，返回 provider 响应
- [ ] `/v1/models` 透传 provider 的模型列表
- [ ] `/health` 返回 200 和 `{"status": "healthy"}`
- [ ] `/ready` 返回 200 和 `{"status": "ready"}`（服务器就绪时）
- [ ] `/metrics` 端点存在并返回 200（占位响应）
- [ ] YAML 配置通过 Pydantic v2 验证加载
- [ ] 环境变量覆盖工作（如 `${OPENAI_API_KEY}` 被实际值替换）
- [ ] 无效配置产生清晰错误消息并阻止启动
- [ ] 配置验证规则生效（如 `block_threshold > flag_threshold`、routing 冲突告警）
- [ ] 内容提取器正确提取 user/system/developer 角色消息文本
- [ ] 内容提取器正确处理字符串内容
- [ ] 内容提取器正确处理多模态内容（提取 text parts，跳过 image_url）
- [ ] 内容提取器正确执行 modify writeback（替换消息内容，保留 image parts）
- [ ] 未提供 `X-Request-ID` 时自动生成 UUID v4
- [ ] 提供 `X-Request-ID` 时传播客户端值
- [ ] 所有响应包含 `X-Request-ID` 头
- [ ] 所有响应包含 `X-Safety-Action: allow` 头
- [ ] Provider 代理基于 `model` 字段通过 glob 路由规则匹配正确 provider
- [ ] Provider 错误包装为 OpenAI 兼容错误格式（HTTP 502 `provider_error`）
- [ ] Docker 容器构建并运行成功
- [ ] 所有 pytest 测试通过
- [ ] `ruff check src/ tests/` 无错误
- [ ] `mypy src/` 无错误
