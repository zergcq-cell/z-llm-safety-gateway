# Proposal: Example Plugins & Plugin Documentation (v0.5.1)

> 变更：2026-08-14-v0.5.1-example-plugins
> 模式：lightweight（纯增量资产，无接口变更）
> 前置：v0.5.0 Plugin Ecosystem（已交付，tag v0.5.0）

## 背景

DESIGN.md 第 18 章 Roadmap 中 v0.5.0 阶段声明了 6 项交付物，实际交付 4 项（gRPC 支持、插件加载器、SDK、CLI），尚缺：

1. **Example plugins** — 帮助第三方开发者快速上手
2. **Plugin documentation** — 开发者必须的对接资料

本次变更补齐这两项，使 v0.5.0 交付完整。

## 范围

### 示例插件（3 个，`examples/plugins/`）

| 示例 | 内容 | 验证方式 |
|------|------|----------|
| `python-inprocess/` | 自定义关键词检测器，SDK 实现 + entry points 注册 + pytest | 本机可运行验证 |
| `python-grpc/` | 完整 gRPC sidecar server（实现 DetectorService v1）+ 生成脚本 | in-process 测试验证 |
| `go-grpc/` | Go sidecar（go.mod + main.go + proto 生成说明） | 环境无 Go，源码交付 + 标注 |

### 插件文档（3 份，`docs/`）

| 文档 | 内容 |
|------|------|
| `plugin-development.md` | in-process 与 gRPC 两种模式对比、SDK 快速开始、测试、发布注册 |
| `grpc-integration.md` | proto 合约、生命周期时序、配置字段、TLS/超时、调试技巧 |
| `commercial-plugin.md` | 商业插件打包、SDK 许可（Apache 2.0）、认证、支持服务建议 |

## 验收标准

- Python in-process 示例：entry points 发现 + 检测通过（自动化测试）
- Python gRPC 示例：生命周期全流程通过（in-process gRPC 测试）
- Go 示例：源码完整、构建说明清晰（标注未验证）
- 文档与 v0.5.0 实现逐项一致（proto 字段、配置键、CLI 子命令）

## 风险

低风险。纯增量资产，不改动任何现有代码路径。主要风险是示例与文档与实现脱节——通过测试和一致性检查控制。
