# v0.1.0 测试方案与详细案例

> 版本：v0.1.0 - Framework Skeleton
> 创建日期：2026-08-11
> 对应 Phase 2 Spec：specs/fastapi-server/, specs/config-system/, specs/provider-proxy/, specs/content-extractor/, specs/health-endpoints/, specs/request-id/

## 一、测试策略

### 1.1 测试金字塔

```
            /\
           /E2E\        — 端到端：完整请求转发流程、Docker 容器运行
          /------\
         /Integration\  — 集成：FastAPI TestClient 测试 API 端点、配置加载全流程
        /------------\
       /    Unit      \ — 单元：每个模块独立测试（config models、router、extractor 等）
      /----------------\
```

单元测试占比约 70%，集成测试约 20%，E2E 约 10%。Phase 1 重点在单元测试，确保每个组件独立正确。

### 1.2 测试原则

- 严格 TDD：RED（写失败测试）-> GREEN（最小实现）-> REFACTOR（重构）
- 每个 Scenario 至少对应 1 个 TC 案例
- 使用 mock provider 避免真实 API 调用
- 使用 FastAPI TestClient 进行集成测试（httpx.AsyncClient + ASGI transport）
- 测试不依赖外部服务（所有 provider 通过 httpx.MockTransport 或 respx mock）

### 1.3 已有测试资产

| 测试文件 | 用例数 | 类型 | 覆盖范围 |
|----------|--------|------|----------|
| 无（全新项目） | 0 | - | Phase 1 从零开始 |

### 1.4 TC-ID 命名规则

`TC-<CAPABILITY>-<NNN>`

| Capability 缩写 | 全名 |
|-----------------|------|
| FASTAPI | fastapi-server |
| CONFIG | config-system |
| PROXY | provider-proxy |
| EXTRACT | content-extractor |
| HEALTH | health-endpoints |
| REQID | request-id |

## 二、详细测试案例

### 功能 1：fastapi-server

对应 spec: fastapi-server/spec.yaml

