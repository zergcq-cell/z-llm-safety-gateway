# Deployment Guide

> 适用版本：v0.1.1

## 1. Docker 部署（推荐）

### 开发/单实例

```bash
docker compose up -d
```

### 生产（多副本 + 资源限制 + sidecar）

```bash
OPENAI_API_KEY=sk-openai-replace \
ACME_API_KEY=sk-sidecar-replace \
docker compose -f docker-compose.prod.yml up -d --build --scale gateway=2
```

生产配置特性（详见 `docker-compose.prod.yml`）：
- gateway 2 副本（`deploy.replicas: 2`）
- CPU/内存资源限制
- `/health` 健康检查（start_period/interval/timeout/retries）
- 可运行的 Python gRPC sidecar 示例服务（生产中应替换为真实检测器）
- gateway 主机端口范围 `8080-8081`，避免两个单机副本争用同一端口

> 说明：`deploy.replicas` 在 Docker Compose 单机模式下需 `--scale gateway=2`
> 生效；Swarm/K8s 模式下自动生效。启动前必须设置 `OPENAI_API_KEY` 和
> `ACME_API_KEY`，示例 Compose 会在缺失时立即失败。

## 2. 构建自定义镜像

```bash
docker build -t z-safety-gateway:0.1.1 .
docker run -d -p 8080:8080 \
  -v $(pwd)/config/gateway.yaml:/app/config/gateway.yaml:ro \
  -e OPENAI_API_KEY=sk-... \
  z-safety-gateway:0.1.1
```

## 3. 生产建议

### 3.1 认证与网络

- 开启 `security.auth`（API key）
- 启用 TLS（`security.tls` 或前置反向代理如 Nginx/ALB 终止 TLS）
- 网关与 gRPC sidecar 间建议启用 mTLS（v0.2.0 路线图提供原生支持；当前可用 sidecar 侧自校验）

### 3.2 资源与容量

参考 [DESIGN.md 14. Performance Targets](../DESIGN.md#14-performance-targets)：

| 场景 | 参考 |
|------|------|
| 纯规则检测 | 1000 req/s / 实例，内存 < 256MB |
| 含 ML 检测（toxicity） | 200 req/s / 实例，内存 < 1GB |

按负载横向扩容（无状态，可任意加副本）。

### 3.3 日志与审计

- 生产示例启用审计并将 `audit.file.path=/var/log/safety-gateway` 挂载到
  `gateway-logs` 持久卷；文件为 JSONL 并按日轮转
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
      acme-guard:
        condition: service_healthy
  acme-guard:
    build:
      context: .
      dockerfile: examples/plugins/python-grpc/Dockerfile
    image: z-safety-acme-example:1.0.0
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
| `/ready` 返回 503 | 查看响应中的 detector `issues`；required/fail-closed 检测器不可用时实例不会接收业务流量 |
| `/ready` 返回 200 且 `degraded: true` | optional fail-open 检测器不可用；流量会继续，但该检测器会被跳过，检查 lifecycle 审计与 `safety_detector_up` |
| 检测器未生效 | `zlg detectors list` 确认注册；配置 `enabled: true` |
| gRPC 检测器 ERROR 日志 | sidecar 未启动或 HealthCheck 非 serving，`zlg detectors check-connection` |
| 限流误触发 | `security.rate_limit` 调参 |
| 审计日志缺失 | `audit.enabled`、`audit.file.enabled` 已开启，且 `audit.file.path` 目录可写 |

编排探针应将 `/health` 用作 liveness、`/ready` 用作 readiness。不要用
`/health` 判断安全能力是否完整；它只表示进程仍在服务。required 检测器初始化失败时
进程拒绝启动，optional fail-closed 故障则保留可诊断但 not-ready 的实例。

## 6. 升级

- 配置向后兼容 v0.0.5（旧版 `pipeline.detectors` 平铺格式自动迁移）
- 升级前备份 `config/` 与 `logs/`
- 滚动发布：先起新版本实例，健康检查通过后摘除旧实例
