# plugin-loader - 行为规格（Human View）

> **Change**: 2026-08-14-v0.5.0-plugin-ecosystem
> **Capability**: plugin-loader
> **Created**: 2026-08-14T10:30:00+08:00
> **Confidence**: high

## Requirements

### REQ-PL-001: 通过 importlib.metadata 发现 z_llm_safety_gateway.detectors entry points 并注册到 DetectorRegistry

#### SC-PL-001: high

- **Given**: 环境安装了包含 entry point z_llm_safety_gateway.detectors 的第三方包（值格式 module:ClassName）
- **When**: PluginLoader 执行 entry points 扫描
- **Then**: PluginLoader SHALL 通过 importlib.metadata.entry_points(group='z_llm_safety_gateway.detectors') 发现所有已注册插件
- **And**: 每个插件 SHALL 按 <module>:<ClassName> 解析并实例化为 Detector 子类
- **And**: 解析成功的插件 SHALL 注册到 DetectorRegistry，可用 detector name 引用
- **And**: 解析失败的插件 SHALL 记录警告日志并跳过，不阻断其他插件注册

### REQ-PL-002: 未知检测器名报错信息增强（含可用列表与第三方提示）

#### SC-PL-002: high

- **Given**: 配置引用了一个既非内置、又无 entry point、且 type 非 grpc 的检测器名 'xxx'
- **When**: 网关启动时校验检测器配置
- **Then**: 网关 SHALL 报错：Unknown detector 'xxx'. Available: [内置+已发现插件列表]. For third-party detectors, ensure the package is installed or use type: grpc.
- **And**: 错误信息 SHALL 包含全部可用检测器名称列表
- **And**: 错误信息 SHALL 包含第三方接入提示（安装包或使用 type: grpc）

### REQ-PL-003: entry points 发现失败不影响内置检测器

#### SC-PL-003: high

- **Given**: 环境中存在损坏的 entry point 或 import 抛异常的插件包
- **When**: create_default_registry 后执行插件加载
- **Then**: 内置检测器 SHALL 全部正常注册，不受插件加载失败影响
- **And**: 插件加载失败 SHALL 记录结构化警告日志（含插件名与错误信息）
- **And**: 加载流程 SHALL 继续处理剩余 entry points

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-PL-001 | PluginLoader SHALL 通过 importlib.metadata.entry_points(group= |
| CP-2 | SC-PL-002 | 网关 SHALL 报错：Unknown detector 'xxx'. Available: [内置+已发现插件列表]. |
| CP-3 | SC-PL-003 | 内置检测器 SHALL 全部正常注册，不受插件加载失败影响 |
| CP-4 | -- | ruff lint 通过 |
| CP-5 | -- | mypy 类型检查通过 |