#### 案例 1.1 — App factory 返回 FastAPI 实例

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-001 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | 存在有效的 YAML 配置文件（含 server, providers, routing 段） |
| **输入** | 调用 create_app(config_path) |
| **预期结果** | 返回 FastAPI 实例，配置已加载，路由已注册（/v1/chat/completions, /v1/models, /health, /ready, /metrics），RequestIDMiddleware 已注册，全局异常处理器已注册 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.2 — App factory 配置文件不存在

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-002 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-002 |
| **优先级** | P0 |
| **预置条件** | 配置文件路径不存在 |
| **输入** | 调用 create_app("/nonexistent/path.yaml") |
| **预期结果** | 抛出异常，异常消息包含文件路径 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.3 — /v1/chat/completions 正常转发

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-003 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-003 |
| **优先级** | P0 |
| **预置条件** | Gateway 运行中，配置了 provider 和路由规则 gpt-4* -> openai，mock provider 返回 200 |
| **输入** | POST /v1/chat/completions，body 含 model: "gpt-4" 和 messages 数组 |
| **预期结果** | 返回 provider 响应，状态码与 provider 一致，body 透传，包含 X-Request-ID 和 X-Safety-Action: allow 头 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.4 — /v1/chat/completions model 无匹配路由

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-004 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-004 |
| **优先级** | P0 |
| **预置条件** | Gateway 运行中，路由规则 gpt-4* -> openai |
| **输入** | POST /v1/chat/completions，model: "claude-3-opus" |
| **预期结果** | HTTP 404，error.type 为 invalid_request_error，code 为 model_not_found，包含 X-Request-ID |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.5 — /v1/chat/completions 无效 JSON body

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-005 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-005 |
| **优先级** | P1 |
| **预置条件** | Gateway 运行中 |
| **输入** | POST /v1/chat/completions，body 为无效 JSON |
| **预期结果** | HTTP 400，OpenAI 兼容错误格式，包含 X-Request-ID |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.6 — /v1/models 透传

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-006 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-006 |
| **优先级** | P0 |
| **预置条件** | Gateway 运行中，至少配置 1 个 provider，mock provider 返回模型列表 |
| **输入** | GET /v1/models |
| **预期结果** | 返回第一个 provider 的模型列表，状态码与 provider 一致，body 透传，不聚合多个 provider |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.7 — 服务器监听配置的 host:port

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-007 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-007 |
| **优先级** | P0 |
| **预置条件** | 配置 server.host=127.0.0.1, server.port=8080 |
| **输入** | 启动服务器 |
| **预期结果** | 服务器绑定到 127.0.0.1:8080，接受 HTTP 连接，配置仅启动时加载一次 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.8 — App factory 无导入副作用

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-008 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-008 |
| **优先级** | P1 |
| **预置条件** | 无 |
| **输入** | import app factory 模块 |
| **预期结果** | 导入不启动服务器，无副作用 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.9 — Provider 5xx 错误包装

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-009 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-009 |
| **优先级** | P0 |
| **预置条件** | Mock provider 返回 500 |
| **输入** | POST /v1/chat/completions |
| **预期结果** | HTTP 502，error.type 为 provider_error，details 含 provider name 和原始 message |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.10 — Provider 超时错误

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-010 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-010 |
| **优先级** | P0 |
| **预置条件** | Mock provider 超时 |
| **输入** | POST /v1/chat/completions |
| **预期结果** | HTTP 502，provider_error，消息指示 timeout，网关中止上游请求 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.11 — Provider 4xx 错误包装

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-011 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-011 |
| **优先级** | P0 |
| **预置条件** | Mock provider 返回 400 |
| **输入** | POST /v1/chat/completions |
| **预期结果** | HTTP 502，provider_error，details 含原始状态码和消息，不重试 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.12 — ConfigError 包装为 500

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-012 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-012 |
| **优先级** | P1 |
| **预置条件** | 请求处理中触发 ConfigError |
| **输入** | 触发配置错误的请求 |
| **预期结果** | HTTP 500，internal_error，code 为 config_error，不暴露 secrets |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.13 — 未处理异常包装为 500

| 字段 | 内容 |
|------|------|
| **ID** | TC-FASTAPI-013 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-013 |
| **优先级** | P1 |
| **预置条件** | 请求处理中触发未处理异常 |
| **输入** | 触发未处理异常的请求 |
| **预期结果** | HTTP 500，internal_error，异常详情记录到日志但不暴露到响应 body |
| **当前状态** | ❌ 测试缺 |

### 功能 2：config-system

对应 spec: config-system/spec.yaml

