# v0.5.0 测试方案与详细案例

> 版本：v0.5.0（Plugin Ecosystem）
> 创建日期：2026-08-14
> 对应 Phase 2 Spec（7 capabilities / 28 scenarios）：
> - `specs/plugin-loader/spec.yaml`（3 REQ / 3 SC）
> - `specs/grpc-sidecar/spec.yaml`（6 REQ / 6 SC）
> - `specs/detector-sdk/spec.yaml`（6 REQ / 6 SC）
> - `specs/plugin-cli/spec.yaml`（4 REQ / 4 SC）
> - `specs/config-system/spec.yaml`（3 REQ / 3 SC）
> - `specs/detector-framework/spec.yaml`（3 REQ / 3 SC）
> - `specs/fastapi-server/spec.yaml`（3 REQ / 3 SC）

## 一、测试策略

### 1.1 测试金字塔

v0.5.0 以单元测试为主（entry points 发现 mock、GRPCDetector 映射、SDK 接口校验、CLI 子命令），辅以集成测试（in-process 插件通过真实 entry point 加载、gRPC 用内存/in-process server 验证完整生命周期、create_app 集成插件初始化）。gRPC 侧车测试采用 fake gRPC server（同进程起 server）避免外部依赖。

### 1.2 测试原则

- 严格 TDD：RED（写失败测试）→ GREEN（最小实现）→ REFACTOR
- entry points 发现通过 monkeypatch `importlib.metadata.entry_points` 模拟，不依赖真实 pip install
- gRPC 测试用 `grpc` in-process server（`grpc.server` + 测试 stub），不启动真实 sidecar 进程
- SDK CLI 测试用 `capsys`/`monkeypatch.sys_argv` 验证子命令行为，模板生成到 tmp_path
- protobuf 生成代码一致性：验证脚本重新生成后 diff 为空
- 所有新增配置校验向后兼容（v0.1.0~v0.4.0 配置无需修改即可加载）

### 1.3 已有测试资产

| 测试文件 | 用例数 | 类型 | 覆盖范围 |
|----------|--------|------|----------|
| tests/unit/detectors/test_registry.py | 若干 | 单元 | DetectorRegistry 注册/查找/初始化 |
| tests/unit/detectors/test_base.py | 若干 | 单元 | Detector 基类接口 |
| tests/unit/config/test_v4_security.py | 若干 | 单元 | v0.4.0 配置模型 |
| tests/unit/test_v4_fastapi_server.py | 14 | 单元/集成 | create_app 中间件链/检测器配置注入 |
| tests/unit/config/test_validators.py | 若干 | 单元 | 配置校验规则 |
| tests/integration/test_chat.py | 6 | 集成 | 非流式 chat 转发 |
| tests/integration/test_pipeline_flow.py | 若干 | 集成 | pipeline 全流程 |

> v0.5.0 的 plugin-loader、grpc-sidecar、detector-sdk、plugin-cli 均为新增能力，对应测试全部「测试缺」；config-system、detector-framework、fastapi-server 为修改类，需在既有资产上补充断言。

## 二、详细测试案例

TC-ID 规则：`TC-<CAPABILITY缩写>-<NNN>`，全局唯一。缩写：PL / GRPC / SDK / CLI / CFG / DF / FSA。每个 spec scenario 至少映射 1 个 TC。

### 功能 1：In-process 插件加载器（plugin-loader）

#### 案例 1.1 — entry points 发现并注册

| 字段 | 内容 |
|------|------|
| **ID** | TC-PL-001 |
| **对应 Spec** | plugin-loader/spec.yaml → SC-PL-001 |
| **优先级** | P0 |
| **预置条件** | monkeypatch entry_points 返回含 `my_detector:module:MyDetector` 的 EntryPoint |
| **输入** | PluginLoader 执行 entry points 扫描 |
| **预期结果** | 发现并解析插件类，注册到 DetectorRegistry；可用 name 引用 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.2 — entry point 解析失败跳过不阻断

| 字段 | 内容 |
|------|------|
| **ID** | TC-PL-002 |
| **对应 Spec** | plugin-loader/spec.yaml → SC-PL-001 |
| **优先级** | P1 |
| **预置条件** | 一个 entry point 指向不存在的模块/类 |
| **输入** | PluginLoader 扫描 |
| **预期结果** | 记录警告日志并跳过；其余 entry points 正常注册 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.3 — 未知检测器名报错含可用列表

