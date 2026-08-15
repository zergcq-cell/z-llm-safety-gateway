# detector-sdk - 行为规格（Human View）

> **Change**: 2026-08-14-v0.5.0-plugin-ecosystem
> **Capability**: detector-sdk
> **Created**: 2026-08-14T10:30:00+08:00
> **Confidence**: high

## Requirements

### REQ-SDK-001: SDK 独立包结构：Detector 基类、DetectionContext、DetectionResult、Modification、testing、cli

#### SC-SDK-001: high

- **Given**: sdk/ 目录下的 z_llm_safety_gateway_sdk 包
- **When**: 检查包结构
- **Then**: SDK 包 SHALL 包含 base.py（Detector 抽象基类）、context.py、result.py、modification.py、testing.py、cli.py
- **And**: SDK 包根 __init__.py SHALL re-export Detector/DetectionContext/DetectionResult/Modification
- **And**: SDK pyproject.toml SHALL 独立版本号（1.0.0）且不依赖网关包

### REQ-SDK-002: Detector 基类接口与网关 Detector 一致（name/category/description/version/initialize/detect）

#### SC-SDK-002: high

- **Given**: 第三方检测器继承 SDK 的 Detector 基类并实现接口
- **When**: SDK Detector 子类被网关 entry point 加载
- **Then**: SDK Detector 基类 SHALL 定义与网关一致的接口（initialize(config)/detect(content, context)）
- **And**: SDK DetectionResult 字段 SHALL 与网关一致（detector_name/category/action/confidence/risk_level/message/details/modified_content）
- **And**: SDK DetectionContext 字段 SHALL 与网关一致（direction/request_id/user_id/metadata/language/message_index）

### REQ-SDK-003: SDK CLI：zlg-sdk new 生成可运行项目模板（python in-process / grpc）

#### SC-SDK-003: high

- **Given**: 执行 zlg-sdk new my-detector --type python
- **When**: 生成项目模板
- **Then**: CLI SHALL 生成含 pyproject.toml（含 entry points 声明）、detector.py、tests/ 的可运行项目目录
- **And**: --type grpc --language python 时 SHALL 生成含 gRPC 服务端模板的项目
- **And**: 生成的项目 SHALL 可被网关 entry point 机制发现（配置入口点）

### REQ-SDK-004: SDK CLI：zlg-sdk validate 校验检测器实现

#### SC-SDK-004: high

- **Given**: 一个检测器项目目录（含 Detector 子类）
- **When**: 执行 zlg-sdk validate ./my-detector
- **Then**: CLI SHALL 校验检测器实现是否为合法 Detector 子类（接口完整）
- **And**: 合法实现 SHALL 退出码 0 并输出通过信息
- **And**: 非法实现（缺方法/属性）SHALL 退出码非 0 并输出错误详情

### REQ-SDK-005: SDK testing 工具：mock context 与断言辅助

#### SC-SDK-005: high

- **Given**: 检测器开发者编写单元测试
- **When**: 使用 SDK testing 工具
- **Then**: SDK SHALL 提供 make_context（构造测试 DetectionContext）与结果断言辅助函数
- **And**: make_context SHALL 提供默认值（direction=input, request_id 自动生成）
- **And**: 断言辅助 SHALL 支持校验 action/risk_level/confidence 范围

### REQ-SDK-006: SDK 版本兼容：网关声明兼容范围并警告不匹配

#### SC-SDK-006: high

- **Given**: 加载的插件依赖的 SDK 版本与网关声明兼容范围（>=1.0,<2.0）不一致
- **When**: 网关启动加载插件
- **Then**: 网关 SHALL 记录警告日志提示 SDK 版本不匹配

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-SDK-001 | SDK 包 SHALL 包含 base.py（Detector 抽象基类）、context.py、result.py、m |
| CP-2 | SC-SDK-002 | SDK Detector 基类 SHALL 定义与网关一致的接口（initialize(config)/detect(c |
| CP-3 | SC-SDK-003 | CLI SHALL 生成含 pyproject.toml（含 entry points 声明）、detector.py、 |
| CP-4 | SC-SDK-004 | CLI SHALL 校验检测器实现是否为合法 Detector 子类（接口完整） |
| CP-5 | SC-SDK-005 | SDK SHALL 提供 make_context（构造测试 DetectionContext）与结果断言辅助函数 |
| CP-6 | SC-SDK-006 | 网关 SHALL 记录警告日志提示 SDK 版本不匹配 |
| CP-7 | -- | ruff lint 通过 |
| CP-8 | -- | mypy 类型检查通过 |