#### 案例 2.1 — YAML safe_load 解析

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-001 |
| **对应 Spec** | config-system/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | 有效的 YAML 配置文件（含所有段） |
| **输入** | 调用 config loader 读取文件 |
| **预期结果** | 使用 yaml.safe_load 解析，返回 dict，保留嵌套结构 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.2 — YAML 结构不完整延迟验证

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-002 |
| **对应 Spec** | config-system/spec.yaml → SC-002 |
| **优先级** | P1 |
| **预置条件** | YAML 语法正确但缺少 providers 段 |
| **输入** | 调用 config loader |
| **预期结果** | YAML 解析成功，结构验证延迟到 Pydantic 层 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.3 — 环境变量插值

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-003 |
| **对应 Spec** | config-system/spec.yaml → SC-003 |
| **优先级** | P0 |
| **预置条件** | YAML 含 api_key: ${OPENAI_API_KEY}，环境变量 OPENAI_API_KEY=sk-test123 |
| **输入** | 调用 config loader |
| **预期结果** | ${OPENAI_API_KEY} 替换为 sk-test123，递归处理嵌套值，Pydantic 验证前完成替换 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.4 — 未设置环境变量解析为空字符串

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-004 |
| **对应 Spec** | config-system/spec.yaml → SC-004 |
| **优先级** | P0 |
| **预置条件** | YAML 含 api_key: ${UNSET_VAR}，环境变量 UNSET_VAR 未设置 |
| **输入** | 调用 config loader |
| **预期结果** | ${UNSET_VAR} 解析为空字符串，不抛出异常，如字段必填则 Pydantic 报错 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.5 — Pydantic v2 验证所有配置段

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-005 |
| **对应 Spec** | config-system/spec.yaml → SC-005 |
| **优先级** | P0 |
| **预置条件** | 完整有效的配置 dict（env var 插值后） |
| **输入** | GatewayConfig(**parsed) |
| **预期结果** | 验证通过，返回 GatewayConfig 实例，每段有对应 Pydantic model |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.6 — 类型不匹配验证失败

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-006 |
| **对应 Spec** | config-system/spec.yaml → SC-006 |
| **优先级** | P0 |
| **预置条件** | server.port 为字符串 "not_a_number" |
| **输入** | GatewayConfig(**parsed) |
| **预期结果** | Pydantic ValidationError，含字段路径和期望类型 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.7 — block_threshold <= flag_threshold 验证失败

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-007 |
| **对应 Spec** | config-system/spec.yaml → SC-007 |
| **优先级** | P0 |
| **预置条件** | detector 配置 block_threshold: 0.50, flag_threshold: 0.85 |
| **输入** | Pydantic 验证 |
| **预期结果** | ValidationError，消息含 detector name 和两个阈值，使用 model_validator(mode='after') |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.8 — block_threshold > flag_threshold 验证通过

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-008 |
| **对应 Spec** | config-system/spec.yaml → SC-008 |
| **优先级** | P0 |
| **预置条件** | detector 配置 block_threshold: 0.85, flag_threshold: 0.50 |
| **输入** | Pydantic 验证 |
| **预期结果** | 验证通过，无错误 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.9 — block_threshold == flag_threshold 验证失败

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-009 |
| **对应 Spec** | config-system/spec.yaml → SC-009 |
| **优先级** | P1 |
| **预置条件** | detector 配置 block_threshold: 0.85, flag_threshold: 0.85 |
| **输入** | Pydantic 验证 |
| **预期结果** | ValidationError，相等值被拒绝 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.10 — 路由冲突检测告警

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-010 |
| **对应 Spec** | config-system/spec.yaml → SC-010 |
| **优先级** | P0 |
| **预置条件** | 路由规则 gpt-4*: openai 和 gpt-*: openai 重叠 |
| **输入** | 启动时配置验证 |
| **预期结果** | 输出 warning 指出重叠模式和受影响 model，不阻止启动，first match 生效 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.11 — 无路由冲突无告警

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-011 |
| **对应 Spec** | config-system/spec.yaml → SC-011 |
| **优先级** | P1 |
| **预置条件** | 路由规则 gpt-4*: openai 和 llama*: local_llama 不重叠 |
| **输入** | 启动时配置验证 |
| **预期结果** | 无重叠 warning |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.12 — 无效配置阻止启动

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-012 |
| **对应 Spec** | config-system/spec.yaml → SC-012 |
| **优先级** | P0 |
| **预置条件** | YAML 配置 Pydantic 验证失败 |
| **输入** | 调用 config loader |
| **预期结果** | ConfigValidationError，消息含失败字段和期望/实际值，阻止启动 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.13 — YAML 语法错误

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-013 |
| **对应 Spec** | config-system/spec.yaml → SC-013 |
| **优先级** | P0 |
| **预置条件** | YAML 文件有语法错误（如括号不匹配） |
| **输入** | 调用 config loader |
| **预期结果** | 错误消息含语法错误和大致位置，阻止启动 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.14 — OpenAI provider 缺少 api_key

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-014 |
| **对应 Spec** | config-system/spec.yaml → SC-014 |
| **优先级** | P0 |
| **预置条件** | openai provider 无 api_key（或 env var 未设置导致空字符串） |
| **输入** | Pydantic 验证 |
| **预期结果** | ValidationError，消息含 provider name 和 missing field name |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.15 — openai_compatible provider 不需要 api_key

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-015 |
| **对应 Spec** | config-system/spec.yaml → SC-015 |
| **优先级** | P1 |
| **预置条件** | openai_compatible provider 有 base_url 无 api_key |
| **输入** | Pydantic 验证 |
| **预期结果** | 验证通过，azure_openai 需要 api_version |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.16 — 未设置环境变量不崩溃

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-016 |
| **对应 Spec** | config-system/spec.yaml → SC-016 |
| **优先级** | P0 |
| **预置条件** | YAML 含 ${TOTALLY_UNSET_VAR}，环境变量未设置 |
| **输入** | 环境变量插值 |
| **预期结果** | 解析为空字符串，不抛 KeyError，使用 os.environ.get('VAR', '') |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.17 — 混合设置/未设置环境变量

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONFIG-017 |
| **对应 Spec** | config-system/spec.yaml → SC-017 |
| **优先级** | P1 |
| **预置条件** | YAML 含多个 ${VAR} 引用，部分设置部分未设置 |
| **输入** | 环境变量插值 |
| **预期结果** | 设置的替换为值，未设置的替换为空字符串，单次递归完成，支持 prefix-${VAR}-suffix 内联替换 |
| **当前状态** | ❌ 测试缺 |

