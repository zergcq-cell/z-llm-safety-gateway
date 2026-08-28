# Python 3.11 令牌桶并发测试确定性

<!-- source_hash: a39191e46dc60c09 -->
<!-- generated_at: 2026-08-28T19:04:47.217394 -->
<!-- canonical: canonical/proposals/2026-08-28-rate-limit-deterministic-concurrency.yaml -->

## Why

TC-RL-005 把并发期间的合法持续补充误判为超额消费，导致 Python 3.11 在执行超过 1ms 时出现期望 5、实际 6 的非确定性失败。

## What Changes

- 明确并发安全契约：消费原子、token 不为负，合法成功次数必须考虑测试期间产生的补充额度。
- 为令牌桶测试建立可控的单调时钟边界，分别验证冻结时间下的并发消费和显式时间推进下的持续补充。
- 在 Python 3.10、3.11、3.12 上重复执行相关回归与完整质量门。

### Modified Capabilities

- **rate-limiting**：补充确定性的并发安全与时间推进验证，不改变公开配置或 HTTP 契约。

## Impact

**代码层面**：预计修改 2–4 个文件、50–150 行，主要涉及 `TokenBucket` 内部时间边界、限流测试和现有 rate-limiting spec。

**配置层面**：不改变 `rate`、`burst`、`per`、429 或 `Retry-After` 的公开语义。

**基础设施**：不新增外部服务或依赖。

## Constraints

- 保持公开限流契约不变。
- 严格 RED→GREEN→REFACTOR，不预设问题只存在于测试。
- 测试不得依赖 wall clock、主机性能或事件循环调度速度。

## Stakeholders

- Gateway 维护者。
- 使用 Python 3.10～3.12 的部署与 CI 使用者。

## Risk and Anchoring

- **Critical**：是；限流属于安全控制边界。
- **Risk Assessment**：`safety_critical=true`、`financial=false`、`cross_system=false`。
- **Risk**：错误冻结或抽象时间可能掩盖真实补充行为，或无意改变生产限流语义。
- **Anchoring**：L3，参考 `2026-08-12-v0.0.4-security-observability`、现有 rate-limiting spec、`TokenBucket` 实现和 TC-RL-005。

## Non-goals

- 不实现 Redis 分布式限流。
- 不调整默认限流策略、容量或性能目标。
- 不修改认证、Flow、Provider 或 detector。
- 不处理 Roadmap 文档漂移。

## Project Principle Check

1. **Plugin / Flow**：不新增领域能力或 Flow 策略；只收敛现有限流运行机制的时间测试边界，核心职责不扩张。
2. **显式策略 / 失败**：明确持续补充、原子消费和失败条件；测试不得把合法补充静默归类为超额消费。
3. **透明边界 / 稳定契约**：保持公开配置、HTTP 429 与 `Retry-After` 契约兼容，时间边界只用于内部可测试性。
4. **证据 / 数据保护**：使用确定性多版本测试提供可审计证据，不采集或保存请求内容及其他敏感数据。

**原则取舍或偏离**：无；若 Phase 2 发现测试期望与既有规范冲突，必须显式记录设计调整。

## Success Criteria

- [ ] 冻结时间时，50 个并发消费只能成功消费初始 burst，token 永不为负。
- [ ] 显式推进时间时，补充 token 符合 rate × elapsed 且不超过 burst。
- [ ] 相关测试不依赖主机速度或事件循环调度时机。
- [ ] Python 3.10、3.11、3.12 均稳定通过相关测试。
- [ ] 完整 pytest、Ruff、Mypy 和覆盖率门通过。
- [ ] 公开限流配置及 HTTP 契约无变化。
