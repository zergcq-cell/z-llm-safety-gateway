# Capability: production-deployment

## MODIFIED Requirements

- **REQ-DEPL-004**：开发和生产 Compose SHALL 都通过 `docker compose config`。
- **REQ-DEPL-005**：生产配置 SHALL 保留多副本、资源、restart、healthcheck 与 sidecar 不变量。
- **REQ-DEPL-006**：Docker 可用时 SHALL 完成并清理健康冒烟；不可用时 SHALL 明确记录限制。