### 功能 3：provider-proxy

对应 spec: provider-proxy/spec.yaml

#### 案例 3.1 — Glob 路由 first match wins

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-001 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | 路由规则：gpt-4* -> openai, gpt-3.5* -> openai, azure-* -> azure, llama* -> local_llama |
| **输入** | model: "gpt-4-turbo" |
| **预期结果** | 匹配 gpt-4*，返回 openai provider |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.2 — 重叠 glob first match wins

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-002 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-002 |
| **优先级** | P0 |
| **预置条件** | 路由规则：gpt-4* -> openai, gpt-* -> local_llama（重叠） |
| **输入** | model: "gpt-4-turbo" |
| **预期结果** | 匹配 gpt-4*（first match），不评估 gpt-* |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.3 — llama 模型路由

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-003 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-003 |
| **优先级** | P0 |
| **预置条件** | 路由规则 llama* -> local_llama |
| **输入** | model: "llama3-70b" |
| **预期结果** | 匹配 llama*，返回 local_llama provider |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.4 — 无匹配路由 404

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-004 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-004 |
| **优先级** | P0 |
| **预置条件** | 路由规则 gpt-4* -> openai, llama* -> local_llama |
| **输入** | model: "claude-3-opus" |
| **预期结果** | HTTP 404，invalid_request_error，code: model_not_found |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.5 — OpenAI provider 转发

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-005 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-005 |
| **优先级** | P0 |
| **预置条件** | OpenAI provider 配置 base_url 和 api_key |
| **输入** | chat completion 请求 |
| **预期结果** | 使用 httpx.AsyncClient 转发到 base_url，Authorization: Bearer <api_key>，body 不修改，返回响应 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.6 — OpenAI-compatible provider 转发

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-006 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-006 |
| **优先级** | P0 |
| **预置条件** | openai_compatible provider 配置 base_url: http://localhost:11434/v1 |
| **输入** | chat completion 请求 |
| **预期结果** | 转发到 base_url，OpenAI 格式无转换，响应原样返回 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.7 — Azure OpenAI provider 转发

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-007 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-007 |
| **优先级** | P0 |
| **预置条件** | azure_openai provider 配置 base_url, api_key, api_version: 2024-06-01 |
| **输入** | chat completion 请求 |
| **预期结果** | 转发到 base_url，含 api-version 查询参数，Authorization: Bearer <api_key> |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.8 — Provider 超时

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-008 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-008 |
| **优先级** | P0 |
| **预置条件** | provider 超时配置 120s，mock provider 不响应 |
| **输入** | 转发请求 |
| **预期结果** | HTTP 502，provider_error，中止上游请求，details 含 provider name 和 timeout 消息 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.9 — Provider 4xx/5xx 错误包装

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-009 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-009 |
| **优先级** | P0 |
| **预置条件** | Mock provider 返回 4xx 或 5xx |
| **输入** | 转发请求 |
| **预期结果** | HTTP 502，provider_error，details 含原始状态码/消息/provider name，Retry-After 转发 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.10 — Provider 网络错误

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-010 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-010 |
| **优先级** | P0 |
| **预置条件** | provider base_url 不可达 |
| **输入** | 转发请求 |
| **预期结果** | HTTP 502，provider_error，details 含 provider name 和通用网络错误消息，详情记录到日志 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.11 — 无重试

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-011 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-011 |
| **优先级** | P0 |
| **预置条件** | Provider 返回错误 |
| **输入** | 转发请求 |
| **预期结果** | 仅 1 次尝试，直接返回错误，无 failover |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.12 — 路由冲突启动告警