| 字段 | 内容 |
|------|------|
| **ID** | TC-PL-003 |
| **对应 Spec** | plugin-loader/spec.yaml → SC-PL-002 |
| **优先级** | P0 |
| **预置条件** | 配置引用未知检测器 'xxx'（非内置、非插件、非 grpc） |
| **输入** | 配置校验运行 |
| **预期结果** | 报错含 `Unknown detector 'xxx'`、可用列表、第三方提示 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.4 — 插件加载失败不影响内置检测器

| 字段 | 内容 |
|------|------|
| **ID** | TC-PL-004 |
| **对应 Spec** | plugin-loader/spec.yaml → SC-PL-003 |
| **优先级** | P1 |
| **预置条件** | 环境存在损坏的 entry point |
| **输入** | 内置注册 + 插件加载 |
| **预期结果** | 内置检测器全部正常；加载失败记录结构化警告日志 |
| **当前状态** | ❌ 测试缺 |

### 功能 2：gRPC Sidecar（grpc-sidecar）

#### 案例 2.1 — initialize 执行 HealthCheck + Initialize 读取 DetectorInfo

| 字段 | 内容 |
|------|------|
| **ID** | TC-GRPC-001 |
| **对应 Spec** | grpc-sidecar/spec.yaml → SC-GRPC-001 |
| **优先级** | P0 |
| **预置条件** | in-process gRPC server（stub 返回 serving + success + DetectorInfo） |
| **输入** | GRPCDetector.initialize(config) |
| **预期结果** | 先 HealthCheck 后 Initialize；DetectorInfo 的 name/category/version 更新实例属性 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.2 — HealthCheck 非 serving 或 Initialize 失败抛异常

| 字段 | 内容 |
|------|------|
| **ID** | TC-GRPC-002 |
| **对应 Spec** | grpc-sidecar/spec.yaml → SC-GRPC-001 |
| **优先级** | P0 |
| **预置条件** | stub 返回 not_serving |
| **输入** | initialize() |
| **预期结果** | 抛出初始化失败异常 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.3 — detect 请求/响应映射

| 字段 | 内容 |
|------|------|
| **ID** | TC-GRPC-003 |
| **对应 Spec** | grpc-sidecar/spec.yaml → SC-GRPC-002 |
| **优先级** | P0 |
| **预置条件** | stub 返回 block 响应（含 details Struct） |
| **输入** | detect(content, context) |
| **预期结果** | DetectRequest 字段正确；DetectionResult 映射正确（含 details 转换） |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.4 — modify 响应透传 modified_content

| 字段 | 内容 |
|------|------|
| **ID** | TC-GRPC-004 |
| **对应 Spec** | grpc-sidecar/spec.yaml → SC-GRPC-002 |
| **优先级** | P1 |
| **预置条件** | stub 返回 action=modify + modified_content |
| **输入** | detect() |
| **预期结果** | DetectionResult.action=modify 且 modified_content 透传 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.5 — shutdown 与 health_check

| 字段 | 内容 |
|------|------|
| **ID** | TC-GRPC-005 |
| **对应 Spec** | grpc-sidecar/spec.yaml → SC-GRPC-003 |
| **优先级** | P1 |
| **预置条件** | 已初始化 GRPCDetector |
| **输入** | shutdown() / health_check() |
| **预期结果** | Shutdown 被调用、通道关闭；health_check 按 serving 返回 True/False |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.6 — gRPC 调用超时

| 字段 | 内容 |
|------|------|
| **ID** | TC-GRPC-006 |
| **对应 Spec** | grpc-sidecar/spec.yaml → SC-GRPC-004 |
| **优先级** | P0 |
| **预置条件** | stub 延迟响应超过 timeout（短超时注入） |
| **输入** | detect() |
| **预期结果** | 超时后抛异常（携带检测器名与超时时长） |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.7 — TLS secure_channel 与 CA 加载

| 字段 | 内容 |
|------|------|
| **ID** | TC-GRPC-007 |
| **对应 Spec** | grpc-sidecar/spec.yaml → SC-GRPC-005 |
| **优先级** | P1 |
| **预置条件** | tls_enabled=true + tls_ca_file 指向测试 CA |
| **输入** | 建立通道 |
| **预期结果** | 使用 secure_channel 与 CA 凭证；tls_enabled=false 用 insecure_channel |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.8 — grpcio 未安装报清晰错误

