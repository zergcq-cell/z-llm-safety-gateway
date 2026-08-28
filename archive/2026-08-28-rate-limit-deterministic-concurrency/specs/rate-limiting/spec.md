# rate-limiting 确定性并发 - 行为规格（Human View）

> **Change**: 2026-08-28-rate-limit-deterministic-concurrency
> **Capability**: rate-limiting
> **Created**: 2026-08-28T19:00:51+08:00
> **Confidence**: high
> **Delta**: 在既有 `REQ-RL-001～005` / `SC-RL-001～006` 上新增以下契约。

## REQ-RL-006：确定性的单调时间边界与生产兼容

#### Scenario: SC-RL-007 — 冻结时间下并发消费只使用初始 burst

- **GIVEN** `TokenBucket` 使用冻结的可控单调时钟、`burst=5`，且 50 个协程共享该桶
- **WHEN** 50 个协程并发调用 `consume`
- **THEN** `TokenBucket` SHALL 恰好允许初始 burst 对应的 5 次消费
- **AND** token 数 SHALL 始终不小于 0，且测试 SHALL NOT 依赖 wall clock、主机速度或事件循环调度速度

#### Scenario: SC-RL-008 — 显式时间推进精确补充 token

- **GIVEN** `TokenBucket` 使用可控单调时钟，当前 token 已耗尽且 rate 已知
- **WHEN** 时钟显式前进给定 elapsed 后触发补充
- **THEN** `TokenBucket` SHALL 精确补充 `rate × elapsed` 个 token
- **AND** 未显式推进时钟时 SHALL NOT 产生额外 token

#### Scenario: SC-RL-009 — 补充不超过 burst

- **GIVEN** 经过时间足以补充超过 burst 的 token
- **WHEN** 时钟显式前进后触发补充
- **THEN** 可用 token SHALL 被限制为 burst 容量

#### Scenario: SC-RL-010 — 默认时钟保持构造兼容

- **GIVEN** 现有调用方仅以 rate 和 burst 构造 `TokenBucket`
- **WHEN** 未传入测试时钟并执行消费与补充
- **THEN** `TokenBucket` SHALL 默认使用生产单调时钟并保持现有构造调用兼容
- **AND** `RateLimitMiddleware` 的公开配置与构造路径 SHALL 保持不变

## REQ-RL-007：明确的并发序列化边界

#### Scenario: SC-RL-011 — 已持锁时 consume 必须等待

- **GIVEN** `TokenBucket` 的消费锁已被测试持有且桶内有 token
- **WHEN** 另一个任务调用 `consume`
- **THEN** `consume` 任务 SHALL 在锁释放前保持等待
- **AND** 锁释放前 token 数 SHALL 保持不变；释放后消费 SHALL 原子完成且 token 不为负

## REQ-RL-008：受支持 Python 版本的稳定证据

#### Scenario: SC-RL-012 — Python 3.10～3.12 重复回归

- **GIVEN** Python 3.10、3.11、3.12 的项目隔离环境与同一变更提交
- **WHEN** 重复执行 rate-limit 定向回归及完整 pytest、Ruff、Mypy 和覆盖率门
- **THEN** 三个 Python 版本的相关回归 SHALL 稳定通过且既有并发案例不再出现时序失败
- **AND** 缺失或失效的版本环境 SHALL 被显式报告而不得计为通过，且完整质量门 SHALL 保持项目既有通过标准

## Verification Checkpoints

| Checkpoint | Scenario | Test Case / Evidence |
|------------|----------|----------------------|
| CP-RL-007 | SC-RL-007 | TC-RL-005：冻结时钟并发消费 |
| CP-RL-008 | SC-RL-008 | TC-RL-008：精确 elapsed 补充 |
| CP-RL-009 | SC-RL-009 | TC-RL-009：burst cap |
| CP-RL-010 | SC-RL-010 | TC-RL-010：默认构造兼容 |
| CP-RL-011 | SC-RL-011 | TC-RL-007：持锁等待 |
| CP-RL-012 | SC-RL-012 | TC-RL-011：三版本质量矩阵 |
