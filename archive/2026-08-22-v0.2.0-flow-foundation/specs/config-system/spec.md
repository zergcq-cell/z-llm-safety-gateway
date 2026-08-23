# Capability: config-system

## ADDED / MODIFIED Requirements

- **REQ-CFG-001**：配置系统解析严格的新 Flow schema 与 stage 引用（2 scenarios）
- **REQ-CFG-002**：旧 YAML 保持加载并编译为等价 Flow（2 scenarios）
- **REQ-CFG-003**：跨 Flow 验证在启动阶段拒绝不安全或不确定配置（1 scenarios）
- **REQ-CFG-004**：安全配置文档示例由真实运行时模型反向验证（1 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/config-system.yaml`
- Agent checkpoints: `canonical/specs/agent/config-system.yaml`
- Test cases: 6