| 字段 | 内容 |
|------|------|
| **ID** | TC-PROXY-012 |
| **对应 Spec** | provider-proxy/spec.yaml → SC-012 |
| **优先级** | P1 |
| **预置条件** | 路由规则 gpt-4* 和 gpt-* 重叠 |
| **输入** | 启动时验证 |
| **预期结果** | 日志 warning 指出重叠模式和受影响 model，说明 first match 优先，不阻止启动 |
| **当前状态** | ❌ 测试缺 |

### 功能 4：content-extractor

对应 spec: content-extractor/spec.yaml

#### 案例 4.1 — 提取 user/system/developer 消息

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-001 |
| **对应 Spec** | content-extractor/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | messages 含 user, system, developer 角色消息 |
| **输入** | extract_content(messages) |
| **预期结果** | 为每个 user/system/developer 消息返回 ExtractedContent |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.2 — 跳过 assistant/function/tool 消息

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-002 |
| **对应 Spec** | content-extractor/spec.yaml → SC-002 |
| **优先级** | P0 |
| **预置条件** | messages 含 assistant, function, tool 角色消息 |
| **输入** | extract_content(messages) |
| **预期结果** | 不返回这些角色的 ExtractedContent |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.3 — 字符串内容提取

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-003 |
| **对应 Spec** | content-extractor/spec.yaml → SC-003 |
| **优先级** | P0 |
| **预置条件** | user 消息 content 为字符串 "Hello world" |
| **输入** | extract_content(messages) |
| **预期结果** | ExtractedContent.text == "Hello world" |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.4 — 多模态内容提取 text parts

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-004 |
| **对应 Spec** | content-extractor/spec.yaml → SC-004 |
| **优先级** | P0 |
| **预置条件** | user 消息 content 为 list: [text: "Describe this", image_url: {...}] |
| **输入** | extract_content(messages) |
| **预期结果** | text == "Describe this"，image_url 被跳过 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.5 — 多模态多 text parts 换行拼接

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-005 |
| **对应 Spec** | content-extractor/spec.yaml → SC-005 |
| **优先级** | P0 |
| **预置条件** | user 消息 content 为 list: [text: "Line 1", text: "Line 2"] |
| **输入** | extract_content(messages) |
| **预期结果** | text == "Line 1\nLine 2" |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.6 — message_index 保留原始位置

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-006 |
| **对应 Spec** | content-extractor/spec.yaml → SC-006 |
| **优先级** | P0 |
| **预置条件** | messages 索引 0=system, 1=user, 2=assistant |
| **输入** | extract_content(messages) |
| **预期结果** | ExtractedContent[0].message_index=0, [1].message_index=1（不含 2），role 正确 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.7 — 修改按优先级排序

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-007 |
| **对应 Spec** | content-extractor/spec.yaml → SC-007 |
| **优先级** | P0 |
| **预置条件** | modifications 优先级 [20, 10, 100] |
| **输入** | apply_modifications(request, modifications) |
| **预期结果** | 按 10, 20, 100 顺序应用 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.8 — 字符串内容修改写回

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-008 |
| **对应 Spec** | content-extractor/spec.yaml → SC-008 |
| **优先级** | P0 |
| **预置条件** | messages[0].content = "original text"，modification message_index=0, modified_content="redacted text" |
| **输入** | apply_modifications(request, modifications) |
| **预期结果** | messages[0].content == "redacted text" |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.9 — 多模态内容修改写回

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-009 |
| **对应 Spec** | content-extractor/spec.yaml → SC-009 |
| **优先级** | P0 |
| **预置条件** | messages[0].content = [text:"A", image_url:{...}, text:"B"]，modification message_index=0, modified_content="modified" |
| **输入** | apply_modifications(request, modifications) |
| **预期结果** | 第一个 text part 设为 "modified"，第二个 text part 清空，image_url 保留不变 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.10 — 空修改列表不修改请求

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-010 |
| **对应 Spec** | content-extractor/spec.yaml → SC-010 |
| **优先级** | P0 |
| **预置条件** | modifications = [] |
| **输入** | apply_modifications(request, []) |
| **预期结果** | 返回原始 request 不变 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.11 — ExtractedContent 模型字段

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-011 |
| **对应 Spec** | content-extractor/spec.yaml → SC-011 |
| **优先级** | P0 |
| **预置条件** | ExtractedContent Pydantic model 定义 |
| **输入** | 创建实例 |
| **预期结果** | 含 message_index (int), role (str), text (str) |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.12 — Modification 模型字段

