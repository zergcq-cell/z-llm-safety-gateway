# Detector 开发指南（Plugin Development Guide）

> 适用版本：v0.5.0（Plugin Ecosystem）
> 配套：`examples/plugins/python-inprocess/`（in-process 示例）、`examples/plugins/python-grpc/`（gRPC 示例）

本指南说明如何为 z LLM Safety Gateway 开发第三方检测器。两种模式：

| 维度 | In-process 插件 | gRPC Sidecar |
|------|-----------------|--------------|
| 运行位置 | 网关进程内 | 独立进程（任意语言） |
| 通信 | Python 直接方法调用 | gRPC（protobuf 合约） |
| 适用 | 纯 Python、无外部依赖、信任的代码 | 隔离、非 Python 语言、独立扩缩容 |
| 依赖 | `z-llm-safety-gateway-sdk` | 无（任何 gRPC 语言栈） |
| 故障影响 | 崩溃影响网关进程 | 由 circuit breaker / on_error 策略隔离 |

## 1. 快速开始（in-process）

### 1.1 用 SDK 脚手架生成项目

```bash
pip install z-llm-safety-gateway-sdk
zlg-sdk new my-detector --type python
cd my-detector
```

### 1.2 实现 Detector

```python
from z_llm_safety_gateway_sdk import Detector, DetectionContext, DetectionResult


class MyDetector(Detector):
    name = "my_detector"          # 注册名（YAML 中引用）
    category = "custom"           # 分类标签
    description = "What it does"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        # config = YAML detectors[].config（透传）
        self.threshold = config.get("threshold", 0.8)

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        # context: direction/request_id/user_id/metadata/language/message_index
        if self.is_unsafe(content):
            return DetectionResult(
                detector_name=self.name, category=self.category,
                action="block", confidence=0.9, risk_level="high",
                message="unsafe content", details={"rule": "r1"},
            )
        return DetectionResult(
            detector_name=self.name, category=self.category,
            action="allow", confidence=0.0, risk_level="low", message="ok",
        )
```

**action 取值**：`allow`（放行）/ `block`（阻断）/ `flag`（标记）/ `modify`（替换，需同时设置 `modified_content`）。

### 1.3 注册 entry point

`pyproject.toml`：

```toml
[project.entry-points."z_llm_safety_gateway.detectors"]
my_detector = "my_detector.detector:MyDetector"
```

网关启动时自动发现并注册。`zlg detectors list` 应能看到它。

### 1.4 配置

```yaml
pipeline:
  detectors:
    input:
      - name: my_detector
        enabled: true
        config:
          threshold: 0.9          # 你的自定义字段
```

## 2. 快速开始（gRPC sidecar）

```bash
zlg-sdk new my-detector --type grpc --language python
```

实现 `DetectorService` v1（合约见 `proto/detector/v1/detector.proto`）：

- `Initialize(InitializeRequest) → InitializeResponse`：接收透传配置，返回 `DetectorInfo`（name/category/version 等）
- `Detect(DetectRequest) → DetectResponse`：核心检测逻辑
- `HealthCheck → HealthCheckResponse`：`serving` = 进程存活（网关在 Initialize 之前先 HealthCheck）
- `Shutdown → ShutdownResponse`：网关停机时调用

**关键映射规则**：

| DetectRequest | 来源 |
|---------------|------|
| `content` | 待检测文本 |
| `direction` | `input` / `output` |
| `request_id` / `user_id` / `language` / `message_index` / `metadata` | DetectionContext |

| DetectResponse | 映射到 DetectionResult |
|----------------|------------------------|
| `action` / `confidence` / `risk_level` / `message` | 对应字段 |
| `modified_content` | `action=modify` 时生效 |
| `details`（google.protobuf.Struct） | 任意 JSON 详情 |

配置示例：

```yaml
pipeline:
  detectors:
    input:
      - name: my_grpc_detector
        type: grpc
        enabled: true
        config:
          endpoint: "localhost:50051"   # 网关内部字段，不透传
          api_key: "sk-..."              # 透传给 InitializeRequest.config
          any_vendor_field: "value"      # 透传
```

## 3. 测试

SDK 提供测试工具（`z_llm_safety_gateway_sdk.testing`）：

```python
from z_llm_safety_gateway_sdk.testing import make_context, assert_allowed, assert_blocked

async def test_my_detector():
    det = MyDetector()
    await det.initialize({"threshold": 0.8})
    result = await det.detect("safe input", make_context())
    assert_allowed(result)
```

- `make_context()`：构造测试上下文（自动生成 request_id）
- `assert_allowed` / `assert_blocked` / `assert_confidence`：结果断言

gRPC 插件测试：参考 `examples/plugins/python-grpc/tests/test_server.py`，in-process 起服务后用网关 `GRPCDetector` 客户端驱动完整生命周期。

## 4. 发布与注册

1. 打包：`python -m build`（in-process 需声明 entry point；gRPC 无此要求）
2. 安装：`pip install your-detector-package`（in-process 必须装进网关同一 Python 环境）
3. 网关侧：配置中按 `name` 启用即可。in-process 插件未安装时，配置校验报错会提示"ensure the package is installed or use type: grpc"

## 5. 最佳实践

- **幂等**：`initialize()` 可被重复调用；`detect()` 无副作用
- **超时**：detect 不应超过配置的超时（`security.timeout.detector`，默认注入 `timeout_seconds`）；gRPC 服务端超时由网关 `asyncio.wait_for` 强制
- **错误处理**：抛异常会被网关捕获并按 `on_error` 策略处理（fail_open/fail_closed/fail_fixed）；建议返回 `action="flag"` + 低置信度而不是抛异常
- **日志**：gRPC 插件建议结构化日志（JSON），便于与网关日志关联（request_id）
- **安全**：in-process 插件与网关同权限，只安装可信包；sidecar 建议独立账号 + 最小权限 + TLS（见 grpc-integration.md）
- **版本**：SDK 采用 `major.minor` 兼容约定，插件声明 `z-llm-safety-gateway-sdk>=1.0,<2.0` 即可
