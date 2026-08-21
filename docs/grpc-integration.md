# gRPC 对接指南（gRPC Integration Guide）

> 适用版本：v0.1.1
> 合约：`proto/detector/v1/detector.proto`
> 示例：`examples/plugins/python-grpc/`、`examples/plugins/go-grpc/`

本文档说明第三方 gRPC sidecar 检测器如何与网关对接：合约、生命周期、配置、TLS、超时与调试。

## 1. 合约总览

`DetectorService` 定义 4 个 RPC（service 名 `z_llm_safety_gateway.detector.v1.DetectorService`）：

| RPC | 方向 | 调用时机 |
|-----|------|----------|
| `HealthCheck` | 网关→sidecar | 启动时、周期健康检查 |
| `Initialize` | 网关→sidecar | HealthCheck 通过后，启动时一次 |
| `Detect` | 网关→sidecar | 每个请求 |
| `Shutdown` | 网关→sidecar | 网关优雅停机 |

**消息结构**（关键字段，完整见 proto 文件）：

```protobuf
message InitializeRequest {
  string detector_name = 1;
  map<string, string> config = 2;      // 透传配置（不含 endpoint/tls_*）
}
message InitializeResponse {
  bool success = 1;
  string error_message = 2;
  DetectorInfo info = 3;               // name/category/description/version
}
message DetectRequest {
  string content = 1;
  string direction = 2;                // "input" | "output"
  string request_id = 3;
  string user_id = 4;
  string language = 5;
  int32 message_index = 6;             // -1 = 无
  map<string, string> metadata = 7;
}
message DetectResponse {
  string detector_name = 1;
  string category = 2;
  string action = 3;                   // allow|block|flag|modify
  float confidence = 4;
  string risk_level = 5;               // low|medium|high|critical
  string message = 6;
  string modified_content = 7;
  google.protobuf.Struct details = 8;  // 任意 JSON
}
message HealthCheckResponse { string status = 1; }   // "serving"|"not_serving"
```

## 2. 生命周期时序

```
Gateway                              Sidecar
   │   HealthCheck()                       │
   │──────────────────────────────────────>│  serving（进程存活即返回 serving）
   │<──────────────────────────────────────│
   │   Initialize(passthrough config)      │
   │──────────────────────────────────────>│  加载配置，返回 DetectorInfo
   │<──────────────────────────────────────│
   │   Detect(content, context)            │  （每个请求）
   │──────────────────────────────────────>│
   │<──────────────────────────────────────│
   │   ...                                 │
   │   Shutdown()                          │  （网关停机）
   │──────────────────────────────────────>│
```

**关键语义**：
1. `HealthCheck` 在 `Initialize` **之前**被调用——`serving` 表示进程存活可接受 RPC，不是"已初始化"
2. `Initialize` 失败（`success=false`）→ 网关记录 ERROR 日志，该检测器不运行
3. `Shutdown` 由网关 lifespan 触发，超时/失败不阻断网关停机

## 3. 配置

```yaml
pipeline:
  detectors:
    input:
      - name: my_grpc_detector
        type: grpc                    # 必须
        enabled: true
        config:
          endpoint: "localhost:50051"  # 必填；缺失则启动报错
          tls_enabled: false          # 可选，默认 false
          tls_ca_file: ""             # 可选；tls_enabled=true 时的 CA 证书路径
          api_key: "sk-..."           # 透传给 InitializeRequest.config
          sensitivity: "high"         # 透传
```

**透传规则**：`endpoint`、`tls_enabled`、`tls_ca_file` 是网关内部字段（不透传）；其余 config 字段全部透传给 `InitializeRequest.config`。

**校验规则**（启动时）：
- `type: grpc` 且缺 `endpoint` → `ConfigValidationError` 阻断启动
- `type: grpc` 无 `circuit_breaker` → UserWarning（建议配置，推荐 fail_open）

## 4. TLS

启用单向 TLS 服务端认证：`tls_enabled: true` + `tls_ca_file` 指向 sidecar CA
证书。网关用 `grpc.ssl_channel_credentials(root_certificates=CA)` 验证 sidecar
服务端证书；未配置 CA 时使用系统默认根证书。v0.1.1 不发送客户端证书，因而
不提供 mTLS；需要双向认证时应在服务网格或反向代理层终止 mTLS。

```yaml
config:
  endpoint: "sidecar.internal:50051"
  tls_enabled: true
  tls_ca_file: "/etc/gateway/certs/sidecar-ca.pem"
```

## 5. 超时

- 每个 gRPC 调用有超时：优先取检测器自身 `timeout`（YAML），回退 `security.timeout.detector`，默认 5s
- 超时由网关 `asyncio.wait_for` 强制（`asyncio.to_thread` 执行阻塞调用）
- 超时异常含检测器名与超时时长，便于定位

## 6. 调试

### 6.1 连接检查

```bash
zlg detectors check-connection my_grpc_detector --config config/gateway.yaml
# 输出 "status: serving" 或报错
```

### 6.2 本地直测

```bash
# 用 grpcurl 直接调用（sidecar 需先启动）
grpcurl -plaintext localhost:50051 list
grpcurl -plaintext -d '{}' localhost:50051 z_llm_safety_gateway.detector.v1.DetectorService/HealthCheck
```

### 6.3 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 启动报 `not serving` | sidecar 未启动或 HealthCheck 返回非 serving | 确认进程存活；HealthCheck 初始应返回 serving |
| 初始化失败 ERROR 日志 | Initialize 返回 success=false | 检查透传配置合法性 |
| Detect 超时 | 检测耗时 > 配置超时 | 调大 `timeout`，或优化检测逻辑 |
| `grpcio` 未安装 | 未装可选依赖 | 在仓库根目录执行 `pip install -e ".[grpc]"` |
| 生成代码 import 报错 | protobuf 7.x well-known type | 重新生成后需补 `from google.protobuf import struct_pb2`（见示例 gen_proto.sh 后处理） |

## 7. 版本与兼容

- 合约路径 `detector/v1/` 中的 `v1` 是合约版本；破坏性变更必须升版本
- 网关与 sidecar 之间建议做最小版本协商：`InitializeResponse.info.version` 由网关日志记录