| 字段 | 内容 |
|------|------|
| **ID** | TC-EXTRACT-012 |
| **对应 Spec** | content-extractor/spec.yaml → SC-012 |
| **优先级** | P0 |
| **预置条件** | Modification Pydantic model 定义 |
| **输入** | 创建实例 |
| **预期结果** | 含 detector_name (str), modified_content (str), priority (int), message_index (int) |
| **当前状态** | ❌ 测试缺 |

### 功能 5：health-endpoints

对应 spec: health-endpoints/spec.yaml

#### 案例 5.1 — /health liveness 探针

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-001 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | 服务器已启动 |
| **输入** | GET /health |
| **预期结果** | HTTP 200, body: {"status": "healthy"}, Content-Type: application/json, 不检查依赖 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.2 — /ready 就绪状态

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-002 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-002 |
| **优先级** | P0 |
| **预置条件** | 配置已加载，provider 客户端已初始化 |
| **输入** | GET /ready |
| **预期结果** | HTTP 200, body: {"status": "ready"}, Content-Type: application/json |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.3 — /ready 未就绪状态

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-003 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-003 |
| **优先级** | P0 |
| **预置条件** | 配置未加载或 provider 客户端未初始化 |
| **输入** | GET /ready |
| **预期结果** | HTTP 503, body: {"status": "not_ready"}, Content-Type: application/json |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.4 — /metrics 端点存在

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-004 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-004 |
| **优先级** | P0 |
| **预置条件** | 服务器已启动 |
| **输入** | GET /metrics |
| **预期结果** | HTTP 200, Content-Type: text/plain; charset=utf-8 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.5 — /metrics 占位内容

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-005 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-005 |
| **优先级** | P0 |
| **预置条件** | 服务器已启动（Phase 1） |
| **输入** | GET /metrics |
| **预期结果** | body == "# z LLM Safety Gateway metrics placeholder\n"，无实际指标采集 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.6 — 健康端点无需认证

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-006 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-006 |
| **优先级** | P0 |
| **预置条件** | 服务器已启动，无认证凭据 |
| **输入** | 分别 GET /health, /ready, /metrics（无 Authorization 头） |
| **预期结果** | 不返回 401，/health 返回 200，/ready 返回 200 或 503，/metrics 返回 200 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.7 — /health 包含 X-Request-ID

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-007 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-007 |
| **优先级** | P0 |
| **预置条件** | 服务器已注册 RequestID 中间件 |
| **输入** | GET /health（无 X-Request-ID 头） |
| **预期结果** | 响应含 X-Request-ID 头，值为 UUID v4 格式 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.8 — /ready 包含 X-Request-ID

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-008 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-008 |
| **优先级** | P0 |
| **预置条件** | 服务器已注册 RequestID 中间件 |
| **输入** | GET /ready（无 X-Request-ID 头） |
| **预期结果** | 响应含 X-Request-ID 头，值为 UUID v4 格式 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.9 — /metrics 包含 X-Request-ID

