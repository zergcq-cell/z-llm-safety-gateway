# v0.1.0 切片执行计划

## Dependency Graph Summary

```
Parallel Group 1 (零依赖，可并行):
  config-system ──────┐
  request-id ─────────┼──────┐
  content-extractor ──┘      │
                             │
Parallel Group 2 (依赖 Group 1):│
  provider-proxy ──────┐      │
  health-endpoints ────┼──────┤
                       │      │
Sequential (依赖 Group 1+2):  │
  fastapi-server ─────────────┘
        │
  docker-setup ────┘
```

**并行化说明**：
- 并行组 1：Slice 1 (config-system), Slice 2 (request-id), Slice 3 (content-extractor) — 均无依赖，可并行开发
- 并行组 2：Slice 4 (provider-proxy), Slice 5 (health-endpoints) — 依赖组 1 完成，两者可并行
- 串行：Slice 6 (fastapi-server) — 依赖以上所有切片；Slice 7 (Docker) — 依赖 Slice 6

## Slice Execution Plan

| # | 优先级 | 风险 | 预估工时 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|---------|--------|---------|---------|------|
| 1 | P0 | 🟡 Med | L | 组1 | TC-CONFIG-001~017 | config loader + Pydantic models + validators | 无 |
| 2 | P0 | 🟡 Med | M | 组1 | TC-REQID-001~010 | RequestID middleware + SafetyHeaders middleware | 无 |
| 3 | P0 | 🟡 Med | M | 组1 | TC-EXTRACT-001~012 | extract_content + apply_modifications + models | 无 |
| 4 | P0 | 🟡 Med | L | 组2 | TC-PROXY-001~012 | ModelRouter + 3 provider adapters + error handling | 1 |
| 5 | P0 | 🟢 Low | S | 组2 | TC-HEALTH-001~009 | /health + /ready + /metrics endpoints | 2 |
| 6 | P0 | 🟡 High | L | — | TC-FASTAPI-001~013 | App factory + routes + global error handlers | 1,2,4,5 |
| 7 | P0 | 🟢 Low | S | — | Docker E2E | Dockerfile + docker-compose.yml | 6 |

## Rationale

### Slice 1: config-system（P0，并行组 1）
- **依赖关系**：零依赖，是所有其他切片的基础（provider-proxy 需要 provider/routing 配置，fastapi-server 需要启动配置）
- **风险分析**：中风险。17 个 Scenario（>5 → +1），核心基础模块影响全局（+1），多条验证规则（+1）。无经验库数据。涉及 YAML 解析、环境变量插值、Pydantic v2 验证、跨字段校验、路由冲突检测
- **工作量估算**：L（17 TC，3 个文件：loader.py, models.py, validators.py）。配置系统是项目根基，必须完整实现

### Slice 2: request-id（P0，并行组 1）
- **依赖关系**：零依赖。ASGI 中间件独立于其他模块。health-endpoints 和 fastapi-server 依赖此中间件注入响应头
- **风险分析**：中风险。10 个 Scenario（>5 → +1），涉及安全相关（ID 消毒防 log injection，+1）。UUID v4 生成、正则验证、header 注入
- **工作量估算**：M（10 TC，2 个文件：request_id.py, safety_headers.py）。中间件逻辑清晰，但需覆盖消毒边界场景

### Slice 3: content-extractor（P0，并行组 1）
- **依赖关系**：零依赖。纯函数模块，Phase 1 不接入请求流程。Phase 2 时接入 Pipeline
- **风险分析**：中风险。12 个 Scenario（>5 → +1），涉及多模态内容处理（+1）。提取逻辑直接影响后续检测准确性
- **工作量估算**：M（12 TC，3 个文件：extractor.py, writeback.py, models.py）。DESIGN.md 提供完整伪代码，实现直接

### Slice 4: provider-proxy（P0，并行组 2）
- **依赖关系**：依赖 Slice 1（需要 ProviderConfig, RoutingConfig Pydantic models）
- **风险分析**：中风险。12 个 Scenario（>5 → +1），涉及外部 HTTP 调用（+1），核心路由逻辑（+1）。httpx 异步客户端、glob 模式匹配、错误包装
- **工作量估算**：L（12 TC，5 个文件：base.py, openai.py, openai_compatible.py, azure_openai.py, router.py）。3 种 provider 类型需要分别实现和测试

### Slice 5: health-endpoints（P0，并行组 2）
- **依赖关系**：依赖 Slice 2（需要 RequestID 中间件注入 X-Request-ID 头）
- **风险分析**：低风险。9 个 Scenario（>5 → +1），但逻辑简单（固定响应），无外部依赖检查（liveness）。readiness 检查配置加载状态
- **工作量估算**：S（9 TC，1 个文件：health.py）。三个端点逻辑简单，主要是 HTTP 响应格式验证

### Slice 6: fastapi-server（P0，串行）
- **依赖关系**：依赖 Slice 1（config）、Slice 2（middleware）、Slice 4（provider）、Slice 5（health routes）。是所有组件的集成点
- **风险分析**：高风险。13 个 Scenario（>5 → +1），集成所有模块（+1），核心入口点（+1），复杂错误处理（+1）。App factory、路由注册、全局异常处理器、OpenAI 兼容错误格式
- **工作量估算**：L（13 TC，4+ 个文件：app.py, routes/chat.py, routes/models.py, error handling）。集成测试需要 mock provider

### Slice 7: Docker setup（P0，串行）
- **依赖关系**：依赖 Slice 6（需要完整可运行的应用）
- **风险分析**：低风险。仅基础设施配置，无复杂逻辑
- **工作量估算**：S（2 个文件：Dockerfile, docker-compose.yml）。多阶段构建 + 开发环境配置
