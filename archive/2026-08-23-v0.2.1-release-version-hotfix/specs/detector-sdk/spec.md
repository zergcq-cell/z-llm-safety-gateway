# Capability: detector-sdk

## MODIFIED Requirements

### REQ-SDK-009：Detector SDK 在 Gateway v0.2.1 发布中保持独立 0.1.1 契约

- **SC-SDK-010 · high**：Gateway 提升到 0.2.1 时，SDK package/runtime SHALL 均保持 0.1.1；SDK 内部错配仍阻断发布。
- **SC-SDK-011 · high**：SDK wheel/sdist SHALL 声明 0.1.1，wheel SHALL 在无 Gateway 包的干净环境安装并运行 `zlg-sdk --help`。
- **SC-SDK-012 · high**：SDK README、CLI 模板、插件文档和示例 direct wheel references SHALL 保持 0.1.1，不得宣传不存在的 SDK 0.2.1。

## Verification

- Canonical spec: `canonical/specs/code/detector-sdk.yaml`
- Agent checkpoints: `canonical/specs/agent/detector-sdk.yaml`
- Test cases: 3
- Compatibility anchor: existing SDK `0.1.1` package/runtime/import/install contracts