| 字段 | 内容 |
|------|------|
| **ID** | TC-GRPC-008 |
| **对应 Spec** | grpc-sidecar/spec.yaml → SC-GRPC-006 |
| **优先级** | P1 |
| **预置条件** | monkeypatch 移除 grpcio |
| **输入** | 实例化 GRPCDetector |
| **预期结果** | 错误信息含 `pip install z-llm-safety-gateway[grpc]` 指引 |
| **当前状态** | ❌ 测试缺 |

### 功能 3：Detector SDK（detector-sdk）

#### 案例 3.1 — SDK 包结构完整

| 字段 | 内容 |
|------|------|
| **ID** | TC-SDK-001 |
| **对应 Spec** | detector-sdk/spec.yaml → SC-SDK-001 |
| **优先级** | P0 |
| **预置条件** | sdk/ 包 |
| **输入** | 检查包结构 |
| **预期结果** | base/context/result/modification/testing/cli 模块存在；__init__ re-export；独立版本 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.2 — SDK 接口与网关一致

| 字段 | 内容 |
|------|------|
| **ID** | TC-SDK-002 |
| **对应 Spec** | detector-sdk/spec.yaml → SC-SDK-002 |
| **优先级** | P0 |
| **预置条件** | SDK Detector 子类 |
| **输入** | 与网关 Detector 接口比对 |
| **预期结果** | 接口字段一致（DetectionResult/DetectionContext 字段匹配网关） |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.3 — zlg-sdk new 生成可运行模板

| 字段 | 内容 |
|------|------|
| **ID** | TC-SDK-003 |
| **对应 Spec** | detector-sdk/spec.yaml → SC-SDK-003 |
| **优先级** | P0 |
| **预置条件** | tmp_path 目录 |
| **输入** | `zlg-sdk new my-detector --type python` |
| **预期结果** | 生成 pyproject.toml（含 entry points）+ detector.py + tests/；项目可被网关发现 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.4 — zlg-sdk new grpc 模板

| 字段 | 内容 |
|------|------|
| **ID** | TC-SDK-004 |
| **对应 Spec** | detector-sdk/spec.yaml → SC-SDK-003 |
| **优先级** | P1 |
| **预置条件** | tmp_path 目录 |
| **输入** | `zlg-sdk new my-detector --type grpc --language python` |
| **预期结果** | 生成含 gRPC 服务端模板的项目 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.5 — zlg-sdk validate

| 字段 | 内容 |
|------|------|
| **ID** | TC-SDK-005 |
| **对应 Spec** | detector-sdk/spec.yaml → SC-SDK-004 |
| **优先级** | P1 |
| **预置条件** | 合法/非法检测器项目 |
| **输入** | `zlg-sdk validate ./proj` |
| **预期结果** | 合法退出码 0；非法退出码非 0 且输出错误详情 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.6 — SDK testing 工具

| 字段 | 内容 |
|------|------|
| **ID** | TC-SDK-006 |
| **对应 Spec** | detector-sdk/spec.yaml → SC-SDK-005 |
| **优先级** | P1 |
| **预置条件** | SDK testing 模块 |
| **输入** | make_context + 断言辅助 |
| **预期结果** | make_context 提供默认值；断言辅助校验 action/risk_level/confidence |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.7 — SDK 版本不匹配警告

| 字段 | 内容 |
|------|------|
| **ID** | TC-SDK-007 |
| **对应 Spec** | detector-sdk/spec.yaml → SC-SDK-006 |
| **优先级** | P2 |
| **预置条件** | 插件依赖 SDK 版本与网关兼容范围不一致 |
| **输入** | 网关启动加载插件 |
| **预期结果** | 记录 SDK 版本不匹配警告日志 |
| **当前状态** | ❌ 测试缺 |

### 功能 4：插件管理 CLI（plugin-cli）

#### 案例 4.1 — zlg detectors list

