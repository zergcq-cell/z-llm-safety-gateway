# Deployment Guide

> 适用版本：v0.1.0

## 1. Docker 部署（推荐）

### 开发/单实例

```bash
docker compose up -d
```

### 生产（多副本 + 资源限制 + sidecar）

```bash
docker compose -f docker-compose.prod.yml up -d
```

生产配置特性（详见 `docker-compose.prod.yml`）：
- gateway 2 副本（`deploy.replicas: 2`）
- CPU/内存资源限制
- `/health` 健康检查（start_period/interval/timeout/retries）
- gRPC sidecar 示例服务（可替换为真实检测器镜像）

> 说明：`deploy.replicas` 在 Docker Compose 单机模式下需 `docker compose up --scale gateway=2` 生效；Swarm/K8s 模式下自动生效。

## 2. 构建自定义镜像

```bash
docker build -t z-safety-gateway:0.1.0 .
docker run -d -p 8080:8080 \
  -v $(pwd)/config/gateway.yaml:/app/config/gateway.yaml:ro \
  -e OPENAI_API_KEY=sk-... \
  z-safety-gateway:0.1.0
```

## 3. 生产建议

### 3.1 认证与网络

- 开启 `security.auth`（API key）
- 启用 TLS（`security.tls` 或前置反向代理如 Nginx/ALB 终止 TLS）
- 网关与 gRPC sidecar 间建议启用 mTLS（v1.1 路线图提供原生支持；当前可用 sidecar 侧自校验）

### 3.2 资源与容量

参考 [DESIGN.md 14. Performance Targets](DESIGN.md#14-performance-targets)：

| 场景 | 参考 |
|------|------|
| 纯规则检测 | 1000 req/s / 实例，内存 < 256MB |
| 含 ML 检测（toxicity） | 200 req/s / 实例，内存 < 1GB |

按负载横向扩容（无状态，可任意加副本）。

### 3.3 日志与审计

- 审计日志默认写 `logs/audit.jsonl`（JSONL，按日轮转），挂载持久化卷
- 生产建议收集 stdout 结构化日志到集中日志平台（Vector/Fluentd/CloudWatch）

### 3.4 配置管理

- 密钥（API key）用环境变量注入，勿提交仓库
- 配置变更后滚动重启（多副本下逐个替换）

## 4. gRPC Sidecar 集成

```yaml
# docker-compose.prod.yml 片段
services:
  gateway:
    # ...
    depends_on:
      - acme-guard
  acme-guard:
    image: acme/detector:1.0.0
    expose: ["50051"]
    healthcheck:
      test: ["CMD", "grpc_health_probe", "-addr=:50051"]
      interval: 30s
```

网关配置：

```yaml
pipeline:
  detectors:
    input:
      - name: acme_guard
        type: grpc
        enabled: true
        config:
          endpoint: "acme-guard:50051"    # compose 服务名解析
          tls_enabled: false
```

验证：

```bash
zlg detectors check-connection acme_guard --config config/gateway.yaml
# status: serving
```

## 5. 故障排查

| 现象 | 检查 |
|------|------|
| `/ready` 返回 503 | 配置加载或 provider 初始化失败，看启动日志 |
| 检测器未生效 | `zlg detectors list` 确认注册；配置 `enabled: true` |
| gRPC 检测器 ERROR 日志 | sidecar 未启动或 HealthCheck 非 serving，`zlg detectors check-connection` |
| 限流误触发 | `security.rate_limit` 调参 |
| 审计日志缺失 | `observability.audit.jsonl_path` 目录可写 |

## 6. 升级

- 配置向后兼容 v0.5.x（旧版 `pipeline.detectors` 平铺格式自动迁移）
- 升级前备份 `config/` 与 `logs/`
- 滚动发布：先起新版本实例，健康检查通过后摘除旧实例
