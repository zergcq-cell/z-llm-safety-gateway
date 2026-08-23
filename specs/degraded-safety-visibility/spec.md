# Degraded Safety Visibility

## Requirements

- `REQ-DSV-001`：fail-open 继续与 fail-closed 拒绝都必须留下请求级降级证据。
- `REQ-DSV-002`：API、日志、审计与指标只暴露稳定、低基数、脱敏字段。

`safety_degraded` 与确定排序的 `detector_availability` 是请求审计的公开降级证据；
endpoint、凭据、敏感正文和原始异常不得进入外部信号。


<!-- 合并自 2026-08-22-v0.2.0-flow-foundation -->
# Capability: degraded-safety-visibility

## ADDED / MODIFIED Requirements

- **REQ-DSV-701**：请求级 Flow snapshot 在全部阶段一致暴露 fail-open 降级（2 scenarios）
- **REQ-DSV-702**：每种降级原因和适用策略均可解释且不泄密（1 scenarios）

## Verification

- Canonical spec: `canonical/specs/code/degraded-safety-visibility.yaml`
- Agent checkpoints: `canonical/specs/agent/degraded-safety-visibility.yaml`
- Test cases: 3