| 字段 | 内容 |
|------|------|
| **ID** | TC-CLI-001 |
| **对应 Spec** | plugin-cli/spec.yaml → SC-CLI-001 |
| **优先级** | P0 |
| **预置条件** | 内置检测器 + mock 插件已注册 |
| **输入** | `zlg detectors list` |
| **预期结果** | 输出全部检测器；--enabled 仅输出启用项；退出码 0 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.2 — zlg detectors info

| 字段 | 内容 |
|------|------|
| **ID** | TC-CLI-002 |
| **对应 Spec** | plugin-cli/spec.yaml → SC-CLI-002 |
| **优先级** | P1 |
| **预置条件** | 注册了 prompt_injection |
| **输入** | `zlg detectors info prompt_injection` |
| **预期结果** | 输出 name/category/description/version；未知名报错退出码非 0 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.3 — zlg detectors test

| 字段 | 内容 |
|------|------|
| **ID** | TC-CLI-003 |
| **对应 Spec** | plugin-cli/spec.yaml → SC-CLI-003 |
| **优先级** | P0 |
| **预置条件** | 已配置检测器 |
| **输入** | `zlg detectors test prompt_injection --input '...'` |
| **预期结果** | 输出 DetectionResult（action/risk_level/confidence/message） |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.4 — zlg detectors check-connection

| 字段 | 内容 |
|------|------|
| **ID** | TC-CLI-004 |
| **对应 Spec** | plugin-cli/spec.yaml → SC-CLI-004 |
| **优先级** | P1 |
| **预置条件** | type=grpc 检测器 + in-process gRPC server |
| **输入** | `zlg detectors check-connection acme_guard` |
| **预期结果** | 输出 serving 状态；失败退出码非 0 |
| **当前状态** | ❌ 测试缺 |

### 功能 5：配置系统扩展（config-system）

#### 案例 5.1 — type=grpc 配置解析与字段分离

| 字段 | 内容 |
|------|------|
| **ID** | TC-CFG-501 |
| **对应 Spec** | config-system/spec.yaml → SC-CFG-501 |
| **优先级** | P0 |
| **预置条件** | type=grpc + config（endpoint/api_key/sensitivity） |
| **输入** | GatewayConfig 加载 |
| **预期结果** | type=grpc 被接受；endpoint/tls_enabled/tls_ca_file 标记网关内部字段；其余透传 |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.2 — grpc 缺 endpoint 报错

| 字段 | 内容 |
|------|------|
| **ID** | TC-CFG-502 |
| **对应 Spec** | config-system/spec.yaml → SC-CFG-502 |
| **优先级** | P0 |
| **预置条件** | type=grpc 但无 endpoint |
| **输入** | 配置校验 |
| **预期结果** | 报错 `gRPC detector 'xxx' is missing required config: endpoint` |
| **当前状态** | ❌ 测试缺 |

#### 案例 5.3 — grpc 无 circuit_breaker 提示 Info

| 字段 | 内容 |
|------|------|
| **ID** | TC-CFG-503 |
| **对应 Spec** | config-system/spec.yaml → SC-CFG-503 |
| **优先级** | P1 |
| **预置条件** | type=grpc 无 circuit_breaker |
| **输入** | 网关启动 |
| **预期结果** | Info 日志提示；不阻断启动 |
| **当前状态** | ❌ 测试缺 |

### 功能 6：检测器框架扩展（detector-framework）

#### 案例 6.1 — register_from_entry_points

| 字段 | 内容 |
|------|------|
| **ID** | TC-DF-501 |
| **对应 Spec** | detector-framework/spec.yaml → SC-DF-501 |
| **优先级** | P0 |
| **预置条件** | registry + mock entry points |
| **输入** | register_from_entry_points(group='...') |
| **预期结果** | 插件注册成功；同名不覆盖；list() 包含插件名 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.2 — create_app 集成插件发现

| 字段 | 内容 |
|------|------|
| **ID** | TC-DF-502 |
| **对应 Spec** | detector-framework/spec.yaml → SC-DF-502 |
| **优先级** | P0 |
| **预置条件** | monkeypatch entry points + create_app |
| **输入** | 初始化默认 registry 后加载插件 |
| **预期结果** | 内置 + 插件全部注册；插件失败不影响内置 |
| **当前状态** | ❌ 测试缺 |

#### 案例 6.3 — type=grpc 创建 GRPCDetector

