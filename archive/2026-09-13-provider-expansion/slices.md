# Slice Execution Plan

依赖拓扑：`PFC` → `APA` / `GPA` → `PCM`。适配器可并行，但共享工作区按串行执行。

| Slice | Scope | TC | Risk | Effort |
|---|---|---|---|---|
| S1 | Anthropic adapter、请求/响应转换 | APA-001/002 | High | M |
| S2 | Gemini adapter、请求/响应转换 | GPA-001/002 | High | M |
| S3 | 统一错误、路由和模型端点 | PFC-001, PCM-001 | High | M |
| S4 | SSE、隐私和既有 Provider 回归 | SSE-001, COMP-001/002, PRIV-001 | High | M |

所有切片均为 P0；每个切片完成后执行聚焦测试和全量回归。