| 字段 | 内容 |
|------|------|
| **ID** | TC-HEALTH-009 |
| **对应 Spec** | health-endpoints/spec.yaml → SC-009 |
| **优先级** | P0 |
| **预置条件** | 服务器已注册 RequestID 中间件 |
| **输入** | GET /metrics（无 X-Request-ID 头） |
| **预期结果** | 响应含 X-Request-ID 头，值为 UUID v4 格式 |
| **当前状态** | ❌ 测试缺 |

### 功能 6：request-id

对应 spec: request-id/spec.yaml

#### 案例 6.1 — 无 X-Request-ID 时生成 UUID v4

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-001 |
| **对应 Spec** | request-id/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | 请求未携带 X-Request-ID 头 |
| **输入** | RequestID 中间件处理请求 |
| **预期结果** | 生成 UUID v4，36 字符格式 xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.2 — 合法 X-Request-ID 传播

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-002 |
| **对应 Spec** | request-id/spec.yaml → SC-002 |
| **优先级** | P0 |
| **预置条件** | 请求携带 X-Request-ID: "my-req-123"，匹配 ^[a-zA-Z0-9_-]{1,128}$ |
| **输入** | RequestID 中间件处理请求 |
| **预期结果** | 使用客户端值 "my-req-123"，不重新生成 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.3 — 非法 X-Request-ID 消毒

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-003 |
| **对应 Spec** | request-id/spec.yaml → SC-003 |
| **优先级** | P0 |
| **预置条件** | 请求携带 X-Request-ID 含特殊字符或超 128 字符 |
| **输入** | RequestID 中间件处理请求 |
| **预期结果** | 丢弃无效 ID，生成新 UUID v4，防止 log injection 和 header injection |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.4 — 空 X-Request-ID 消毒

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-004 |
| **对应 Spec** | request-id/spec.yaml → SC-004 |
| **优先级** | P0 |
| **预置条件** | 请求携带 X-Request-ID: ""（空字符串） |
| **输入** | RequestID 中间件处理请求 |
| **预期结果** | 丢弃空 ID，生成新 UUID v4 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.5 — 生成 ID 的响应头注入

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-005 |
| **对应 Spec** | request-id/spec.yaml → SC-005 |
| **优先级** | P0 |
| **预置条件** | 请求未携带 X-Request-ID |
| **输入** | 服务器返回响应 |
| **预期结果** | 响应含 X-Request-ID 头，值为生成的 UUID v4 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.6 — 传播 ID 的响应头注入

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-006 |
| **对应 Spec** | request-id/spec.yaml → SC-006 |
| **优先级** | P0 |
| **预置条件** | 请求携带 X-Request-ID: "my-req-123" |
| **输入** | 服务器返回响应 |
| **预期结果** | 响应含 X-Request-ID: "my-req-123" |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.7 — X-Safety-Action: allow 头

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-007 |
| **对应 Spec** | request-id/spec.yaml → SC-007 |
| **优先级** | P0 |
| **预置条件** | Phase 1 服务器已启动 |
| **输入** | 任意请求 |
| **预期结果** | 响应含 X-Safety-Action: "allow"，Phase 1 无安全检测 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.8 — allow 时不包含 X-Safety-Risk-Level

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-008 |
| **对应 Spec** | request-id/spec.yaml → SC-008 |
| **优先级** | P0 |
| **预置条件** | X-Safety-Action 为 "allow" |
| **输入** | 服务器返回响应 |
| **预期结果** | 响应不包含 X-Safety-Risk-Level 头 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.9 — request.state.request_id 存储

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-009 |
| **对应 Spec** | request-id/spec.yaml → SC-009 |
| **优先级** | P0 |
| **预置条件** | RequestID 中间件已处理请求 |
| **输入** | 路由函数访问 request.state.request_id |
| **预期结果** | request.state.request_id 包含请求 ID 值，为字符串类型 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.10 — UUID v4 格式验证