| 字段 | 内容 |
|------|------|
| **ID** | TC-DF-503 |
| **对应 Spec** | detector-framework/spec.yaml → SC-DF-503 |
| **优先级** | P0 |
| **预置条件** | config 含 type=grpc 检测器 + in-process gRPC server |
| **输入** | 初始化检测器 |
| **预期结果** | 创建 GRPCDetector 并 initialize；满足 Detector 接口 |
| **当前状态** | ❌ 测试缺 |

### 功能 7：FastAPI 集成（fastapi-server）

#### 案例 7.1 — create_app 集成插件 + gRPC 初始化

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-501 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-501 |
| **优先级** | P0 |
| **预置条件** | mock 插件 entry points + type=grpc 配置 + in-process gRPC server |
| **输入** | create_app(config_path) |
| **预期结果** | app.state 检测器集合含内置+插件+gRPC；加载失败不阻断 |
| **当前状态** | ❌ 测试缺 |

#### 案例 7.2 — 插件/gRPC 检测器接入 pipeline 与审计指标

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-502 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-502 |
| **优先级** | P0 |
| **预置条件** | 插件 + gRPC 检测器已配置，发起请求 |
| **输入** | input/output pipeline 运行 |
| **预期结果** | 插件与 gRPC 检测器被调用；结果进聚合器、审计、指标 |
| **当前状态** | ❌ 测试缺 |

#### 案例 7.3 — lifespan shutdown 关闭 gRPC 通道

| 字段 | 内容 |
|------|------|
| **ID** | TC-FSA-503 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-FSA-503 |
| **优先级** | P1 |
| **预置条件** | 已初始化 gRPC 检测器 |
| **输入** | lifespan shutdown |
| **预期结果** | 每个 gRPC 检测器 shutdown() 被调用；单失败不阻断整体 |
| **当前状态** | ❌ 测试缺 |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 集成测试 | E2E | 状态 |
|----------|---------|----------|-----|------|
| In-process 插件加载器 | ✅ | ✅ | ❌ | 🟡 |
| gRPC Sidecar | ✅ | ✅ | ❌ | 🟡 |
| Detector SDK | ✅ | ❌ | ❌ | 🟡 |
| 插件管理 CLI | ✅ | ❌ | ❌ | 🟡 |
| 配置系统扩展 | ✅ | ❌ | ❌ | 🟡 |
| 检测器框架扩展 | ✅ | ✅ | ❌ | 🟡 |
| FastAPI 集成 | ✅ | ✅ | ❌ | 🟡 |

## 四、回归风险矩阵

| 风险区域 | v0.5.0 改动 | 已有回归保护 | 风险等级 |
|----------|-------------|-------------|---------|
| detectors/registry.py | 新增 register_from_entry_points | test_registry.py | 🟡 |
| detectors/__init__.py | create_default_registry 扩展 | 现有 detector 测试 | 🟡 |
| config/validators.py | type=grpc 校验（endpoint 必填） | test_validators.py | 🔴 |
| config/models.py | DetectorConfig.type 语义扩展 | test_v4_security.py | 🟢 |
| app.py / create_app | 插件加载 + gRPC 初始化 | test_app.py、test_v4_fastapi_server.py | 🔴 |
| app.py lifespan | gRPC 通道关闭 | test_main_tls.py（lifespan） | 🟡 |
| pyproject.toml | [grpc] 可选依赖 + zlg/zlg-sdk 脚本 | -- | 🟡 |
| sdk/（新目录） | 独立包，不改网关 | -- | 🟢 |

## 五、建议补充顺序

1. **第一优先**（部署前必补，P0）：
   - 插件加载：TC-PL-001/003、TC-DF-501/502/503、TC-FSA-501/502
   - gRPC：TC-GRPC-001/002/003/006
   - SDK：TC-SDK-001/002/003
   - CLI：TC-CLI-001/003
   - 配置：TC-CFG-501/502
2. **第二优先**（部署后尽快补，P1）：
   - 插件加载：TC-PL-002/004
   - gRPC：TC-GRPC-004/005/007/008
   - SDK：TC-SDK-004/005/006
   - CLI：TC-CLI-002/004
   - 配置：TC-CFG-503
   - FastAPI：TC-FSA-503
3. **第三优先**（后续补，P2）：
   - TC-SDK-007（SDK 版本不匹配警告）
