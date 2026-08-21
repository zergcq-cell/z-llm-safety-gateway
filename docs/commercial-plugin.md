# 商业插件指南（Commercial Plugin Guide）

> 适用版本：v0.1.1
> 许可证：网关与 SDK 均为 Apache License 2.0

本指南面向希望通过第三方检测器商业化的团队：如何基于 SDK / gRPC 合约构建、打包、授权并销售检测器插件。

## 1. 商业模式概览

| 模式 | 说明 | 适用 |
|------|------|------|
| 闭源 sidecar | 检测逻辑在 sidecar 进程内，网关仅通过 gRPC 调用 | 保护核心算法（推荐） |
| 开源源码插件 | in-process 插件，源码公开 | 社区贡献、生态建设 |
| SaaS 托管检测 | sidecar 部署在你的基础设施，网关远程调用 | 多租户云服务 |

**建议**：商业检测器优先采用 **gRPC sidecar** 模式——算法不出进程、可独立授权与计量、语言自由。

## 2. SDK 许可与合规

- 网关与 SDK 采用 **Apache 2.0**：可自由使用、修改、商用，但需保留版权声明
- 基于 SDK 开发的检测器**不要求**开放源代码（Apache 2.0 允许闭源衍生作品）
- 若修改 SDK 本身并再分发，需保留 Apache 2.0 声明
- 网关的 entry point 机制不构成对插件包的代码审查——商业插件应自行保证合规

## 3. 打包与分发

### 3.1 in-process 插件

```toml
[project]
name = "acme-detector"
version = "1.0.0"
dependencies = [
  "z-llm-safety-gateway-sdk @ https://github.com/zergcq-cell/z-llm-safety-gateway/releases/download/v0.1.1/z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl"
]

[project.entry-points."z_llm_safety_gateway.detectors"]
acme_detector = "acme_detector.detector:AcmeDetector"
```

分发：PyPI（公开）或私有 index（商业）。`pip install acme-detector` 到网关同一环境。

### 3.2 gRPC sidecar

分发产物：容器镜像（推荐）或二进制包。

```dockerfile
# Dockerfile 示例
FROM python:3.11-slim
COPY . /app
WORKDIR /app
RUN pip install .
EXPOSE 50051
CMD ["python", "-m", "acme_detector.server", "--port", "50051"]
```

```yaml
# docker-compose 片段：sidecar 与网关同网
services:
  gateway:
    image: your-gateway:latest
    depends_on: [acme-guard]
  acme-guard:
    image: acme/detector:1.0.0
    restart: unless-stopped
```

## 4. 认证与密钥

- **API key**：网关 `config.api_key` 透传给 `InitializeRequest.config`，sidecar 内校验并锁定
- **TLS**：v0.1.1 的 `tls_enabled` + `tls_ca_file` 仅验证 sidecar 服务端证书；
  双向 mTLS 仍在路线图中，当前请由服务网格或反向代理提供
- **许可证 key**：建议在 `config` 中透传 license key，`Initialize` 时校验；无效返回 `success=false`，网关记录 ERROR 并停止使用该检测器

## 5. 计量与计费（建议）

sidecar 可在 `Detect` 内计量（请求数/字符数/模型调用），通过：
- 结构化日志（每请求一行，含 request_id），网关审计日志可关联
- 独立的计量上报端点（与检测路径分离，避免影响延迟）

## 6. 支持与 SLA

| 项 | 建议 |
|----|------|
| 版本契约 | 遵循 `DetectorService` v1；破坏性变更升版本并提前通知 |
| 兼容性 | 声明 SDK 版本范围；sidecar 声明合约版本 |
| 文档 | 提供配置字段说明（透传字段语义）、阈值建议、错误码说明 |
| 健康 | 实现 `HealthCheck` 反映真实就绪状态（依赖的模型/服务不可用时应返回 not_serving） |
| 降级 | 配合网关 `circuit_breaker`（推荐 fail_open）与 `on_error` 策略设计故障行为 |

## 7. 上架建议

- 提供 `zlg-sdk validate` 通过的自检（SDK 接口合规）
- 提供 gRPC 合约兼容性自测脚本（grpcurl 或示例测试）
- 在 README 中给出网关配置片段与 `zlg detectors check-connection` 验证步骤
- 标注性能指标（延迟 P50/P95、吞吐）帮助用户做容量规划