| 字段 | 内容 |
|------|------|
| **ID** | TC-REQID-010 |
| **对应 Spec** | request-id/spec.yaml → SC-010 |
| **优先级** | P0 |
| **预置条件** | 请求未携带 X-Request-ID |
| **输入** | 网关生成请求 ID |
| **预期结果** | 36 字符，匹配 ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$，第 14 位为 '4'，第 19 位为 8/9/a/b |
| **当前状态** | ❌ 测试缺 |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 集成测试 | E2E | 状态 |
|----------|---------|----------|-----|------|
| config-system | TC-CONFIG-001 ~ 017 | TC-CONFIG-005, 010, 012 | - | 🔴 待建 |
| provider-proxy (router) | TC-PROXY-001 ~ 004, 012 | TC-PROXY-005 ~ 011 | - | 🔴 待建 |
| provider-proxy (forward) | TC-PROXY-005 ~ 011 | TC-FASTAPI-003, 006, 009 ~ 011 | - | 🔴 待建 |
| content-extractor | TC-EXTRACT-001 ~ 012 | - | - | 🔴 待建 |
| health-endpoints | TC-HEALTH-001 ~ 006 | TC-HEALTH-007 ~ 009 | - | 🔴 待建 |
| request-id | TC-REQID-001 ~ 004, 008 ~ 010 | TC-REQID-005 ~ 007 | - | 🔴 待建 |
| fastapi-server (app) | TC-FASTAPI-001, 002, 008 | TC-FASTAPI-003 ~ 007, 009 ~ 013 | TC-FASTAPI-007 (Docker) | 🔴 待建 |
| Docker | - | - | Docker build + run | 🔴 待建 |

## 四、回归风险矩阵

| 风险区域 | v0.1.0 改动 | 已有回归保护 | 风险等级 |
|----------|-------------|-------------|---------|
| config-system | 全新实现 | 无（新项目） | 🟡 中（核心基础，后续 Phase 依赖） |
| provider-proxy | 全新实现 | 无 | 🔴 高（影响所有请求转发） |
| content-extractor | 全新实现 | 无 | 🟡 中（Phase 1 独立模块，Phase 2 接入） |
| health-endpoints | 全新实现 | 无 | 🟢 低（简单端点） |
| request-id | 全新实现 | 无 | 🟡 中（影响所有响应头） |
| fastapi-server | 全新实现 | 无 | 🔴 高（核心入口） |
| Docker | 全新实现 | 无 | 🟢 低（基础设施） |

## 五、建议补充顺序

1. **第一优先（部署前必补）**：
   - TC-CONFIG-001, 003, 004, 005, 007, 008, 012, 013, 014, 016（配置加载核心路径）
   - TC-PROXY-001, 003, 004, 005, 008, 009, 010, 011（路由和转发核心路径）
   - TC-EXTRACT-001, 003, 004, 005, 008, 009, 010（提取和写回核心路径）
   - TC-HEALTH-001, 002, 003, 004, 005（健康检查核心）
   - TC-REQID-001, 002, 003, 005, 007（Request ID 核心路径）
   - TC-FASTAPI-001, 002, 003, 004, 006, 007, 009, 010, 011（服务器核心路径）

2. **第二优先（部署后尽快补）**：
   - TC-CONFIG-002, 006, 009, 010, 011, 015, 017（配置边界场景）
   - TC-PROXY-002, 006, 007, 012（provider 类型和冲突检测）
   - TC-EXTRACT-002, 006, 007, 011, 012（提取边界和模型验证）
   - TC-HEALTH-006, 007, 008, 009（健康端点认证和头注入）
   - TC-REQID-004, 006, 008, 009, 010（Request ID 边界场景）

3. **第三优先（后续补）**：
   - TC-FASTAPI-005, 008, 012, 013（服务器边界场景）
   - Docker E2E 测试
