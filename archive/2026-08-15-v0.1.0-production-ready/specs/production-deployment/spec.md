# production-deployment — 行为规格（Human View）

> 变更：2026-08-15-v1.0.0-production-ready | 置信度：medium

## Requirements

### REQ-DEPL-001: docker-compose.prod.yml 提供生产级部署配置且通过校验

**SC-DEPL-001**（置信度 medium）— evidence: proposal.yaml -> what_changes C6; DESIGN.md 13

- GIVEN: docker-compose.prod.yml
- WHEN: 执行 docker compose -f docker-compose.prod.yml config
- THEN: 配置 SHALL 通过 compose config 校验（exit 0）
- AND: gateway 服务 SHALL 配置 deploy.replicas ≥ 2（多副本）
- AND: gateway 服务 SHALL 配置 deploy.resources.limits（cpu 与 memory）
- AND: gateway 服务 SHALL 配置 healthcheck（探测 /health）
- AND: gateway 服务 SHALL 配置 restart: unless-stopped
- AND: 文件 SHALL 与现有 docker-compose.yml（开发版）并存，不修改开发版

### REQ-DEPL-002: 生产 compose 包含 gRPC sidecar 示例集成

**SC-DEPL-002**（置信度 medium）— evidence: proposal.yaml -> what_changes C6

- GIVEN: docker-compose.prod.yml 中的 sidecar 服务
- WHEN: 检查 sidecar 配置
- THEN: 配置 SHALL 包含 gRPC sidecar 服务（示例镜像）与 gateway 的关联配置（endpoint/网络）
- AND: sidecar 服务 SHALL 有健康检查与资源限制
- AND: 配置注释 SHALL 说明如何替换为真实 sidecar 镜像

### REQ-DEPL-003: 单副本冒烟验证可运行（本地无容器时降级为 config 校验）

**SC-DEPL-003**（置信度 low）— evidence: proposal.yaml -> risk_areas production-deployment

- GIVEN: 本地 Docker 环境
- WHEN: 执行 docker compose -f docker-compose.prod.yml up -d --scale gateway=1
- THEN: gateway 容器 SHALL 启动并通过 healthcheck
- AND: 若本地无 Docker，则 SHALL 至少通过 docker compose config 校验（验证降级路径）
